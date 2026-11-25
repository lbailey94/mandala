#!/usr/bin/env python3
"""Argv and envelope validation tests for runners/bwrap-landlock-v1."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class BwrapLandlockArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.capture = self.directory / "argv.json"
        self.bwrap_capture = self.directory / "bwrap"
        self.bwrap_capture.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['ARGV_CAPTURE'], 'w') as f: json.dump(sys.argv[1:], f)\n",
            encoding="utf-8",
        )
        self.bwrap_capture.chmod(0o755)
        self.fake_wm = self.directory / "fake-wm-sandbox"
        self.fake_wm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.fake_wm.chmod(0o755)

    def run_wrapper(self, envelope):
        env = os.environ.copy()
        env["PATH"] = f"{self.directory}:{env['PATH']}"
        env["ARGV_CAPTURE"] = str(self.capture)
        env["WM_SANDBOX_BIN"] = str(self.fake_wm)
        env["HOME"] = "/nonexistent"
        result = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-bwrap-landlock"), "--exec", json.dumps(envelope)],
            env=env,
            text=True,
            capture_output=True,
        )
        captured = json.loads(self.capture.read_text()) if self.capture.exists() else None
        return result, captured

    def test_binds_wm_sandbox_and_preserves_exact_inner_envelope(self):
        ws = self.directory / "ws"
        ws.mkdir()
        args = ["", "line1\nline2", "tab\tvalue", "ends-with-newline\n"]
        result, captured = self.run_wrapper(
            {"program": "tool", "args": args, "workspace": str(ws), "rw": False}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            ["--ro-bind", str(self.fake_wm), "/run/wm-sandbox"],
            [captured[i:i + 3] for i in range(len(captured) - 2)],
        )
        self.assertIn(
            ["--ro-bind", str(ws), "/workspace"],
            [captured[i:i + 3] for i in range(len(captured) - 2)],
        )
        sep_idx = captured.index("--")
        self.assertEqual(captured[sep_idx + 1], "/run/wm-sandbox")
        self.assertEqual(captured[sep_idx + 2], "--exec")
        inner = json.loads(captured[sep_idx + 3])
        self.assertEqual(inner["program"], "tool")
        self.assertEqual(inner["args"], args)
        self.assertEqual(inner["workspace"], "/workspace")
        self.assertFalse(inner["rw"])
        self.assertFalse(inner["net"])

    def test_rejects_malformed_and_missing_writable_workspace(self):
        for bad in (
            {"program": "tool", "workspace": str(self.directory / "missing"), "rw": True},
            {"program": "tool", "rw": "yes"},
            {"program": "tool", "args": ["has\x00nul"]},
        ):
            self.capture.unlink(missing_ok=True)
            result, captured = self.run_wrapper(bad)
            self.assertEqual(result.returncode, 64)
            self.assertIsNone(captured)


if __name__ == "__main__":
    unittest.main()
