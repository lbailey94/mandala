#!/usr/bin/env python3
"""Lakshmi v0 — 7-dimension Harmony Vector digestor (MandalaOS).

Computes the OS-level Harmony Vector spec (feasibility/harmony-vector-spec.md)
from kernel telemetry available without privileges: /proc, PSI pressure, and
RAPL when readable. All dimensions normalized to [0.0, 1.0], 1.0 = ideal;
cold start is 0.7, never 1.0.

Honest v0 proxies (documented rather than hidden):
  fairness       1 - Gini of per-process CPU ticks over the window
  responsiveness 1 - clamp(PSI cpu "some" avg10 / 40)  [p95 wake-to-run is eBPF work]
  throughput     triangular around 0.5x the session baseline (ctx switches/s)
  stability      1 - clamp(PSI memory "full" avg10 / 50 + defunct penalty)
  energy         RAPL watts vs budget (0.5 neutral when unreadable, root-only sysfs)
  dharma         0.7 stub (no Yama/policy engine wired yet)
  karma_debt     0.7 stub or LAKSHMI_KARMA_DEBT (WM ledger seam not wired yet)

eBPF is deliberately absent: this machine boots with
kernel.unprivileged_bpf_disabled=2 (permanent). PSI is the privileged-free
substitute; Tetragon/Falco land in the eBPF sprint.

Usage:
  lakshmi.py --once                     # two samples, one vector, exit
  lakshmi.py --interval 5               # continuous terminal display
  lakshmi.py --once --json              # machine-readable snapshot
  lakshmi.py --count 3 --interval 2 --json
  lakshmi.py --interval 5 --window 60 --emit
                                        # emit 1-min windows to the telemetry
                                        # galaxy (spools locally on failure)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import signal
import sys
import time
import urllib.request
from wm_mcp import call_tool
from collections import deque
from datetime import datetime, timezone

import actuator

CLK_TCK = os.sysconf("SC_CLK_TCK")

WEIGHTS = {
    "fairness": 0.15,
    "responsiveness": 0.15,
    "throughput": 0.10,
    "stability": 0.20,
    "energy": 0.10,
    "dharma": 0.15,
    "karma_debt": 0.15,
}

COLD_START = 0.7
NEUTRAL_UNAVAILABLE = 0.5

RAPL_CANDIDATES = (
    "/sys/class/powercap/intel-rapl:1/energy_uj",
    "/sys/class/powercap/intel-rapl:0/energy_uj",
)


def read_psi(resource: str) -> dict | None:
    try:
        with open(f"/proc/pressure/{resource}", encoding="ascii") as fh:
            text = fh.read()
    except OSError:
        return None
    out: dict = {}
    for line in text.strip().splitlines():
        parts = line.replace("=", " ").split()
        if len(parts) < 3:
            continue
        kind = parts[0]
        vals = {}
        for i in range(1, len(parts), 2):
            try:
                vals[parts[i]] = float(parts[i + 1])
            except (ValueError, IndexError):
                continue
        out[kind] = vals
    return out or None


def read_proc_sample() -> dict[int, tuple[str, int, str]]:
    procs: dict[int, tuple[str, int, str]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="ascii") as fh:
                stat = fh.read()
        except OSError:
            continue
        close = stat.rfind(")")
        open_ = stat.find("(")
        if open_ == -1 or close == -1:
            continue
        comm = stat[open_ + 1 : close]
        fields = stat[close + 2 :].split()
        if len(fields) < 13:
            continue
        try:
            ticks = int(fields[11]) + int(fields[12])
        except ValueError:
            continue
        procs[int(entry)] = (comm, ticks, fields[0])
    return procs


def read_proc_stat_meta() -> tuple[int | None, int | None]:
    ctxt = None
    created = None
    try:
        with open("/proc/stat", encoding="ascii") as fh:
            for line in fh:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "ctxt":
                    ctxt = int(parts[1])
                elif parts[0] == "processes":
                    created = int(parts[1])
                if ctxt is not None and created is not None:
                    break
    except OSError:
        pass
    return ctxt, created


def read_energy_uj() -> tuple[str | None, int | None, int | None]:
    for path in RAPL_CANDIDATES:
        try:
            with open(path, encoding="ascii") as fh:
                value = int(fh.read().strip())
        except OSError:
            continue
        max_path = os.path.join(os.path.dirname(path), "max_energy_range_uj")
        max_range = None
        try:
            with open(max_path, encoding="ascii") as fh:
                max_range = int(fh.read().strip())
        except OSError:
            pass
        return path, value, max_range
    return None, None, None


def read_battery_watts() -> tuple[str | None, float | None]:
    for path in sorted(glob.glob("/sys/class/power_supply/BAT*/power_now")):
        try:
            with open(path, encoding="ascii") as fh:
                microwatts = int(fh.read().strip())
        except (OSError, ValueError):
            continue
        if microwatts > 0:
            return path, microwatts / 1_000_000.0
    return None, None


def call_wm_tool(endpoint: str, tool: str, arguments: dict | None = None, timeout: float = 4.0) -> dict:
    return call_tool(endpoint, tool, arguments or {}, timeout)

# ── Edge galaxy emission (telemetry windows → WM) ─────────────────────
#
# Rule 2 (evidence, not cognition): windows go to the dedicated `telemetry`
# galaxy; raw samples never leave the local process (the ring in
# `Lakshmi.samples`). Rule 4 (fail-soft): a window is spooled to a bounded
# local ring file *before* it is sent, and replayed oldest-first on the next
# successful emission — OS safety never depends on WM being up.

EMIT_TAGS = ["telemetry", "edge", "laksmi", "window"]
SPOOL_DEFAULT = os.path.expanduser("~/.local/share/lakshmi/telemetry_spool.jsonl")
SPOOL_MAX = 1008  # ~7 days at one window per minute
STATE_DEFAULT = os.path.expanduser("~/.local/share/lakshmi")
HISTORY_MAX = 2880  # 48h at one window per minute
OBSERVATIONS_MAX = 50  # recent decision records mirrored for the dashboard


def write_json_atomic(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)


class Mirror:
    """Dashboard-facing local mirror: latest snapshot + bounded window history.

    The galaxy is the durable record; this mirror is how the UI stays live
    and useful when WM is down (fail-soft, rule 4).
    """

    def __init__(
        self,
        state_dir: str,
        history_max: int = HISTORY_MAX,
        observations_max: int = OBSERVATIONS_MAX,
    ) -> None:
        self.dir = os.path.expanduser(state_dir)
        self.history_path = os.path.join(self.dir, "history.jsonl")
        self.latest_path = os.path.join(self.dir, "latest.json")
        self.observations_path = os.path.join(self.dir, "observations.jsonl")
        self.history_max = history_max
        self.observations_max = observations_max
        self.last_record: dict | None = None

    def write_live(self, snapshot: dict, meta: dict) -> None:
        """Update only latest.json — the fast lane (every sampler tick).

        Carries the last emitted record alongside so the UI keeps guna/top
        and karma/dharma counters between window emissions.
        """
        payload = {
            "snapshot": snapshot,
            "meta": meta,
            "written_at": time.time(),
        }
        if self.last_record is not None:
            payload["record"] = self.last_record
        write_json_atomic(self.latest_path, payload)

    def write(self, snapshot: dict, record: dict, meta: dict) -> None:
        self.last_record = record
        write_json_atomic(
            self.latest_path,
            {
                "snapshot": snapshot,
                "record": record,
                "meta": meta,
                "written_at": time.time(),
            },
        )
        try:
            with open(self.history_path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except OSError:
            lines = []
        lines.append(json.dumps(record, separators=(",", ":"), sort_keys=True))
        if len(lines) > self.history_max:
            lines = lines[-self.history_max :]
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = f"{self.history_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            os.replace(tmp, self.history_path)
        except OSError as exc:
            print(f"mirror: history write failed ({exc})", file=sys.stderr)

    def write_observations(self, observations: list[dict]) -> None:
        """Append decision records to the bounded observations ring.

        `memory.search` is FTS-ranked, so the newest records are not guaranteed
        to appear in the store's result window; the dashboard merges this local
        ring (mirror-first) with the store so recency survives volume growth.
        """
        if not observations:
            return
        try:
            with open(self.observations_path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except OSError:
            lines = []
        for record in observations:
            lines.append(json.dumps(record, separators=(",", ":"), sort_keys=True))
        if len(lines) > self.observations_max:
            lines = lines[-self.observations_max :]
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = f"{self.observations_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            os.replace(tmp, self.observations_path)
        except OSError as exc:
            print(f"mirror: observations write failed ({exc})", file=sys.stderr)


class WindowSpool:
    """Bounded append-only ring of unsent telemetry windows."""

    def __init__(self, path: str, max_entries: int = SPOOL_MAX) -> None:
        self.path = os.path.expanduser(path)
        self.max_entries = max_entries
        self.entries: list[dict] = []

    def load(self) -> int:
        self.entries = []
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.entries.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            self.entries = []
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        return len(self.entries)

    def append(self, record: dict) -> None:
        self.entries.append(record)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for entry in self.entries:
                    fh.write(json.dumps(entry, separators=(",", ":"), sort_keys=True))
                    fh.write("\n")
            os.replace(tmp, self.path)
        except OSError as exc:
            print(f"emit: spool write failed ({exc})", file=sys.stderr)

    def flush(self, endpoint: str, galaxy: str, timeout: float = 6.0) -> tuple[int, str | None]:
        """Send spooled windows, oldest-first, with a freshness path.

        The head is retried first (order preserved when WM is healthy). If the
        head fails — a slow server under load can time out even while newer
        windows would succeed — the newest entry is probed once so live data
        keeps flowing; windows carry their own `ts`, so out-of-order arrival
        is harmless. Stops on the first failure with no tail progress.

        Returns (sent_count, last_error). Sent entries are dropped; the
        remainder stays spooled for the next attempt.
        """
        sent = 0
        last_error: str | None = None

        def attempt(record: dict) -> tuple[bool, str | None]:
            reply = emit_window(endpoint, galaxy, record, timeout=timeout)
            # `deduplicated` means the row already exists in the galaxy —
            # that IS delivery (a lost response can leave a stored window
            # still spooled; replay must acknowledge and drop it).
            if isinstance(reply, dict) and reply.get("status") in ("success", "deduplicated"):
                return True, None
            reason = (
                reply.get("_error")
                if isinstance(reply, dict)
                else (json.dumps(reply)[:200] if reply else "no reply")
            )
            return False, reason

        while self.entries:
            ok, reason = attempt(self.entries[0])
            if ok:
                self.entries.pop(0)
                sent += 1
                continue
            last_error = reason
            if len(self.entries) > 1:
                ok_tail, reason_tail = attempt(self.entries[-1])
                if ok_tail:
                    self.entries.pop()
                    sent += 1
                    continue
                last_error = reason_tail
            break
        return sent, last_error


def emit_window(
    endpoint: str, galaxy: str, record: dict, timeout: float = 6.0
) -> dict | None:
    """POST one telemetry window via memory.create. Returns the tool reply."""
    content = json.dumps(record, separators=(",", ":"), sort_keys=True)
    return call_wm_tool(
        endpoint,
        "memory.create",
        {
            "content": content,
            "galaxy": galaxy,
            "tags": EMIT_TAGS,
            "title": f"telemetry.window {record.get('ts', '')}",
            "importance": 0.3,
            "source": "laksmi",
        },
        timeout=timeout,
    )


def emit_threshold_event(endpoint: str, event: dict, timeout: float = 4.0) -> dict | None:
    """POST one threshold crossing via bus.emit (ephemeral, low-latency)."""
    return call_wm_tool(
        endpoint,
        "bus.emit",
        {"event_type": "os_telemetry_threshold", "source": "laksmi", "data": event},
        timeout=timeout,
    )


def emit_actuation_notify(endpoint: str, payload: dict, timeout: float = 4.0) -> dict | None:
    """POST one Y1 notify action via bus.emit (Yama ladder step 1).

    Fleets predating the `actuation_notify` event type reject this; the
    decision record still lands, so notify degrades to the dashboard inbox.
    """
    return call_wm_tool(
        endpoint,
        "bus.emit",
        {"event_type": "actuation_notify", "source": "laksmi", "data": payload},
        timeout=timeout,
    )


def emit_observation(
    endpoint: str, galaxy: str, record: dict, timeout: float = 6.0
) -> dict | None:
    """POST one policy observation (step-0 decision record).

    Prefers the typed `telemetry.record` path; falls back to `memory.create`
    for fleets that predate the observation kind (v9.1.4 and earlier).
    """
    typed = call_wm_tool(
        endpoint, "telemetry.record", {"record": record, "source": "laksmi"}, timeout
    )
    if (
        isinstance(typed, dict)
        and "_error" not in typed
        and typed.get("status") in ("success", "deduplicated")
    ):
        return typed
    content = json.dumps(record, separators=(",", ":"), sort_keys=True)
    return call_wm_tool(
        endpoint,
        "memory.create",
        {
            "content": content,
            "galaxy": galaxy,
            "tags": record["tags"],
            "title": f"telemetry.observation {record['policy_id']} {record['state']}",
            "importance": 0.3,
            "source": "laksmi",
        },
        timeout=timeout,
    )


# ── Yama v0 bridge inputs (sandbox drift + Tetragon observations) ──────
#
# The bridge legs land in WM first (S1 sandbox_observation bus events; S2
# Tetragon observation records); the policy engine reads them back per
# window so step-0 stays the single evaluation point. Feed reachability is
# explicit: an unreachable feed holds state instead of clearing it.
# The Tetragon leg merges the store search with the collector's bounded
# sent-log ring (mirror-first): `memory.search` is FTS-ranked, so recency
# cannot rely on it. Only records that reached WM are in the ring.

BRIDGE_METRICS = ("sandbox_unconfined", "sandbox_degraded", "tetragon_shadow")
BRIDGE_FEED_DEFAULT = os.path.expanduser("~/.local/share/yama-collector/sent.jsonl")

# Which captured subjects belong to which bridge policy (contract §2, Y1.1).
BRIDGE_SUBJECT_SOURCES = {
    "spawn.undeclared.v1": "sandbox_subjects",
    "sandbox.degraded.v1": "sandbox_subjects",
    "shadow.access.v1": "tetragon_subjects",
}


def load_bridge_feed(path: str, since: str) -> list[dict]:
    """Read the collector's sent-log ring, keeping records newer than `since`."""
    if not path:
        return []
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
                if not isinstance(record, dict):
                    continue
                if record.get("kind") != "telemetry.observation":
                    continue
                if str(record.get("ts", "")) < since:
                    continue
                rows.append(record)
    except OSError:
        return []
    return rows


