"""Tests for dashboard.py — run: python3 -m unittest test_dashboard"""

import json
import os
import tempfile
import unittest

import dashboard


def window(ts, harmony=0.5):
    return {"kind": "telemetry.window", "ts": ts, "harmony_score": harmony,
            "dims": {}, "tags": ["telemetry"]}


class TestHistory(unittest.TestCase):
    def test_mirror_filter_by_hours_and_limit(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for minutes in (1, 120, 600):
                    fh.write(json.dumps(window((now - timedelta(minutes=minutes)).isoformat())) + "\n")
            rows = dashboard.load_mirror_history(tmp, hours=6, limit=10)
            self.assertEqual(len(rows), 2, "600-minute window falls outside 6h")
            rows = dashboard.load_mirror_history(tmp, hours=6, limit=1)
            self.assertEqual(len(rows), 1, "limit trims from the end")

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(dashboard.load_mirror_history(tmp, hours=1, limit=5), [])

    def test_merge_history_dedupes_by_ts(self):
        a = [window("2026-09-13T10:00:00+00:00", 0.4)]
        b = [window("2026-09-13T10:00:00+00:00", 0.9), window("2026-09-13T10:01:00+00:00", 0.5)]
        merged = dashboard.merge_history(a, b, 10)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["harmony_score"], 0.9, "remote wins the duplicate ts")
        self.assertEqual(merged[-1]["ts"], "2026-09-13T10:01:00+00:00")

    def test_parse_ts_accepts_naive_and_z(self):
        self.assertIsNotNone(dashboard.parse_ts("2026-09-13T10:00:00"))
        self.assertIsNotNone(dashboard.parse_ts("2026-09-13T10:00:00+00:00"))
        self.assertIsNone(dashboard.parse_ts("not-a-time"))


class TestGalaxy(unittest.TestCase):
    def test_unreachable_wm_returns_error_not_crash(self):
        rows, error = dashboard.galaxy_history("http://127.0.0.1:9", "telemetry", 5, 0.4)
        self.assertEqual(rows, [])
        self.assertIsInstance(error, str)
        self.assertTrue(error)


class TestRollups(unittest.TestCase):
    def test_rollup_to_point_extracts_avgs(self):
        record = {
            "kind": "telemetry.rollup",
            "period_start": "2026-09-13T22:00:00+00:00",
            "samples": 28,
            "dims": {"fairness": {"avg": 0.15, "min": 0.1, "max": 0.2},
                     "energy": {"avg": 0.3}},
            "harmony": {"avg": 0.6, "min": 0.5, "max": 0.7},
            "events": {"count": 2, "topics": {}},
        }
        point = dashboard.rollup_to_point(record)
        self.assertEqual(point["ts"], "2026-09-13T22:00:00+00:00")
        self.assertEqual(point["harmony_score"], 0.6)
        self.assertEqual(point["dims"]["fairness"], 0.15)
        self.assertEqual(point["samples"], 28)
        self.assertEqual(point["events"], [])

    def test_rollup_to_point_rejects_windows_and_empty(self):
        self.assertIsNone(dashboard.rollup_to_point({"kind": "telemetry.window"}))
        self.assertIsNone(dashboard.rollup_to_point({"kind": "telemetry.rollup"}))
        self.assertIsNone(dashboard.rollup_to_point("nope"))

    def test_galaxy_rollups_unreachable_is_soft(self):
        rows, error = dashboard.galaxy_rollups("http://127.0.0.1:9", "telemetry", 168, 10, 0.4)
        self.assertEqual(rows, [])
        self.assertIsInstance(error, str)
        self.assertTrue(error)

    def test_galaxy_observations_unreachable_is_soft(self):
        rows, error = dashboard.galaxy_observations("http://127.0.0.1:9", "telemetry", 50, 0.4)
        self.assertEqual(rows, [])
        self.assertIsInstance(error, str)
        self.assertTrue(error)


