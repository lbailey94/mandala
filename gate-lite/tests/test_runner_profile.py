"""Fail-closed tests for the unresolved published-0.4 runner profile."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gate_lite.orchestrator import (
    Orchestrator,
    RunnerProfileError,
    SandboxRunner,
    StubRunner,
)


class TestRunnerProfileFailClosed(unittest.TestCase):
    def make_runner(self, path: Path) -> SandboxRunner:
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o700)
        return SandboxRunner(str(path))

    def test_missing_profile_is_unknown_and_refuses_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runner"
            runner = self.make_runner(path)
            self.assertEqual(runner.sandbox_class, "unknown")
            self.assertIsNone(runner.profile_id)
            self.assertEqual(runner.profile_status, "unqualified")
            with self.assertRaisesRegex(RunnerProfileError, "no reviewed runner profile"):
                runner.run({}, "echo should-not-run", on_spawn=lambda *_: self.fail("spawned"))

    def test_missing_runner_executable_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RunnerProfileError, "identity unavailable"):
                SandboxRunner(str(Path(tmp) / "missing"))

    def test_non_executable_runner_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runner"
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaisesRegex(RunnerProfileError, "not runnable"):
                SandboxRunner(str(path))

    def test_changed_executable_fails_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runner"
            runner = self.make_runner(path)
            path.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
            with self.assertRaisesRegex(RunnerProfileError, "identity changed"):
                runner.run({}, "echo should-not-run", on_spawn=lambda *_: self.fail("spawned"))

    def test_class_mismatch_fails_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.make_runner(Path(tmp) / "runner")
            runner.sandbox_class = "bwrap-landlock"
            with self.assertRaisesRegex(RunnerProfileError, "class mismatch"):
                runner.run({}, "echo should-not-run", on_spawn=lambda *_: self.fail("spawned"))

    def test_status_reports_runner_identity_and_stub_receipt_class_agrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner_path = Path(tmp) / "runner"
            runner = self.make_runner(runner_path)
            orch = Orchestrator(Path(tmp) / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:test"])
            issued = orch.pass_("tenant", "did:key:test")
            # A real run is refused, and no execution receipt is emitted.
            with self.assertRaises(RunnerProfileError):
                orch.exec_("tenant", issued["slot_id"], "echo blocked", token=issued["token"])
            # A second attempt with the same token must reach the profile gate
            # again, rather than fail as a replay of a token no run consumed.
            with self.assertRaises(RunnerProfileError):
                orch.exec_("tenant", issued["slot_id"], "echo blocked", token=issued["token"])
            status = orch.status("tenant", issued["slot_id"])["runner"]
            self.assertEqual(status["class"], "unknown")
            self.assertEqual(status["path"], str(runner_path.resolve()))
            self.assertEqual(status["executable_sha256"], runner.runner_digest)
            bundle = orch.receipt(orch.task_id_for(issued["slot_id"]))
            self.assertFalse(any(r["type"] == "task.execution" for r in bundle["receipts"]))
            self.assertFalse(any(r["type"] == "task.decision" for r in bundle["receipts"]))

    def test_stub_status_identity_is_explicitly_simulated(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Orchestrator(tmp, runner=StubRunner())
            orch.add_tenant("tenant", ["did:key:test"])
            issued = orch.pass_("tenant", "did:key:test")
            orch.exec_("tenant", issued["slot_id"], "echo simulated", token=issued["token"])
            info = orch.status("tenant", issued["slot_id"])["runner"]
            bundle = orch.receipt(orch.task_id_for(issued["slot_id"]))
            execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
            self.assertEqual(info["class"], execution["body"]["sandbox_class"])
            self.assertTrue(info["simulated"])
            self.assertEqual(info["profile_status"], "simulated")
            self.assertEqual(bundle["spec"], "continuity-receipt/0.4")

    def test_cached_exec_cannot_bypass_unqualified_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.make_runner(Path(tmp) / "runner")
            orch = Orchestrator(Path(tmp) / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:test"])
            issued = orch.pass_("tenant", "did:key:test")
            slot_id = issued["slot_id"]
            orch.registry.remember(
                f"exec:tenant:{slot_id}:old",
                {"request": {"payload_ref": "echo old"}, "result": {"exit": 0}},
            )
            with self.assertRaises(RunnerProfileError):
                orch.exec_("tenant", slot_id, "echo old", idempotency_key="old", token=issued["token"])

    def test_unexpected_receipt_dependency_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("importlib.metadata.version", return_value="0.5.0"):
                with self.assertRaisesRegex(RuntimeError, "expected continuity-receipt==0.4.0"):
                    Orchestrator(tmp)

    def test_imported_receipt_code_must_support_pinned_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("gate_lite.orchestrator.records.SUPPORTED_SPECS", ()):
                with self.assertRaisesRegex(RuntimeError, "does not support.*continuity-receipt/0.4"):
                    Orchestrator(tmp)

    def test_names_and_class_hints_select_adapters_but_do_not_qualify(self):
        from gate_lite.orchestrator import LandlockRunner, build_runner

        with tempfile.TemporaryDirectory() as tmp:
            cases = [
                ("landrun-sandbox", None, {}, "landlock"),
                ("runner", "landlock", {}, "landlock"),
                ("runner", "landlock-v5", {}, "landlock-v5"),
                ("runner", "bwrap", {}, "bwrap"),
                ("runner", "bwrap-landlock", {}, "bwrap-landlock"),
                ("runner", None, {"WM_MANDALA_SANDBOX_CLASS": "landlock"}, "landlock"),
                ("runner", None, {"WM_SANDBOX_CLASS": "bwrap"}, "bwrap"),
                ("runner", None, {"WM_MANDALA_SANDBOX_CLASS": "bwrap-landlock"}, "bwrap-landlock"),
            ]
            for index, (name, hint, env, adapter_id) in enumerate(cases):
                with self.subTest(name=name, hint=hint, env=env):
                    marker = Path(tmp) / f"spawned-{index}"
                    path = Path(tmp) / name
                    path.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
                    path.chmod(0o700)
                    clean_env = os.environ.copy()
                    clean_env.pop("WM_MANDALA_SANDBOX_CLASS", None)
                    clean_env.pop("WM_SANDBOX_CLASS", None)
                    clean_env.update(env)
                    with patch.dict("os.environ", clean_env, clear=True):
                        runner = SandboxRunner(str(path), sandbox_class=hint)
                    self.assertEqual(runner.adapter_id, adapter_id)
                    self.assertEqual(runner.sandbox_class, "unknown")
                    self.assertEqual(runner.profile_status, "unqualified")
                    self.assertIsNone(runner.profile_id)
                    with self.assertRaisesRegex(RunnerProfileError, "no reviewed runner profile"):
                        runner.run({}, "echo should-not-run", on_spawn=lambda *_: self.fail("spawned"))
                    self.assertFalse(marker.exists())

            # Mutable status fields cannot make an unreviewed profile appear
            # qualified to status consumers or exec callers.
            path = Path(tmp) / "runner-status-mutation"
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o700)
            runner = SandboxRunner(str(path))
            runner.profile_id = "profile-landlock"
            runner.profile_status = "qualified"
            with self.assertRaisesRegex(RunnerProfileError, "profile status mismatch"):
                runner.run({}, "echo should-not-run")

            # The named adapter class and the automatic builder follow the same
            # rule: adapter selection is not mechanism qualification.
            path = Path(tmp) / "landrun-adapter"
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o700)
            selected = LandlockRunner(str(path))
            built = build_runner(str(path))
            for runner in (selected, built):
                self.assertEqual(runner.adapter_id, "landlock")
                self.assertEqual(runner.sandbox_class, "unknown")
                self.assertEqual(runner.profile_status, "unqualified")
                with self.assertRaises(RunnerProfileError):
                    runner.run({}, "echo should-not-run")

    def test_unqualified_hints_do_not_consume_token_or_spawn(self):
        from gate_lite.orchestrator import LandlockRunner

        with tempfile.TemporaryDirectory() as tmp:
            runner_script = Path(tmp) / "landrun-sandbox"
            marker = Path(tmp) / "spawned"
            runner_script.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
            runner_script.chmod(0o700)
            runner = LandlockRunner(str(runner_script))
            orch = Orchestrator(Path(tmp) / "state", runner=runner)
            orch.add_tenant("tenant", ["did:key:test"])
            issued = orch.pass_("tenant", "did:key:test")
            from gate_lite.tokens import verify_pass

            claims = verify_pass(issued["token"], orch.gate_did)

            for _ in range(2):
                with self.assertRaisesRegex(RunnerProfileError, "no reviewed runner profile"):
                    orch.exec_("tenant", issued["slot_id"], "echo blocked", token=issued["token"])
            self.assertFalse(orch.registry.jti_consumed(claims["jti"]))
            self.assertFalse(marker.exists())
            status = orch.status("tenant", issued["slot_id"])["runner"]
            self.assertEqual(status["adapter_id"], "landlock")
            self.assertEqual(status["class"], "unknown")
            self.assertEqual(status["profile_status"], "unqualified")
            bundle = orch.receipt(orch.task_id_for(issued["slot_id"]))
            self.assertFalse(any(r["type"] in ("task.decision", "task.execution") for r in bundle["receipts"]))


if __name__ == "__main__":
    unittest.main()
