#!/usr/bin/env python3
"""Lakshmi dashboard — stdlib reader for the local mirror + WM telemetry galaxy.

Serves a static page and a tiny JSON API on 127.0.0.1 (default :3109):

    GET /             the dashboard page
    GET /mandala      the living-Mandala view (P0 encoding harness)
    GET /api/live     latest mirror snapshot + sampler meta, annotated with
                      freshness (age/stale) and per-policy explain/band zones
    GET /api/history  mirror windows (hours/limit), enriched from the galaxy
                      when WM is reachable (deduped by ts)
    GET /api/observations  mirror observation ring merged with the galaxy
                      (deduped by ts+policy_id; newest guaranteed)
    GET /api/events   os_telemetry_threshold events via WM bus.recent
                      (explicit feed_ok so empty is not confused with down)
    GET /api/bridge   Yama bridge strip: last window counts, feed
                      reachability, newest sandbox/shadow records
    GET /api/healthz  this server + WM link state

No dependencies and no writes: the sampler owns the mirror files, WM owns the
galaxy. If WM is down the page keeps working from the mirror (fail-soft).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE_DEFAULT = os.path.expanduser("~/.local/share/lakshmi")
PAGE_NAME = "dashboard.html"
LIVE_STALE_SECONDS = 90.0  # mirror older than this is disclosed as stalled
BRIDGE_METRICS = ("sandbox_unconfined", "sandbox_degraded", "tetragon_shadow")


def wm_tool(base: str, tool: str, arguments: dict, timeout: float) -> dict:
    """Call one WM MCP tool; errors come back as ``{"_error": ...}``."""
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
    ).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/mcp",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            outer = json.loads(response.read().decode())
        if "error" in outer:
            message = (outer.get("error") or {}).get("message", "json-rpc error")
            return {"_error": message}
        return json.loads(outer["result"]["content"][0]["text"])
    except Exception as exc:  # noqa: BLE001 — disclose, never crash the API
        return {"_error": str(exc)}


def wm_alive(base: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/healthz", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def parse_ts(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def load_mirror_history(state_dir: str, hours: float, limit: int) -> list[dict]:
    path = os.path.join(state_dir, "history.jsonl")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                stamp = parse_ts(record.get("ts", ""))
                if stamp is None or stamp >= cutoff:
                    rows.append(record)
    except OSError:
        return []
    rows = rows[-limit:]
    return rows


def galaxy_history(base: str, galaxy: str, limit: int, timeout: float) -> tuple[list[dict], str | None]:
    reply = wm_tool(
        base,
        "memory.search",
        {"query": "telemetry.window", "galaxy": galaxy, "limit": max(limit, 10)},
        timeout,
    )
    if not isinstance(reply, dict) or "_error" in reply or reply.get("status") != "success":
        reason = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        return [], str(reason)
    rows: list[dict] = []
    for hit in reply.get("results", []):
        content = hit.get("content") if isinstance(hit, dict) else None
        if not isinstance(content, str):
            continue
        try:
            record = json.loads(content)
        except ValueError:
            continue
        if (
            isinstance(record, dict)
            and record.get("kind") == "telemetry.window"
            and isinstance(record.get("dim_notes"), dict)
        ):
            rows.append(record)
    return rows, None


def merge_history(local: list[dict], remote: list[dict], limit: int) -> list[dict]:
    by_ts: dict[str, dict] = {}
    for record in local + remote:
        ts = record.get("ts")
        if isinstance(ts, str) and ts:
            by_ts[ts] = record
    rows = sorted(by_ts.values(), key=lambda r: str(r.get("ts", "")))
    return rows[-limit:]


def load_mirror_observations(state_dir: str, limit: int) -> list[dict]:
    """Read the sampler's bounded observation ring (oldest first)."""
    path = os.path.join(state_dir, "observations.jsonl")
    rows: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if (
                    isinstance(record, dict)
                    and record.get("kind") == "telemetry.observation"
                ):
                    rows.append(record)
    except OSError:
        return []
    rows.sort(key=lambda r: str(r.get("ts", "")))
    return rows[-limit:]


