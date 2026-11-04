"""Tests for the Y1.0 actuator router — run: python3 -m unittest -v test_actuator"""

import os
import unittest
from unittest import mock

import actuator


def observation(**overrides):
    record = {
        "kind": "telemetry.observation",
        "ts": "2026-09-15T16:00:00+00:00",
        "policy_id": "energy.over_budget.v1",
        "version": 1,
        "metric": "energy",
        "direction": "below",
        "value": 0.5,
        "enter": 0.9,
        "exit": 0.97,
        "state": "confirmed",
        "action": "observe",
        "evidence": {"window": "2026-09-15T16:00:00+00:00"},
    }
    record.update(overrides)
    return record


class TestKillSwitch(unittest.TestCase):
    def test_env_disarms_only_on_zero(self):
        with mock.patch.dict(os.environ, {"WM_ACTUATION": "0"}):
            self.assertFalse(actuator.armed_from_env())
        with mock.patch.dict(os.environ, {"WM_ACTUATION": "1"}):
            self.assertTrue(actuator.armed_from_env())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(actuator.armed_from_env())

    def test_router_reads_env_live(self):
        with mock.patch.dict(os.environ, {"WM_ACTUATION": "1"}):
            router = actuator.Router()
            self.assertTrue(router.armed)
            os.environ["WM_ACTUATION"] = "0"
            self.assertFalse(router.armed)

    def test_explicit_override_wins(self):
        with mock.patch.dict(os.environ, {"WM_ACTUATION": "1"}):
            self.assertFalse(actuator.Router(armed=False).armed)


class TestSubjectResolution(unittest.TestCase):
    def test_dim_subject(self):
        self.assertEqual(actuator.resolve_subject(observation()), "dim:energy")

    def test_captured_subject_wins(self):
        record = observation(subject="proc:cat:cat")
        self.assertEqual(actuator.resolve_subject(record), "proc:cat:cat")

    def test_bridge_subjects_not_captured_yet(self):
        record = observation(policy_id="shadow.access.v1", metric="tetragon_shadow")
        self.assertIsNone(actuator.resolve_subject(record))

    def test_bridge_with_captured_subject(self):
        record = observation(
            policy_id="shadow.access.v1",
            metric="tetragon_shadow",
            subject="proc:cat:cat",
        )
        self.assertEqual(actuator.resolve_subject(record), "proc:cat:cat")

    def test_missing_metric_is_none(self):
        self.assertIsNone(actuator.resolve_subject(observation(metric=None)))


class TestRouter(unittest.TestCase):
    def test_observing_and_clear_never_actuate(self):
        router = actuator.Router()
        records, notifications = router.route(
            [
                observation(state="observing"),
                observation(state="clear", ts="2026-09-15T16:01:00+00:00"),
            ]
        )
        self.assertEqual(notifications, [])
        for record in records:
            self.assertEqual(record["step"], 0)
            self.assertEqual(record["actuator"], "none")

    def test_confirmed_notifies_when_armed(self):
        router = actuator.Router()
        records, notifications = router.route([observation()])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(records[0]["step"], 1)
        self.assertEqual(records[0]["actuator"], "notify")
        self.assertEqual(records[0]["subject"], "dim:energy")
        self.assertIsNone(records[0]["undo_token"])
        self.assertIsNone(records[0]["expires_at"])
        self.assertTrue(records[0]["action"], "observe")

    def test_disarmed_keeps_step_zero(self):
        router = actuator.Router(armed=False)
        records, notifications = router.route([observation()])
        self.assertEqual(notifications, [])
        self.assertEqual(records[0]["step"], 0)
        self.assertEqual(records[0]["actuator"], "none")

    def test_duplicate_suppression(self):
        router = actuator.Router()
        _, first = router.route([observation()])
        _, second = router.route([observation()])
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_route_does_not_mutate_input(self):
        record = observation()
        actuator.Router().route([record])
        self.assertNotIn("step", record)

    def test_policy_max_step_zero_blocks_notify(self):
        with mock.patch.dict(actuator.POLICY_MAX_STEP, {"energy.over_budget.v1": 0}):
            records, notifications = actuator.Router().route([observation()])
        self.assertEqual(notifications, [])
        self.assertEqual(records[0]["step"], 0)

    def test_applied_ring_is_bounded(self):
        router = actuator.Router()
        for i in range(actuator.APPLIED_MAX + 50):
            router.route(
                [observation(ts=f"2026-09-15T16:{i // 60:02d}:{i % 60:02d}+00:00")]
            )
        self.assertLessEqual(router.applied_count(), actuator.APPLIED_MAX)

    def test_annotate_policies_discloses_arming(self):
        rows = actuator.annotate_policies(
            [{"policy_id": "energy.over_budget.v1"}], actuator.Router(armed=False)
        )
        self.assertFalse(rows[0]["actuator_armed"])
        self.assertEqual(rows[0]["actuator_max_step"], 1)


class TestNotifyPayload(unittest.TestCase):
    def test_below_direction_reason(self):
        record = observation(subject="dim:energy", step=1, actuator="notify")
        payload = actuator.notify_payload(record)
        self.assertIn("fell below its sufficiency floor", payload["reason"])
        self.assertEqual(payload["policy_id"], "energy.over_budget.v1")
        self.assertEqual(payload["step"], 1)

    def test_above_direction_reason(self):
        record = observation(direction="above", metric="dharma_blocked_delta")
        payload = actuator.notify_payload(record)
        self.assertIn("crossed its threshold", payload["reason"])


if __name__ == "__main__":
    unittest.main()
