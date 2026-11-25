#!/usr/bin/env python3
"""Argv and envelope validation tests for runners/landlock-wm-v1."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class LandlockArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.capture = self.directory / "argv.json"
        self.capture_script = self.directory / "wm-sandbox"
        self.capture_script.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['ARGV_CAPTURE'], 'w') as f: json.dump(sys.argv[1:], f)\n",
            encoding="utf-8",
        )
        self.capture_script.chmod(0o755)

    def run_wrapper(self, envelope, extra_env=None):
        env = os.environ.copy()
        env["PATH"] = f"{self.directory}:{env['PATH']}"
        env["ARGV_CAPTURE"] = str(self.capture)
        env["WM_SANDBOX_BIN"] = str(self.capture_script)
        env["HOME"] = "/nonexistent"
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-landlock"), "--exec", json.dumps(envelope)],
            env=env,
            text=True,
            capture_output=True,
        )
        captured = json.loads(self.capture.read_text()) if self.capture.exists() else None
        return result, captured

    def test_preserves_exact_argument_bytes_and_empty_args(self):
        args = ["", "line1\nline2", "tab\tvalue", "ends-with-newline\n"]
        result, captured = self.run_wrapper({"program": "tool", "args": args})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(captured[0], "--exec")
        inner = json.loads(captured[1])
        self.assertEqual(inner["schema"], "wm-sandbox-exec-v1")
        self.assertEqual(inner["program"], "tool")
        self.assertEqual(inner["args"], args)
        self.assertFalse(inner["net"])

        self.capture.unlink(missing_ok=True)
        result2, captured2 = self.run_wrapper({"program": "pwd", "args": []})
        self.assertEqual(result2.returncode, 0, result2.stderr)
        self.assertEqual(json.loads(captured2[1])["args"], [])

    def test_writable_and_ro_workspace_modes(self):
        ws = self.directory / "ws"
        ws.mkdir()
        for writable in (False, True):
            self.capture.unlink(missing_ok=True)
            result, captured = self.run_wrapper(
                {"program": "tool", "args": [], "workspace": str(ws), "rw": writable}
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            inner = json.loads(captured[1])
            self.assertEqual(inner["workspace"], str(ws))
            self.assertEqual(inner["rw"], writable)

    def test_rejects_invalid_envelopes_and_missing_writable_workspace(self):
        for bad in (
            {"program": "tool", "workspace": str(self.directory / "missing"), "rw": True},
            {"program": "tool", "rw": "true"},
            {"program": "tool", "args": None},
            {"program": "tool", "args": ["bad\x00arg"]},
            {"program": "bad\x00prog", "args": []},
        ):
            self.capture.unlink(missing_ok=True)
            result, captured = self.run_wrapper(bad)
            self.assertEqual(result.returncode, 64, result.stderr)
            self.assertIsNone(captured)

    def test_malformed_json_and_partial_jq_fail_closed(self):
        env = os.environ.copy()
        env["WM_SANDBOX_BIN"] = str(self.capture_script)
        for raw in ('{"program":"tool","args":[1]}', "{bad json"):
            self.capture.unlink(missing_ok=True)
            proc = subprocess.run(
                ["bash", str(ROOT / "mandala-sandbox-landlock"), "--exec", raw],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 64)
            self.assertFalse(self.capture.exists())

        fake_jq = self.directory / "jq"
        fake_jq.write_text(
            "#!/usr/bin/python3\nimport os, sys\n"
            "os.write(1, b'tool\\0false\\0\\0false\\0')\nsys.exit(23)\n",
            encoding="utf-8",
        )
        fake_jq.chmod(0o755)
        proc = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-landlock"), "--exec", '{"program":"tool"}'],
            env={**env, "PATH": f"{self.directory}:{env['PATH']}"},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 64)
        self.assertFalse(self.capture.exists())

    def test_missing_wm_sandbox_exits_127(self):
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "WM_SANDBOX_BIN": str(self.directory / "missing-wm-sandbox"),
        }
        proc = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-landlock"), "--exec", '{"program":"tool"}'],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 127)


if __name__ == "__main__":
    unittest.main()
