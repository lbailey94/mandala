"""Tests for yama-collector — run: python3 -m unittest -v test_yama_collector"""

import importlib.util
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "yama_collector", os.path.join(os.path.dirname(__file__), "yama-collector.py")
)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def make_args(**overrides):
    args = SimpleNamespace(
        endpoint="http://127.0.0.1:9",
        spool=os.path.join(tempfile.gettempdir(), "yama-test-spool.jsonl"),
        timeout=1.0,
        no_spool=True,
        sent_log=os.path.join(tempfile.gettempdir(), "yama-test-sent.jsonl"),
        no_sent_log=False,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class TestSendRecords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sent = os.path.join(self.tmp.name, "sent.jsonl")

    def test_sent_records_are_logged_failed_are_not(self):
        args = make_args(sent_log=self.sent)

        def reply(_endpoint, record, _timeout):
            return {"status": "success"} if record["ts"] == "t1" else {"_error": "down"}

        with mock.patch.object(collector, "emit_observation", side_effect=reply):
            replayed, sent, failed = collector.send_records(
                args, [{"ts": "t1"}, {"ts": "t2"}]
            )
        self.assertEqual((replayed, sent), (0, 1))
        self.assertEqual([r["ts"] for r in failed], ["t2"])
        self.assertEqual([r["ts"] for r in read_jsonl(self.sent)], ["t1"])

    def test_failed_send_writes_no_feed(self):
        args = make_args(sent_log=self.sent)
        with mock.patch.object(
            collector, "emit_observation", return_value={"_error": "down"}
        ):
            collector.send_records(args, [{"ts": "t1"}])
        self.assertFalse(os.path.exists(self.sent))

    def test_no_sent_log_disables_feed(self):
        args = make_args(sent_log=self.sent, no_sent_log=True)
        with mock.patch.object(
            collector, "emit_observation", return_value={"status": "success"}
        ):
            collector.send_records(args, [{"ts": "t1"}])
        self.assertFalse(os.path.exists(self.sent))

    def test_replayed_records_are_logged(self):
        spool = os.path.join(self.tmp.name, "spool.jsonl")
        collector.spool_write(spool, [{"ts": "old"}])
        args = make_args(spool=spool, no_spool=False, sent_log=self.sent)
        with mock.patch.object(
            collector, "emit_observation", return_value={"status": "success"}
        ):
            replayed, sent, failed = collector.send_records(args, [])
        self.assertEqual((replayed, sent, failed), (1, 0, []))
        self.assertEqual([r["ts"] for r in read_jsonl(self.sent)], ["old"])

    def test_sent_log_is_bounded(self):
        original = collector.SENT_LOG_MAX
        collector.SENT_LOG_MAX = 3
        self.addCleanup(setattr, collector, "SENT_LOG_MAX", original)
        collector.sent_log_write(self.sent, [{"ts": f"t{i}"} for i in range(5)])
        self.assertEqual(
            [r["ts"] for r in read_jsonl(self.sent)], ["t2", "t3", "t4"]
        )


class TestSubjects(unittest.TestCase):
    @staticmethod
    def match_event(**identity):
        process = {"pid": 1430, **identity}
        return {
            "process_kprobe": {
                "function_name": "security_file_open",
                "args": [{"file_arg": {"path": "/etc/shadow"}}],
                "process": process,
            }
        }

    def test_classify_carries_proc_subject(self):
        hit = collector.classify(
            self.match_event(comm="cat", binary="/usr/bin/cat")
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit["subject"], "proc:cat:cat")

    def test_subject_never_pid_only(self):
        hit = collector.classify(self.match_event())
        self.assertIsNotNone(hit)
        self.assertIsNone(hit["subject"])
        self.assertIn("pid=1430", hit["evidence"])

    def test_build_records_dedupes_and_carries_subjects(self):
        hits = [
            {"policy_id": "shadow.access.v1", "metric": "tetragon.shadow_access",
             "evidence": "comm=a", "subject": "proc:a:a"},
            {"policy_id": "shadow.access.v1", "metric": "tetragon.shadow_access",
             "evidence": "comm=a", "subject": "proc:a:a"},
            {"policy_id": "shadow.access.v1", "metric": "tetragon.shadow_access",
             "evidence": "comm=b", "subject": "proc:b:b"},
        ]
        records = collector.build_records(hits)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["value"], 3)
        self.assertEqual(record["subject"], "proc:a:a")
        self.assertEqual(record["subjects"], ["proc:a:a", "proc:b:b"])


if __name__ == "__main__":
    unittest.main()
