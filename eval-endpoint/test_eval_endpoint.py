"""End-to-end tests for the eval endpoint (lexical backend always; wm if present)."""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN = "test-token-eval-01"


def call(port: int, path: str, body: dict | None = None, token: str | None = TOKEN):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


class ServiceCase(unittest.TestCase):
    backend = "lexical"
    port = 18821

    @classmethod
    def setUpClass(cls):
        cls.state = tempfile.mkdtemp(prefix="eval-endpoint-test-")
        cls.process = subprocess.Popen(
            [sys.executable, str(ROOT / "eval_endpoint.py"),
             "--listen", f"127.0.0.1:{cls.port}", "--state", cls.state,
             "--backend", cls.backend, "--token", TOKEN],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                status, _ = call(cls.port, "/health", token=None)
                if status == 200:
                    return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("eval endpoint did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        shutil.rmtree(cls.state, ignore_errors=True)

    def test_health_is_keyless(self):
        status, payload = call(self.port, "/health", token=None)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_auth_required(self):
        status, payload = call(self.port, "/search", {"user_id": "u1", "query": "x"}, token=None)
        self.assertEqual(status, 401)
        status, payload = call(self.port, "/search", {"user_id": "u1", "query": "x"}, token="wrong-token")
        self.assertEqual(status, 401)

    def test_add_then_search(self):
        status, payload = call(self.port, "/add", {
            "user_id": "alice",
            "content": "Alice prefers tea over coffee in the morning.",
            "metadata": {"title": "preference"},
        })
        self.assertEqual(status, 200, payload)
        self.assertEqual(len(payload["ids"]), 1)
        status, payload = call(self.port, "/search", {"user_id": "alice", "query": "morning tea", "top_k": 5})
        self.assertEqual(status, 200, payload)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn("tea", payload["results"][0]["content"])

    def test_user_isolation(self):
        call(self.port, "/add", {"user_id": "bob", "content": "Bob's secret launch code is ORCHID-7."})
        status, payload = call(self.port, "/search", {"user_id": "carol", "query": "launch code ORCHID", "top_k": 10})
        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 0)
        status, payload = call(self.port, "/search", {"user_id": "bob", "query": "launch code ORCHID", "top_k": 10})
        self.assertGreaterEqual(payload["count"], 1)

    def test_batch_add(self):
        status, payload = call(self.port, "/add", {"items": [
            {"user_id": "dave", "content": "Dave runs a Rust workshop."},
            {"user_id": "dave", "content": "Dave's workshop uses LMDB."},
        ]})
        self.assertEqual(status, 200, payload)
        self.assertEqual(len(payload["ids"]), 2)

    def test_top_k_validation(self):
        status, _ = call(self.port, "/search", {"user_id": "alice", "query": "tea", "top_k": 1000})
        self.assertEqual(status, 400)

    def test_delete_removes_user_data(self):
        call(self.port, "/add", {"user_id": "erin", "content": "Erin's temporary eval memory."})
        status, payload = call(self.port, "/delete", {"user_id": "erin"})
        self.assertEqual(status, 200, payload)
        status, payload = call(self.port, "/search", {"user_id": "erin", "query": "temporary eval", "top_k": 5})
        self.assertEqual(payload["count"], 0)

    def test_unknown_path(self):
        status, _ = call(self.port, "/nope", {"user_id": "x"})
        self.assertEqual(status, 404)


class LexicalBackendCase(ServiceCase):
    backend = "lexical"
    port = 18821


@unittest.skipIf(shutil.which("wm") is None, "wm binary not on PATH")
class WmBackendCase(ServiceCase):
    backend = "wm"
    port = 18822


if __name__ == "__main__":
    unittest.main(verbosity=2)
