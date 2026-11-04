import http.server
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import dashboard


class DashboardQueryTests(unittest.TestCase):
    def test_bad_queries_return_400_and_server_still_answers(self):
        with tempfile.TemporaryDirectory() as root:
            server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0),
                dashboard.build_api(root, "http://127.0.0.1:9", "http://127.0.0.1:9", "telemetry", 0.01),
            )
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                for query in ("hours=invalid", "hours=nan", "hours=inf", "hours=-1", "hours=8761",
                              "hours=", "hours=1&hours=2", "limit=0", "limit=1001", "limit=1.5", "limit=inf"):
                    with self.subTest(query=query), self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(base + "/api/history?" + query, timeout=2)
                    self.assertEqual(caught.exception.code, 400)
                    self.assertIn("error", json.loads(caught.exception.read()))
                    caught.exception.close()
                with urllib.request.urlopen(base + "/api/history?hours=0.5&limit=1", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response)["count"], 0)
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