def _bridge_key(record: dict) -> tuple[str, str, str]:
    return (
        str(record.get("ts", "")),
        str(record.get("policy_id", "")),
        str(record.get("metric", "")),
    )


def _bridge_value(record: dict) -> int:
    value = record.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 1:
        return int(value)
    return 1


def fetch_bridge_inputs(
    endpoint: str,
    since: str,
    timeout: float = 4.0,
    feed_path: str | None = None,
) -> dict:
    """Poll WM for bridge signals newer than `since` (lexicographic RFC3339).

    The Tetragon leg merges the store search with the collector's local ring
    (mirror-first, deduped by ``(ts, policy_id, metric)``) and counts event
    totals (each record's ``value``), so bursts are not collapsed. Store
    reachability decides `tetragon_ok`; when the store is down, policy state
    holds even though the ring may still report counts. Pass `feed_path=""`
    to disable the ring (soak/offline stores).
    """
    path = BRIDGE_FEED_DEFAULT if feed_path is None else feed_path
    feed_rows = [
        record
        for record in load_bridge_feed(path, since)
        if record.get("metric") == "tetragon.shadow_access"
    ]
    out = {
        "sandbox_unconfined": 0,
        "sandbox_degraded": 0,
        "tetragon_shadow": 0,
        "sandbox_subjects": [],
        "tetragon_subjects": [],
        "bus_ok": False,
        "tetragon_ok": False,
    }
    reply = call_wm_tool(
        endpoint, "bus.recent", {"limit": 200, "category": "harmony"}, timeout
    )
    if isinstance(reply, dict) and "_error" not in reply:
        out["bus_ok"] = True
        for event in reply.get("events", []):
            if event.get("event_type") != "sandbox_observation":
                continue
            if str(event.get("timestamp", "")) < since:
                continue
            payload = event.get("payload") or {}
            kind = payload.get("kind")
            tool = payload.get("tool")
            if tool and str(tool) not in out["sandbox_subjects"]:
                out["sandbox_subjects"].append(str(tool))
            if kind == "unconfined_spawn":
                out["sandbox_unconfined"] += 1
            elif kind == "degraded":
                out["sandbox_degraded"] += 1

    remote_rows: list[dict] = []
    reply = call_wm_tool(
        endpoint,
        "memory.search",
        {"query": "tetragon.shadow_access", "galaxy": "telemetry", "limit": 50},
        timeout,
    )
    if isinstance(reply, dict) and "_error" not in reply:
        out["tetragon_ok"] = True
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
                and record.get("kind") == "telemetry.observation"
                and record.get("metric") == "tetragon.shadow_access"
                and str(record.get("ts", "")) >= since
            ):
                remote_rows.append(record)

    by_key: dict[tuple[str, str, str], dict] = {}
    for record in remote_rows:
        by_key[_bridge_key(record)] = record
    for record in feed_rows:
        by_key[_bridge_key(record)] = record
    for record in by_key.values():
        subject = record.get("subject")
        if subject and subject not in out["tetragon_subjects"]:
            out["tetragon_subjects"].append(str(subject))
    out["tetragon_subjects"] = out["tetragon_subjects"][:10]
    out["tetragon_shadow"] = sum(_bridge_value(record) for record in by_key.values())
    return out


