"""Tests for Lakshmi v0 — run: python3 -m unittest -v test_lakshmi"""

import json
import os
import tempfile
import unittest
from unittest import mock

import lakshmi


class TestGini(unittest.TestCase):
    def test_uniform_is_zero(self):
        self.assertAlmostEqual(lakshmi.gini([2.0, 2.0, 2.0, 2.0]), 0.0, places=6)

    def test_unequal_is_positive(self):
        self.assertGreater(lakshmi.gini([1.0, 1.0, 1.0, 9.0]), 0.3)

    def test_empty_and_zero_values(self):
        self.assertEqual(lakshmi.gini([]), 0.0)
        self.assertEqual(lakshmi.gini([0.0, 0.0]), 0.0)

    def test_bounded(self):
        for values in ([1, 2, 3], [0.1, 100.0], [5]):
            score = lakshmi.gini([float(v) for v in values])
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


class TestClamp(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(lakshmi.clamp(-1.0), 0.0)
        self.assertEqual(lakshmi.clamp(2.0), 1.0)
        self.assertEqual(lakshmi.clamp(0.42), 0.42)


class TestBar(unittest.TestCase):
    def test_full_and_empty(self):
        self.assertEqual(lakshmi.bar(1.0, width=10), "█" * 10)
        self.assertEqual(lakshmi.bar(0.0, width=10), "░" * 10)

    def test_midpoint(self):
        self.assertEqual(lakshmi.bar(0.5, width=10), "█" * 5 + "░" * 5)


class TestKarmaDim(unittest.TestCase):
    def make_engine(self, **kwargs):
        defaults = dict(window=10.0, budget_watts=15.0, karma_debt=None)
        defaults.update(kwargs)
        return lakshmi.Lakshmi(**defaults)

    def test_env_override(self):
        engine = self.make_engine(karma_debt=0.25)
        result = engine._karma()
        self.assertEqual(result["score"], 0.25)
        self.assertEqual(result["source"], "env")

    def test_stub_without_endpoint(self):
        engine = self.make_engine(wm_mcp=None)
        result = engine._karma()
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertEqual(result["source"], "stub")

    def test_wm_endpoint_maps_total_debt(self):
        original = lakshmi.call_wm_tool
        lakshmi.call_wm_tool = lambda endpoint, tool, timeout=4.0: {"total_debt": 30.0}
        try:
            engine = self.make_engine(wm_mcp="http://127.0.0.1:18790", karma_max=150.0)
            result = engine._karma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertAlmostEqual(result["score"], 0.8, places=3)
        self.assertEqual(result["source"], "wm")

    def test_wm_failure_falls_back_to_stub(self):
        original = lakshmi.call_wm_tool
        lakshmi.call_wm_tool = lambda endpoint, tool, timeout=4.0: {"_error": "connection refused"}
        try:
            engine = self.make_engine(wm_mcp="http://127.0.0.1:9", karma_max=150.0)
            result = engine._karma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertIn("connection refused", result["note"])


class TestDharmaDim(unittest.TestCase):
    def make_engine(self, **kwargs):
        defaults = dict(window=10.0, budget_watts=15.0, karma_debt=None)
        defaults.update(kwargs)
        return lakshmi.Lakshmi(**defaults)

    def test_stub_without_endpoint(self):
        engine = self.make_engine(dharma_mcp=None)
        result = engine._dharma()
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertEqual(result["source"], "stub")

    def test_first_poll_records_baseline(self):
        original = lakshmi.call_wm_tool
        lakshmi.call_wm_tool = lambda e, t, timeout=4.0: {
            "decisions": {"total": 10, "blocked": 2, "observe": 8}
        }
        try:
            engine = self.make_engine(dharma_mcp="http://x")
            result = engine._dharma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertIn("baseline", result["note"])

    def test_blocked_delta_drops_score(self):
        original = lakshmi.call_wm_tool
        calls = {"n": 0}

        def fake(e, t, timeout=4.0):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"decisions": {"total": 100, "blocked": 10}}
            return {"decisions": {"total": 120, "blocked": 16}}

        lakshmi.call_wm_tool = fake
        try:
            engine = self.make_engine(dharma_mcp="http://x")
            engine._dharma()
            result = engine._dharma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertAlmostEqual(result["score"], 0.0, places=3)
        self.assertEqual(result["source"], "wm")
        self.assertIn("blocked 6/20", result["note"])

    def test_no_decisions_window_is_cold_start(self):
        original = lakshmi.call_wm_tool
        calls = {"n": 0}

        def fake(e, t, timeout=4.0):
            calls["n"] += 1
            return {"decisions": {"total": 100, "blocked": 10}}

        lakshmi.call_wm_tool = fake
        try:
            engine = self.make_engine(dharma_mcp="http://x")
            engine._dharma()
            result = engine._dharma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertIn("no decisions", result["note"])

    def test_missing_decisions_key_falls_back(self):
        original = lakshmi.call_wm_tool
        lakshmi.call_wm_tool = lambda e, t, timeout=4.0: {"status": "success"}
        try:
            engine = self.make_engine(dharma_mcp="http://x")
            result = engine._dharma()
        finally:
            lakshmi.call_wm_tool = original
        self.assertEqual(result["score"], lakshmi.COLD_START)
        self.assertIn("lacks decisions", result["note"])


