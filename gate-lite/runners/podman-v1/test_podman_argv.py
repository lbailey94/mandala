#!/usr/bin/env python3
"""Argv and fail-closed tests for runners/podman-v1."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class PodmanArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.capture = self.directory / "podman-argv.json"
        self.fake_podman = self.directory / "podman"
        self.fake_podman.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['PODMAN_CAPTURE'], 'w') as f: json.dump(sys.argv[1:], f)\n",
            encoding="utf-8",
        )
        self.fake_podman.chmod(0o755)

    def test_rootless_readonly_none_network_argv(self):
        ws = self.directory / "ws"
        ws.mkdir()
        env = {
            **os.environ,
            "PODMAN_CAPTURE": str(self.capture),
            "MANDALA_PODMAN_BIN": str(self.fake_podman),
            "MANDALA_PODMAN_IMAGE": "ghcr.io/example/mandala-worker@sha256:0000",
        }
        proc = subprocess.run(
            [
                "bash",
                str(ROOT / "mandala-sandbox-podman"),
                "--exec",
                json.dumps({"program": "/bin/echo", "args": ["a\nb"], "workspace": str(ws), "rw": False}),
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = json.loads(self.capture.read_text())
        self.assertIn("--network=none", argv)
        self.assertIn("--read-only", argv)
        self.assertIn("--userns=keep-id", argv)
        self.assertIn("--cap-drop=ALL", argv)
        self.assertIn(f"{ws}:/workspace:ro", argv)
        self.assertEqual(argv[-3:], ["ghcr.io/example/mandala-worker@sha256:0000", "/bin/echo", "a\nb"])

    def test_requires_image_and_podman_binary(self):
        proc_no_img = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-podman"), "--exec", '{"program":"/bin/echo"}'],
            env={**os.environ, "MANDALA_PODMAN_BIN": str(self.fake_podman)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc_no_img.returncode, 64)

        proc_no_bin = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-podman"), "--exec", '{"program":"/bin/echo"}'],
            env={**os.environ, "PATH": "/usr/bin:/bin", "MANDALA_PODMAN_BIN": str(self.directory / "missing")},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc_no_bin.returncode, 127)


if __name__ == "__main__":
    unittest.main()
