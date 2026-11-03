#!/usr/bin/env python3
"""Egress semantics: declared destinations are recorded intent, not enforcement.

When `net: true` and destinations are declared, the current wrapper profile
shares the whole network; the declared list is not an allowlist, and entries
carry `"enforced": false`. Denials are enforced by the netns unshare and carry
`"enforced": true`. These vocabulary guarantees are what receipts rely on, so
they are pinned here without needing a qualified runner.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from continuity_receipt import keys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate_lite.orchestrator import (  # noqa: E402
    ExecResult,
    Orchestrator,
    PROFILE_ID,
    PROFILE_ID_EGRESS,
    SandboxRunner,
    SliceRunner,
    _egress_outcomes_from_log,
    parse_payload,
)


class TestEgressSemantics(unittest.TestCase):
    def test_string_false_cannot_become_a_network_grant(self):
        payload = json.dumps({"program": "curl", "net": "false", "egress": ["example.org"]})
        for runner_class in (SandboxRunner, SliceRunner):
            with self.subTest(runner=runner_class.__name__):
                runner = object.__new__(runner_class)
                runner._require_profile = lambda: None
                with patch.object(runner, "_popen") as spawn:
                    with self.assertRaisesRegex(ValueError, "'net' must be a boolean"):
                        runner.run({}, payload)
                    spawn.assert_not_called()

    def test_envelope_rejects_ambiguous_types_and_nul_before_planning(self):
        invalid_members = (
            {"program": 1}, {"program": ""}, {"program": "echo\x00ignored"},
            {"args": "hello"}, {"args": None}, {"args": [1]}, {"args": ["\x00"]},
            {"net": 0}, {"net": 1}, {"net": "true"}, {"net": None},
            {"egress": "example.org"}, {"egress": None}, {"egress": [1]},
            {"egress": [""]}, {"egress": ["example.org\x00ignored"]},
        )
        for members in invalid_members:
            with self.subTest(members=members):
                with self.assertRaises(ValueError):
                    parse_payload(json.dumps({"program": "echo", **members}))

    def test_duplicate_envelope_members_cannot_change_network_authority(self):
        with self.assertRaisesRegex(ValueError, "duplicate payload envelope member: net"):
            parse_payload('{"program":"curl","net":false,"net":true,"egress":["example.org"]}')

    def test_valid_envelope_preserves_literal_arguments_and_boolean_authority(self):
        for net in (False, True):
            with self.subTest(net=net):
                plan = parse_payload(json.dumps({
                    "program": "echo", "args": ["", "false", "雪", "a b"],
                    "net": net, "egress": ["example.org:443"],
                }))
                self.assertEqual(plan["args"], ["", "false", "雪", "a b"])
                self.assertIs(plan["net"], net)
                self.assertEqual(plan["declared"], ["example.org:443"])
        self.assertEqual(parse_payload('{"program":"echo"}')["args"], [])
        self.assertFalse(parse_payload('{"program":"echo"}')["net"])

    def test_granted_egress_records_unenforced_destinations(self):
        plan = parse_payload(
            json.dumps(
                {
                    "program": "curl",
                    "args": ["-sS", "https://example.com"],
                    "net": True,
                    "egress": ["example.com", "api.example.org"],
                }
            )
        )
        self.assertTrue(plan["net"])
        self.assertEqual(
            [entry["destination"] for entry in plan["egress"]],
            ["example.com", "api.example.org"],
        )
        for entry in plan["egress"]:
            self.assertTrue(entry["allowed"], entry)
            self.assertFalse(entry["enforced"], entry)
            self.assertIn("whole network", entry["enforcer"])

    def test_net_without_declared_destinations_is_enforced_denial(self):
        plan = parse_payload(
            json.dumps(
                {
                    "program": "curl",
                    "args": ["-sS", "https://example.com"],
                    "net": True,
                    "egress": [],
                }
            )
        )
        self.assertFalse(plan["net"])
        entry = plan["egress"][0]
        self.assertEqual(entry["destination"], "undeclared")
        self.assertFalse(entry["allowed"])
        self.assertTrue(entry["enforced"])
        self.assertEqual(entry["bytes"], 0)

    def test_declared_without_net_is_enforced_denial(self):
        plan = parse_payload(
            json.dumps(
                {
                    "program": "curl",
                    "args": ["-sS", "https://example.com"],
                    "egress": ["example.com"],
                }
            )
        )
        self.assertFalse(plan["net"])
        entry = plan["egress"][0]
        self.assertEqual(entry["destination"], "example.com")
        self.assertFalse(entry["allowed"])
        self.assertTrue(entry["enforced"])

    def test_plain_command_requests_no_egress(self):
        plan = parse_payload("echo hello")
        self.assertFalse(plan["net"])
        self.assertEqual(plan["egress"], [])

    def test_proxy_receipt_totals_are_keyed_by_host_and_port(self):
        plan = {"declared": ["example.org:80", "example.org:443"]}
        records = [
            {"event": "connect_start", "connection_id": "a", "host": "example.org",
             "port": 80, "allowed": True},
            {"event": "connect_complete", "connection_id": "a", "host": "example.org",
             "port": 80, "allowed": True, "bytes_out": 10, "bytes_in": 20},
            {"event": "connect_start", "connection_id": "b", "host": "example.org",
             "port": 443, "allowed": True},
            {"event": "connect_complete", "connection_id": "b", "host": "example.org",
             "port": 443, "allowed": True, "bytes_out": 100, "bytes_in": 200},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            outcomes = _egress_outcomes_from_log(plan, path)
        self.assertEqual([entry["bytes"] for entry in outcomes], [30, 300])
        self.assertEqual([entry["bytes_out"] for entry in outcomes], [10, 100])
        self.assertTrue(all(entry["allowed"] and entry["enforced"] for entry in outcomes))

    def test_port_specific_denial_does_not_deny_another_allowed_port(self):
        plan = {"declared": ["example.org:80", "example.org:443"]}
        records = [
            {"event": "connect", "host": "example.org", "port": 80,
             "allowed": False, "reason": "not-in-allowlist"},
            {"event": "connect_start", "connection_id": "b", "host": "example.org",
             "port": 443, "allowed": True},
            {"event": "connect_complete", "connection_id": "b", "host": "example.org",
             "port": 443, "allowed": True, "bytes_out": 5, "bytes_in": 7},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress.jsonl"
            path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            outcomes = _egress_outcomes_from_log(plan, path)
        self.assertFalse(outcomes[0]["allowed"])
        self.assertEqual(outcomes[0]["denied_reason"], "not-in-allowlist")
        self.assertTrue(outcomes[1]["allowed"])
        self.assertEqual(outcomes[1]["bytes"], 12)

    def test_idna_aliases_attribute_allowed_bytes_to_declared_destination(self):
        for declared_host, observed_host in (
                ("xn--bcher-kva.example", "bücher.example"),
                ("bücher.example", "xn--bcher-kva.example")):
            with self.subTest(declared=declared_host, observed=observed_host):
                plan = {"declared": [declared_host + ":443"]}
                records = [
                    {"event": "connect_start", "connection_id": "idna",
                     "host": observed_host, "port": 443, "allowed": True},
                    {"event": "connect_complete", "connection_id": "idna",
                     "host": observed_host, "port": 443, "allowed": True,
                     "bytes_out": 52, "bytes_in": 112},
                ]
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "egress.jsonl"
                    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
                    outcomes = _egress_outcomes_from_log(plan, path)
                self.assertEqual(outcomes[0]["bytes"], 164)
                self.assertTrue(outcomes[0]["allowed"])
                self.assertTrue(outcomes[0]["enforced"])

    def test_allowed_traffic_outside_declared_host_or_port_fails_closed(self):
        plan = {"declared": ["example.org:443"]}
        for host, port in (("unlisted.example", 443), ("example.org", 80)):
            with self.subTest(host=host, port=port):
                records = [
                    {"event": "connect_start", "connection_id": "unexpected",
                     "host": host, "port": port, "allowed": True},
                    {"event": "connect_complete", "connection_id": "unexpected",
                     "host": host, "port": port, "allowed": True,
                     "bytes_out": 5, "bytes_in": 7},
                ]
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "egress.jsonl"
                    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
                    outcomes = _egress_outcomes_from_log(plan, path)
                self.assertFalse(outcomes[0]["allowed"])
                self.assertFalse(outcomes[0]["enforced"])
                self.assertIn("outside the declared allowlist", outcomes[0]["evidence_error"])

    def test_missing_or_malformed_requested_log_is_explicitly_unavailable(self):
        plan = {"declared": ["example.org:443"]}
        with tempfile.TemporaryDirectory() as tmp:
            missing = _egress_outcomes_from_log(plan, Path(tmp) / "missing.jsonl")
            malformed_path = Path(tmp) / "malformed.jsonl"
            malformed_path.write_text('{"host": "example.org",\n')
            malformed = _egress_outcomes_from_log(plan, malformed_path)
        for outcomes in (missing, malformed):
            self.assertEqual(len(outcomes), 1)
            self.assertFalse(outcomes[0]["allowed"])
            self.assertFalse(outcomes[0]["enforced"])
            self.assertIn("evidence_error", outcomes[0])

    def test_invalid_log_record_fails_closed_instead_of_being_dropped(self):
        plan = {"declared": ["example.org:443"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress.jsonl"
            path.write_text(json.dumps({"host": "example.org", "allowed": True}) + "\n")
            outcomes = _egress_outcomes_from_log(plan, path)
        self.assertFalse(outcomes[0]["allowed"])
        self.assertFalse(outcomes[0]["enforced"])
        self.assertIn("invalid destination", outcomes[0]["evidence_error"])

    def test_incomplete_connection_log_fails_closed(self):
        plan = {"declared": ["example.org:443"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress.jsonl"
            path.write_text(json.dumps({
                "event": "connect_start", "connection_id": "cut-short",
                "host": "example.org", "port": 443, "allowed": True,
            }) + "\n")
            outcomes = _egress_outcomes_from_log(plan, path)
        self.assertFalse(outcomes[0]["allowed"])
        self.assertFalse(outcomes[0]["enforced"])
        self.assertIn("without a terminal", outcomes[0]["evidence_error"])

    def test_non_object_jsonl_record_fails_closed(self):
        plan = {"declared": ["example.org:443"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "egress.jsonl"
            path.write_text(json.dumps([{"event": "connect", "allowed": True}]) + "\n")
            outcomes = _egress_outcomes_from_log(plan, path)
        self.assertFalse(outcomes[0]["allowed"])
        self.assertIn("non-object", outcomes[0]["evidence_error"])

    def test_runner_returns_failure_when_requested_proxy_log_is_missing(self):
        class FakeProcess:
            returncode = 0

            @staticmethod
            def communicate(timeout=None):
                return b"completed", b""

        runner = object.__new__(SandboxRunner)
        runner.profile_id = PROFILE_ID_EGRESS
        runner._require_profile = lambda: None
        runner._popen = lambda *args, **kwargs: FakeProcess()
        runner._wall_seconds = lambda slot: 1
        runner._inspect_kill = lambda slot, proc: None
        result = runner.run(
            {"quotas": {"wall_ms": 1000}},
            json.dumps({"program": "echo", "args": ["ok"], "net": True,
                        "egress": ["example.org:443"]}),
        )
        self.assertEqual(result.exit_code, 125)
        self.assertFalse(result.egress[0]["allowed"])
        self.assertFalse(result.egress[0]["enforced"])
        self.assertIn("evidence_error", result.egress[0])

    def test_runner_returns_failure_when_requested_proxy_log_is_malformed(self):
        class FakeProcess:
            returncode = 0

            @staticmethod
            def communicate(timeout=None):
                return b"completed", b""

        runner = object.__new__(SandboxRunner)
        runner.profile_id = PROFILE_ID_EGRESS
        runner._require_profile = lambda: None

        def fake_popen(_slot, _plan, env=None):
            Path(env["MANDALA_EGRESS_LOG"]).write_text("[]\n", encoding="utf-8")
            return FakeProcess()

        runner._popen = fake_popen
        runner._wall_seconds = lambda slot: 1
        runner._inspect_kill = lambda slot, proc: None
        result = runner.run(
            {"quotas": {"wall_ms": 1000}},
            json.dumps({"program": "echo", "args": ["ok"], "net": True,
                        "egress": ["example.org:443"]}),
        )
        self.assertEqual(result.exit_code, 125)
        self.assertFalse(result.egress[0]["allowed"])
        self.assertIn("non-object", result.egress[0]["evidence_error"])

    def test_runner_profiles_keep_baseline_intent_and_use_l2_proxy_outcomes(self):
        class FakeProcess:
            returncode = 0

            @staticmethod
            def communicate(timeout=None):
                return b"completed", b""

        payload = json.dumps({"program": "echo", "args": ["ok"], "net": True,
                              "egress": ["example.org:443"]})
        records = [
            {"event": "connect_start", "connection_id": "complete",
             "host": "example.org", "port": 443, "allowed": True},
            {"event": "connect_complete", "connection_id": "complete",
             "host": "example.org", "port": 443, "allowed": True,
             "bytes_out": 5, "bytes_in": 7},
        ]
        for runner_class in (SandboxRunner, SliceRunner):
            for profile_id in (PROFILE_ID, PROFILE_ID_EGRESS):
                with self.subTest(runner=runner_class.__name__, profile=profile_id):
                    runner = object.__new__(runner_class)
                    runner.profile_id = profile_id
                    runner._require_profile = lambda: None
                    runner._wall_seconds = lambda slot: 1
                    runner._inspect_kill = lambda slot, proc: None

                    def fake_popen(_slot, _plan, env=None):
                        if profile_id == PROFILE_ID:
                            self.assertIsNone(env)
                        else:
                            Path(env["MANDALA_EGRESS_LOG"]).write_text(
                                "\n".join(json.dumps(record) for record in records) + "\n",
                                encoding="utf-8",
                            )
                        return FakeProcess()

                    runner._popen = fake_popen
                    result = runner.run({"quotas": {"wall_ms": 1000}}, payload)
                    self.assertEqual(result.exit_code, 0)
                    self.assertTrue(result.egress[0]["allowed"])
                    self.assertEqual(result.egress[0]["enforced"], profile_id == PROFILE_ID_EGRESS)
                    if profile_id == PROFILE_ID:
                        self.assertIn("whole network", result.egress[0]["enforcer"])
                        self.assertIsNone(result.egress[0]["bytes"])
                    else:
                        self.assertEqual(result.egress[0]["enforcer"], "unix-proxy-allowlist")
                        self.assertEqual(result.egress[0]["bytes"], 12)

    def test_slice_transient_service_receives_only_l2_proxy_log_override(self):
        plan = parse_payload(json.dumps({"program": "echo", "args": ["ok"],
                                        "net": True, "egress": ["example.org:443"]}))
        for profile_id in (PROFILE_ID, PROFILE_ID_EGRESS):
            with self.subTest(profile=profile_id):
                runner = object.__new__(SliceRunner)
                runner.profile_id = profile_id
                runner.runner_path = "/reviewed/wrapper"
                runner.cpu_percent = None
                env = {"MANDALA_EGRESS_LOG": "/tmp/owned-proxy-log.jsonl",
                       "UNRELATED_PRIVATE_VALUE": "do-not-forward"}
                with patch("gate_lite.orchestrator.subprocess.Popen") as popen:
                    runner._popen({"slot_id": "fixture", "quotas": {}}, plan, env=env)
                argv = popen.call_args.args[0]
                forwarded = [argument for argument in argv if argument.startswith("--setenv=")]
                self.assertEqual(forwarded, (
                    ["--setenv=MANDALA_EGRESS_LOG=/tmp/owned-proxy-log.jsonl"]
                    if profile_id == PROFILE_ID_EGRESS else []
                ))
                if forwarded:
                    self.assertLess(argv.index(forwarded[0]), argv.index("/reviewed/wrapper"))

    def test_orchestrator_holds_slot_when_runner_reports_incomplete_egress(self):
        class IncompleteRunner:
            sandbox_class = "test-egress"

            @staticmethod
            def run(slot, payload_ref, on_spawn=None):
                return ExecResult(
                    exit_code=125,
                    stdout_hash="sha256:" + "0" * 64,
                    resources={},
                    egress=[{
                        "destination": "example.org:443",
                        "bytes": 0,
                        "allowed": False,
                        "enforced": False,
                        "evidence_error": "proxy log missing",
                    }],
                )

        with tempfile.TemporaryDirectory() as tmp:
            agent_did, _ = keys.generate(keys.deterministic_seed("egress-incomplete-agent"))
            gate_did, gate_key = keys.generate(keys.deterministic_seed("egress-incomplete-gate"))
            orch = Orchestrator(tmp, gate_id="egress-incomplete", gate_key=gate_key,
                                gate_did=gate_did, runner=IncompleteRunner())
            orch.add_tenant("tenant", [agent_did])
            issued = orch.pass_("tenant", agent_did)
            response = orch.exec_("tenant", issued["slot_id"], "echo test",
                                  token=issued["token"])
            self.assertEqual(response["exit"], 125)
            self.assertTrue(response["egress_evidence_incomplete"])
            self.assertEqual(
                orch.registry.get_slot(issued["slot_id"])["state"], "receipt_incomplete"
            )
            execution = next(
                receipt for receipt in orch.receipt(orch.task_id_for(issued["slot_id"]))["receipts"]
                if receipt["type"] == "task.execution"
            )
            self.assertFalse(execution["body"]["egress_evidence_complete"])
            self.assertEqual(execution["body"]["exit_code"], 125)


if __name__ == "__main__":
    unittest.main()