class TestEnergyScore(unittest.TestCase):
    def make_engine(self):
        return lakshmi.Lakshmi(window=10.0, budget_watts=15.0, karma_debt=None)

    def test_under_budget_is_perfect(self):
        result = self.make_engine()._energy_score(10.0, "rapl", "test")
        self.assertEqual(result["score"], 1.0)

    def test_over_budget_decays(self):
        result = self.make_engine()._energy_score(22.5, "battery", "test")
        self.assertAlmostEqual(result["score"], 0.5, places=3)

    def test_double_budget_floors_at_zero(self):
        result = self.make_engine()._energy_score(30.0, "battery", "test")
        self.assertEqual(result["score"], 0.0)


DIM_SOURCES = {"responsiveness": "psi", "stability": "psi+proc", "energy": "rapl"}


def snapshot(dims_scores, window_seconds=60.0, dim_sources=None):
    sources = dict(DIM_SOURCES)
    sources.update(dim_sources or {})
    dims = {
        key: {"score": dims_scores.get(key, 1.0), "source": sources.get(key, "test"), "note": "n"}
        for key in lakshmi.WEIGHTS
    }
    return {
        "timestamp": "2026-09-13T20:00:00+00:00",
        "window_seconds": window_seconds,
        "harmony_score": 0.9,
        "dims": dims,
        "guna": {"sattvic": 1, "rajasic": 0, "tamasic": 0},
        "top_processes": [{"pid": 1, "comm": "init", "cpu_share": 0.5, "guna": "sattvic"}],
    }


class TestThresholdEvents(unittest.TestCase):
    def make_engine(self):
        return lakshmi.Lakshmi(window=10.0, budget_watts=15.0, karma_debt=None)

    def test_crossing_emits_once_then_silent(self):
        engine = self.make_engine()
        low = snapshot({"responsiveness": 0.2})
        first = engine.threshold_events(low)
        self.assertEqual([e["topic"] for e in first], ["os.telemetry.responsiveness"])
        self.assertEqual(first[0]["threshold"], 0.3)
        self.assertEqual(engine.threshold_events(low), [])
        # Leaving the band re-arms the crossing.
        engine.threshold_events(snapshot({"responsiveness": 0.9}))
        again = engine.threshold_events(low)
        self.assertEqual(len(again), 1)

    def test_neutral_energy_proxy_never_fires(self):
        # RAPL unreadable → neutral 0.5 with source "energy"; that is an
        # unavailable proxy, not an over-budget crossing.
        engine = self.make_engine()
        neutral = snapshot({"energy": 0.5, "responsiveness": 0.1}, dim_sources={"energy": "energy"})
        topics = [e["topic"] for e in engine.threshold_events(neutral)]
        self.assertNotIn("os.telemetry.energy", topics)
        self.assertIn("os.telemetry.responsiveness", topics)

    def test_dharma_blocked_delta_emits_every_window(self):
        engine = self.make_engine()
        engine.dharma_deltas = {"delta_total": 4, "delta_blocked": 2}
        events = engine.threshold_events(snapshot({}))
        topics = [e["topic"] for e in events]
        self.assertIn("os.telemetry.dharma_blocked", topics)
        again = engine.threshold_events(snapshot({}))
        self.assertIn("os.telemetry.dharma_blocked", [e["topic"] for e in again])

    def test_window_record_shape(self):
        engine = self.make_engine()
        record = engine.window_record(snapshot({"stability": 0.5}), [])
        self.assertEqual(record["kind"], "telemetry.window")
        self.assertEqual(record["source"], "laksmi")
        self.assertEqual(record["tags"], lakshmi.EMIT_TAGS)
        self.assertEqual(sorted(record["dims"]), sorted(lakshmi.WEIGHTS))
        self.assertIn("top", record)
        self.assertIn("dharma", record)