def merge_observations(mirror: list[dict], remote: list[dict], limit: int) -> list[dict]:
    """Merge mirror + store observations, deduped by ``(ts, policy_id)``.

    Mirror-first: the sampler's local ring is authoritative for the records it
    has seen, so it wins a key collision; the store supplies deep history that
    is older than the ring (recency fix A — FTS ranking alone loses the tail).
    """
    by_key: dict[tuple[str, str], dict] = {}
    for record in remote:
        ts = record.get("ts")
        pid = record.get("policy_id")
        if isinstance(ts, str) and ts and isinstance(pid, str) and pid:
            by_key[(ts, pid)] = record
    for record in mirror:
        ts = record.get("ts")
        pid = record.get("policy_id")
        if isinstance(ts, str) and ts and isinstance(pid, str) and pid:
            by_key[(ts, pid)] = record
    rows = sorted(by_key.values(), key=lambda r: str(r.get("ts", "")))
    return rows[-limit:]


def rollup_to_point(record: dict) -> dict | None:
    """Normalize a telemetry.rollup into a window-shaped point for the UI."""
    if not isinstance(record, dict) or record.get("kind") != "telemetry.rollup":
        return None
    dims_in = record.get("dims")
    dims: dict[str, float] = {}
    if isinstance(dims_in, dict):
        for name, stats in dims_in.items():
            if isinstance(stats, dict) and isinstance(stats.get("avg"), (int, float)):
                dims[name] = stats["avg"]
    harmony = record.get("harmony")
    score = harmony.get("avg") if isinstance(harmony, dict) else None
    if not isinstance(score, (int, float)):
        return None
    ts = record.get("period_start") or record.get("ts")
    if not isinstance(ts, str):
        return None
    return {
        "kind": "telemetry.rollup",
        "ts": ts,
        "window_seconds": 3600,
        "harmony_score": score,
        "dims": dims,
        "samples": record.get("samples"),
        "events": [],
    }


def galaxy_rollups(
    base: str, galaxy: str, hours: float, limit: int, timeout: float
) -> tuple[list[dict], str | None]:
    reply = wm_tool(
        base,
        "memory.search",
        {"query": "telemetry.rollup", "galaxy": galaxy, "limit": max(limit, 10)},
        timeout,
    )
    if not isinstance(reply, dict) or "_error" in reply or reply.get("status") != "success":
        reason = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        return [], str(reason)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    points: list[dict] = []
    for hit in reply.get("results", []):
        content = hit.get("content") if isinstance(hit, dict) else None
        if not isinstance(content, str):
            continue
        try:
            record = json.loads(content)
        except ValueError:
            continue
        point = rollup_to_point(record)
        if point is None:
            continue
        stamp = parse_ts(point["ts"])
        if stamp is not None and stamp < cutoff:
            continue
        points.append(point)
    points.sort(key=lambda p: str(p.get("ts", "")))
    return points[-limit:], None


def galaxy_observations(
    base: str, galaxy: str, limit: int, timeout: float
) -> tuple[list[dict], str | None]:
    reply = wm_tool(
        base,
        "memory.search",
        {"query": "telemetry.observation", "galaxy": galaxy, "limit": max(limit, 10)},
        timeout,
    )
    if not isinstance(reply, dict) or "_error" in reply or reply.get("status") != "success":
        reason = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        return [], str(reason)
    rows: list[dict] = []
    for hit in reply.get("results", []):
        content = hit.get("content") if isinstance(hit, dict) else None
        if not isinstance(content, str):
            continue
        try:
            record = json.loads(content)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("kind") == "telemetry.observation":
            rows.append(record)
    rows.sort(key=lambda r: str(r.get("ts", "")))
    return rows[-limit:], None


def live_freshness(
    payload: dict, now: float | None = None, stale_after: float = LIVE_STALE_SECONDS
) -> dict:
    """Freshness disclosure for the mirror snapshot (no silent staleness).

    Anti-Maya / Reflection of State: the UI must render Lakshmi's real status,
    so a missing or old ``written_at`` is disclosed, never hidden behind a
    plausible-looking last value.
    """
    written = payload.get("written_at") if isinstance(payload, dict) else None
    if not isinstance(written, (int, float)):
        return {"written_at": None, "age_seconds": None, "stale": True}
    age = max(0.0, (now if now is not None else time.time()) - float(written))
    return {"written_at": written, "age_seconds": round(age, 1), "stale": age > stale_after}


def _number(value: object) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else "?"


