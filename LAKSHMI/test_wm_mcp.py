import io
import json
import unittest
from unittest import mock

import wm_mcp


class McpClientTests(unittest.TestCase):
    def call(self, result):
        reply = io.BytesIO(json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode())
        with mock.patch.object(wm_mcp.urllib.request, "urlopen", return_value=reply) as transport:
            value = wm_mcp.call_tool("http://127.0.0.1:9/mcp", "memory.stats", {}, 0.1)
            self.assertEqual(transport.call_args.args[0].full_url, "http://127.0.0.1:9/mcp")
            return value

    def test_structured_and_text_objects(self):
        self.assertEqual(self.call({"structuredContent": {"count": 3}}), {"count": 3})
        self.assertEqual(self.call({"content": [{"type": "text", "text": "note"},
                                               {"type": "text", "text": '{"count":3}'}]}), {"count": 3})

    def test_tool_errors_and_ambiguous_payloads_are_feed_failures(self):
        self.assertIn("_error", self.call({"isError": True, "structuredContent": {"count": 3}}))
        self.assertIn("_error", self.call({"content": [{"text": '{}'}, {"text": '{}'}]}))

    def test_wrong_response_id_does_not_become_telemetry(self):
        for identity in (2, True, "1", None):
            reply = io.BytesIO(json.dumps({"jsonrpc": "2.0", "id": identity,
                                          "result": {"structuredContent": {}}}).encode())
            with mock.patch.object(wm_mcp.urllib.request, "urlopen", return_value=reply):
                self.assertIn("_error", wm_mcp.call_tool("http://127.0.0.1:9", "stats", {}, 0.1))
