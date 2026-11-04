#!/usr/bin/env python3
"""yama-collector — Tetragon observe events → WM telemetry observations.

Yama v0 bridge, collector leg (design: MANDALA_OS/implementation/
yama-v0-bridge-design.md §2, slice S2).

Reads newline-delimited Tetragon JSON (e.g. `tetra getevents -o json`) or a
JSON file, maps matching events to observation records, and posts them to a
writable WhiteMagic MCP endpoint via the same transport Lakshmi uses.

Observe-only: records carry `action: observe`. No enforcement happens here —
the step-0 policy engine (Lakshmi) owns transitions per the hysteresis
contract in `design/ACTUATION_HYSTERESIS_2026-09-13.md`.

Fail-soft (rule 4): records are spooled to a bounded local ring file when WM
is unreachable, and replayed oldest-first on the next successful run. OS
safety never depends on WM being up.

Read-back: every record that reached WM is also appended to a bounded local
feed (`--sent-log`) that Lakshmi reads mirror-first — `memory.search` is
FTS-ranked, so the newest bridge records cannot be guaranteed to appear in
its result window. Only sent records are logged, so the feed never fabricates
evidence while WM is down.

Usage:
    tetra getevents -o json | yama-collector.py --follow
    yama-collector.py --input tetragon.jsonl --dry-run
    yama-collector.py --endpoint http://127.0.0.1:28795   # VM read-only? use a writable one

`--follow` streams stdin line-by-line and flushes aggregated observations every
`--flush-interval` seconds (and on SIGTERM/SIGINT/EOF), so it can run under
systemd against a `tetra getevents` pipeline without waiting for EOF. Without
`--follow` the collector keeps the original batch behaviour (read to EOF, then
send).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import urllib.request
from datetime import datetime, timezone

ENDPOINT_DEFAULT = "http://127.0.0.1:18790"
SPOOL_DEFAULT = os.path.expanduser("~/.local/share/yama-collector/spool.jsonl")
SPOOL_MAX = 2000
SENT_LOG_DEFAULT = os.path.expanduser("~/.local/share/yama-collector/sent.jsonl")
SENT_LOG_MAX = 1000  # recent sent records, read back by Lakshmi as the bridge feed
FOLLOW_MAX_BATCH = 500  # flush early when a burst exceeds this many hits
TAGS = ["telemetry", "edge", "yama", "observation"]

# v0 policy map (design §2). Matching is deliberately liberal: the function
# name and path substring must appear among the event's string values, so
# schema drift in Tetragon's JSON does not silently drop observations.
POLICIES = {
    "shadow.access.v1": {
        "metric": "tetragon.shadow_access",
        "function": "security_file_open",
        "path_substr": "/etc/shadow",
    },
}


# ── MCP transport (mirrors LAKSHMI/lakshmi.py:call_wm_tool) ───────────


def call_wm_tool(
    endpoint: str, tool: str, arguments: dict | None = None, timeout: float = 4.0
) -> dict | None:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        }
    ).encode()
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/mcp",
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
    except Exception as exc:  # noqa: BLE001 — fail-soft by design
        return {"_error": str(exc)}


def emit_observation(endpoint: str, record: dict, timeout: float = 6.0) -> dict | None:
    """POST one observation. Typed path first; `memory.create` for pre-9.1.5."""
    typed = call_wm_tool(
        endpoint, "telemetry.record", {"record": record, "source": "tetragon"}, timeout
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
            "galaxy": "telemetry",
            "tags": record["tags"],
            "title": f"telemetry.observation {record['policy_id']} {record['state']}",
            "importance": 0.3,
            "source": "tetragon",
        },
        timeout=timeout,
    )


# ── Event mapping ──────────────────────────────────────────────────────


def walk_strings(node) -> list[str]:
    """Collect every string value in a nested JSON structure."""
    found: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            found.append(current)
        elif isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


def walk_identity(node, out: dict) -> None:
    """Collect process identity hints (binary/comm/pid) from anywhere."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("binary", "comm") and isinstance(value, str):
                out.setdefault(key, value)
            elif key == "pid" and isinstance(value, int):
                out.setdefault("pid", value)
            else:
                walk_identity(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_identity(item, out)


def subject_for(identity: dict) -> str | None:
    """Stable subject handle (contract §2): ``proc:<comm>:<binary-basename>``.

    Never pid-only — comm/binary survive pid reuse; the pid stays in the
    evidence for the audit trail.
    """
    comm = identity.get("comm")
    binary = identity.get("binary")
    if comm and binary:
        return f"proc:{comm}:{os.path.basename(binary)}"
    if comm:
        return f"proc:{comm}"
    if binary:
        return f"proc:{os.path.basename(binary)}"
    return None


def classify(event: dict) -> dict | None:
    """Return a policy hit for the event, or None. Liberal string matching."""
    strings = walk_strings(event)
    for policy_id, spec in POLICIES.items():
        if not any(spec["function"] in s for s in strings):
            continue
        if not any(spec["path_substr"] in s for s in strings):
            continue
        identity: dict = {}
        walk_identity(event, identity)
        evidence = " ".join(f"{k}={v}" for k, v in sorted(identity.items()))
        return {
            "policy_id": policy_id,
            "metric": spec["metric"],
            "evidence": evidence,
            "subject": subject_for(identity),
        }
    return None


def build_records(hits: list[dict]) -> list[dict]:
    """Aggregate a batch of hits into one observation record per policy."""
    grouped: dict[str, list[dict]] = {}
    for hit in hits:
        grouped.setdefault(hit["policy_id"], []).append(hit)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    records = []
    for policy_id, items in sorted(grouped.items()):
        samples = []
        subjects: list[str] = []
        for item in items:
            if item["evidence"] and item["evidence"] not in samples:
                samples.append(item["evidence"])
            subject = item.get("subject")
            if subject and subject not in subjects:
                subjects.append(subject)
            if len(samples) == 3 and len(subjects) == 3:
                break
        records.append(
            {
                "kind": "telemetry.observation",
                "ts": now,
                "policy_id": policy_id,
                "metric": items[0]["metric"],
                "state": "observed",
                "action": "observe",
                "value": len(items),
                "subject": subjects[0] if subjects else None,
                "subjects": subjects[:3],
                "evidence": samples,
                "tags": TAGS,
            }
        )
    return records


def iter_events(stream) -> tuple[list[dict], int]:
    """Parse newline-delimited JSON (or one JSON array); return (events, bad)."""
    text = stream.read().strip()
    events: list[dict] = []
    bad = 0
    if not text:
        return events, bad
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            return [e for e in parsed if isinstance(e, dict)], 0
        except json.JSONDecodeError:
            return [], 1
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            bad += 1
    return events, bad


# ── Spool (bounded local ring, replayed oldest-first) ──────────────────


def spool_load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


def spool_write(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kept = records[-SPOOL_MAX:]
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for record in kept:
            fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    os.replace(tmp, path)


def sent_log_write(path: str, records: list[dict]) -> None:
    """Append sent records to the bounded bridge feed ring (oldest trimmed).

    Lakshmi reads this ring mirror-first, deduped against its store search by
    ``(ts, policy_id)``; the galaxy stays the durable record.
    """
    if not records:
        return
    kept = (spool_load(path) + records)[-SENT_LOG_MAX:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for record in kept:
            fh.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    os.replace(tmp, path)


def replay_spool(endpoint: str, path: str, timeout: float) -> tuple[list[dict], list[dict]]:
    """Send spooled records oldest-first; return (sent records, still_pending)."""
    pending = spool_load(path)
    sent: list[dict] = []
    while pending:
        reply = emit_observation(endpoint, pending[0], timeout)
        if isinstance(reply, dict) and "_error" not in reply:
            sent.append(pending.pop(0))
        else:
            break
    if pending or os.path.exists(path):
        spool_write(path, pending)
    return sent, pending


def send_records(args, records: list[dict]) -> tuple[int, int, list[dict]]:
    """Replay the spool, then send fresh records; return (replayed, sent, failed).

    Every record that reached WM — replayed or fresh — is appended to the
    sent-log feed so Lakshmi can read the newest bridge records without
    relying on FTS ranking.
    """
    replayed: list[dict] = []
    pending: list[dict] = []
    if not args.no_spool:
        replayed, pending = replay_spool(args.endpoint, args.spool, args.timeout)
    sent: list[dict] = []
    failed = list(pending)
    for record in records:
        reply = emit_observation(args.endpoint, record, args.timeout)
        if isinstance(reply, dict) and "_error" not in reply:
            sent.append(record)
        else:
            failed.append(record)
    if failed and not args.no_spool:
        spool_write(args.spool, failed)
    if not args.no_sent_log:
        sent_log_write(args.sent_log, replayed + sent)
    return len(replayed), len(sent), failed


# ── Follow mode (streaming, systemd-friendly) ──────────────────────────


def follow_stream(stream, args) -> int:
    """Consume newline-delimited JSON as it arrives, flushing on an interval.

    Aggregates hits per policy and flushes every ``--flush-interval`` seconds
    (or when a burst exceeds ``FOLLOW_MAX_BATCH``), so records land while the
    upstream `tetra getevents` pipeline stays open. SIGTERM/SIGINT/EOF flush
    whatever is buffered before exit; spool semantics are unchanged.
    """
    hits: list[dict] = []
    state = {"events": 0, "malformed": 0, "replayed": 0, "sent": 0, "spooled": 0, "flushes": 0}
    last_flush = time.monotonic()

    def flush(reason: str) -> None:
        nonlocal hits, last_flush
        if hits:
            records = build_records(hits)
            hits = []
            if args.dry_run:
                for record in records:
                    print(json.dumps(record, indent=2, sort_keys=True))
                print(json.dumps({"flush": reason, "records": len(records),
                                  "mode": "dry-run"}), file=sys.stderr)
            else:
                replayed, sent, failed = send_records(args, records)
                state["replayed"] += replayed
                state["sent"] += sent
                state["spooled"] += len(failed)
                print(json.dumps({"flush": reason, "records": len(records),
                                  "sent": sent, "replayed": replayed,
                                  "spooled": len(failed)}), file=sys.stderr)
            state["flushes"] += 1
        last_flush = time.monotonic()

    def handle(_sig: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                state["malformed"] += 1
                continue
            if not isinstance(event, dict):
                state["malformed"] += 1
                continue
            state["events"] += 1
            hit = classify(event)
            if hit is not None:
                hits.append(hit)
            if hits and (
                len(hits) >= FOLLOW_MAX_BATCH
                or time.monotonic() - last_flush >= args.flush_interval
            ):
                flush("interval")
    except KeyboardInterrupt:
        pass
    finally:
        flush("exit")

    print(json.dumps({
        "events": state["events"],
        "malformed": state["malformed"],
        "sent": state["sent"],
        "replayed": state["replayed"],
        "spooled": state["spooled"],
        "flushes": state["flushes"],
        "mode": "follow",
    }))
    return 0


# ── Main ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Tetragon → WM observation collector")
    parser.add_argument("--input", help="Tetragon JSON file (default: stdin)")
    parser.add_argument("--endpoint", default=ENDPOINT_DEFAULT)
    parser.add_argument("--spool", default=SPOOL_DEFAULT)
    parser.add_argument("--no-spool", action="store_true", help="disable spooling")
    parser.add_argument(
        "--sent-log",
        default=SENT_LOG_DEFAULT,
        help="bounded feed of sent records read by Lakshmi "
        "(default: ~/.local/share/yama-collector/sent.jsonl)",
    )
    parser.add_argument(
        "--no-sent-log", action="store_true", help="disable the sent-record feed"
    )
    parser.add_argument("--dry-run", action="store_true", help="print, do not send")
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument(
        "--follow",
        action="store_true",
        help="stream newline-delimited events line-by-line (tails stdin/file)",
    )
    parser.add_argument(
        "--flush-interval",
        type=float,
        default=5.0,
        help="seconds between aggregated flushes in --follow mode (default 5)",
    )
    args = parser.parse_args()

    if args.follow:
        if args.input:
            try:
                with open(args.input, encoding="utf-8") as fh:
                    return follow_stream(fh, args)
            except OSError as exc:
                print(json.dumps({"error": f"cannot read input: {exc}"}), file=sys.stderr)
                return 1
        return follow_stream(sys.stdin, args)

    if args.input:
        try:
            with open(args.input, encoding="utf-8") as fh:
                events, bad = iter_events(fh)
        except OSError as exc:
            print(json.dumps({"error": f"cannot read input: {exc}"}), file=sys.stderr)
            return 1
    else:
        events, bad = iter_events(sys.stdin)

    hits = [hit for event in events if (hit := classify(event)) is not None]
    records = build_records(hits)

    if args.dry_run:
        for record in records:
            print(json.dumps(record, indent=2, sort_keys=True))
        summary = {
            "events": len(events),
            "malformed": bad,
            "matched": len(hits),
            "records": len(records),
            "mode": "dry-run",
        }
        print(json.dumps(summary), file=sys.stderr)
        return 0

    replayed, sent, failed = send_records(args, records)

    summary = {
        "events": len(events),
        "malformed": bad,
        "matched": len(hits),
        "records": len(records),
        "replayed": replayed,
        "sent": sent,
        "spooled": len(failed),
    }
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
