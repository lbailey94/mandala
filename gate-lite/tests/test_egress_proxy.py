#!/usr/bin/env python3
"""Egress proxy and fetch helper tests (no runner/profile required).

Starts the allowlist proxy over a Unix socket, a local HTTP server as the
allowed destination, and exercises CONNECT tunneling, denial, the log
records, and the sandbox-side fetch helper.
"""

import http.server
import json
import os
import pathlib
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent.parent / "tools"
PROXY = TOOLS / "mandala-egress-proxy.py"
FETCH = TOOLS / "mandala-fetch.py"
WRAPPER = TOOLS / "mandala-sandbox-egress"
BODY = b"hello-egress\n"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *_args):
        pass


class TestEgressProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(prefix="egress-proxy-test-")
        root = pathlib.Path(cls.tempdir.name)
        cls.socket_path = root / "egress.sock"
        cls.log_path = root / "egress.log"

        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.http_port = cls.httpd.server_address[1]
        cls.http_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.http_thread.start()

        cls.proxy = subprocess.Popen(
            [sys.executable, str(PROXY),
             "--socket", str(cls.socket_path),
             "--log", str(cls.log_path),
             "--timeout", "1",
             "--allow", f"127.0.0.1:{cls.http_port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 10
        while time.time() < deadline and not cls.socket_path.exists():
            time.sleep(0.05)
        if not cls.socket_path.exists():
            raise RuntimeError("egress proxy did not create its socket")

    @classmethod
    def tearDownClass(cls):
        cls.proxy.terminate()
        try:
            cls.proxy.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proxy.kill()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.http_thread.join(timeout=5)
        cls.tempdir.cleanup()

    def _records(self):
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text().splitlines() if line.strip()]

    def test_allowed_connect_tunnel_and_log(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(self.socket_path))
        client.sendall(f"CONNECT 127.0.0.1:{self.http_port} HTTP/1.1\r\n\r\n".encode())
        head = client.recv(256)
        self.assertIn(b"200 Connection Established", head)
        client.sendall(
            f"GET /file HTTP/1.1\r\nHost: 127.0.0.1:{self.http_port}\r\n"
            "Connection: close\r\n\r\n".encode()
        )
        data = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            data += chunk
        client.close()
        self.assertIn(BODY.strip(), data)
        allowed = [r for r in self._records() if r.get("allowed") and r.get("host") == "127.0.0.1"]
        self.assertTrue(allowed, "allowed record missing")
        self.assertGreater(allowed[-1]["bytes_out"], 0)

    def test_unlisted_destination_denied_and_recorded(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(self.socket_path))
        client.sendall(b"CONNECT example.org:443 HTTP/1.1\r\n\r\n")
        head = client.recv(256)
        client.close()
        self.assertIn(b"403 Forbidden", head)
        denied = [r for r in self._records()
                  if not r.get("allowed") and r.get("host") == "example.org"]
        self.assertTrue(denied, "denied record missing")
        self.assertEqual(denied[-1]["reason"], "not-in-allowlist")

    def test_allowlist_is_port_specific(self):
        other_port = self.http_port + 1
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(3)
        client.connect(str(self.socket_path))
        client.sendall(f"CONNECT 127.0.0.1:{other_port} HTTP/1.1\r\n\r\n".encode())
        response = client.recv(256)
        client.close()
        self.assertIn(b"403 Forbidden", response)
        denied = [r for r in self._records()
                  if not r.get("allowed") and r.get("port") == other_port]
        self.assertTrue(denied)

    def test_malformed_connect_authority_is_rejected(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(3)
        client.connect(str(self.socket_path))
        client.sendall(b"CONNECT 127.0.0.1:notaport HTTP/1.1\r\n\r\n")
        response = client.recv(256)
        client.close()
        self.assertIn(b"502 Bad Gateway", response)

    def test_zero_port_authority_is_rejected_instead_of_using_default_port(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(3)
        client.connect(str(self.socket_path))
        client.sendall(b"CONNECT 127.0.0.1:0 HTTP/1.1\r\n\r\n")
        response = client.recv(256)
        client.close()
        self.assertIn(b"502 Bad Gateway", response)

    def test_idle_tunnel_closes_and_records_a_bounded_outcome(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(4)
        client.connect(str(self.socket_path))
        client.sendall(f"CONNECT 127.0.0.1:{self.http_port} HTTP/1.1\r\n\r\n".encode())
        self.assertIn(b"200 Connection Established", client.recv(256))
        started = time.monotonic()
        self.assertEqual(client.recv(1), b"")
        self.assertLess(time.monotonic() - started, 3.5)
        client.close()
        allowed = [r for r in self._records()
                   if r.get("allowed") and r.get("port") == self.http_port]
        self.assertTrue(allowed)
        self.assertEqual(allowed[-1]["bytes_out"], 0)

    def test_proxy_socket_is_private_to_the_runner_uid(self):
        mode = stat.S_IMODE(self.socket_path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_proxy_override_is_rejected_before_payload_output(self):
        env = {**os.environ, "MANDALA_EGRESS_PROXY": "/tmp/unreviewed-proxy.py"}
        result = subprocess.run(
            [str(WRAPPER), "--exec", json.dumps({"program": "echo", "args": ["MUST_NOT_RUN"]})],
            capture_output=True, text=True, env=env, timeout=5,
        )
        self.assertEqual(result.returncode, 70)
        self.assertNotIn("MUST_NOT_RUN", result.stdout)
        self.assertIn("override is not permitted", result.stderr)

    def test_sigterm_drains_active_connect_and_flushes_terminal_log(self):
        with tempfile.TemporaryDirectory(prefix="egress-proxy-stop-") as tmp:
            root = pathlib.Path(tmp)
            socket_path = root / "egress.sock"
            log_path = root / "egress.jsonl"
            proxy = subprocess.Popen(
                [sys.executable, str(PROXY), "--socket", str(socket_path),
                 "--log", str(log_path), "--timeout", "1",
                 "--allow", f"127.0.0.1:{self.http_port}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 5
                while not socket_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(socket_path.exists(), "proxy socket did not start")
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client.settimeout(3)
                client.connect(str(socket_path))
                client.sendall(
                    f"CONNECT 127.0.0.1:{self.http_port} HTTP/1.1\r\n\r\n".encode()
                )
                self.assertIn(b"200 Connection Established", client.recv(256))
                proxy.terminate()
                proxy.wait(timeout=5)
                self.assertEqual(client.recv(1), b"")
                client.close()
                records = [json.loads(line) for line in log_path.read_text().splitlines()]
                self.assertEqual(
                    [record["event"] for record in records],
                    ["connect_start", "connect_complete"],
                )
                self.assertEqual(records[0]["connection_id"], records[1]["connection_id"])
            finally:
                if proxy.poll() is None:
                    proxy.kill()
                    proxy.wait(timeout=5)

    def test_fetch_helper_through_proxy(self):
        result = subprocess.run(
            [sys.executable, str(FETCH), f"http://127.0.0.1:{self.http_port}/file",
             "--sock", str(self.socket_path)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.encode(), BODY)
        self.assertIn("status=200", result.stderr)

    def test_fetch_helper_denied(self):
        result = subprocess.run(
            [sys.executable, str(FETCH), "http://example.org/",
             "--sock", str(self.socket_path)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("proxy refused", result.stderr)

    def test_fetch_helper_requires_socket(self):
        result = subprocess.run(
            [sys.executable, str(FETCH), "http://127.0.0.1/", "--sock", "/nonexistent.sock"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
