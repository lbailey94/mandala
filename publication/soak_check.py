#!/usr/bin/env python3
"""soak_check — edge-galaxy soak continuity evidence for the publication gate.

**Gate definition (redefined 2026-09-15, public):** the soak passes when the
current uninterrupted run holds **≥ 72 h of accumulated *active* soak time**
(wall-clock minus declared host-suspend intervals), with **no non-suspend gap
> 150 s**, cadence ≥ 98 % of one window per active minute, suspend/resume
disclosed from the host journal, and resume latency ≤ 300 s. Suspend intervals
are excluded because a sleeping machine is not a software stall; everything
else (restarts, crashes, stalls) still resets the run.

Read-only. Sources, disclosed per check:

1. **Store coverage** — enumerate the telemetry galaxy over MCP
   (`memory.list`, paged); window `created_at` for the full span.
2. **Local mirror continuity** — the samplers' `history.jsonl` carries the
   record `ts`; replay-masked outages in the last ≤ 48 h surface as true gaps.
3. **Spot reads** — a few `memory.read` calls compare record `ts` with
   `created_at` (paced; the dev serve rate-limits bursts).
4. **Suspend intervals** — `--suspend-journal` (journalctl `PM: suspend
   entry/exit`), `--suspend-file`, or repeated `--suspend START,END` (ISO-8601).

Exit 0 = PASS, 1 = FAIL.

Usage:
  python3 soak_check.py --suspend-journal
  python3 soak_check.py --endpoint http://127.0.0.1:18790 \
      --mirror ~/.local/share/lakshmi/history.jsonl --suspend-journal
  python3 soak_check.py --json publication/evidence_<date>/soak_18798.json --suspend-journal
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

DEFAULT_ENDPOINT = "http://127.0.0.1:18798"
MIRROR_CANDIDATES = (
    "~/.local/share/lakshmi-edge/history.jsonl",
    "~/.local/share/lakshmi/history.jsonl",
)
PAGE = 1000
FULL_TS_CAP = 400
RATE_LIMIT_HINTS = ("rate limited", "too many")
SUSPEND_ENTRY = re.compile(r"PM:\s*suspend entry")
SUSPEND_EXIT = re.compile(r"PM:\s*suspend exit")
JOURNAL_TS = re.compile(r"^(\S+)\s")


# ── MCP transport ──────────────────────────────────────────────────────


def mcp_call(endpoint: str, tool: str, arguments: dict, timeout: float = 15.0) -> dict:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
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
    except Exception as exc:
        return {"_error": str(exc)}
    if "error" in outer:
        return {"_error": (outer.get("error") or {}).get("message", "json-rpc error")}
    try:
        return json.loads(outer["result"]["content"][0]["text"])
    except Exception as exc:
        return {"_error": f"unparseable reply: {exc}"}


def is_rate_limit(reply: dict) -> bool:
    message = str(reply.get("_error", "")).lower()
    return any(hint in message for hint in RATE_LIMIT_HINTS)


def fetch_records(endpoint: str) -> tuple[list[dict], str | None]:
    rows: list[dict] = []
    offset = 0
    while True:
        reply = mcp_call(
            endpoint,
            "memory.list",
            {"galaxy": "telemetry", "limit": PAGE, "offset": offset},
        )
        if "_error" in reply:
            return rows, reply["_error"]
        page = reply.get("memories", [])
        rows.extend(page)
        matched = int(reply.get("matched", len(rows)))
        offset += PAGE
        if len(page) < PAGE or offset >= matched or offset > 100_000:
            return rows, None


# ── time helpers ───────────────────────────────────────────────────────


def parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    # journalctl short-iso emits +0000 without a colon
    if re.search(r"[+-]\d{4}$", text):
        text = text[:-5] + text[-5:-2] + ":" + text[-2:]
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def window_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if "window" in (row.get("tags") or [])]


def suspend_overlap(start: datetime, end: datetime, suspends: list) -> float:
    total = 0.0
    for sup_start, sup_end in suspends:
        lo = max(start, sup_start)
        hi = min(end, sup_end)
        if hi > lo:
            total += (hi - lo).total_seconds()
    return total


# ── suspend sources ────────────────────────────────────────────────────


def suspends_from_journal(since: datetime) -> tuple[list, str | None]:
    cmd = [
        "journalctl",
        "-k",
        "--utc",
        "-o",
        "short-iso",
        "--no-pager",
        "--since",
        since.strftime("%Y-%m-%d %H:%M:%S"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # journalctl missing or refused
        return [], str(exc)
    if proc.returncode != 0:
        return [], (proc.stderr.strip() or "journalctl failed")
    entries: list[datetime] = []
    exits: list[datetime] = []
    for line in proc.stdout.splitlines():
        stamp = None
        match = JOURNAL_TS.match(line)
        if match:
            stamp = parse_ts(match.group(1))
        if stamp is None:
            continue
        if SUSPEND_ENTRY.search(line):
            entries.append(stamp)
        elif SUSPEND_EXIT.search(line):
            exits.append(stamp)
    suspends = []
    for stamp in entries:
        after = [x for x in exits if x > stamp]
        if after:
            suspends.append((stamp, min(after)))
    return suspends, None


def suspends_from_file(path: str) -> list:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[,\s]+", line)
            if len(parts) < 2:
                continue
            start, end = parse_ts(parts[0]), parse_ts(parts[1])
            if start and end and end > start:
                out.append((start, end))
    return out


def suspends_from_args(specs: list[str] | None) -> list:
    out = []
    for spec in specs or []:
        parts = re.split(r"[,;]", spec)
        if len(parts) != 2:
            continue
        start, end = parse_ts(parts[0]), parse_ts(parts[1])
        if start and end and end > start:
            out.append((start, end))
    return out


# ── analysis ───────────────────────────────────────────────────────────


def analyze(stamps: list[datetime], gap_seconds: float, suspends: list) -> dict:
    """Full-history numbers plus the current uninterrupted active run."""
    stamps = sorted(stamps)
    out: dict = {"timestamped": len(stamps)}
    if not stamps:
        return out
    first, last = stamps[0], stamps[-1]
    span_seconds = (last - first).total_seconds()
    total_suspend = suspend_overlap(first, last, suspends)

    gaps = []
    for prev, cur in zip(stamps, stamps[1:]):
        delta = (cur - prev).total_seconds()
        if delta <= gap_seconds:
            continue
        covered = suspend_overlap(prev, cur, suspends)
        active = max(0.0, delta - covered)
        gaps.append(
            {
                "from": prev.isoformat(),
                "to": cur.isoformat(),
                "seconds": round(delta, 1),
                "suspend_seconds": round(covered, 1),
                "active_seconds": round(active, 1),
                "kind": "suspend" if active <= gap_seconds else "active",
            }
        )

    active_gaps = [g for g in gaps if g["kind"] == "active"]
    run_start = parse_ts(active_gaps[-1]["to"]) if active_gaps else first
    run_suspend = suspend_overlap(run_start, last, suspends)
    active_run = (last - run_start).total_seconds() - run_suspend
    active_run_minutes = active_run / 60.0
    run_stamps = [s for s in stamps if s >= run_start]
    run_gaps = [g for g in gaps if (parse_ts(g["from"]) or first) >= run_start]
    run_active_gap_max = max((g["active_seconds"] for g in run_gaps), default=0.0)

    out.update(
        {
            "first": first.isoformat(),
            "last": last.isoformat(),
            "span_hours": round(span_seconds / 3600.0, 2),
            "suspend_hours": round(total_suspend / 3600.0, 2),
            "run_start": run_start.isoformat(),
            "active_run_hours": round(active_run / 3600.0, 2),
            "active_run_suspend_hours": round(run_suspend / 3600.0, 2),
            "gap_count": len(gaps),
            "active_gap_count": len(active_gaps),
            "gaps": gaps[-10:],
            "max_gap_seconds": round(max((g["seconds"] for g in gaps), default=0.0), 1),
            "max_active_gap_seconds": round(
                max((g["active_seconds"] for g in active_gaps), default=0.0), 1
            ),
            "run_active_gap_seconds": round(run_active_gap_max, 1),
            "cadence_ratio": round(len(run_stamps) / active_run_minutes, 4)
            if active_run_minutes
            else None,
        }
    )

    resume = []
    for sup_start, sup_end in suspends:
        if sup_end < first or sup_end > last:
            continue
        after = [s for s in stamps if s >= sup_end]
        latency = (after[0] - sup_end).total_seconds() if after else None
        resume.append(
            {
                "suspend_end": sup_end.isoformat(),
                "resume_latency_seconds": round(latency, 1) if latency is not None else None,
            }
        )
    out["resume"] = resume
    out["max_resume_latency_seconds"] = round(
        max((r["resume_latency_seconds"] or 0.0 for r in resume), default=0.0), 1
    )
    out["suspends"] = [
        {"start": s.isoformat(), "end": e.isoformat(), "hours": round((e - s).total_seconds() / 3600.0, 2)}
        for s, e in suspends
    ]
    return out


def mirror_path(explicit: str | None) -> str | None:
    if explicit:
        return os.path.expanduser(explicit)
    for candidate in MIRROR_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.exists(path):
            return path
    return None


def analyze_mirror(path: str | None, gap_seconds: float, suspends: list) -> dict:
    if not path:
        return {"available": False}
    stamps: list[datetime] = []
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
                stamp = None
                if isinstance(record, dict):
                    stamp = parse_ts(record.get("ts"))
                    if record.get("kind") == "telemetry.window" and stamp:
                        stamps.append(stamp)
    except OSError:
        return {"available": False, "path": path}
    coverage = analyze(stamps, gap_seconds, suspends)
    coverage.update({"available": True, "path": path})
    return coverage


def read_window_ts(endpoint: str, row: dict) -> datetime | None:
    reply = mcp_call(endpoint, "memory.read", {"id": row.get("id"), "galaxy": "telemetry"})
    if "_error" in reply:
        return None
    content = reply.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return None
    if not isinstance(content, dict):
        return None
    return parse_ts(content.get("ts"))


def spot_stamps(
    endpoint: str, windows: list[dict], count: int, delay: float, suspends: list
) -> dict:
    if not windows or count <= 0:
        return {"checked": 0}
    picks = sorted(
        {0, len(windows) // 4, len(windows) // 2, (3 * len(windows)) // 4, len(windows) - 1}
    )
    deltas, covered = [], 0
    for index in picks[:count]:
        row = windows[index]
        record_ts = read_window_ts(endpoint, row)
        created = parse_ts(row.get("created_at"))
        if not record_ts or not created:
            if delay > 0:
                time.sleep(delay)
            continue
        delta = abs((created - record_ts).total_seconds())
        lo, hi = sorted((record_ts, created))
        overlap = suspend_overlap(lo, hi, suspends)
        by_suspend = overlap >= max(0.0, delta - 300.0) and delta > 300.0
        if by_suspend:
            covered += 1
        else:
            deltas.append(
                {
                    "record_ts": record_ts.isoformat(),
                    "created_at": created.isoformat(),
                    "delta_seconds": round(delta, 1),
                }
            )
        if delay > 0:
            time.sleep(delay)
    return {
        "checked": len(deltas) + covered,
        "suspend_covered": covered,
        "max_delta_seconds": round(max((d["delta_seconds"] for d in deltas), default=0.0), 1),
        "deltas": deltas,
    }


# ── main ───────────────────────────────────────────────────────────────


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="edge-galaxy soak continuity evidence (read-only)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--hours", type=float, default=72.0)
    parser.add_argument("--gap-seconds", type=float, default=150.0)
    parser.add_argument("--min-ratio", type=float, default=0.95)
    parser.add_argument("--mirror", default=None, help="sampler history.jsonl (default: auto-detect)")
    parser.add_argument("--no-mirror", action="store_true", help="skip mirror analysis")
    parser.add_argument(
        "--suspend-journal",
        action="store_true",
        help="extract host suspend intervals from journalctl (PM: suspend entry/exit)",
    )
    parser.add_argument("--suspend-file", default=None, help="lines of 'START END' ISO timestamps")
    parser.add_argument(
        "--suspend",
        action="append",
        help="one suspend interval 'START,END' (repeatable)",
    )
    parser.add_argument("--full-ts", action="store_true", help=f"read up to {FULL_TS_CAP} window records (paced)")
    parser.add_argument("--read-delay", type=float, default=1.0, help="seconds between memory.read calls")
    parser.add_argument("--json", dest="json_path", help="write the report as JSON")
    args = parser.parse_args(argv)

    suspends = suspends_from_args(args.suspend)
    if args.suspend_file:
        suspends.extend(suspends_from_file(args.suspend_file))
    report: dict = {
        "endpoint": args.endpoint,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "gate": "72h accumulated active soak time; suspend excluded but disclosed; no non-suspend gap > 150s",
        "thresholds": {
            "hours": args.hours,
            "gap_seconds": args.gap_seconds,
            "min_ratio": args.min_ratio,
        },
    }

    rows, error = fetch_records(args.endpoint)
    if error:
        print(f"soak-check: store unreachable ({error}) — continuing with mirror only")
        report["store_error"] = error
        windows = []
    else:
        windows = window_rows(rows)
        report["galaxy_records"] = len(rows)
        report["rollups"] = sum(1 for r in rows if "rollup" in (r.get("tags") or []))
        report["observations"] = sum(1 for r in rows if "observation" in (r.get("tags") or []))

    if args.suspend_journal:
        since = None
        if windows:
            created = [parse_ts(r.get("created_at")) for r in windows]
            created = [c for c in created if c]
            since = min(created) if created else None
        if since is None:
            since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        journal, journal_error = suspends_from_journal(since)
        suspends.extend(journal)
        report["suspend_journal"] = {
            "since": since.isoformat(),
            "found": len(journal),
            "error": journal_error,
        }

    if windows:
        stamps = [s for s in (parse_ts(r.get("created_at")) for r in windows) if s]
        report["store_coverage"] = analyze(stamps, args.gap_seconds, suspends)
        report["store_coverage"]["source"] = "created_at"
        if args.full_ts and windows:
            full: list[datetime] = []
            missing = 0
            for index, row in enumerate(windows[:FULL_TS_CAP], start=1):
                stamp = read_window_ts(args.endpoint, row)
                if stamp:
                    full.append(stamp)
                else:
                    missing += 1
                if index % 100 == 0:
                    print(f"  full-ts scan: {index}/{min(len(windows), FULL_TS_CAP)}", file=sys.stderr)
                if args.read_delay > 0:
                    time.sleep(args.read_delay)
            report["full_ts"] = {
                "read": len(full),
                "missing": missing,
                "coverage": analyze(full, args.gap_seconds, suspends),
            }
        report["spot_check"] = spot_stamps(args.endpoint, windows, 5, args.read_delay, suspends)

    path = None if args.no_mirror else mirror_path(args.mirror)
    report["mirror"] = analyze_mirror(path, args.gap_seconds, suspends)

    store = report.get("store_coverage") or {}
    mirror = report.get("mirror") or {}
    checks = {
        "active_run": store.get("active_run_hours", 0.0) >= args.hours,
        "active_gaps": store.get("run_active_gap_seconds", float("inf")) <= args.gap_seconds,
        "cadence": (store.get("cadence_ratio") or 0.0) >= args.min_ratio,
        "resume": store.get("max_resume_latency_seconds", float("inf")) <= 300.0,
    }
    if mirror.get("available"):
        checks["mirror_active_gaps"] = (
            mirror.get("max_active_gap_seconds", float("inf")) <= args.gap_seconds
        )
    spot = report.get("spot_check") or {}
    if spot.get("checked"):
        checks["spot_ts"] = spot.get("max_delta_seconds", float("inf")) <= 300.0
    report["suspends"] = [
        {"start": s.isoformat(), "end": e.isoformat()} for s, e in sorted(suspends)
    ]
    report["verdict"] = "PASS" if checks and all(checks.values()) else "FAIL"
    report["checks"] = checks

    print(f"soak-check: {report['verdict']} — {args.endpoint}")
    if store:
        print(
            f"  store: windows={store.get('timestamped')} span={store.get('span_hours')}h "
            f"suspend={store.get('suspend_hours')}h active_run={store.get('active_run_hours')}h "
            f"(since {store.get('run_start')})"
        )
        print(
            f"    active_gaps(history)>{args.gap_seconds:.0f}s={store.get('active_gap_count')} "
            f"max_active_gap(run)={store.get('run_active_gap_seconds')}s "
            f"cadence={store.get('cadence_ratio')} resume_max={store.get('max_resume_latency_seconds')}s"
        )
        for gap in store.get("gaps", [])[-4:]:
            print(
                f"    gap[{gap['kind']}] {gap['seconds']}s (suspend {gap['suspend_seconds']}s, "
                f"active {gap['active_seconds']}s) — {gap['from']} → {gap['to']}"
            )
    if mirror.get("available"):
        print(
            f"  mirror ({mirror.get('path')}): windows={mirror.get('timestamped')} "
            f"active_run={mirror.get('active_run_hours')}h "
            f"active_gaps={mirror.get('active_gap_count')} "
            f"max_active_gap={mirror.get('max_active_gap_seconds')}s"
        )
    if report.get("suspend_journal"):
        info = report["suspend_journal"]
        print(
            f"  suspend journal: found={info['found']}"
            + (f" error={info['error']}" if info.get("error") else "")
        )
    if spot.get("checked"):
        print(
            f"  spot-ts: checked={spot['checked']} suspend_covered={spot['suspend_covered']} "
            f"max_delta={spot['max_delta_seconds']}s"
        )
    print(f"  checks={checks}")
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
        print(f"  report → {args.json_path}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
