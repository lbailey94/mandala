#!/usr/bin/env python3
"""Argv, snapshot validation, and sparse-copy tests for runners/firecracker-snap-v1."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class FirecrackerArgvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.capture = self.directory / "fc-invoke.json"
        self.fake_fc = self.directory / "firecracker"
        self.fake_fc.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "idx = sys.argv.index('--config-file')\n"
            "cfg = json.loads(pathlib.Path(sys.argv[idx + 1]).read_text())\n"
            "payload = json.loads(pathlib.Path(cfg['payload_path']).read_text())\n"
            "with open(os.environ['FC_CAPTURE'], 'w') as f:\n"
            "    json.dump({'argv': sys.argv[1:], 'cfg': cfg, 'payload': payload}, f)\n",
            encoding="utf-8",
        )
        self.fake_fc.chmod(0o755)
        self.snap_dir = self.directory / "snaps"
        self.snap_dir.mkdir()
        for name in ("kernel.bin", "rootfs.ext4", "mem.snap", "vmstate.snap"):
            (self.snap_dir / name).write_bytes(b"stub-" + name.encode())

    def test_valid_snapshot_invocation_and_cleanup(self):
        ws = self.directory / "ws"
        ws.mkdir()
        env = {
            **os.environ,
            "FC_CAPTURE": str(self.capture),
            "MANDALA_FC_BIN": str(self.fake_fc),
            "MANDALA_FC_SNAPSHOT_DIR": str(self.snap_dir),
        }
        proc = subprocess.run(
            [
                "bash",
                str(ROOT / "mandala-sandbox-firecracker"),
                "--exec",
                json.dumps({"program": "/bin/echo", "args": ["hello"], "workspace": str(ws), "rw": True}),
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(self.capture.read_text())
        self.assertEqual(data["payload"]["program"], "/bin/echo")
        self.assertEqual(data["payload"]["args"], ["hello"])
        self.assertEqual(data["cfg"]["kernel_image_path"], str(self.snap_dir / "kernel.bin"))
        self.assertFalse(Path(data["cfg"]["rootfs_path"]).parent.exists())  # cleaned on exit

    def test_fails_closed_when_binary_or_snapshot_missing(self):
        base_env = {**os.environ, "MANDALA_FC_SNAPSHOT_DIR": str(self.snap_dir)}
        proc_no_bin = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-firecracker"), "--exec", '{"program":"/bin/echo"}'],
            env={**base_env, "PATH": "/usr/bin:/bin", "MANDALA_FC_BIN": str(self.directory / "missing-fc")},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc_no_bin.returncode, 127)

        (self.snap_dir / "mem.snap").unlink()
        proc_no_snap = subprocess.run(
            ["bash", str(ROOT / "mandala-sandbox-firecracker"), "--exec", '{"program":"/bin/echo"}'],
            env={**base_env, "MANDALA_FC_BIN": str(self.fake_fc)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc_no_snap.returncode, 65)


if __name__ == "__main__":
    unittest.main()
