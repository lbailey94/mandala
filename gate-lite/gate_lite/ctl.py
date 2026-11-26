#!/usr/bin/env python3
"""mandala-ctl — gate-lite v0 CLI (pass / exec / terminate / verify)."""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gate_lite.errors import PreflightError  # noqa: E402
from gate_lite.orchestrator import EmitterError, Orchestrator, build_runner  # noqa: E402

RUNNER_PROFILE_MAP = {
    "bwrap-landlock-v1": "runners/bwrap-landlock-v1/mandala-sandbox-bwrap-landlock",
    "landlock-wm-v1": "runners/landlock-wm-v1/mandala-sandbox-landlock",
    "bwrap-v1": "runners/bwrap-v1/mandala-sandbox",
    "firecracker-snap-v1": "runners/firecracker-snap-v1/mandala-sandbox-firecracker",
    "podman-v1": "runners/podman-v1/mandala-sandbox-podman",
}


def resolve_grimoire_runner(root: Path, profile_path: Path | None = None) -> tuple[str | None, str | None]:
    """Resolve a Mandala runner binary path from `grimoire_profile.json`."""
    p = profile_path
    if p is None:
        env_p = (os.environ.get("WM_GRIMOIRE_PROFILE") or "").strip()
        p = Path(env_p) if env_p else (Path.home() / ".local" / "share" / "whitemagic" / "grimoire_profile.json")
    if not p.is_file():
        return None, f"grimoire profile not found at {p}"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"invalid grimoire profile JSON: {exc}"
    conf = obj.get("confinement") or {}
    runner_id = str(conf.get("runner_profile") or "").strip()
    degraded_reason = conf.get("degraded_reason")
    if runner_id == "landlock-wm-direct-v1":
        sb = shutil.which("wm-sandbox") or str(Path.home() / ".local" / "bin" / "wm-sandbox")
        if Path(sb).is_file():
            return sb, None
        return None, "landlock-wm-direct-v1 selected by Grimoire, but wm-sandbox executable was not found"
    if runner_id == "pre-command-vfs":
        msg = degraded_reason or "Non-Linux / degraded host: pre-command + VFS policy active only; pass --demo for stub exec"
        return None, str(msg)
    rel = RUNNER_PROFILE_MAP.get(runner_id)
    if rel:
        cand = (root / rel).resolve()
        if cand.is_file():
            return str(cand), None
        return None, f"Grimoire selected runner '{runner_id}', but wrapper not found at {cand}"
    return None, f"unsupported Grimoire runner_profile: {runner_id!r}"


