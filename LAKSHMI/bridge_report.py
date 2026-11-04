#!/usr/bin/env python3
"""bridge_report — per-policy observation summary for promotion reviews.

Reads the telemetry galaxy (``memory.list`` for the inventory, ``memory.read``
for full records, paced) and reports, per policy:

- decision records by state (observing / confirmed / clear), first/last, per-day
- input records (Tetragon / sandbox observations) in range
- **false-positive candidates**: for input-fed policies, observing/confirmed
  decisions with no matching input record inside the decision window ± grace
  (the evidence needed before a policy may climb the actuator ladder)

Read-only; no writes. Promotions per `design/ACTUATOR_CONTRACT_2026-09-15.md`.

Usage:
  python3 bridge_report.py --hours 168
  python3 bridge_report.py --endpoint http://127.0.0.1:18790 --hours 24 \
      --json /tmp/bridge.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from wm_mcp import call_tool
from datetime import datetime, timedelta, timezone

DEFAULT_ENDPOINT = "http://127.0.0.1:18790"
PAGE = 1000
MAX_RECORDS = 800
GRACE_BEFORE = 90.0
GRACE_AFTER = 150.0

# Input metrics and the policy they feed (bridge design §2).
INPUT_METRICS = {
    "tetragon.shadow_access": "shadow.access.v1",
    "sandbox_unconfined": "spawn.undeclared.v1",
    "sandbox_degraded": "sandbox.degraded.v1",
}


def mcp_call(endpoint: str, tool: str, arguments: dict, timeout: float = 15.0) -> dict:
    return call_tool(endpoint, tool, arguments, timeout)

def parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def fetch_rows(endpoint: str) -> tuple[list[dict], str | None]:
    rows: list[dict] = []
    offset = 0
    while True:
        reply = mcp_call(
            endpoint, "memory.list", {"galaxy": "telemetry", "limit": PAGE, "offset": offset}
        )
        if "_error" in reply:
            return rows, reply["_error"]
        page = reply.get("memories", [])
        rows.extend(page)
        matched = int(reply.get("matched", len(rows)))
        offset += PAGE
        if len(page) < PAGE or offset >= matched or offset > 100_000:
            return rows, None


def read_record(endpoint: str, memory_id: str) -> dict | None:
    reply = mcp_call(endpoint, "memory.read", {"id": memory_id, "galaxy": "telemetry"})
    if "_error" in reply:
        return None
    content = reply.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return None
    return content if isinstance(content, dict) else None


def in_range(record: dict, cutoff: datetime) -> bool:
    stamp = parse_ts(record.get("ts"))
    return stamp is not None and stamp >= cutoff


def summarize(decisions: list[dict], inputs: list[dict], cutoff: datetime) -> dict:
    by_policy: dict[str, dict] = {}
    for record in decisions:
        policy_id = str(record.get("policy_id") or "unknown")
        entry = by_policy.setdefault(
            policy_id,
            {"states": {}, "first": None, "last": None, "records": [], "days": {}},
        )
        state = str(record.get("state") or "?")
        entry["states"][state] = entry["states"].get(state, 0) + 1
        entry["records"].append(record)
        stamp = parse_ts(record.get("ts"))
        if stamp:
            entry["first"] = min(filter(None, [entry["first"], stamp]))
            entry["last"] = max(filter(None, [entry["last"], stamp]))
            day = stamp.date().isoformat()
            entry["days"][day] = entry["days"].get(day, 0) + 1

    inputs_by_metric: dict[str, list[datetime]] = {}
    for record in inputs:
        metric = record.get("metric")
        stamp = parse_ts(record.get("ts"))
        if metric and stamp:
            inputs_by_metric.setdefault(metric, []).append(stamp)

    candidates = []
    for policy_id, entry in sorted(by_policy.items()):
        fed_by = [m for m, p in INPUT_METRICS.items() if p == policy_id]
        entry["input_metric"] = fed_by[0] if fed_by else None
        entry["input_records"] = sum(len(inputs_by_metric.get(m, [])) for m in fed_by)
        if fed_by:
            stamps = inputs_by_metric.get(fed_by[0], [])
            for record in entry["records"]:
                if record.get("state") not in ("observing", "confirmed"):
                    continue
                stamp = parse_ts(record.get("ts"))
                if not stamp:
                    continue
                window = float(record.get("window_seconds") or 60.0)
                lo = stamp - timedelta(seconds=window + GRACE_BEFORE)
                hi = stamp + timedelta(seconds=window + GRACE_AFTER)
                if not any(lo <= s <= hi for s in stamps):
                    candidates.append(
                        {
                            "policy_id": policy_id,
                            "ts": stamp.isoformat(),
                            "state": record.get("state"),
                            "value": record.get("value"),
                        }
                    )

    report = {
        "policies": {},
        "false_positive_candidates": candidates,
        "input_totals": {m: len(v) for m, v in sorted(inputs_by_metric.items())},
        "range_start": cutoff.isoformat(),
    }
    for policy_id, entry in sorted(by_policy.items()):
        report["policies"][policy_id] = {
            "states": entry["states"],
            "first": entry["first"].isoformat() if entry["first"] else None,
            "last": entry["last"].isoformat() if entry["last"] else None,
            "per_day": entry["days"],
            "input_metric": entry["input_metric"],
            "input_records": entry["input_records"],
        }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="per-policy observation summary (read-only)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--hours", type=float, default=168.0)
    parser.add_argument("--json", dest="json_path", help="write the report as JSON")
    parser.add_argument("--read-delay", type=float, default=0.3)
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS)
    args = parser.parse_args(argv)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    rows, error = fetch_rows(args.endpoint)
    if error:
        print(f"bridge-report: FAIL — feed unreachable ({error})")
        return 1

    observation_ids = [
        row for row in rows if "observation" in (row.get("tags") or [])
    ][: args.max_records]
    decisions, inputs, unreadable = [], [], 0
    for index, row in enumerate(observation_ids, start=1):
        record = read_record(args.endpoint, row.get("id", ""))
        if record is None:
            unreadable += 1
        elif not in_range(record, cutoff):
            continue
        elif record.get("metric") in INPUT_METRICS and record.get("state") == "observed":
            inputs.append(record)
        elif record.get("policy_id") and record.get("state"):
            decisions.append(record)
        if index % 100 == 0:
            print(f"  reading: {index}/{len(observation_ids)}", file=sys.stderr)
        if args.read_delay > 0:
            time.sleep(args.read_delay)

    report = summarize(decisions, inputs, cutoff)
    report.update(
        {
            "endpoint": args.endpoint,
            "hours": args.hours,
            "scanned": len(observation_ids),
            "unreadable": unreadable,
            "decisions": len(decisions),
            "inputs": len(inputs),
        }
    )

    print(f"bridge-report — last {args.hours:g}h at {args.endpoint}")
    print(f"  scanned={len(observation_ids)} decisions={len(decisions)} inputs={len(inputs)} unreadable={unreadable}")
    for policy_id, entry in sorted(report["policies"].items()):
        states = ", ".join(f"{k}={v}" for k, v in sorted(entry["states"].items()))
        print(
            f"  {policy_id}: {states} | first={entry['first']} last={entry['last']}"
            + (f" | inputs={entry['input_records']}" if entry["input_metric"] else "")
        )
        per_day = entry.get("per_day") or {}
        if per_day:
            days = ", ".join(f"{d}:{n}" for d, n in sorted(per_day.items()))
            print(f"    per-day: {days}")
    candidates = report["false_positive_candidates"]
    print(f"  false-positive candidates: {len(candidates)}")
    for candidate in candidates[:10]:
        print(f"    {candidate['ts']} {candidate['policy_id']} {candidate['state']} value={candidate['value']}")
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
        print(f"  report → {args.json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