class TestObservationsMirror(unittest.TestCase):
    def observation(self, ts, pid="responsiveness.below.v1", state="observing"):
        return {"kind": "telemetry.observation", "ts": ts, "policy_id": pid,
                "state": state, "value": 0.1}

    def test_load_mirror_observations_filters_and_bounds(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "observations.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(self.observation("t0")) + "\n")
                fh.write("not-json\n")
                fh.write(json.dumps(window("t1")) + "\n")  # windows are not observations
                fh.write(json.dumps(self.observation("t2")) + "\n")
            rows = dashboard.load_mirror_observations(tmp, limit=10)
            self.assertEqual([r["ts"] for r in rows], ["t0", "t2"])
            self.assertEqual(len(dashboard.load_mirror_observations(tmp, limit=1)), 1)

    def test_missing_observations_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(dashboard.load_mirror_observations(tmp, 5), [])

    def test_merge_observations_dedupes_and_mirror_wins(self):
        ts = "2026-09-14T22:00:00Z"
        mirror = [self.observation(ts, state="clear")]
        remote = [
            self.observation(ts, state="observing"),
            self.observation(ts, pid="stability.below.v1", state="observing"),
            self.observation("2026-09-14T21:00:00Z", state="observing"),
        ]
        merged = dashboard.merge_observations(mirror, remote, 10)
        self.assertEqual(len(merged), 3, "same ts with different policy_id is kept")
        by_pid = {r["policy_id"]: r for r in merged if r["ts"] == ts}
        self.assertEqual(by_pid["responsiveness.below.v1"]["state"], "clear")
        self.assertEqual(merged[0]["ts"], "2026-09-14T21:00:00Z", "oldest first")
        self.assertEqual(len(dashboard.merge_observations(mirror, remote, 2)), 2)

    def test_merge_observations_skips_keyless_records(self):
        merged = dashboard.merge_observations(
            [{"kind": "telemetry.observation", "ts": "t", "policy_id": ""}], [], 5
        )
        self.assertEqual(merged, [])


class TestLiveAnnotations(unittest.TestCase):
    def test_freshness_age_and_stale(self):
        out = dashboard.live_freshness({"written_at": 1000.0}, now=1030.0)
        self.assertEqual(out["age_seconds"], 30.0)
        self.assertFalse(out["stale"])
        out = dashboard.live_freshness({"written_at": 1000.0}, now=1200.0)
        self.assertTrue(out["stale"])

    def test_freshness_missing_written_at_is_stale_with_no_age(self):
        out = dashboard.live_freshness({"snapshot": {}}, now=100.0)
        self.assertIsNone(out["age_seconds"])
        self.assertTrue(out["stale"])

    def test_annotate_live_attaches_explain_and_zone(self):
        policy = {
            "policy_id": "responsiveness.below.v1",
            "metric": "responsiveness",
            "direction": "below",
            "enter": 0.3,
            "exit": 0.5,
            "version": 1,
            "min_dwell_windows": 5,
            "cooldown_windows": 3,
            "value": 0.2,
            "source_available": True,
        }
        payload = {"written_at": 1000.0, "meta": {"policies": [policy]}}
        out = dashboard.annotate_live(payload, now=1010.0)
        self.assertEqual(out["age_seconds"], 10.0)
        self.assertFalse(out["stale"])
        self.assertEqual(policy["samma_zone"], "enter")
        self.assertIn("falls below 0.3", policy["explain"])

    def test_annotate_live_tolerates_missing_meta(self):
        out = dashboard.annotate_live({"written_at": 5.0}, now=6.0)
        self.assertEqual(out["age_seconds"], 1.0)


class TestExplainPolicy(unittest.TestCase):
    def test_below_sentence(self):
        text = dashboard.explain_policy({
            "metric": "responsiveness", "direction": "below", "enter": 0.3,
            "exit": 0.5, "version": 1, "min_dwell_windows": 5, "cooldown_windows": 3,
        })
        self.assertIn("falls below 0.3", text)
        self.assertIn("recovers above 0.5", text)
        self.assertIn("confirms after 5 consecutive windows", text)
        self.assertIn("3-window cooldown before re-entry", text)
        self.assertTrue(text.endswith("observe only (v1)"))

    def test_above_sentence_without_dwell(self):
        text = dashboard.explain_policy({
            "metric": "sandbox_unconfined", "direction": "above", "enter": 0.5,
            "exit": 0.0, "version": 1, "min_dwell_windows": 1, "cooldown_windows": 0,
        })
        self.assertIn("rises above 0.5", text)
        self.assertIn("returns to 0 or less", text)
        self.assertNotIn("confirms after", text)
        self.assertNotIn("cooldown", text)

    def test_unknown_direction_degrades_to_watch_sentence(self):
        text = dashboard.explain_policy({"metric": "x", "enter": 0.1, "exit": 0.2})
        self.assertIn("watches x", text)


class TestSammaZone(unittest.TestCase):
    def test_below_policy_zones(self):
        base = {"direction": "below", "enter": 0.3, "exit": 0.5}
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.2}), "enter")
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.4}), "band")
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.6}), "clear")

    def test_above_policy_zones(self):
        base = {"direction": "above", "enter": 0.5, "exit": 0.0}
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.7}), "enter")
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.25}), "band")
        self.assertEqual(dashboard.samma_zone({**base, "value": 0.0}), "clear")

    def test_unknown_when_value_or_bounds_missing(self):
        self.assertEqual(dashboard.samma_zone({"direction": "below", "enter": 0.3,
                                               "exit": 0.5, "value": None}), "unknown")
        self.assertEqual(dashboard.samma_zone({"direction": "sideways", "enter": 0.3,
                                               "exit": 0.5, "value": 0.4}), "unknown")


