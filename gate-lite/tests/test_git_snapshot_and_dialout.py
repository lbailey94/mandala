"""Tests for git-backed slot snapshot/restore and outbound dial-out worker."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from continuity_receipt import verify_bundle
from continuity_receipt.canon import canonical_bytes

from gate_lite.orchestrator import Orchestrator, StubRunner

ROOT = Path(__file__).resolve().parents[1]


def _load_dialout_module():
    spec = importlib.util.spec_from_file_location(
        "mandala_dialout_worker",
        ROOT / "tools/mandala-dialout-worker.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestGitSnapshotAndRestore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.orch = Orchestrator(self.root / "state", runner=StubRunner())
        self.agent = "did:key:zGitSnap"
        self.orch.add_tenant("tenant-a", [self.agent])
        self.orch.add_tenant("tenant-b", [self.agent])

    def test_git_snapshot_restore_preserves_tree_hash_and_trust(self):
        src = self.orch.pass_("tenant-a", self.agent)
        ws = self.orch.workspaces_dir / src["slot_id"]
        (ws / "sub").mkdir(parents=True, exist_ok=True)
        (ws / "hello.txt").write_text("hello mandala\n", encoding="utf-8")
        (ws / "sub" / "data.json").write_text('{"k":1}\n', encoding="utf-8")

        snap = self.orch.snapshot("tenant-a", src["slot_id"], mode="git")
        self.assertEqual(snap["mode"], "git")
        self.assertEqual(snap["state"], "frozen")
        self.assertFalse((ws / ".git").exists())

        dst = self.orch.pass_("tenant-a", self.agent)
        restored = self.orch.restore("tenant-a", dst["slot_id"], snap["snapshot_id"])
        self.assertEqual(restored["mode"], "git")
        self.assertEqual(restored["restored_hash"], snap["tree_hash"])

        dst_ws = self.orch.workspaces_dir / dst["slot_id"]
        self.assertEqual((dst_ws / "hello.txt").read_text(encoding="utf-8"), "hello mandala\n")
        self.assertEqual((dst_ws / "sub" / "data.json").read_text(encoding="utf-8"), '{"k":1}\n')

        # Non-empty placed slot and cross-tenant restore must be denied
        nonempty = self.orch.pass_("tenant-a", self.agent)
        (self.orch.workspaces_dir / nonempty["slot_id"] / "existing.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "workspace is not empty"):
            self.orch.restore("tenant-a", nonempty["slot_id"], snap["snapshot_id"])

        term = self.orch.terminate("tenant-a", dst["slot_id"])
        bundle = self.orch.receipt(term["task_id"])
        self.assertEqual(verify_bundle(bundle).as_dict()["verdict"], "TRUSTED")

        # Cross-tenant restore and terminated target slot must be denied
        other = self.orch.pass_("tenant-b", self.agent)
        with self.assertRaises(PermissionError):
            self.orch.restore("tenant-b", other["slot_id"], snap["snapshot_id"])
        with self.assertRaisesRegex(ValueError, "terminated"):
            self.orch.restore("tenant-a", dst["slot_id"], snap["snapshot_id"])

    def test_git_snapshot_empty_workspace_succeeds(self):
        src = self.orch.pass_("tenant-a", self.agent)
        snap = self.orch.snapshot("tenant-a", src["slot_id"], mode="git")
        dst = self.orch.pass_("tenant-a", self.agent)
        restored = self.orch.restore("tenant-a", dst["slot_id"], snap["snapshot_id"])
        self.assertEqual(restored["restored_hash"], snap["tree_hash"])


class TestDialoutWorker(unittest.TestCase):
    def test_outbound_poll_exec_post_pointer_and_dedup(self):
        dialout = _load_dialout_module()
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            orch = Orchestrator(state, runner=StubRunner())
            agent = "did:key:zDialout"
            orch.add_tenant("tenant", [agent])
            issued = orch.pass_("tenant", agent)

            jobs_feed = [
                {
                    "id": "job-other",
                    "target": "@other-worker",
                    "action": "mandala.status",
                    "slot": issued["slot_id"],
                },
                {
                    "job_id": "job-exec-1",
                    "target": "@worker-1",
                    "action": "mandala.exec",
                    "tenant": "tenant",
                    "slot": issued["slot_id"],
                    "payload_ref": "/bin/echo dialout-ok",
                    "token": issued["token"],
                    "agent": agent,
                    "terminate": True,
                },
            ]
            posted = []

            class MockBoardHandler(BaseHTTPRequestHandler):
                def log_message(self, fmt, *args):
                    pass

                def do_GET(self):  # noqa: N802
                    body = json.dumps({"jobs": jobs_feed}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def do_POST(self):  # noqa: N802
                    length = int(self.headers.get("Content-Length") or 0)
                    posted.append(json.loads(self.rfile.read(length).decode("utf-8")))
                    resp = b'{"ok":true}'
                    self.send_response(202)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)

            server = ThreadingHTTPServer(("127.0.0.1", 0), MockBoardHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                board_url = f"http://127.0.0.1:{port}"
                secret = "test-hmac-secret"
                first = dialout.poll_once(
                    orch,
                    tenant="tenant",
                    worker_id="worker-1",
                    board_url=board_url,
                    poll_path="/jobs",
                    post_path="/post",
                    state_dir=state,
                    hmac_key=secret,
                )
                self.assertEqual(len(first), 1)
                self.assertEqual(len(posted), 1)
                ptr = posted[0]
                self.assertEqual(ptr["job_id"], "job-exec-1")
                self.assertEqual(ptr["verdict"], "TRUSTED")
                self.assertEqual(ptr["receipt_count"], 4)
                self.assertTrue(ptr["head_receipt_id"])
                compact = json.dumps(ptr, separators=(",", ":"))
                self.assertLessEqual(len(compact), 600)

                # Verify HMAC-SHA256 signature over canonical CPR pointer
                sig = ptr.pop("hmac_sha256")
                expected_sig = "hmac-sha256:" + hmac.new(
                    secret.encode("utf-8"), canonical_bytes(ptr), hashlib.sha256
                ).hexdigest()
                self.assertEqual(sig, expected_sig)

                # Second poll must deduplicate and emit zero new outbound posts
                second = dialout.poll_once(
                    orch,
                    tenant="tenant",
                    worker_id="worker-1",
                    board_url=board_url,
                    poll_path="/jobs",
                    post_path="/post",
                    state_dir=state,
                    hmac_key=secret,
                )
                self.assertEqual(second, [])
                self.assertEqual(len(posted), 1)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