def gini(values: list[float]) -> float:
    vals = sorted(v for v in values if v > 0)
    n = len(vals)
    if n == 0:
        return 0.0
    total = sum(vals)
    if total <= 0:
        return 0.0
    weighted = sum((i + 1) * v for i, v in enumerate(vals))
    return max(0.0, min(1.0, (2.0 * weighted) / (n * total) - (n + 1.0) / n))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class Sample:
    __slots__ = (
        "t",
        "procs",
        "ctxt",
        "created",
        "energy_uj",
        "max_range",
        "path",
        "battery_path",
        "battery_watts",
        "psi",
    )

    def __init__(self) -> None:
        self.t = time.monotonic()
        self.procs = read_proc_sample()
        self.ctxt, self.created = read_proc_stat_meta()
        self.path, self.energy_uj, self.max_range = read_energy_uj()
        self.battery_path, self.battery_watts = read_battery_watts()
        self.psi = {
            "cpu": read_psi("cpu"),
            "io": read_psi("io"),
            "memory": read_psi("memory"),
        }


class Lakshmi:
    def __init__(
        self,
        window: float,
        budget_watts: float,
        karma_debt: float | None,
        wm_mcp: str | None = None,
        karma_max: float = 150.0,
        dharma_mcp: str | None = None,
    ) -> None:
        self.window = window
        self.budget_watts = budget_watts
        self.karma_debt_override = karma_debt
        self.wm_mcp = wm_mcp
        self.karma_max = karma_max
        self.karma_baseline: float | None = None
        self.dharma_mcp = dharma_mcp
        self.dharma_prev: dict | None = None
        self.dharma_counts: dict | None = None
        self.dharma_deltas: dict | None = None
        self.karma_total: float | None = None
        self.karma_delta: float | None = None
        self.threshold_state: dict[str, bool] = {}
        self.policy_state: dict[str, dict] = {}
        self.bridge_inputs: dict = {}
        self.samples: deque[Sample] = deque()
        self.ctxt_baseline: float | None = None

    def add(self, sample: Sample) -> None:
        self.samples.append(sample)
        cutoff = sample.t - self.window
        while len(self.samples) > 2 and self.samples[0].t < cutoff:
            self.samples.popleft()

    def window_seconds(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return self.samples[-1].t - self.samples[0].t

    def _fairness(self, active: dict[int, float], note_extra: str) -> dict:
        if len(active) < 5:
            return dim(COLD_START, "proc", f"cold start: only {len(active)} active procs in window")
        score = clamp(1.0 - gini(list(active.values())))
        return dim(score, "proc", f"1-Gini over {len(active)} active procs{note_extra}")

    def _responsiveness(self, sample: Sample) -> dict:
        psi = sample.psi.get("cpu")
        if not psi or "some" not in psi:
            return dim(NEUTRAL_UNAVAILABLE, "psi", "PSI cpu unavailable")
        avg10 = psi["some"].get("avg10", 0.0)
        return dim(clamp(1.0 - avg10 / 40.0), "psi", f"PSI cpu some avg10={avg10:.1f}")

    def _throughput(self, sample: Sample) -> dict:
        first = self.samples[0]
        dt = self.window_seconds()
        if dt <= 0 or first.ctxt is None or sample.ctxt is None:
            return dim(COLD_START, "proc", "baseline calibrating")
        rate = (sample.ctxt - first.ctxt) / dt
        if self.ctxt_baseline is None:
            self.ctxt_baseline = rate
            return dim(COLD_START, "proc", "baseline calibrating (first window)")
        baseline = max(1.0, self.ctxt_baseline)
        self.ctxt_baseline = 0.9 * self.ctxt_baseline + 0.1 * rate
        ratio = rate / baseline
        if ratio <= 0.5:
            score = ratio / 0.5
        else:
            score = max(0.0, 1.0 - (ratio - 0.5) / 1.5)
        return dim(clamp(score), "proc", f"ctx-sw/s {rate:.0f} = {ratio:.2f}x baseline")

    def _stability(self, sample: Sample) -> dict:
        psi = sample.psi.get("memory")
        full_avg10 = psi["full"].get("avg10", 0.0) if psi and "full" in psi else 0.0
        defunct = sum(1 for (_, _, state) in sample.procs.values() if state == "Z")
        score = clamp(1.0 - (full_avg10 / 50.0 + defunct * 0.02))
        return dim(score, "psi+proc", f"mem full avg10={full_avg10:.1f}, defunct={defunct}")

    def _energy(self, sample: Sample) -> dict:
        first = self.samples[0]
        dt = self.window_seconds()
        if (
            sample.energy_uj is not None
            and first.energy_uj is not None
            and dt > 0
        ):
            delta = sample.energy_uj - first.energy_uj
            if delta < 0 and sample.max_range:
                delta += sample.max_range
            watts = (delta / 1_000_000.0) / dt
            return self._energy_score(watts, "rapl", sample.path or "rapl")
        if sample.battery_watts is not None:
            return self._energy_score(
                sample.battery_watts, "battery", sample.battery_path or "battery"
            )
        return dim(
            NEUTRAL_UNAVAILABLE,
            "energy",
            "RAPL unreadable (root-only sysfs) and battery power_now absent/idle; neutral 0.5",
        )

    def _energy_score(self, watts: float, source: str, path: str) -> dict:
        if watts <= self.budget_watts:
            score = 1.0
        else:
            score = clamp(1.0 - (watts - self.budget_watts) / self.budget_watts)
        return dim(score, source, f"{watts:.1f}W vs {self.budget_watts:.0f}W budget ({path})")

    def _dharma(self) -> dict:
        if not self.dharma_mcp:
            return dim(
                COLD_START,
                "stub",
                "no dharma endpoint (--dharma-mcp); stub 0.7",
            )
        report = call_wm_tool(self.dharma_mcp, "dharma.status")
        decisions = report.get("decisions") if isinstance(report, dict) else None
        if not isinstance(decisions, dict):
            reason = (
                report.get("_error", "dharma.status lacks decisions (pre-B3 WM)")
                if isinstance(report, dict)
                else "unexpected payload"
            )
            return dim(COLD_START, "wm", f"dharma unavailable ({reason}); stub 0.7")
        keys = ("observe", "advise", "correct", "intervene", "panic", "total", "blocked")
        counts = {key: int(decisions.get(key, 0)) for key in keys}
        prev = self.dharma_prev
        self.dharma_prev = counts
        if prev is None:
            self.dharma_counts = counts
            self.dharma_deltas = {"delta_total": 0, "delta_blocked": 0}
            return dim(
                COLD_START,
                "wm",
                f"baseline recorded (totals total={counts['total']}, blocked={counts['blocked']})",
            )
        total_delta = max(0, counts["total"] - prev["total"])
        blocked_delta = max(0, counts["blocked"] - prev["blocked"])
        self.dharma_counts = counts
        self.dharma_deltas = {"delta_total": total_delta, "delta_blocked": blocked_delta}
        if total_delta == 0:
            return dim(COLD_START, "wm", "no decisions this window (cold start 0.7)")
        ratio = blocked_delta / total_delta
        score = clamp(1.0 - ratio * 5.0)
        return dim(
            score,
            "wm",
            f"blocked {blocked_delta}/{total_delta} since last poll ({ratio:.0%})",
        )

    def _karma(self) -> dict:
        if self.karma_debt_override is not None:
            return dim(clamp(self.karma_debt_override), "env", "LAKSHMI_KARMA_DEBT override")
        if self.wm_mcp:
            report = call_wm_tool(self.wm_mcp, "karma.report")
            total = None
            if isinstance(report, dict) and "_error" not in report:
                total = report.get("total_debt")
            if total is None:
                reason = report.get("_error", "unexpected karma.report payload") if isinstance(report, dict) else "unexpected payload"
                return dim(COLD_START, "wm", f"karma.report unavailable ({reason}); stub 0.7")
            if self.karma_baseline is None:
                self.karma_baseline = float(total)
            delta = float(total) - self.karma_baseline
            self.karma_total = float(total)
            self.karma_delta = delta
            score = clamp(1.0 - float(total) / self.karma_max)
            return dim(
                score,
                "wm",
                f"WM ledger total {float(total):.1f} (cap {self.karma_max:.0f}), session delta {delta:+.1f}",
            )
        return dim(
            COLD_START,
            "stub",
            "no WM endpoint (--wm-mcp) and no LAKSHMI_KARMA_DEBT override; stub 0.7",
        )

    def vector(self, sample: Sample) -> dict:
        first = self.samples[0]
        dt = self.window_seconds()
        active: dict[int, float] = {}
        for pid, (comm, ticks, _) in sample.procs.items():
            prior = first.procs.get(pid)
            if prior is None:
                delta = ticks
                label = comm
            else:
                delta = max(0, ticks - prior[1])
                label = prior[0]
            if delta > 0:
                active[pid] = active.get(pid, 0.0) + delta

        note = "" if self.window >= 300 else f" (window {dt:.0f}s < 300s target)"
        dims = {
            "fairness": self._fairness(active, note),
            "responsiveness": self._responsiveness(sample),
            "throughput": self._throughput(sample),
            "stability": self._stability(sample),
            "energy": self._energy(sample),
            "dharma": self._dharma(),
            "karma_debt": self._karma(),
        }

        composite = sum(WEIGHTS[k] * dims[k]["score"] for k in WEIGHTS)
        guna = self._guna_tags(active, sample)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "window_seconds": round(dt, 2),
            "harmony_score": round(composite, 3),
            "dims": dims,
            "guna": guna,
            "top_processes": self._top(active, sample),
        }

    # ── Edge galaxy record builders (spec: SESSION_HANDOFF §5) ────────

    # (dimension, danger threshold, sources where the score is real — a
    # neutral "unavailable" proxy must never trigger an event)
    THRESHOLD_CHECKS = (
        ("responsiveness", 0.3, ("psi",)),
        ("stability", 0.8, None),
        ("energy", 0.9, ("rapl", "battery")),
    )

    def threshold_events(self, snapshot: dict) -> list[dict]:
        """Change-based crossings: emit only when a dim ENTERS the danger
        band, plus every window whose dharma blocked-delta is positive."""
        events: list[dict] = []
        for name, threshold, sources in self.THRESHOLD_CHECKS:
            dim = snapshot["dims"][name]
            if sources is not None and dim.get("source") not in sources:
                # Unavailable proxy (e.g. RAPL unreadable → neutral 0.5):
                # not evidence of a crossing; clear any armed state.
                self.threshold_state[name] = False
                continue
            value = float(dim["score"])
            crossed = value < threshold
            was = self.threshold_state.get(name, False)
            self.threshold_state[name] = crossed
            if crossed and not was:
                events.append(
                    {
                        "topic": f"os.telemetry.{name}",
                        "value": round(value, 3),
                        "threshold": threshold,
                        "window": f"{snapshot['window_seconds']:.0f}s",
                        "state": "crossed",
                    }
                )
        blocked_delta = int((self.dharma_deltas or {}).get("delta_blocked", 0))
        if blocked_delta > 0:
            events.append(
                {
                    "topic": "os.telemetry.dharma_blocked",
                    "value": blocked_delta,
                    "threshold": 0,
                    "window": f"{snapshot['window_seconds']:.0f}s",
                    "state": "crossed",
                }
            )
        return events

    # ── Step-0 policies (observe only) ────────────────────────────────
    #
    # Enter != exit thresholds create the hysteresis band; transitions are
    # recorded as `telemetry.observation` decision records per
    # design/ACTUATION_HYSTERESIS_2026-09-13.md. No actuation: state is
    # recorded, never acted on. `direction=below` observes a dim falling
    # under `enter` and recovering above `exit`; `above` watches a rising
    # value (dharma blocked-delta: >0 enters, <=0 clears).
    POLICIES = (
        # id, metric, direction, enter, exit, sources, version, min_dwell, cooldown
        ("responsiveness.below.v1", "responsiveness", "below", 0.30, 0.50, ("psi",), 1, 5, 3),
        ("stability.below.v1", "stability", "below", 0.80, 0.95, None, 1, 5, 3),
        ("energy.over_budget.v1", "energy", "below", 0.90, 0.97, ("rapl", "battery"), 1, 5, 3),
        # a blocked-dharma window is already significant: dwell 1, no cooldown
        ("dharma.blocked.v1", "dharma_blocked_delta", "above", 0.5, 0.0, None, 1, 1, 0),
        # Yama v0 bridge signals (S3): any drift/access event in the window
        # enters; a clean window clears. Feeds must be reachable to move state.
        ("spawn.undeclared.v1", "sandbox_unconfined", "above", 0.5, 0.0, ("bus",), 1, 1, 0),
        ("sandbox.degraded.v1", "sandbox_degraded", "above", 0.5, 0.0, ("bus",), 1, 1, 0),
        ("shadow.access.v1", "tetragon_shadow", "above", 0.5, 0.0, ("tetragon",), 1, 1, 0),
    )

    def _policy_metric(self, snapshot: dict, metric: str) -> float:
        if metric in BRIDGE_METRICS:
            return float(self.bridge_inputs.get(metric, 0))
        if metric == "dharma_blocked_delta":
            return float(int((self.dharma_deltas or {}).get("delta_blocked", 0)))
        return float(snapshot["dims"][metric]["score"])

    def _policy_source_ok(self, snapshot: dict, metric: str, sources: tuple | None) -> bool:
        if sources is None or metric == "dharma_blocked_delta":
            return True
        if sources == ("bus",):
            return bool(self.bridge_inputs.get("bus_ok", False))
        if sources == ("tetragon",):
            return bool(self.bridge_inputs.get("tetragon_ok", False))
        return snapshot["dims"][metric].get("source") in sources

    def policy_observations(self, snapshot: dict) -> list[dict]:
        """Transition records: observing on enter, confirmed at dwell, clear
        on recovery (step 0; cooldown gates re-entry)."""
        out: list[dict] = []
        for (
            pid,
            metric,
            direction,
            enter,
            exit_,
            sources,
            version,
            min_dwell,
            cooldown,
        ) in self.POLICIES:
            # Unavailable proxies (e.g. RAPL unreadable) must not flip state:
            # hold whatever we last knew rather than clearing on missing data.
            if not self._policy_source_ok(snapshot, metric, sources):
                continue
            value = self._policy_metric(snapshot, metric)
            st = self.policy_state.setdefault(
                pid,
                {"state": "clear", "dwell": 0, "since": None, "cooldown_left": 0},
            )
            entering = (value < enter) if direction == "below" else (value > enter)
            recovered = (value > exit_) if direction == "below" else (value <= exit_)
            new_state: str | None = None
            if st["state"] == "clear":
                if st["cooldown_left"] > 0:
                    st["cooldown_left"] -= 1
                elif entering:
                    st["state"] = "observing"
                    st["dwell"] = 1
                    st["since"] = snapshot["timestamp"]
                    new_state = "observing"
            elif st["state"] == "observing":
                st["dwell"] += 1
                if recovered:
                    st["state"] = "clear"
                    st["since"] = snapshot["timestamp"]
                    st["cooldown_left"] = cooldown
                    new_state = "clear"
                elif st["dwell"] == min_dwell and min_dwell > 1:
                    st["state"] = "confirmed"
                    new_state = "confirmed"
            elif st["state"] == "confirmed":
                st["dwell"] += 1
                if recovered:
                    st["state"] = "clear"
                    st["since"] = snapshot["timestamp"]
                    st["cooldown_left"] = cooldown
                    new_state = "clear"
            if new_state is None:
                continue
            subjects: list[str] = []
            source_name = BRIDGE_SUBJECT_SOURCES.get(pid)
            if source_name:
                subjects = list(self.bridge_inputs.get(source_name, []))[:3]
            out.append(
                {
                    "kind": "telemetry.observation",
                    "ts": snapshot["timestamp"],
                    "window_seconds": snapshot["window_seconds"],
                    "source": "laksmi",
                    "tags": ["telemetry", "edge", "laksmi", "observation", "policy"],
                    "policy_id": pid,
                    "version": version,
                    "metric": metric,
                    "direction": direction,
                    "value": round(value, 3),
                    "enter": enter,
                    "exit": exit_,
                    "min_dwell_windows": min_dwell,
                    "cooldown_windows": cooldown,
                    "state": new_state,
                    "dwell_windows": st["dwell"],
                    "action": "observe",
                    "subject": subjects[0] if subjects else None,
                    "subjects": subjects,
                    "evidence": {"window": snapshot["timestamp"]},
                }
            )
        return out

    def policy_snapshot(self, snapshot: dict) -> list[dict]:
        """Current step-0 policy view for the mirror/dashboard (no records)."""
        view: list[dict] = []
        for (
            pid,
            metric,
            direction,
            enter,
            exit_,
            sources,
            version,
            min_dwell,
            cooldown,
        ) in self.POLICIES:
            st = self.policy_state.get(
                pid,
                {"state": "clear", "dwell": 0, "since": None, "cooldown_left": 0},
            )
            available = self._policy_source_ok(snapshot, metric, sources)
            value = self._policy_metric(snapshot, metric) if available else None
            view.append(
                {
                    "policy_id": pid,
                    "metric": metric,
                    "direction": direction,
                    "enter": enter,
                    "exit": exit_,
                    "version": version,
                    "min_dwell_windows": min_dwell,
                    "cooldown_windows": cooldown,
                    "state": st["state"],
                    "dwell_windows": st["dwell"],
                    "cooldown_left": st["cooldown_left"],
                    "since": st["since"],
                    "value": round(value, 3) if value is not None else None,
                    "source_available": available,
                }
            )
        return view

    def window_record(self, snapshot: dict, events: list[dict]) -> dict:
        """1-minute rollup window per the edge-galaxy schema."""
        return {
            "kind": "telemetry.window",
            "ts": snapshot["timestamp"],
            "window_seconds": snapshot["window_seconds"],
            "source": "laksmi",
            "tags": list(EMIT_TAGS),
            "harmony_score": snapshot["harmony_score"],
            "dims": {k: snapshot["dims"][k]["score"] for k in WEIGHTS},
            "dim_notes": {k: snapshot["dims"][k]["note"] for k in WEIGHTS},
            "guna": snapshot["guna"],
            "top": [
                {"comm": r["comm"], "share": r["cpu_share"], "guna": r["guna"]}
                for r in snapshot["top_processes"][:5]
            ],
            "events": events,
            "bridge": {
                key: self.bridge_inputs.get(key, 0)
                for key in BRIDGE_METRICS
            },
            "karma": {
                "total": self.karma_total,
                "delta": round(self.karma_delta, 3) if self.karma_delta is not None else None,
            },
            "dharma": {
                "total": (self.dharma_counts or {}).get("total", 0),
                "blocked": (self.dharma_counts or {}).get("blocked", 0),
                "delta_total": (self.dharma_deltas or {}).get("delta_total", 0),
                "delta_blocked": (self.dharma_deltas or {}).get("delta_blocked", 0),
            },
        }

    def _guna_tags(self, active: dict[int, float], sample: Sample) -> dict:
        total = sum(active.values())
        tags = {"sattvic": 0, "rajasic": 0, "tamasic": 0}
        if total <= 0:
            return tags
        for delta in active.values():
            share = delta / total
            if share >= 0.15:
                tags["rajasic"] += 1
            elif share <= 0.01:
                tags["tamasic"] += 1
            else:
                tags["sattvic"] += 1
        blocked = sum(1 for (_, _, state) in sample.procs.values() if state in ("D", "Z"))
        tags["tamasic"] += blocked
        return tags

    def _top(self, active: dict[int, float], sample: Sample) -> list[dict]:
        total = sum(active.values())
        rows = []
        for pid, delta in sorted(active.items(), key=lambda kv: -kv[1])[:10]:
            comm = sample.procs.get(pid, ("?", 0, "?"))[0]
            share = (delta / total) if total else 0.0
            if share >= 0.15:
                tag = "rajasic"
            elif share <= 0.01:
                tag = "tamasic"
            else:
                tag = "sattvic"
            rows.append({"pid": pid, "comm": comm, "cpu_share": round(share, 3), "guna": tag})
        return rows