class TestEventsFeed(unittest.TestCase):
    def threshold(self, topic):
        return {"event_type": "os_telemetry_threshold", "source": "laksmi",
                "timestamp": "2026-09-14T22:00:00Z", "payload": {"topic": topic}}

    def test_error_is_disclosed_not_an_empty_feed(self):
        out = dashboard.events_feed({"_error": "connection refused"}, 50)
        self.assertFalse(out["feed_ok"])
        self.assertIn("connection refused", out["error"])
        self.assertEqual(out["events"], [])

    def test_empty_feed_is_ok(self):
        out = dashboard.events_feed({"events": []}, 50)
        self.assertTrue(out["feed_ok"])
        self.assertIsNone(out["error"])
        self.assertEqual(out["count"], 0)

    def test_filters_event_types_and_honours_limit(self):
        reply = {"events": [self.threshold("a"), {"event_type": "other"},
                            self.threshold("b")]}
        out = dashboard.events_feed(reply, 1)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["events"][0]["payload"]["topic"], "a")


class TestBridgeSnapshot(unittest.TestCase):
    def test_counts_from_mirror_feeds_down_when_wm_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "latest.json"), "w", encoding="utf-8") as fh:
                json.dump({"written_at": 1.0, "record": {
                    "kind": "telemetry.window", "ts": "2026-09-14T22:00:00Z",
                    "bridge": {"sandbox_unconfined": 2, "sandbox_degraded": 0,
                               "tetragon_shadow": 1}}}, fh)
            out = dashboard.bridge_snapshot(tmp, "http://127.0.0.1:9", "telemetry", 0.3)
            self.assertEqual(out["counts"]["sandbox_unconfined"], 2)
            self.assertEqual(out["counts_ts"], "2026-09-14T22:00:00Z")
            self.assertFalse(out["feeds"]["bus_ok"])
            self.assertFalse(out["feeds"]["tetragon_ok"])
            self.assertEqual(out["recent"], [])
            self.assertTrue(out["errors"]["bus"])

    def test_no_mirror_keeps_counts_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = dashboard.bridge_snapshot(tmp, "http://127.0.0.1:9", "telemetry", 0.3)
            self.assertIsNone(out["counts"]["tetragon_shadow"])
            self.assertIsNone(out["counts_ts"])


class TestRoutes(unittest.TestCase):
    def test_mandala_page_is_served(self):
        import http.server
        import threading
        import urllib.request

        with tempfile.TemporaryDirectory() as tmp:
            handler = dashboard.build_api(
                tmp, "http://127.0.0.1:9", "http://127.0.0.1:9", "telemetry", 0.2
            )
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                body = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/mandala", timeout=3
                ).read().decode()
                self.assertIn("MANDALA", body)
                self.assertIn("/api/live", body)
            finally:
                server.shutdown()
                server.server_close()

    def test_unknown_route_is_404(self):
        import http.server
        import threading
        import urllib.error
        import urllib.request

        with tempfile.TemporaryDirectory() as tmp:
            handler = dashboard.build_api(
                tmp, "http://127.0.0.1:9", "http://127.0.0.1:9", "telemetry", 0.2
            )
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=3)
                self.assertEqual(ctx.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()


class TestRetentionSummary(unittest.TestCase):
    def test_success_shapes_prune_due(self):
        reply = {
            "status": "success",
            "prune_due": True,
            "basis": "record created_at (identical to telemetry.prune)",
            "inventory": {
                "windows": {
                    "count": 10,
                    "eligible": 2,
                    "oldest_created": "2026-09-01T00:00:00Z",
                    "next_eligible_since": "2026-09-20T00:00:00Z",
                },
                "rollups": {"count": 3, "eligible": 1},
                "observations": {"count": 7, "managed": False},
            },
        }
        summary = dashboard.retention_summary(reply)
        self.assertTrue(summary["available"])
        self.assertTrue(summary["prune_due"])
        self.assertEqual(summary["eligible"], 3)
        self.assertEqual(summary["windows"]["count"], 10)
        self.assertEqual(summary["observations"]["count"], 7)
        self.assertFalse(summary["observations"]["managed"])
        self.assertEqual(summary["next_eligible_since"], "2026-09-20T00:00:00Z")

    def test_pre_915_replies_are_unavailable(self):
        summary = dashboard.retention_summary(
            {"_error": "Unknown tool: 'telemetry.retention'"}
        )
        self.assertFalse(summary["available"])
        self.assertIn("Unknown tool", summary["error"])


if __name__ == "__main__":
    unittest.main()
