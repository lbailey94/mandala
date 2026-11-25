"""Tests for reviewed Landlock, bwrap+Landlock, Podman argv, and Firecracker snapshot profiles."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from continuity_receipt import verify_bundle

from gate_lite import orchestrator as orch_mod
from gate_lite.orchestrator import (
    FirecrackerSnapRunner,
    LandlockRunner,
    Orchestrator,
    RunnerProfileError,
    SandboxRunner,
    build_runner,
)

ROOT = Path(__file__).resolve().parents[1]
LANDLOCK_RUNNER = ROOT / "runners/landlock-wm-v1/mandala-sandbox-landlock"
BWRAP_LANDLOCK_RUNNER = ROOT / "runners/bwrap-landlock-v1/mandala-sandbox-bwrap-landlock"
FC_RUNNER = ROOT / "runners/firecracker-snap-v1/mandala-sandbox-firecracker"
PODMAN_RUNNER = ROOT / "runners/podman-v1/mandala-sandbox-podman"
REAL_TESTS = os.environ.get("GATE_LITE_REAL_RUNNER_TESTS") == "1"


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class TestShippedMultiProfiles(unittest.TestCase):
    def test_shipped_wrapper_digests_match_constants(self):
        expected = {
            LANDLOCK_RUNNER: orch_mod.PROFILE_WRAPPER_LANDLOCK_SHA256,
            BWRAP_LANDLOCK_RUNNER: orch_mod.PROFILE_WRAPPER_BWRAP_LANDLOCK_SHA256,
            FC_RUNNER: orch_mod.PROFILE_WRAPPER_FC_SHA256,
        }
        for path, digest in expected.items():
            with self.subTest(runner=str(path.relative_to(ROOT))):
                self.assertEqual(_sha256_file(path), digest)

    def test_runner_argv_suites_pass(self):
        for test_dir in (
            ROOT / "runners/landlock-wm-v1",
            ROOT / "runners/bwrap-landlock-v1",
            ROOT / "runners/firecracker-snap-v1",
            ROOT / "runners/podman-v1",
        ):
            with self.subTest(suite=str(test_dir.relative_to(ROOT))):
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", str(test_dir), "-p", "test_*.py"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

    def test_hint_conflicts_and_auto_detection(self):
        if shutil.which("wm-sandbox"):
            with self.assertRaisesRegex(RunnerProfileError, "contradicts the reviewed landlock wrapper"):
                SandboxRunner(str(LANDLOCK_RUNNER), sandbox_class="bwrap")
            ll = build_runner(str(LANDLOCK_RUNNER))
            self.assertIsInstance(ll, LandlockRunner)
            self.assertEqual(ll.sandbox_class, "landlock")
            self.assertEqual(ll.profile_id, orch_mod.PROFILE_ID_LANDLOCK)
            if shutil.which("bwrap"):
                with self.assertRaisesRegex(RunnerProfileError, "contradicts the reviewed bwrap-landlock wrapper"):
                    SandboxRunner(str(BWRAP_LANDLOCK_RUNNER), sandbox_class="landlock")
                bl = build_runner(str(BWRAP_LANDLOCK_RUNNER))
                self.assertEqual(bl.sandbox_class, "bwrap-landlock")
                self.assertEqual(bl.profile_id, orch_mod.PROFILE_ID_BWRAP_LANDLOCK)


class TestFirecrackerSnapRunner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snap_dir = self.root / "fc-snap"
        self.snap_dir.mkdir()
        self.digests = {}
        for name in ("kernel.bin", "rootfs.ext4", "mem.snap", "vmstate.snap"):
            p = self.snap_dir / name
            p.write_bytes(b"img-" + name.encode())
            self.digests[name] = _sha256_file(p)
        self.fake_fc = self.root / "firecracker"
        self.fake_fc.write_text("#!/bin/sh\necho fc-ok\n", encoding="utf-8")
        self.fake_fc.chmod(0o755)
        self.fc_sha = _sha256_file(self.fake_fc)

    def test_missing_assets_fail_closed_before_spawn(self):
        unqualified = FirecrackerSnapRunner(str(FC_RUNNER))
        self.assertEqual(unqualified.profile_status, "unqualified")
        self.assertEqual(unqualified.sandbox_class, "unknown")
        with self.assertRaisesRegex(RunnerProfileError, "no reviewed runner profile"):
            unqualified.run({}, "echo nope", on_spawn=lambda *_: self.fail("spawned"))

    def test_tampered_snapshot_artifact_refuses_before_spawn(self):
        with patch.dict(os.environ, {"MANDALA_FC_BIN": str(self.fake_fc)}):
            runner = FirecrackerSnapRunner(
                str(FC_RUNNER),
                snapshot_dir=self.snap_dir,
                expected_image_digests=self.digests,
                expected_firecracker_sha256=self.fc_sha,
            )
            self.assertEqual(runner.profile_status, "locally_qualified")
            self.assertEqual(runner.sandbox_class, "microvm-fc")
            (self.snap_dir / "mem.snap").write_bytes(b"tampered")
            with self.assertRaisesRegex(RunnerProfileError, "snapshot artifact identity mismatch"):
                runner.run({}, "echo blocked", on_spawn=lambda *_: self.fail("spawned"))

    def test_qualified_firecracker_emits_cpr05_trusted_bundle(self):
        with patch.dict(os.environ, {"MANDALA_FC_BIN": str(self.fake_fc)}):
            runner = FirecrackerSnapRunner(
                str(FC_RUNNER),
                snapshot_dir=self.snap_dir,
                expected_image_digests=self.digests,
                expected_firecracker_sha256=self.fc_sha,
            )
            orch = Orchestrator(self.root / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:zFc"])
            issued = orch.pass_("tenant", "did:key:zFc")
            res = orch.exec_("tenant", issued["slot_id"], "/bin/echo fc-ok", token=issued["token"])
            self.assertEqual(res["exit"], 0)
            term = orch.terminate("tenant", issued["slot_id"])
            bundle = orch.receipt(term["task_id"])
            verdict = verify_bundle(bundle).as_dict()
            self.assertEqual(verdict["verdict"], "TRUSTED", verdict["errors"])
            execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
            self.assertEqual(execution["body"]["sandbox_class"], "microvm-fc")
            self.assertEqual(
                set(execution["body"]["runner_profile"]),
                {"profile_id", "executable_digest", "invocation_digest"},
            )
            self.assertEqual(execution["body"]["vm_image"]["artifacts"], self.digests)


@unittest.skipUnless(
    REAL_TESTS and shutil.which("wm-sandbox") is not None,
    "set GATE_LITE_REAL_RUNNER_TESTS=1 with wm-sandbox installed to run live Landlock tests",
)
class TestLiveLandlockAndBwrapLandlock(unittest.TestCase):
    def test_live_landlock_wm_v1_confinement_and_receipt(self):
        tmp_base = Path.home() / ".cache"
        tmp_base.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix="mandala-ll-live-", dir=tmp_base))
        self.addCleanup(shutil.rmtree, workdir, True)

        runner = build_runner(str(LANDLOCK_RUNNER))
        orch = Orchestrator(workdir / "state", runner=runner)
        orch.add_tenant("tenant", ["did:key:zLL"])

        # Writable run + CPR 0.5 TRUSTED chain
        p1 = orch.pass_("tenant", "did:key:zLL")
        r1 = orch.exec_("tenant", p1["slot_id"], "/bin/sh -c 'echo ok > marker.txt && cat marker.txt'", token=p1["token"])
        self.assertEqual(r1["exit"], 0)
        term1 = orch.terminate("tenant", p1["slot_id"])
        bundle = orch.receipt(term1["task_id"])
        verdict = verify_bundle(bundle).as_dict()
        self.assertEqual(verdict["verdict"], "TRUSTED", verdict["errors"])
        execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
        self.assertEqual(execution["body"]["sandbox_class"], "landlock")

        # Home credential lockout + zero egress
        p2 = orch.pass_("tenant", "did:key:zLL")
        bashrc = Path.home() / ".bashrc"
        if bashrc.exists():
            r2 = orch.exec_("tenant", p2["slot_id"], f"/bin/cat {bashrc}", token=p2["token"])
            self.assertNotEqual(r2["exit"], 0)

        p3 = orch.pass_("tenant", "did:key:zLL")
        r3 = orch.exec_(
            "tenant",
            p3["slot_id"],
            json.dumps({
                "program": "/usr/bin/python3",
                "args": ["-c", "import socket; socket.create_connection(('1.1.1.1', 80), timeout=1)"],
                "net": False,
            }),
            token=p3["token"],
        )
        self.assertNotEqual(r3["exit"], 0)

        # Direct rw=False outside /tmp is blocked by Landlock ABI 8
        ro_target = workdir / "ro-dir"
        ro_target.mkdir()
        proc = subprocess.run(
            [
                str(LANDLOCK_RUNNER),
                "--exec",
                json.dumps({
                    "program": "/bin/sh",
                    "args": ["-c", f"echo nope > {ro_target}/x.txt"],
                    "net": False,
                    "workspace": str(ro_target),
                    "rw": False,
                }),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((ro_target / "x.txt").exists())

    @unittest.skipUnless(shutil.which("bwrap") is not None, "bwrap required for bwrap-landlock")
    def test_live_bwrap_landlock_v1_ro_workspace_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = build_runner(str(BWRAP_LANDLOCK_RUNNER))
            orch = Orchestrator(Path(tmp) / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:zBL"])
            p = orch.pass_("tenant", "did:key:zBL")
            res = orch.exec_(
                "tenant",
                p["slot_id"],
                "/bin/sh -c 'echo ok > /workspace/out.txt && cat /workspace/out.txt'",
                token=p["token"],
            )
            self.assertEqual(res["exit"], 0)
            term = orch.terminate("tenant", p["slot_id"])
            bundle = orch.receipt(term["task_id"])
            verdict = verify_bundle(bundle).as_dict()
            self.assertEqual(verdict["verdict"], "TRUSTED", verdict["errors"])
            execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
            self.assertEqual(execution["body"]["sandbox_class"], "bwrap-landlock")

            # rw=False enforced on /workspace even when backed by host /tmp
            ws = Path(tmp) / "ro-ws"
            ws.mkdir()
            ro_proc = subprocess.run(
                [
                    str(BWRAP_LANDLOCK_RUNNER),
                    "--exec",
                    json.dumps({
                        "program": "/bin/sh",
                        "args": ["-c", "echo nope > /workspace/deny.txt"],
                        "net": False,
                        "workspace": str(ws),
                        "rw": False,
                    }),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(ro_proc.returncode, 0)
            self.assertFalse((ws / "deny.txt").exists())

    def test_live_direct_wm_sandbox_profile_and_receipt(self):
        wm_bin = shutil.which("wm-sandbox")
        self.assertIsNotNone(wm_bin)
        with tempfile.TemporaryDirectory() as tmp:
            runner = build_runner(wm_bin)
            self.assertEqual(runner.profile_id, orch_mod.PROFILE_ID_LANDLOCK_DIRECT)
            self.assertEqual(runner.sandbox_class, "landlock")
            orch = Orchestrator(Path(tmp) / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:zDirect"])
            p = orch.pass_("tenant", "did:key:zDirect")
            res = orch.exec_(
                "tenant",
                p["slot_id"],
                "/bin/sh -c 'echo direct > ok.txt && cat ok.txt'",
                token=p["token"],
            )
            self.assertEqual(res["exit"], 0)
            term = orch.terminate("tenant", p["slot_id"])
            bundle = orch.receipt(term["task_id"])
            verdict = verify_bundle(bundle).as_dict()
            self.assertEqual(verdict["verdict"], "TRUSTED", verdict["errors"])
            execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
            self.assertEqual(
                execution["body"]["runner_profile"]["profile_id"],
                orch_mod.PROFILE_ID_LANDLOCK_DIRECT,
            )


if __name__ == "__main__":
    unittest.main()