def build_orchestrator(args) -> Orchestrator:
    runner_path = args.runner or os.environ.get("WM_GATELITE_RUNNER")
    auto_flag = getattr(args, "auto_runner", False) or (runner_path == "auto")
    grimoire_diag = None
    if auto_flag:
        runner_path, grimoire_diag = resolve_grimoire_runner(ROOT)
    slice_mode = args.slice or os.environ.get("WM_GATELITE_SLICE") == "1"
    sandbox_class = getattr(args, "sandbox_class", None) or os.environ.get("WM_MANDALA_SANDBOX_CLASS")
    if slice_mode and not runner_path:
        raise SystemExit(
            "--slice/WM_GATELITE_SLICE requires a runner path: pass --runner <path> "
            "or set WM_GATELITE_RUNNER"
        )
    runner = build_runner(runner_path, slice_mode, sandbox_class=sandbox_class)
    if runner is None and args.cmd == "exec" and not args.demo:
        if grimoire_diag:
            raise SystemExit(f"refusing to exec: {grimoire_diag}")
        raise SystemExit(
            "refusing to exec: no sandbox runner configured (pass --runner <path> "
            "[--slice], pass --auto-runner, or set WM_GATELITE_RUNNER), or pass --demo to run the simulated stub"
        )
    orchestrator = Orchestrator(args.state, gate_id=args.gate_id, runner=runner)
    if runner is None and args.cmd == "exec" and args.demo:
        print(
            "mandala-ctl: warning: simulated execution (stub runner); no sandbox involved",
            file=sys.stderr,
        )
    return orchestrator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mandala-ctl")
    parser.add_argument("--state", default="./gate-state")
    parser.add_argument("--gate-id", default="gate-lite-1")
    parser.add_argument("--runner", default=None, help="path to mandala-sandbox wrapper (or 'auto' for Grimoire profile)")
    parser.add_argument(
        "--auto-runner",
        action="store_true",
        help="resolve confinement runner from ~/.local/share/whitemagic/grimoire_profile.json",
    )
    parser.add_argument(
        "--sandbox-class",
        default=None,
        help="sandbox confinement class (e.g. landlock, landlock-v5, bwrap)",
    )
    parser.add_argument(
        "--slice",
        action="store_true",
        help="run payloads under a systemd user slice with cgroup quotas (G2)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="allow exec with the built-in stub runner (simulated execution, no sandbox)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    tenant = sub.add_parser("tenant-add")
    tenant.add_argument("--tenant", required=True)
    tenant.add_argument("--agent", action="append", required=True)

    pass_cmd = sub.add_parser("pass")
    pass_cmd.add_argument("--tenant", required=True)
    pass_cmd.add_argument("--agent", required=True)
    pass_cmd.add_argument("--minutes", type=int, default=90)
    pass_cmd.add_argument("--class", dest="slot_class", default="small")
    pass_cmd.add_argument("--spend-minor", type=int, default=0)
    pass_cmd.add_argument("--idempotency-key", default=None)

    exec_cmd = sub.add_parser("exec")
    exec_cmd.add_argument("--tenant", required=True)
    exec_cmd.add_argument("--slot", required=True)
    exec_cmd.add_argument("--payload-ref", required=True)
    token_input = exec_cmd.add_mutually_exclusive_group(required=True)
    token_input.add_argument("--token", help="pass token from `pass` (binds agent + slot, single use)")
    token_input.add_argument("--token-stdin", action="store_true", help="read the pass token from stdin without echoing or logging it")
    exec_cmd.add_argument("--idempotency-key", default=None)
    exec_cmd.add_argument(
        "--trace",
        default=None,
        help="path to a JSON agent trace evaluated by the PEB-23 trace guard and bound into task.execution",
    )

    settle = sub.add_parser("settle")
    settle.add_argument("--tenant", required=True)
    settle.add_argument("--slot", required=True)
    settle.add_argument("--rail", default="invoice")
    settle.add_argument("--rail-ref", required=True)
    settle.add_argument("--minor", type=int, required=True)

    term = sub.add_parser("terminate")
    term.add_argument("--tenant", required=True)
    term.add_argument("--slot", required=True)
    term.add_argument("--reason", default="completed")

    kill = sub.add_parser("kill")
    kill.add_argument("--tenant", required=True)
    kill.add_argument("--slot", required=True)
    kill.add_argument("--signal", default="SIGTERM")
    kill.add_argument("--wait", type=float, default=5.0, help="seconds before SIGKILL escalation")

    snap = sub.add_parser("snapshot")
    snap.add_argument("--tenant", required=True)
    snap.add_argument("--slot", required=True)

    restore = sub.add_parser("restore")
    restore.add_argument("--tenant", required=True)
    restore.add_argument("--slot", required=True)
    restore.add_argument("--snapshot", required=True, dest="snapshot_id")

    sweep = sub.add_parser("sweep")
    sweep.add_argument("--tenant", default=None)

    status = sub.add_parser("status")
    status.add_argument("--tenant", required=True)
    status.add_argument("--slot", required=True)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--tenant", required=True)

    receipt = sub.add_parser("receipt")
    receipt.add_argument("--task-id", required=True)
    receipt.add_argument("--verdict", action="store_true")

    args = parser.parse_args(argv)
    token = None
    if args.cmd == "exec":
        token = sys.stdin.readline().rstrip("\r\n") if args.token_stdin else args.token
        if not token:
            print(json.dumps({"error": "token_required", "detail": "pass token input is empty"}), file=sys.stderr)
            return 2

    try:
        orch = build_orchestrator(args)
    except PreflightError as exc:
        print(json.dumps(exc.as_dict()), file=sys.stderr)
        return 3

    try:
        if args.cmd == "tenant-add":
            output = orch.add_tenant(args.tenant, args.agent)
        elif args.cmd == "pass":
            spend_cap = {"minor": args.spend_minor, "currency": "USD"} if args.spend_minor else None
            output = orch.pass_(
                args.tenant,
                args.agent,
                minutes=args.minutes,
                slot_class=args.slot_class,
                spend_cap=spend_cap,
                idempotency_key=args.idempotency_key,
            )
        elif args.cmd == "exec":
            output = orch.exec_(
                args.tenant,
                args.slot,
                args.payload_ref,
                idempotency_key=args.idempotency_key,
                token=token,
                trace_path=args.trace,
            )
        elif args.cmd == "settle":
            output = orch.settle(args.tenant, args.slot, args.rail, args.rail_ref, args.minor)
        elif args.cmd == "terminate":
            output = orch.terminate(args.tenant, args.slot, reason=args.reason)
        elif args.cmd == "kill":
            output = orch.kill(args.tenant, args.slot, signal_name=args.signal, wait_s=args.wait)
        elif args.cmd == "snapshot":
            output = orch.snapshot(args.tenant, args.slot)
        elif args.cmd == "restore":
            output = orch.restore(args.tenant, args.slot, args.snapshot_id)
        elif args.cmd == "sweep":
            output = orch.sweep_expired(args.tenant)
        elif args.cmd == "status":
            output = orch.status(args.tenant, args.slot)
        elif args.cmd == "list":
            output = orch.list_(args.tenant)
        elif args.cmd == "receipt":
            bundle = orch.receipt(args.task_id)
            if args.verdict:
                from continuity_receipt import verify_bundle
                output = verify_bundle(bundle).as_dict()
            else:
                output = bundle
        else:  # pragma: no cover
            parser.error("unknown command")
    except EmitterError as exc:
        print(json.dumps({"error": str(exc), "code": "emitter_unavailable"}), file=sys.stderr)
        return 3
    except PreflightError as exc:
        print(json.dumps(exc.as_dict()), file=sys.stderr)
        return 3
    except (KeyError, PermissionError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