class TestMirror(unittest.TestCase):
    def test_latest_and_history_roundtrip_with_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = lakshmi.Mirror(tmp, history_max=3)
            for i in range(5):
                mirror.write(
                    {"harmony_score": i / 10.0},
                    {"kind": "telemetry.window", "ts": f"t{i}"},
                    {"spool_pending": 0},
                )
            with open(os.path.join(tmp, "latest.json"), encoding="utf-8") as fh:
                latest = json.load(fh)
            self.assertEqual(latest["snapshot"]["harmony_score"], 0.4)
            self.assertEqual(latest["meta"]["spool_pending"], 0)
            with open(os.path.join(tmp, "history.jsonl"), encoding="utf-8") as fh:
                lines = [json.loads(ln) for ln in fh if ln.strip()]
            self.assertEqual([r["ts"] for r in lines], ["t2", "t3", "t4"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "latest.json.tmp")))

    def test_observations_ring_roundtrip_and_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            mirror = lakshmi.Mirror(tmp, observations_max=3)
            mirror.write_observations([])  # no records, no file
            self.assertFalse(os.path.exists(os.path.join(tmp, "observations.jsonl")))
            for i in range(5):
                mirror.write_observations(
                    [
                        {
                            "kind": "telemetry.observation",
                            "ts": f"t{i}",
                            "policy_id": "responsiveness.below.v1",
                        }
                    ]
                )
            with open(os.path.join(tmp, "observations.jsonl"), encoding="utf-8") as fh:
                lines = [json.loads(ln) for ln in fh if ln.strip()]
            self.assertEqual([r["ts"] for r in lines], ["t2", "t3", "t4"])
            self.assertFalse(os.path.exists(os.path.join(tmp, "observations.jsonl.tmp")))