def dim(score: float, source: str, note: str) -> dict:
    return {"score": round(clamp(score), 3), "source": source, "note": note}


def bar(score: float, width: int = 10) -> str:
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)


def render(snapshot: dict) -> str:
    lines = [
        f"Lakshmi v0 — Harmony Vector  {snapshot['timestamp']}  "
        f"(window {snapshot['window_seconds']:.0f}s)"
    ]
    for name in WEIGHTS:
        d = snapshot["dims"][name]
        lines.append(f"  {name:<15} {d['score']:.2f}  {bar(d['score'])}  {d['note']}")
    lines.append(f"  {'harmony_score':<15} {snapshot['harmony_score']:.2f}  "
                 f"{bar(snapshot['harmony_score'])}  weighted mean")
    g = snapshot["guna"]
    lines.append(f"  guna: sattvic={g['sattvic']} rajasic={g['rajasic']} tamasic={g['tamasic']}")
    lines.append("  top: " + ", ".join(
        f"{r['comm']}({r['cpu_share']:.0%},{r['guna'][:4]})" for r in snapshot["top_processes"][:5]
    ))
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Lakshmi v0 — 7-dim Harmony Vector digestor")
    ap.add_argument("--once", action="store_true", help="take two samples and exit")
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between snapshots")
    ap.add_argument("--count", type=int, default=0, help="stop after N snapshots (0 = forever)")
    ap.add_argument("--window", type=float, default=300.0, help="rolling window seconds")
    ap.add_argument("--sample-seconds", type=float, default=4.0, help="baseline gap for --once")
    ap.add_argument("--budget-watts", type=float, default=15.0, help="energy budget")
    ap.add_argument(
        "--wm-mcp",
        default="http://127.0.0.1:18790",
        help="WhiteMagic MCP endpoint for karma.report (dim 7); default home scope",
    )
    ap.add_argument("--no-wm", action="store_true", help="disable the WM karma seam (stub dim 7)")
    ap.add_argument(
        "--dharma-mcp",
        default=None,
        help=(
            "WhiteMagic MCP endpoint for dharma.status (dim 6); e.g. "
            "http://127.0.0.1:28795 for the MandalaOS VM's read-only serve"
        ),
    )
    ap.add_argument(
        "--karma-max",
        type=float,
        default=150.0,
        help="total WM debt mapped to score 0 (WM accumulates; spec's <1.0 is per-entry)",
    )
    ap.add_argument("--json", action="store_true", help="emit JSON snapshots instead of bars")
    ap.add_argument(
        "--emit",
        action="store_true",
        help="emit telemetry windows to WM (memory.create → --emit-galaxy) with local spool replay",
    )
    ap.add_argument(
        "--emit-url",
        default="http://127.0.0.1:18790",
        help="WM MCP endpoint for telemetry emission (default: home scope gateway)",
    )
    ap.add_argument(
        "--emit-galaxy",
        default="telemetry",
        help="target galaxy (use 'substrate' for servers predating the telemetry galaxy)",
    )
    ap.add_argument(
        "--emit-every",
        type=float,
        default=60.0,
        help="minimum seconds between emitted windows (0 = every snapshot); pair with --window",
    )
    ap.add_argument(
        "--emit-spool",
        default=SPOOL_DEFAULT,
        help="fail-soft ring file for unsent windows",
    )
    ap.add_argument(
        "--state-dir",
        default=STATE_DEFAULT,
        help="dashboard mirror directory (latest.json + history.jsonl; written when --emit)",
    )
    ap.add_argument(
        "--emit-no-thresholds",
        action="store_true",
        help="suppress bus.emit threshold events (window records still sent)",
    )
    ap.add_argument(
        "--bridge-feed",
        default=None,
        help="collector sent-log ring read for bridge inputs "
        f"(default: {BRIDGE_FEED_DEFAULT}; empty string disables)",
    )
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    karma_env = os.environ.get("LAKSHMI_KARMA_DEBT")
    karma_override = float(karma_env) if karma_env is not None else None
    engine = Lakshmi(
        window=args.window,
        budget_watts=args.budget_watts,
        karma_debt=karma_override,
        wm_mcp=None if args.no_wm else args.wm_mcp,
        karma_max=args.karma_max,
        dharma_mcp=args.dharma_mcp,
    )

    stop = {"flag": False}

    def handle(_sig: int, _frame: object) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    # Edge galaxy: spool first, replay oldest-first, never let WM being down
    # affect OS sampling (rule 4).
    spool = WindowSpool(args.emit_spool) if args.emit else None
    mirror = Mirror(args.state_dir) if args.emit else None
    router = actuator.Router()
    if spool is not None:
        pending = spool.load()
        if pending:
            print(
                f"emit: {pending} spooled window(s) pending replay → {args.emit_url}",
                file=sys.stderr,
            )
    emit_state = {"last": 0.0, "sent": 0, "last_error": None, "bridge_since": None}

    def do_emit(snapshot: dict, force: bool) -> None:
        if spool is None:
            return
        now = time.monotonic()
        if (
            not force
            and args.emit_every > 0
            and (now - emit_state["last"]) < args.emit_every
        ):
            return
        emit_state["last"] = now
        events = engine.threshold_events(snapshot)
        # Yama v0 bridge: read the WM-side signals since the previous window
        # (an unreachable feed holds policy state instead of clearing it).
        since = emit_state["bridge_since"] or snapshot["timestamp"]
        engine.bridge_inputs = fetch_bridge_inputs(
            args.emit_url, since, feed_path=args.bridge_feed
        )
        emit_state["bridge_since"] = snapshot["timestamp"]
        observations, notifications = router.route(engine.policy_observations(snapshot))
        record = engine.window_record(snapshot, events)
        record["actuation"] = {"armed": router.armed, "applied": len(notifications)}
        spool.append(record)
        spool.save()
        sent, err = spool.flush(args.emit_url, args.emit_galaxy)
        # Persist the post-flush state (drained entries), otherwise the next
        # load would replay windows that already reached WM.
        spool.save()
        emit_state["sent"] = sent
        emit_state["last_error"] = err
        if mirror is not None:
            mirror.write(
                snapshot,
                record,
                {
                    "sent": sent,
                    "last_error": err,
                    "spool_pending": len(spool.entries),
                    "endpoint": args.emit_url,
                    "galaxy": args.emit_galaxy,
                    "policies": actuator.annotate_policies(
                        engine.policy_snapshot(snapshot), router
                    ),
                },
            )
            mirror.write_observations(observations)
        if sent:
            print(
                f"emit: {sent} window(s) → {args.emit_galaxy} "
                f"(spool {len(spool.entries)})",
                file=sys.stderr,
            )
        if err:
            print(
                f"emit: WM unreachable ({err}); "
                f"{len(spool.entries)} window(s) spooled",
                file=sys.stderr,
            )
        if sent and not args.emit_no_thresholds:
            for event in events:
                reply = emit_threshold_event(args.emit_url, event)
                if reply is None or "_error" in reply or reply.get("status") != "success":
                    print(
                        f"emit: threshold event dropped ({event['topic']})",
                        file=sys.stderr,
                    )
        if sent:
            for observation in observations:
                reply = emit_observation(args.emit_url, args.emit_galaxy, observation)
                if reply is None or "_error" in reply or reply.get("status") not in (
                    "success",
                    "deduplicated",
                ):
                    print(
                        "emit: observation dropped "
                        f"({observation['policy_id']} {observation['state']})",
                        file=sys.stderr,
                    )
        if sent:
            for notification in notifications:
                payload = actuator.notify_payload(notification)
                reply = emit_actuation_notify(args.emit_url, payload)
                if reply is None or "_error" in reply or reply.get("status") != "success":
                    print(
                        "emit: actuation notify dropped "
                        f"({notification['policy_id']})",
                        file=sys.stderr,
                    )

    first = Sample()
    engine.add(first)
    if args.once:
        time.sleep(args.sample_seconds)
        second = Sample()
        engine.add(second)
        snapshot = engine.vector(second)
        do_emit(snapshot, force=True)
        if args.json:
            json.dump(snapshot, sys.stdout, indent=2)
            print()
        else:
            print(render(snapshot))
        return 0

    count = 0
    while not stop["flag"]:
        time.sleep(args.interval)
        sample = Sample()
        engine.add(sample)
        snapshot = engine.vector(sample)
        do_emit(snapshot, force=False)
        if mirror is not None:
            mirror.write_live(
                snapshot,
                {
                    "sent": emit_state["sent"],
                    "last_error": emit_state["last_error"],
                    "spool_pending": len(spool.entries) if spool else 0,
                    "endpoint": args.emit_url,
                    "galaxy": args.emit_galaxy,
                    "kind": "fast_lane",
                    "policies": actuator.annotate_policies(
                        engine.policy_snapshot(snapshot), router
                    ),
                },
            )
        if args.json:
            print(json.dumps(snapshot))
        else:
            print(render(snapshot))
            print()
        sys.stdout.flush()
        count += 1
        if args.count and count >= args.count:
            break
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
