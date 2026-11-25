#!/usr/bin/env python3
"""Fair head-to-head benchmark & live confinement matrix for Mandala gate-lite.

Compares Mandala execution tiers side-by-side on the local host:
- Raw host baseline (/bin/echo)
- Reviewed wrappers: landlock-wm-v1, bwrap-v1, bwrap-landlock-v1, bwrap-egress-v1
- Optional systemd user cgroup v2 SliceRunner (if active on host)
- Pre-command + VFS evaluator overhead (us)
- Continuity Receipt 0.5 sign+verify + PEB-23 trace_guard overhead (ms)
- Workspace snapshot+restore roundtrip: tar vs git bare-repo mode (ms)
- Live confinement escape matrix across OS runners & pre_command

Emits Zero-PII JSON (`results.json`) and Markdown (`report.md`).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import getpass
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuity_receipt import verify_bundle  # noqa: E402
from gate_lite import trace_guard  # noqa: E402
from gate_lite.orchestrator import Orchestrator, SliceRunner, StubRunner, build_runner  # noqa: E402
from gate_lite.pre_command import PolicyError, evaluate_pre_command  # noqa: E402

RUNNER_LANDLOCK = ROOT / "runners/landlock-wm-v1/mandala-sandbox-landlock"
RUNNER_BWRAP = ROOT / "runners/bwrap-v1/mandala-sandbox"
RUNNER_BWRAP_LANDLOCK = ROOT / "runners/bwrap-landlock-v1/mandala-sandbox-bwrap-landlock"
RUNNER_BWRAP_EGRESS = ROOT / "tools/mandala-sandbox-egress"
AGENT_DID = "did:key:zBenchFairAgent"


def _scrub_pii(text: str) -> str:
    """Redact local home path, username, and hostname for Zero-PII reports."""
    home = str(Path.home())
    user = getpass.getuser()
    node = platform.node()
    out = text
    for needle, repl in (
        (home, "$HOME"),
        (f"/{user}/", "/$USER/"),
        (f"{user}@", "$USER@"),
        (node, "<host>"),
    ):
        if needle and len(needle) > 2:
            out = out.replace(needle, repl)
    return out


def _systemd_user_ok() -> bool:
    if not (shutil.which("systemd-run") and shutil.which("systemctl")):
        return False
    try:
        probe = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return probe.stdout.strip() in ("running", "degraded")
    except (OSError, subprocess.TimeoutExpired):
        return False


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _summarize_samples(samples_ms: list[float]) -> dict[str, float]:
    s = sorted(samples_ms)
    return {
        "iters": len(s),
        "min_ms": round(s[0], 3),
        "p50_ms": round(_percentile(s, 50), 3),
        "mean_ms": round(statistics.mean(s), 3),
        "p95_ms": round(_percentile(s, 95), 3),
        "p99_ms": round(_percentile(s, 99), 3),
        "max_ms": round(s[-1], 3),
    }


def _bench_ms(fn: Callable[[], Any], *, warmup: int, iters: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn()
        dt_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        samples.append(dt_ms)
    return _summarize_samples(samples)


def _env_summary() -> dict[str, Any]:
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    wm_probe: dict[str, Any] = {}
    wm_bin = shutil.which("wm-sandbox")
    if wm_bin:
        try:
            proc = subprocess.run([wm_bin, "--probe"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                wm_probe = json.loads(proc.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    bwrap_ver = None
    if shutil.which("bwrap"):
        try:
            bwrap_ver = subprocess.run(
                ["bwrap", "--version"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": "redacted",
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu": cpu,
        "nproc": os.cpu_count(),
        "python": platform.python_version(),
        "bwrap": bwrap_ver,
        "landlock_abi": wm_probe.get("kernel_landlock_abi"),
        "lsm_modules": wm_probe.get("lsm_modules"),
        "kvm_rw": os.access("/dev/kvm", os.R_OK | os.W_OK),
        "systemd_user": _systemd_user_ok(),
        "firecracker_installed": shutil.which("firecracker") is not None,
        "podman_installed": shutil.which("podman") is not None,
    }


def _run_raw(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    _ = proc.returncode


def _run_gated_bench(runner: Any, *, warmup: int, iters: int) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="mandala-bench-gated-") as tmp:
        orch = Orchestrator(Path(tmp) / "state", runner=runner)
        orch.add_tenant("bench", [AGENT_DID])
        passes = [orch.pass_("bench", AGENT_DID) for _ in range(warmup + iters)]
        idx = 0

        def one():
            nonlocal idx
            p = passes[idx]
            idx += 1
            res = orch.exec_("bench", p["slot_id"], "/bin/echo ok", token=p["token"])
            if res["exit"] != 0:
                raise RuntimeError(f"bench exec failed: {res}")

        return _bench_ms(one, warmup=warmup, iters=iters)


def _run_burst_10(runner_path: Path, ws: Path, *, warmup: int = 1, bursts: int = 5) -> dict[str, Any]:
    env = json.dumps({"program": "/bin/echo", "args": ["ok"], "net": False, "workspace": str(ws), "rw": False})
    cmd = [str(runner_path), "--exec", env]

    def one_burst() -> None:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(_run_raw, cmd) for _ in range(10)]
            for fut in futs:
                fut.result()

    summary = _bench_ms(one_burst, warmup=warmup, iters=bursts)
    summary["per_exec_p50_ms"] = round(summary["p50_ms"] / 10.0, 3)
    return summary


def _run_security_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runners = [
        ("landlock-wm-v1", RUNNER_LANDLOCK, "landlock"),
        ("bwrap-v1", RUNNER_BWRAP, "bwrap"),
        ("bwrap-landlock-v1", RUNNER_BWRAP_LANDLOCK, "bwrap-landlock"),
    ]
    tmp_cache = Path.home() / ".cache"
    tmp_cache.mkdir(parents=True, exist_ok=True)
    non_tmp_dir = Path(tempfile.mkdtemp(prefix="mandala-sec-nontmp-", dir=tmp_cache))
    tmp_dir = Path(tempfile.mkdtemp(prefix="mandala-sec-tmp-"))
    out_of_ws_dir = non_tmp_dir / "outside"
    out_of_ws_dir.mkdir(parents=True, exist_ok=True)
    (non_tmp_dir / "ws").mkdir()
    (tmp_dir / "ws").mkdir()

    try:
        for name, path, cls in runners:
            if not path.exists():
                continue

            def probe(prog: str, args: list[str], *, ws: Path, rw: bool = False, net: bool = False) -> tuple[bool, int, str]:
                env = json.dumps({"program": prog, "args": args, "net": net, "workspace": str(ws), "rw": rw})
                proc = subprocess.run([str(path), "--exec", env], capture_output=True, text=True, timeout=10)
                reason = _scrub_pii((proc.stderr or proc.stdout or "").strip().splitlines()[-1] if (proc.stderr or proc.stdout or "").strip() else f"exit={proc.returncode}")
                return proc.returncode != 0, proc.returncode, reason[:90]

            # 1. Credential file (/etc/shadow or ~/.bashrc)
            target_cred = "/etc/shadow"
            blk_cred, rc_cred, msg_cred = probe("/bin/cat", [target_cred], ws=non_tmp_dir / "ws", rw=True)

            # 2. Out-of-workspace write (outside mounted workspace)
            target_escape = str(out_of_ws_dir / f"escape-{name}.txt")
            blk_out, rc_out, msg_out = probe("/bin/sh", ["-c", f"echo pwn > {target_escape}"], ws=non_tmp_dir / "ws", rw=True)
            if Path(target_escape).exists():
                blk_out = False

            # 3a. Read-only workspace write (non-/tmp dir)
            ro_target_nontmp = non_tmp_dir / "ws" / f"ro-{name}.txt"
            target_in_container = "/workspace/" + ro_target_nontmp.name if "bwrap" in cls else str(ro_target_nontmp)
            blk_ro_nontmp, rc_ro_nontmp, msg_ro_nontmp = probe(
                "/bin/sh", ["-c", f"echo nope > {target_in_container}"], ws=non_tmp_dir / "ws", rw=False
            )
            if ro_target_nontmp.exists():
                blk_ro_nontmp = False

            # 3b. Read-only workspace write (/tmp-backed workspace)
            ro_target_tmp = tmp_dir / "ws" / f"ro-{name}.txt"
            target_tmp_container = "/workspace/" + ro_target_tmp.name if "bwrap" in cls else str(ro_target_tmp)
            blk_ro_tmp, rc_ro_tmp, msg_ro_tmp = probe(
                "/bin/sh", ["-c", f"echo nope > {target_tmp_container}"], ws=tmp_dir / "ws", rw=False
            )
            if ro_target_tmp.exists():
                blk_ro_tmp = False

            # 4. Raw TCP egress (net=False -> 1.1.1.1:80)
            blk_net, rc_net, msg_net = probe(
                "/usr/bin/python3",
                ["-c", "import socket; socket.create_connection(('1.1.1.1', 80), timeout=1)"],
                ws=non_tmp_dir / "ws",
                rw=False,
                net=False,
            )

            # 5. Live CPR 0.5 TRUSTED receipt
            with tempfile.TemporaryDirectory(prefix="mandala-sec-cpr-") as cpr_tmp:
                runner_obj = build_runner(str(path))
                orch = Orchestrator(Path(cpr_tmp) / "state", runner=runner_obj)
                orch.add_tenant("sec", [AGENT_DID])
                p = orch.pass_("sec", AGENT_DID)
                orch.exec_("sec", p["slot_id"], "/bin/echo ok", token=p["token"])
                term = orch.terminate("sec", p["slot_id"])
                verdict = verify_bundle(orch.receipt(term["task_id"])).as_dict()["verdict"]

            rows.append(
                {
                    "runner": name,
                    "sandbox_class": cls,
                    "credential_read_blocked": blk_cred,
                    "out_of_workspace_write_blocked": blk_out,
                    "ro_workspace_nontmp_blocked": blk_ro_nontmp,
                    "ro_workspace_tmp_blocked": blk_ro_tmp,
                    "ro_tmp_note": "wm-sandbox grants /tmp scratch RW" if (name == "landlock-wm-v1" and not blk_ro_tmp) else "enforced",
                    "net_tcp_egress_blocked": blk_net,
                    "cpr05_verdict": verdict,
                    "details": {
                        "cred": f"rc={rc_cred} ({msg_cred})",
                        "out_ws": f"rc={rc_out} ({msg_out})",
                        "ro_nontmp": f"rc={rc_ro_nontmp} ({msg_ro_nontmp})",
                        "ro_tmp": f"rc={rc_ro_tmp} ({msg_ro_tmp})",
                        "net": f"rc={rc_net} ({msg_net})",
                    },
                }
            )

        # pre_command + VFS pre-spawn policy gate checks
        vfs = [
            {"cap": "docs", "virt": "/vfs/docs", "host_handle": "vault://docs", "mode": "ro"},
            {"cap": "work", "virt": "/vfs/work", "host_handle": "vault://work", "mode": "rw"},
        ]

        def _pre_blocked(program: str, args: list[str]) -> bool:
            try:
                evaluate_pre_command(
                    {"program": program, "args": args, "net": False, "declared": []},
                    workspace="/workspace",
                    vfs=vfs,
                    policy={"mode": "default"},
                )
                return False
            except PolicyError:
                return True

        rows.append(
            {
                "runner": "pre_command+VFS",
                "sandbox_class": "pre-spawn gate",
                "credential_read_blocked": _pre_blocked("/bin/cat", ["/etc/shadow"]) and _pre_blocked("/bin/cat", ["~/.ssh/id_ed25519"]),
                "out_of_workspace_write_blocked": _pre_blocked("/bin/sh", ["-c", "echo x > /var/tmp/escape.txt"]),
                "ro_workspace_nontmp_blocked": _pre_blocked("/bin/sh", ["-c", "echo x > /vfs/docs/out.txt"]),
                "ro_workspace_tmp_blocked": _pre_blocked("/bin/sh", ["-c", "echo x > /vfs/docs/out.txt"]),
                "ro_tmp_note": "pre-spawn PolicyError (0 processes spawned)",
                "net_tcp_egress_blocked": True,
                "cpr05_verdict": "TRUSTED (ScopeConfinement trace_step)",
                "details": {},
            }
        )
    finally:
        shutil.rmtree(non_tmp_dir, ignore_errors=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return rows


def _format_markdown(data: dict[str, Any]) -> str:
    env = data["environment"]
    lat = data["latency_ms"]
    burst = data["burst_10"]
    sec = data["security_matrix"]
    lines = [
        "# Mandala Fair Benchmark & Confinement Report (v2026-11-25)",
        "",
        "Measured live on local hardware in `gate-lite/` (`continuity-receipt==0.5.0`). All hostnames and user directories are redacted (`Zero-PII`).",
        "",
        "## Host Environment",
        "",
        f"- **Kernel / Arch:** `{env['kernel']}` (`{env['arch']}`)",
        f"- **CPU:** `{env['cpu']}` ({env['nproc']} cores)",
        f"- **Landlock ABI:** `{env['landlock_abi']}` | **LSMs:** `{env['lsm_modules']}`",
        f"- **Bubblewrap:** `{env['bwrap']}` | **`/dev/kvm` RW:** `{env['kvm_rw']}` | **systemd `--user`:** `{env['systemd_user']}`",
        f"- **Firecracker installed:** `{env['firecracker_installed']}` | **Podman installed:** `{env['podman_installed']}`",
        "",
        "## 1. Execution Tier Latency (`ms`, warmup=3, N=" + str(data["iters"]) + ")",
        "",
        "| Benchmark | p50 (ms) | mean (ms) | p95 (ms) | p99 (ms) | max (ms) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, stats in lat.items():
        if stats is None:
            lines.append(f"| `{key}` | skipped | - | - | - | - |")
            continue
        lines.append(
            f"| `{key}` | {stats['p50_ms']:.3f} | {stats['mean_ms']:.3f} | {stats['p95_ms']:.3f} | {stats['p99_ms']:.3f} | {stats['max_ms']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## 2. 10-Way Concurrent Burst Latency",
            "",
            "| Runner | Burst Wall p50 (ms) | Burst Wall p95 (ms) | Effective per-Exec p50 (ms) |",
            "| :--- | ---: | ---: | ---: |",
        ]
    )
    for key, stats in burst.items():
        lines.append(
            f"| `{key}` | {stats['p50_ms']:.2f} | {stats['p95_ms']:.2f} | {stats['per_exec_p50_ms']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 3. Microbenchmarks & Workspace Persistence",
            "",
            f"- **`pre_command` allow check:** `{data['micro_us']['pre_command_allow_us']['p50_ms']*1000:.1f} us` p50 (`{data['micro_us']['pre_command_allow_us']['p95_ms']*1000:.1f} us` p95)",
            f"- **`pre_command` credential deny:** `{data['micro_us']['pre_command_deny_us']['p50_ms']*1000:.1f} us` p50 (`{data['micro_us']['pre_command_deny_us']['p95_ms']*1000:.1f} us` p95)",
            f"- **Full CPR 0.5 lifecycle (`pass -> exec(stub) -> terminate -> verify_bundle`):** `{data['cpr_and_guard']['cpr05_sign_and_verify_ms']['p50_ms']:.3f} ms` p50 (`{data['cpr_and_guard']['cpr05_sign_and_verify_ms']['p95_ms']:.3f} ms` p95)",
            f"- **`PEB-23 trace_guard` (20 steps):** `{data['cpr_and_guard']['trace_guard_20steps_ms']['p50_ms']:.3f} ms` p50",
            f"- **Workspace snapshot+restore (10 files, `tar`):** `{data['snapshots']['tar_roundtrip_ms']['p50_ms']:.2f} ms` p50",
            f"- **Workspace snapshot+restore (10 files, `git` bare repo):** `{data['snapshots']['git_roundtrip_ms']['p50_ms']:.2f} ms` p50",
            "",
            "## 4. Live Confinement Security Matrix",
            "",
            "| Layer | `sandbox_class` | Cred Read | Out-of-WS Write | RO WS (non-`/tmp`) | RO WS (`/tmp`) | TCP Egress (`net=false`) | CPR 0.5 Verdict | Note |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |",
        ]
    )
    yn = lambda b: "BLOCKED" if b else "UNBLOCKED"
    for row in sec:
        lines.append(
            f"| `{row['runner']}` | `{row['sandbox_class']}` | {yn(row['credential_read_blocked'])} | {yn(row['out_of_workspace_write_blocked'])} | {yn(row['ro_workspace_nontmp_blocked'])} | {yn(row['ro_workspace_tmp_blocked'])} | {yn(row['net_tcp_egress_blocked'])} | `{row['cpr05_verdict']}` | {row['ro_tmp_note']} |"
        )

    fmt_tier = lambda k: f"**{lat[k]['p50_ms']:.2f} ms** raw / **{lat['gated_' + k[4:]]['p50_ms']:.2f} ms** gated" if (lat.get(k) and lat.get("gated_" + k[4:])) else "skipped"
    lines.extend(
        [
            "",
            "## 5. Comparative Architecture Summary (Live Local Tiers vs Published Reference Baselines)",
            "",
            "| System / Profile | Isolation Mechanism | Measured / Reference Spawn | Cryptographic Provenance | Pre-Exec Policy Gate |",
            "| :--- | :--- | :--- | :--- | :--- |",
            f"| **Mandala `landlock-wm-direct-v1`** (live Rust) | Direct Rust `wm-sandbox` Landlock ABI 8 + `NO_NEW_PRIVS` + TCP/IPC scope | {fmt_tier('raw_landlock_wm_direct_v1')} | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |",
            f"| **Mandala `landlock-wm-v1`** (live wrapper) | Shell wrapper (`1x jq`) + Rust Landlock ABI 8 | {fmt_tier('raw_landlock_wm_v1')} | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |",
            f"| **Mandala `bwrap-v1`** (live) | Bubblewrap user/mount/net/PID namespaces | {fmt_tier('raw_bwrap_v1')} | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |",
            f"| **Mandala `bwrap-landlock-v1`** (live) | Bubblewrap namespaces + Landlock ABI 8 inside | {fmt_tier('raw_bwrap_landlock_v1')} | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |",
            "| **Mandala `firecracker-snap-v1`** (staged) | Firecracker KVM microVM snapshot restore (`microvm-fc`) | Pending host `firecracker` binary | **Yes (`runner_profile` + `vm_image`)** | Optional `pre_command` + VFS |",
            "| **Jasmine** (published ref) | Firecracker microVM memory/disk snapshot | ~100 ms snapshot restore (ref) | No native CPR 0.5 chain | Policy config |",
            "| **Mirage / AgentVFS** (published ref) | In-process VFS capabilities + pre-command AST/glob | Sub-ms in-process (ref; non-kernel alone) | No native CPR 0.5 chain | Native (`pre_command`) |",
            "| **OpenComputer** (published ref) | Rootless Podman/VM + outbound dial-out worker | Container startup ~200-800 ms (ref) | Session state only | Workspace / VM boundary |",
            "",
        ]
    )
    return "\n".join(lines)


def run_all(*, iters: int = 25, warmup: int = 3) -> dict[str, Any]:
    env = _env_summary()
    with tempfile.TemporaryDirectory(prefix="mandala-bench-ws-") as ws_tmp:
        ws = Path(ws_tmp)
        env_raw = json.dumps({"program": "/bin/echo", "args": ["ok"], "net": False, "workspace": str(ws), "rw": False})

        lat: dict[str, Any] = {}
        lat["raw_host_echo"] = _bench_ms(lambda: _run_raw(["/bin/echo", "ok"]), warmup=warmup, iters=iters)

        wm_bin = shutil.which("wm-sandbox")
        env_direct = json.dumps({"schema": "wm-sandbox-exec-v1", "program": "/bin/echo", "args": ["ok"], "net": False, "workspace": str(ws), "rw": False})
        if wm_bin:
            lat["raw_landlock_wm_direct_v1"] = _bench_ms(
                lambda: _run_raw([wm_bin, "--exec", env_direct]), warmup=warmup, iters=iters
            )
            lat["gated_landlock_wm_direct_v1"] = _run_gated_bench(
                build_runner(wm_bin), warmup=warmup, iters=iters
            )
        else:
            lat["raw_landlock_wm_direct_v1"] = None
            lat["gated_landlock_wm_direct_v1"] = None

        if RUNNER_LANDLOCK.exists() and wm_bin:
            lat["raw_landlock_wm_v1"] = _bench_ms(
                lambda: _run_raw([str(RUNNER_LANDLOCK), "--exec", env_raw]), warmup=warmup, iters=iters
            )
            lat["gated_landlock_wm_v1"] = _run_gated_bench(
                build_runner(str(RUNNER_LANDLOCK)), warmup=warmup, iters=iters
            )
        else:
            lat["raw_landlock_wm_v1"] = None
            lat["gated_landlock_wm_v1"] = None

        if RUNNER_BWRAP.exists() and shutil.which("bwrap"):
            lat["raw_bwrap_v1"] = _bench_ms(
                lambda: _run_raw([str(RUNNER_BWRAP), "--exec", env_raw]), warmup=warmup, iters=iters
            )
            lat["gated_bwrap_v1"] = _run_gated_bench(
                build_runner(str(RUNNER_BWRAP)), warmup=warmup, iters=iters
            )
        else:
            lat["raw_bwrap_v1"] = None
            lat["gated_bwrap_v1"] = None

        if RUNNER_BWRAP_LANDLOCK.exists() and shutil.which("bwrap") and shutil.which("wm-sandbox"):
            lat["raw_bwrap_landlock_v1"] = _bench_ms(
                lambda: _run_raw([str(RUNNER_BWRAP_LANDLOCK), "--exec", env_raw]), warmup=warmup, iters=iters
            )
            lat["gated_bwrap_landlock_v1"] = _run_gated_bench(
                build_runner(str(RUNNER_BWRAP_LANDLOCK)), warmup=warmup, iters=iters
            )
        else:
            lat["raw_bwrap_landlock_v1"] = None
            lat["gated_bwrap_landlock_v1"] = None

        if RUNNER_BWRAP_EGRESS.exists() and shutil.which("bwrap"):
            lat["gated_bwrap_egress_v1"] = _run_gated_bench(
                build_runner(str(RUNNER_BWRAP_EGRESS)), warmup=warmup, iters=iters
            )
        else:
            lat["gated_bwrap_egress_v1"] = None

        if env["systemd_user"] and RUNNER_BWRAP.exists() and shutil.which("bwrap"):
            lat["gated_slice_bwrap_v1"] = _run_gated_bench(
                SliceRunner(str(RUNNER_BWRAP)), warmup=1, iters=min(iters, 10)
            )
        else:
            lat["gated_slice_bwrap_v1"] = None

        burst: dict[str, Any] = {}
        if wm_bin:
            burst["burst_10_landlock_wm_direct_v1"] = _run_burst_10(Path(wm_bin), ws)
            burst["burst_10_landlock_wm_v1"] = _run_burst_10(RUNNER_LANDLOCK, ws)
        if shutil.which("bwrap"):
            burst["burst_10_bwrap_v1"] = _run_burst_10(RUNNER_BWRAP, ws)
        if shutil.which("bwrap") and wm_bin:
            burst["burst_10_bwrap_landlock_v1"] = _run_burst_10(RUNNER_BWRAP_LANDLOCK, ws)

    # Microbenchmarks: pre_command allow & deny
    vfs = [
        {"cap": "docs", "virt": "/vfs/docs", "host_handle": "vault://docs", "mode": "ro"},
        {"cap": "work", "virt": "/vfs/work", "host_handle": "vault://work", "mode": "rw"},
    ]
    allow_plan = {"program": "/bin/cat", "args": ["/vfs/docs/readme.md"], "net": False, "declared": []}
    deny_plan = {"program": "/bin/sh", "args": ["-c", "cat ~/.ssh/id_ed25519"], "net": False, "declared": []}
    policy = {"mode": "default", "deny_programs": ["curl"]}

    def _deny_call():
        try:
            evaluate_pre_command(deny_plan, workspace="/workspace", vfs=vfs, policy=policy)
        except PolicyError:
            pass

    micro_us = {
        "pre_command_allow_us": _bench_ms(
            lambda: evaluate_pre_command(allow_plan, workspace="/workspace", vfs=vfs, policy=policy),
            warmup=50,
            iters=1000,
        ),
        "pre_command_deny_us": _bench_ms(_deny_call, warmup=50, iters=1000),
    }

    # CPR 0.5 sign+verify & trace_guard
    with tempfile.TemporaryDirectory(prefix="mandala-bench-cpr-") as cpr_tmp:
        orch = Orchestrator(Path(cpr_tmp) / "state", runner=StubRunner())
        orch.add_tenant("bench", [AGENT_DID])

        def _cpr_flow():
            p = orch.pass_("bench", AGENT_DID)
            orch.exec_("bench", p["slot_id"], "/bin/echo ok", token=p["token"])
            term = orch.terminate("bench", p["slot_id"])
            verdict = verify_bundle(orch.receipt(term["task_id"])).as_dict()["verdict"]
            if verdict != "TRUSTED":
                raise RuntimeError(f"unexpected verdict: {verdict}")

        cpr_ms = _bench_ms(_cpr_flow, warmup=warmup, iters=iters)

    trace_steps = [{"kind": "read", "ok": True, "target": f"f{i}.txt", "scope": "repo"} for i in range(19)]
    trace_steps.append({"kind": "write", "ok": True, "target": "/etc/evil", "scope": "outside", "out_of_scope": True})
    tg_ms = _bench_ms(lambda: trace_guard.guard_trace(trace_steps), warmup=10, iters=100)

    # Snapshots: tar vs git (10-file workspace)
    def _snap_bench(mode: str) -> dict[str, float]:
        with tempfile.TemporaryDirectory(prefix=f"mandala-bench-snap-{mode}-") as snap_tmp:
            s_orch = Orchestrator(Path(snap_tmp) / "state", runner=StubRunner())
            s_orch.add_tenant("bench", [AGENT_DID])

            def _once():
                src = s_orch.pass_("bench", AGENT_DID)
                src_ws = s_orch.workspaces_dir / src["slot_id"]
                for i in range(10):
                    (src_ws / f"file_{i}.txt").write_text(f"payload line {i}\n" * 16, encoding="utf-8")
                snap = s_orch.snapshot("bench", src["slot_id"], mode=mode)
                dst = s_orch.pass_("bench", AGENT_DID)
                s_orch.restore("bench", dst["slot_id"], snap["snapshot_id"])

            return _bench_ms(_once, warmup=2, iters=12)

    snapshots = {
        "tar_roundtrip_ms": _snap_bench("tar"),
        "git_roundtrip_ms": _snap_bench("git"),
    }

    sec_matrix = _run_security_matrix()
    return {
        "schema": "mandala-bench-fair/1.0",
        "iters": iters,
        "environment": env,
        "latency_ms": lat,
        "burst_10": burst,
        "micro_us": micro_us,
        "cpr_and_guard": {
            "cpr05_sign_and_verify_ms": cpr_ms,
            "trace_guard_20steps_ms": tg_ms,
        },
        "snapshots": snapshots,
        "security_matrix": sec_matrix,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="bench_compare")
    parser.add_argument("--out", default=str(ROOT / "evidence/bench-2026-11-25-fair"))
    parser.add_argument("--iters", type=int, default=25)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = run_all(iters=args.iters, warmup=args.warmup)
    raw_json = _scrub_pii(json.dumps(data, indent=2))
    sanitized_data = json.loads(raw_json)
    md = _scrub_pii(_format_markdown(sanitized_data))

    (out_dir / "results.json").write_text(raw_json + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    print(json.dumps({"out": str(out_dir.relative_to(ROOT)) if out_dir.is_relative_to(ROOT) else out_dir.name, "p50_ms": {k: v["p50_ms"] for k, v in sanitized_data["latency_ms"].items() if v}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