def explain_policy(policy: dict) -> str:
    """Plain-language sentence for one step-0 policy (explain-first).

    Built only from the declared enter/exit/direction/dwell/cooldown/version —
    no guarantees beyond the record, no Rego.
    """
    direction = policy.get("direction")
    enter = policy.get("enter")
    exit_ = policy.get("exit")
    metric = str(policy.get("metric", "value"))
    dwell = policy.get("min_dwell_windows", 1)
    cooldown = policy.get("cooldown_windows", 0)
    version = policy.get("version", "?")
    if direction == "below":
        text = (
            f"enters when {metric} falls below {_number(enter)}; "
            f"clears once it recovers above {_number(exit_)}"
        )
    elif direction == "above":
        text = (
            f"enters when {metric} rises above {_number(enter)}; "
            f"clears once it returns to {_number(exit_)} or less"
        )
    else:
        text = (
            f"watches {metric} between enter {_number(enter)} "
            f"and exit {_number(exit_)}"
        )
    if isinstance(dwell, int) and dwell > 1:
        text += f"; confirms after {dwell} consecutive windows"
    if isinstance(cooldown, int) and cooldown > 0:
        text += f"; {cooldown}-window cooldown before re-entry"
    return text + f"; observe only (v{version})"


def samma_zone(policy: dict) -> str:
    """Classify the current value against the hysteresis band (Middle Way).

    Returns ``enter`` (on the threshold side), ``band`` (holding inside the
    enter/exit gap), ``clear`` (recovered past exit), or ``unknown``.
    """
    value = policy.get("value")
    enter = policy.get("enter")
    exit_ = policy.get("exit")
    direction = policy.get("direction")
    if (
        not isinstance(value, (int, float))
        or not isinstance(enter, (int, float))
        or not isinstance(exit_, (int, float))
    ):
        return "unknown"
    if direction == "below":
        if value < enter:
            return "enter"
        if value > exit_:
            return "clear"
        return "band"
    if direction == "above":
        if value > enter:
            return "enter"
        if value <= exit_:
            return "clear"
        return "band"
    return "unknown"


def annotate_live(payload: dict, now: float | None = None) -> dict:
    """Attach freshness + per-policy explain/band zones to a mirror payload.

    Mutates and returns ``payload`` so the handler can stream it as-is; the
    policy snapshot the sampler wrote stays the source of the numbers.
    """
    if not isinstance(payload, dict):
        return payload
    payload.update(live_freshness(payload, now=now))
    meta = payload.get("meta")
    if isinstance(meta, dict):
        policies = meta.get("policies")
        if isinstance(policies, list):
            for policy in policies:
                if isinstance(policy, dict):
                    policy["explain"] = explain_policy(policy)
                    policy["samma_zone"] = samma_zone(policy)
    return payload


def retention_summary(reply: dict) -> dict:
    """Compact retention view for the dashboard.

    `telemetry.retention` is v9.1.5+; on older fleets the tool answers an
    error and the dashboard simply hides the line. Pure function so the
    summary shape is unit-testable without a WM link.
    """
    if not isinstance(reply, dict) or reply.get("status") != "success":
        reason = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        return {"available": False, "error": str(reason)}
    inventory = reply.get("inventory", {})
    windows = inventory.get("windows", {})
    rollups = inventory.get("rollups", {})
    observations = inventory.get("observations", {})
    eligible = int(windows.get("eligible", 0)) + int(rollups.get("eligible", 0))
    return {
        "available": True,
        "prune_due": bool(reply.get("prune_due")),
        "eligible": eligible,
        "next_eligible_since": windows.get("next_eligible_since"),
        "windows": {
            "count": windows.get("count", 0),
            "oldest": windows.get("oldest_created"),
            "eligible": windows.get("eligible", 0),
        },
        "rollups": {
            "count": rollups.get("count", 0),
            "oldest": rollups.get("oldest_created"),
            "eligible": rollups.get("eligible", 0),
        },
        "observations": {"count": observations.get("count", 0), "managed": False},
        "basis": reply.get("basis"),
    }