class TestWindowSpool(unittest.TestCase):
    def test_roundtrip_and_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "spool.jsonl")
            spool = lakshmi.WindowSpool(path, max_entries=3)
            spool.load()
            for i in range(5):
                spool.append({"kind": "telemetry.window", "n": i})
            spool.save()
            reloaded = lakshmi.WindowSpool(path, max_entries=3)
            self.assertEqual(reloaded.load(), 3)
            self.assertEqual([e["n"] for e in reloaded.entries], [2, 3, 4])

    def test_flush_replays_oldest_first_and_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = lakshmi.WindowSpool(os.path.join(tmp, "spool.jsonl"))
            spool.append({"n": 0})
            spool.append({"n": 1})
            spool.append({"n": 2})
            seen = []
            mode = {"up": False}
            original = lakshmi.emit_window

            def fake(endpoint, galaxy, record, timeout=6.0):
                if not mode["up"]:
                    return {"_error": "down"}
                seen.append(record["n"])
                return {"status": "success"}

            lakshmi.emit_window = fake
            try:
                sent, err = spool.flush("http://x", "telemetry")
                self.assertEqual(sent, 0)
                self.assertEqual(seen, [])
                self.assertIn("down", err)
                self.assertEqual([e["n"] for e in spool.entries], [0, 1, 2])
                mode["up"] = True
                sent, err = spool.flush("http://x", "telemetry")
            finally:
                lakshmi.emit_window = original
            self.assertEqual(sent, 3)
            self.assertEqual(seen, [0, 1, 2], "oldest-first replay")
            self.assertIsNone(err)
            self.assertEqual(spool.entries, [])


    def test_flush_treats_deduplicated_as_delivered(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = lakshmi.WindowSpool(os.path.join(tmp, "spool.jsonl"))
            spool.append({"n": 0})
            original = lakshmi.emit_window
            lakshmi.emit_window = lambda endpoint, galaxy, record, timeout=6.0: {
                "status": "deduplicated",
                "id": "already-there",
            }
            try:
                sent, err = spool.flush("http://x", "telemetry")
            finally:
                lakshmi.emit_window = original
            self.assertEqual(sent, 1)
            self.assertIsNone(err)
            self.assertEqual(spool.entries, [])

    def test_flush_freshness_path_drains_newest_when_head_stuck(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = lakshmi.WindowSpool(os.path.join(tmp, "spool.jsonl"))
            for n in range(3):
                spool.append({"n": n})
            original = lakshmi.emit_window

            def fake(endpoint, galaxy, record, timeout=6.0):
                if record["n"] == 0:
                    return {"_error": "timed out"}
                return {"status": "success"}

            lakshmi.emit_window = fake
            try:
                sent, err = spool.flush("http://x", "telemetry")
            finally:
                lakshmi.emit_window = original
            self.assertEqual(sent, 2, "newest two drain while the head is stuck")
            self.assertEqual([e["n"] for e in spool.entries], [0])
            self.assertIn("timed out", err)


class TestPolicyObservations(unittest.TestCase):
    def make_engine(self):
        return lakshmi.Lakshmi(window=10.0, budget_watts=15.0, karma_debt=None)

    def test_enter_confirm_and_clear_transitions_with_dwell(self):
        engine = self.make_engine()
        low = snapshot({"energy": 0.5, "responsiveness": 0.1})
        obs = engine.policy_observations(low)
        ids = {(o["policy_id"], o["state"]) for o in obs}
        self.assertIn(("energy.over_budget.v1", "observing"), ids)
        self.assertIn(("responsiveness.below.v1", "observing"), ids)
        entering = next(o for o in obs if o["policy_id"] == "energy.over_budget.v1")
        self.assertEqual(entering["enter"], 0.90)
        self.assertEqual(entering["exit"], 0.97)
        self.assertEqual(entering["min_dwell_windows"], 5)
        self.assertEqual(entering["action"], "observe")
        # Dwell 2..4: no records. Dwell 5: confirmed.
        self.assertEqual(engine.policy_observations(low), [])
        engine.policy_observations(low)
        engine.policy_observations(low)
        confirmed = engine.policy_observations(low)
        conf = next(o for o in confirmed if o["policy_id"] == "energy.over_budget.v1")
        self.assertEqual(conf["state"], "confirmed")
        self.assertEqual(conf["dwell_windows"], 5)
        # Recovery above exit emits clear with the full dwell count.
        high = snapshot({"energy": 1.0, "responsiveness": 0.9})
        clears = {o["policy_id"]: o for o in engine.policy_observations(high)}
        self.assertEqual(clears["energy.over_budget.v1"]["state"], "clear")
        self.assertGreaterEqual(clears["energy.over_budget.v1"]["dwell_windows"], 6)

    def test_cooldown_gates_reentry(self):
        engine = self.make_engine()
        low = snapshot({"energy": 0.5})
        engine.policy_observations(low)  # observing
        high = snapshot({"energy": 1.0})
        engine.policy_observations(high)  # clear → cooldown 3
        view = engine.policy_snapshot(low)
        energy = next(v for v in view if v["policy_id"] == "energy.over_budget.v1")
        self.assertEqual(energy["cooldown_left"], 3)
        # In-band windows during cooldown do not start a new observation.
        self.assertEqual(engine.policy_observations(low), [])
        self.assertEqual(engine.policy_observations(low), [])
        self.assertEqual(engine.policy_observations(low), [])
        # Cooldown exhausted: the next in-band window enters again.
        obs = engine.policy_observations(low)
        self.assertEqual(obs[0]["state"], "observing")

    def test_neutral_energy_proxy_never_changes_state(self):
        engine = self.make_engine()
        neutral = snapshot({"energy": 0.5}, dim_sources={"energy": "energy"})
        self.assertEqual(engine.policy_observations(neutral), [])
        view = engine.policy_snapshot(neutral)
        energy = next(v for v in view if v["policy_id"] == "energy.over_budget.v1")
        self.assertFalse(energy["source_available"])
        self.assertIsNone(energy["value"])

    def test_dharma_pulse_enters_and_clears_next_window(self):
        engine = self.make_engine()
        engine.dharma_deltas = {"delta_total": 3, "delta_blocked": 2}
        obs = engine.policy_observations(snapshot({}))
        self.assertEqual(obs[0]["policy_id"], "dharma.blocked.v1")
        self.assertEqual(obs[0]["state"], "observing")
        self.assertEqual(obs[0]["exit"], 0.0)
        engine.dharma_deltas = {"delta_total": 1, "delta_blocked": 0}
        obs2 = engine.policy_observations(snapshot({}))
        self.assertEqual(obs2[0]["state"], "clear")

    def test_policy_snapshot_shape_matches_table(self):
        engine = self.make_engine()
        view = engine.policy_snapshot(snapshot({"stability": 0.5}))
        self.assertEqual(len(view), len(lakshmi.Lakshmi.POLICIES))
        keys = set(view[0])
        self.assertLessEqual(
            {
                "policy_id", "state", "enter", "exit", "value", "source_available",
                "min_dwell_windows", "cooldown_windows", "cooldown_left",
            },
            keys,
        )

    def test_bridge_policies_enter_and_clear(self):
        engine = self.make_engine()
        engine.bridge_inputs = {
            "sandbox_unconfined": 2,
            "sandbox_degraded": 1,
            "tetragon_shadow": 1,
            "sandbox_subjects": ["tool:oss.bounty.scan"],
            "tetragon_subjects": ["proc:cat:cat"],
            "bus_ok": True,
            "tetragon_ok": True,
        }
        obs = engine.policy_observations(snapshot({}))
        states = {(o["policy_id"], o["state"]) for o in obs}
        self.assertIn(("spawn.undeclared.v1", "observing"), states)
        self.assertIn(("sandbox.degraded.v1", "observing"), states)
        self.assertIn(("shadow.access.v1", "observing"), states)
        spawn = next(o for o in obs if o["policy_id"] == "spawn.undeclared.v1")
        self.assertEqual(spawn["value"], 2.0)
        self.assertEqual(spawn["action"], "observe")
        self.assertEqual(spawn["subject"], "tool:oss.bounty.scan")
        shadow = next(o for o in obs if o["policy_id"] == "shadow.access.v1")
        self.assertEqual(shadow["subject"], "proc:cat:cat")

        engine.bridge_inputs = {
            "sandbox_unconfined": 0,
            "sandbox_degraded": 0,
            "tetragon_shadow": 0,
            "bus_ok": True,
            "tetragon_ok": True,
        }
        clears = {o["policy_id"]: o for o in engine.policy_observations(snapshot({}))}
        self.assertEqual(clears["spawn.undeclared.v1"]["state"], "clear")
        self.assertEqual(clears["sandbox.degraded.v1"]["state"], "clear")
        self.assertEqual(clears["shadow.access.v1"]["state"], "clear")

    def test_bridge_feed_outage_holds_state(self):
        engine = self.make_engine()
        engine.bridge_inputs = {"sandbox_unconfined": 3, "bus_ok": True, "tetragon_ok": False}
        engine.policy_observations(snapshot({}))
        # WM unreachable: no clear emitted, observing state is held.
        engine.bridge_inputs = {"bus_ok": False, "tetragon_ok": False}
        self.assertEqual(engine.policy_observations(snapshot({})), [])
        view = engine.policy_snapshot(snapshot({}))
        spawn = next(v for v in view if v["policy_id"] == "spawn.undeclared.v1")
        self.assertEqual(spawn["state"], "observing")
        self.assertFalse(spawn["source_available"])

    def test_window_record_carries_bridge_counts(self):
        engine = self.make_engine()
        engine.bridge_inputs = {"sandbox_unconfined": 1, "sandbox_degraded": 0, "tetragon_shadow": 2}
        record = engine.window_record(snapshot({}), [])
        self.assertEqual(record["bridge"]["tetragon_shadow"], 2)
        self.assertNotIn("bus_ok", record["bridge"])


class TestFetchBridgeInputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.feed = os.path.join(self.tmp.name, "sent.jsonl")

    @staticmethod
    def observation(ts, value=None, metric="tetragon.shadow_access"):
        record = {
            "kind": "telemetry.observation",
            "metric": metric,
            "ts": ts,
            "policy_id": "shadow.access.v1",
        }
        if value is not None:
            record["value"] = value
        return record

    def write_feed(self, records):
        with open(self.feed, "w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")

    def fetch(self, bus, search, since="2026-09-14T22:00:00Z", feed=""):
        replies = [bus, search]
        with mock.patch.object(
            lakshmi, "call_wm_tool", side_effect=lambda *a, **k: replies.pop(0)
        ):
            return lakshmi.fetch_bridge_inputs("http://x", since, feed_path=feed)

    def test_maps_bus_and_tetragon_since_cursor(self):
        bus_reply = {
            "events": [
                {
                    "event_type": "sandbox_observation",
                    "timestamp": "2026-09-14T22:00:05Z",
                    "payload": {"kind": "unconfined_spawn", "tool": "x"},
                },
                {
                    "event_type": "sandbox_observation",
                    "timestamp": "2026-09-14T21:59:00Z",
                    "payload": {"kind": "degraded"},
                },
                {"event_type": "os_telemetry_threshold", "timestamp": "2026-09-14T22:00:06Z"},
            ]
        }
        search_reply = {
            "results": [
                {
                    "content": json.dumps(
                        dict(
                            self.observation("2026-09-14T22:00:07Z"),
                            subject="proc:cat:cat",
                        )
                    )
                },
                {"content": json.dumps(self.observation("2026-09-14T21:00:00Z"))},
            ]
        }
        out = self.fetch(bus_reply, search_reply)
        self.assertTrue(out["bus_ok"])
        self.assertTrue(out["tetragon_ok"])
        self.assertEqual(out["sandbox_unconfined"], 1)
        self.assertEqual(out["sandbox_degraded"], 0)
        self.assertEqual(out["tetragon_shadow"], 1)
        self.assertEqual(out["sandbox_subjects"], ["x"])
        self.assertEqual(out["tetragon_subjects"], ["proc:cat:cat"])

    def test_unreachable_feeds_report_not_ok(self):
        with mock.patch.object(lakshmi, "call_wm_tool", return_value={"_error": "down"}):
            out = lakshmi.fetch_bridge_inputs(
                "http://x", "2026-09-14T22:00:00Z", feed_path=""
            )
        self.assertFalse(out["bus_ok"])
        self.assertFalse(out["tetragon_ok"])
        self.assertEqual(out["sandbox_unconfined"], 0)

    def test_feed_merges_with_store_and_sums_values(self):
        store_record = self.observation("2026-09-14T22:00:07Z", value=2)
        newer = self.observation("2026-09-14T22:00:20Z", value=3)
        self.write_feed([store_record, newer])
        search_reply = {"results": [{"content": json.dumps(store_record)}]}
        out = self.fetch({"events": []}, search_reply, feed=self.feed)
        self.assertTrue(out["tetragon_ok"])
        self.assertEqual(out["tetragon_shadow"], 5)  # deduped 2 + 3

    def test_feed_supplies_records_the_store_missed(self):
        self.write_feed([self.observation("2026-09-14T22:00:30Z")])
        out = self.fetch({"events": []}, {"results": []}, feed=self.feed)
        self.assertTrue(out["tetragon_ok"])
        self.assertEqual(out["tetragon_shadow"], 1)

    def test_store_down_reports_feed_counts_but_marks_feed_down(self):
        self.write_feed([self.observation("2026-09-14T22:00:30Z", value=4)])
        with mock.patch.object(lakshmi, "call_wm_tool", return_value={"_error": "down"}):
            out = lakshmi.fetch_bridge_inputs(
                "http://x", "2026-09-14T22:00:00Z", feed_path=self.feed
            )
        self.assertFalse(out["tetragon_ok"])
        self.assertEqual(out["tetragon_shadow"], 4)

    def test_feed_respects_since_and_metric(self):
        self.write_feed(
            [
                self.observation("2026-09-14T21:00:00Z"),
                self.observation("2026-09-14T22:00:30Z"),
                self.observation("2026-09-14T22:00:31Z", metric="sandbox.unconfined"),
            ]
        )
        out = self.fetch({"events": []}, {"results": []}, feed=self.feed)
        self.assertEqual(out["tetragon_shadow"], 1)

    def test_missing_feed_is_safe(self):
        out = self.fetch({"events": []}, {"results": []}, feed=self.feed)
        self.assertEqual(out["tetragon_shadow"], 0)


if __name__ == "__main__":
    unittest.main()
