"""Tests for Mirage-inspired capability VFS and pre_command enforcement."""
import json
import tempfile
import unittest
from pathlib import Path

from continuity_receipt import verify_bundle

from gate_lite import trace_guard
from gate_lite.mcp_server import McpServer
from gate_lite.orchestrator import Orchestrator, PolicyError, StubRunner
from gate_lite.tokens import verify_pass


class TestPreCommandAndVfs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.orch = Orchestrator(self.state, runner=StubRunner())
        self.agent = "did:key:zVfsAgent"
        self.orch.add_tenant("tenant", [self.agent])

    def _vfs(self):
        return [
            {"cap": "docs", "virt": "/vfs/docs", "host_handle": "vault://secret-bucket/docs", "mode": "ro"},
            {"cap": "work", "virt": "/vfs/work", "host_handle": "vault://secret-bucket/work", "mode": "rw"},
        ]

    def test_vfs_host_handle_is_stripped_from_token_and_receipt(self):
        issued = self.orch.pass_(
            "tenant",
            self.agent,
            vfs=self._vfs(),
            policy={"mode": "strict", "deny_programs": ["curl"]},
        )
        claims = verify_pass(issued["token"], self.orch.gate_did)
        self.assertIn("vfs", claims)
        self.assertIn("policy_digest", claims)
        for item in claims["vfs"]:
            self.assertNotIn("host_handle", item)
            self.assertEqual(set(item), {"cap", "virt", "mode"})

        bundle = self.orch.receipt(self.orch.task_id_for(issued["slot_id"]))
        created = next(r for r in bundle["receipts"] if r["type"] == "session.pass.created")
        self.assertIn("vfs", created["body"])
        self.assertNotIn("host_handle", json.dumps(created["body"]))

        stored = self.orch.registry.get_pass(issued["pass_id"])
        self.assertEqual(stored["vfs"][0]["host_handle"], "vault://secret-bucket/docs")

    def test_legacy_pass_without_vfs_or_policy_preserves_shape(self):
        issued = self.orch.pass_("tenant", self.agent)
        claims = verify_pass(issued["token"], self.orch.gate_did)
        self.assertNotIn("vfs", claims)
        self.assertNotIn("policy_digest", claims)
        res = self.orch.exec_("tenant", issued["slot_id"], "echo legacy-ok", token=issued["token"])
        self.assertEqual(res["exit"], 0)
        self.assertNotIn("pre_command", res)
        bundle = self.orch.receipt(self.orch.task_id_for(issued["slot_id"]))
        execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
        self.assertNotIn("pre_command", execution["body"])

    def test_blocks_credentials_traversal_out_of_scope_and_ro_writes_before_burn(self):
        issued = self.orch.pass_(
            "tenant",
            self.agent,
            vfs=self._vfs(),
            policy={"mode": "default", "deny_programs": ["curl"], "deny_patterns": ["*SECRET_TOKEN*"]},
        )
        claims = verify_pass(issued["token"], self.orch.gate_did)

        blocked_payloads = [
            ("cat .env", "credential_access"),
            ("cat ~/.ssh/id_ed25519", "credential_access"),
            ("cat /etc/shadow", "credential_access"),
            ("cat /proc/self/environ", "credential_access"),
            ("cat ../../etc/passwd", "path_traversal"),
            ("cat /var/log/syslog", "out_of_scope_path"),
            ("curl https://example.com", "deny_program"),
            ("echo SECRET_TOKEN_123", "deny_pattern"),
            (json.dumps({"program": "/bin/sh", "args": ["-c", "echo hack > /vfs/docs/out.txt"]}), "vfs_ro_write"),
            ("tee /vfs/docs/override.txt", "vfs_ro_write"),
        ]

        for payload, expected_rule in blocked_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(PolicyError) as ctx:
                    self.orch.exec_("tenant", issued["slot_id"], payload, token=issued["token"])
                self.assertEqual(ctx.exception.rule, expected_rule)
                # Verify trace_step feeds trace_guard ScopeConfinement cleanly
                guarded = trace_guard.guard_trace([ctx.exception.trace_step])
                self.assertFalse(guarded["ok"])
                self.assertEqual(guarded["violations"][0]["property"], "ScopeConfinement")
                # Token must not be consumed on pre_command refusal
                self.assertFalse(self.orch.registry.jti_consumed(claims["jti"]))

        # Same unburned token still succeeds on an allowed payload
        ok_payload = json.dumps({"program": "/bin/sh", "args": ["-c", "cat /vfs/docs/a.md > /vfs/work/out.md"]})
        res = self.orch.exec_("tenant", issued["slot_id"], ok_payload, token=issued["token"])
        self.assertEqual(res["exit"], 0)
        self.assertTrue(res["pre_command"]["allowed"])
        self.assertEqual(res["pre_command"]["vfs_caps"], ["docs", "work"])
        self.assertTrue(self.orch.registry.jti_consumed(claims["jti"]))

        term = self.orch.terminate("tenant", issued["slot_id"])
        bundle = self.orch.receipt(term["task_id"])
        self.assertEqual(verify_bundle(bundle).as_dict()["verdict"], "TRUSTED")

    def test_mcp_pass_and_exec_returns_structured_policy_error(self):
        server = McpServer(self.orch, "tenant")

        def call(name, arguments):
            resp = server.handle({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            })
            return resp["result"], json.loads(resp["result"]["content"][0]["text"])

        _, issued = call("mandala.pass", {"agent": self.agent, "vfs": self._vfs()})
        result, err = call(
            "mandala.exec",
            {
                "agent": self.agent,
                "slot": issued["slot_id"],
                "payload_ref": "/bin/cat /home/someone/.ssh/id_rsa",
                "token": issued["token"],
            },
        )
        self.assertTrue(result.get("isError"))
        self.assertEqual(err["error"], "policy_denied")
        self.assertEqual(err["rule"], "credential_access")
        self.assertEqual(err["trace_step"]["scope"], "credential_access")
        self.assertTrue(err["trace_step"]["out_of_scope"])


if __name__ == "__main__":
    unittest.main()