def events_feed(reply: dict, limit: int) -> dict:
    """Shape the bus feed response with an explicit ok/error/empty distinction.

    Stoic card / no silent zeros: "no events" and "feed unreachable" must look
    different on the page.
    """
    if not isinstance(reply, dict) or "_error" in reply:
        reason = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        return {"feed_ok": False, "error": str(reason), "count": 0, "events": []}
    events = [
        {
            "event_type": e.get("event_type"),
            "source": e.get("source"),
            "timestamp": e.get("timestamp"),
            "payload": e.get("payload"),
        }
        for e in reply.get("events", [])[:limit]
        if isinstance(e, dict)
        and e.get("event_type") in ("os_telemetry_threshold", "sandbox_observation")
    ]
    return {"feed_ok": True, "error": None, "count": len(events), "events": events}


def bridge_snapshot(
    state_dir: str, base: str, galaxy: str, timeout: float
) -> dict:
    """Read-only Yama bridge strip (Gnosis Portals: introspect every layer).

    Counts come from the sampler's last emitted window (mirror); feed
    reachability and the newest raw records are read from WM live, so an
    unreachable feed is visible instead of silently zero.
    """
    counts: dict[str, int | None] = {key: None for key in BRIDGE_METRICS}
    counts_ts: str | None = None
    try:
        with open(os.path.join(state_dir, "latest.json"), encoding="utf-8") as fh:
            mirror = json.load(fh)
        record = mirror.get("record") if isinstance(mirror, dict) else None
        if isinstance(record, dict):
            counts_ts = record.get("ts")
            bridge = record.get("bridge")
            if isinstance(bridge, dict):
                counts = {key: bridge.get(key, 0) for key in BRIDGE_METRICS}
    except (OSError, ValueError):
        pass

    recent: list[dict] = []
    bus_error: str | None = None
    tetragon_error: str | None = None

    reply = wm_tool(base, "bus.recent", {"limit": 50, "category": "harmony"}, timeout)
    if isinstance(reply, dict) and "_error" not in reply:
        for event in reply.get("events", []):
            if not isinstance(event, dict) or event.get("event_type") != "sandbox_observation":
                continue
            payload = event.get("payload") or {}
            kind = payload.get("kind", "sandbox_observation")
            recent.append(
                {
                    "ts": event.get("timestamp"),
                    "source": "bus",
                    "kind": kind,
                    "policy_id": (
                        "spawn.undeclared.v1"
                        if kind == "unconfined_spawn"
                        else "sandbox.degraded.v1"
                    ),
                }
            )
    else:
        bus_error = reply.get("_error") if isinstance(reply, dict) else "unexpected reply"

    reply = wm_tool(
        base,
        "memory.search",
        {"query": "tetragon.shadow_access", "galaxy": galaxy, "limit": 20},
        timeout,
    )
    if (
        isinstance(reply, dict)
        and "_error" not in reply
        and reply.get("status") == "success"
    ):
        for hit in reply.get("results", []):
            content = hit.get("content") if isinstance(hit, dict) else None
            if not isinstance(content, str):
                continue
            try:
                rec = json.loads(content)
            except ValueError:
                continue
            if (
                isinstance(rec, dict)
                and rec.get("kind") == "telemetry.observation"
                and rec.get("metric") == "tetragon.shadow_access"
            ):
                recent.append(
                    {
                        "ts": rec.get("ts"),
                        "source": "tetragon",
                        "kind": rec.get("state", "observed"),
                        "policy_id": rec.get("policy_id", "shadow.access.v1"),
                    }
                )
    else:
        tetragon_error = (
            reply.get("_error") if isinstance(reply, dict) else "unexpected reply"
        )

    recent = [r for r in recent if isinstance(r.get("ts"), str)]
    recent.sort(key=lambda r: str(r["ts"]), reverse=True)
    return {
        "counts": counts,
        "counts_ts": counts_ts,
        "feeds": {
            "bus_ok": bus_error is None,
            "tetragon_ok": tetragon_error is None,
        },
        "errors": {"bus": bus_error, "tetragon": tetragon_error},
        "recent": recent[:10],
    }


def build_api(state_dir: str, wm: str, galaxy_wm: str, galaxy: str, wm_timeout: float) -> dict:
    class Handler(BaseHTTPRequestHandler):
        server_version = "lakshmi-dashboard/0.1"

        def log_message(self, fmt: str, *args: object) -> None:  # quiet by default
            pass

        def _json(self, payload: object, code: int = 200) -> None:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: str, content_type: str) -> None:
            try:
                with open(path, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json({"error": "not found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 — http.server API
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path in ("/", "/index.html"):
                page = os.path.join(os.path.dirname(os.path.abspath(__file__)), PAGE_NAME)
                self._file(page, "text/html; charset=utf-8")
                return
            if parsed.path in ("/mandala", "/mandala.html"):
                page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mandala.html")
                self._file(page, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/live":
                latest = os.path.join(state_dir, "latest.json")
                try:
                    with open(latest, encoding="utf-8") as fh:
                        self._json(annotate_live(json.load(fh)))
                except (OSError, ValueError):
                    self._json({"error": "no mirror yet", "state_dir": state_dir}, 404)
                return
            if parsed.path == "/api/history":
                hours = float(query.get("hours", ["6"])[0])
                limit = int(query.get("limit", ["360"])[0])
                local = load_mirror_history(state_dir, hours, limit)
                remote, error = galaxy_history(
                    galaxy_wm, query.get("galaxy", [galaxy])[0], limit, wm_timeout
                )
                rows = merge_history(local, remote, limit)
                self._json(
                    {
                        "count": len(rows),
                        "source": {"mirror": len(local), "galaxy": len(remote)},
                        "galaxy_error": error,
                        "windows": rows,
                    }
                )
                return
            if parsed.path == "/api/rollups":
                hours = float(query.get("hours", ["168"])[0])
                limit = int(query.get("limit", ["200"])[0])
                rows, error = galaxy_rollups(
                    galaxy_wm, query.get("galaxy", [galaxy])[0], hours, limit, wm_timeout
                )
                self._json({"count": len(rows), "galaxy_error": error, "windows": rows})
                return
            if parsed.path == "/api/observations":
                limit = int(query.get("limit", ["100"])[0])
                local = load_mirror_observations(state_dir, limit)
                remote, error = galaxy_observations(
                    galaxy_wm, query.get("galaxy", [galaxy])[0], limit, wm_timeout
                )
                rows = merge_observations(local, remote, limit)
                self._json(
                    {
                        "count": len(rows),
                        "source": {"mirror": len(local), "galaxy": len(remote)},
                        "galaxy_error": error,
                        "observations": rows,
                    }
                )
                return
            if parsed.path == "/api/retention":
                reply = wm_tool(galaxy_wm, "telemetry.retention", {}, wm_timeout)
                self._json(retention_summary(reply))
                return
            if parsed.path == "/api/events":
                limit = int(query.get("limit", ["50"])[0])
                reply = wm_tool(
                    galaxy_wm, "bus.recent", {"limit": limit, "category": "harmony"}, wm_timeout
                )
                self._json(events_feed(reply, limit))
                return
            if parsed.path == "/api/bridge":
                self._json(
                    bridge_snapshot(
                        state_dir,
                        galaxy_wm,
                        query.get("galaxy", [galaxy])[0],
                        wm_timeout,
                    )
                )
                return
            if parsed.path == "/api/healthz":
                self._json({"server": "ok", "wm": wm_alive(wm)})
                return
            self._json({"error": "not found"}, 404)

    return Handler


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Lakshmi dashboard (stdlib, read-only)")
    ap.add_argument("--bind", default="127.0.0.1", help="bind address (default loopback)")
    ap.add_argument("--port", type=int, default=3109, help="port (default 3109)")
    ap.add_argument("--state-dir", default=STATE_DEFAULT, help="mirror directory written by lakshmi.py --emit")
    ap.add_argument("--wm", default="http://127.0.0.1:18790", help="WM MCP endpoint for bus events")
    ap.add_argument(
        "--galaxy-wm",
        default=None,
        help="WM MCP endpoint hosting the telemetry galaxy + threshold events (default: --wm)",
    )
    ap.add_argument("--galaxy", default="telemetry", help="telemetry galaxy name")
    ap.add_argument("--wm-timeout", type=float, default=2.5, help="WM request timeout (seconds)")
    return ap.parse_args(argv)



def main() -> int:
    args = parse_args(sys.argv[1:])
    galaxy_wm = args.galaxy_wm or args.wm
    server = ThreadingHTTPServer(
        (args.bind, args.port),
        build_api(args.state_dir, args.wm, galaxy_wm, args.galaxy, args.wm_timeout),
    )
    print(
        f"lakshmi-dashboard on http://{args.bind}:{args.port} "
        f"(state {args.state_dir}, wm {args.wm}, galaxy-wm {galaxy_wm}, galaxy {args.galaxy})",
        file=sys.stderr,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
