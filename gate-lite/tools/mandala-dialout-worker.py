#!/usr/bin/env python3
"""OpenComputer-inspired outbound-only dial-out worker for Mandala gate-lite.

Opens zero listening sockets. Periodically polls an upstream board/control HTTP
endpoint (e.g. Sangha Whiteboard on http://127.0.0.1:8787 or any JSON job feed),
dispatches matching `mandala.{exec,status,kill,terminate}` directives locally
inside the configured reviewed sandbox runner, and POSTs a <=150-token CPR
pointer summary back outbound.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from continuity_receipt import verify_bundle  # noqa: E402
from continuity_receipt.canon import canonical_bytes, sha256_prefixed  # noqa: E402
from gate_lite.orchestrator import Orchestrator, build_runner  # noqa: E402


def _extract_directives(payload: Any, worker_id: str) -> list[dict[str, Any]]:
    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = (
            payload.get("jobs")
            or payload.get("posts")
            or payload.get("messages")
            or payload.get("items")
            or []
        )
    else:
        return []

    directives: list[dict[str, Any]] = []
    tag = f"@{worker_id}"
    for item in items:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or item.get("worker_id") or "")
        body_obj = item
        if "action" not in item:
            raw_text = item.get("body") or item.get("message") or ""
            if isinstance(raw_text, str) and raw_text.strip().startswith("{"):
                try:
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        body_obj = parsed
                except json.JSONDecodeError:
                    continue
        if not isinstance(body_obj, dict) or "action" not in body_obj:
            continue
        dir_target = str(body_obj.get("worker_id") or target)
        if dir_target and dir_target not in (worker_id, tag, "@all", "all"):
            continue
        job_id = str(
            body_obj.get("job_id")
            or item.get("id")
            or hashlib.sha256(canonical_bytes(body_obj)).hexdigest()[:16]
        )
        directives.append({**body_obj, "job_id": job_id})
    return directives


def _load_seen(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except (OSError, json.JSONDecodeError):
        return set()


def _save_seen(path: Path, seen: set[str]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    os.replace(tmp, path)


def _sign_pointer(pointer: dict[str, Any], hmac_key: str | None) -> dict[str, Any]:
    out = dict(pointer)
    if hmac_key:
        sig = hmac.new(
            hmac_key.encode("utf-8"),
            canonical_bytes(out),
            hashlib.sha256,
        ).hexdigest()
        out["hmac_sha256"] = f"hmac-sha256:{sig}"
    return out


def _execute_directive(
    orch: Orchestrator,
    default_tenant: str,
    worker_id: str,
    directive: dict[str, Any],
    hmac_key: str | None = None,
) -> dict[str, Any]:
    action = directive["action"]
    tenant = str(directive.get("tenant") or default_tenant)
    slot_id = str(directive["slot"])

    if action == "mandala.exec":
        result = orch.exec_(
            tenant,
            slot_id,
            directive["payload_ref"],
            idempotency_key=directive.get("idempotency_key"),
            token=directive.get("token"),
            agent_id=directive.get("agent"),
        )
        if directive.get("terminate") and orch.status(tenant, slot_id)["slot"]["state"] == "active":
            term = orch.terminate(tenant, slot_id, reason=directive.get("reason", "completed"))
            if term.get("receipt_id"):
                result.setdefault("receipt_ids", []).append(term["receipt_id"])
    elif action == "mandala.status":
        result = orch.status(tenant, slot_id)
    elif action == "mandala.kill":
        result = orch.kill(
            tenant,
            slot_id,
            signal_name=directive.get("signal", "SIGTERM"),
            wait_s=float(directive.get("wait_s", 5.0)),
        )
    elif action == "mandala.terminate":
        result = orch.terminate(tenant, slot_id, reason=directive.get("reason", "completed"))
    else:
        raise ValueError(f"unsupported dialout action: {action}")

    status_info = orch.status(tenant, slot_id)
    task_id = status_info["slot"].get("task_id") or orch.task_id_for(slot_id)
    bundle = orch.receipt(task_id)
    verdict = verify_bundle(bundle).as_dict()["verdict"] if bundle.get("receipts") else "NONE"
    receipt_ids = result.get("receipt_ids", [])
    pointer: dict[str, Any] = {
        "schema": "mandala-cpr-pointer/0.5",
        "job_id": directive["job_id"],
        "worker_id": worker_id,
        "action": action,
        "slot_id": slot_id,
        "task_id": task_id,
        "sandbox_class": orch.runner_info()["class"],
        "exit": result.get("exit"),
        "stdout_hash": result.get("stdout_hash"),
        "head_receipt_id": receipt_ids[-1] if receipt_ids else None,
        "receipt_count": len(receipt_ids),
        "bundle_sha256": sha256_prefixed(canonical_bytes(bundle)),
        "verdict": verdict,
    }
    return _sign_pointer(pointer, hmac_key)


def _http_get_json(url: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {"status": resp.status}


def poll_once(
    orch: Orchestrator,
    *,
    tenant: str,
    worker_id: str,
    board_url: str,
    poll_path: str,
    post_path: str,
    state_dir: Path,
    hmac_key: str | None = None,
) -> list[dict[str, Any]]:
    seen_path = state_dir / f"dialout-seen-{worker_id}.json"
    seen = _load_seen(seen_path)
    poll_url = urllib.parse.urljoin(board_url.rstrip("/") + "/", poll_path.lstrip("/"))
    post_url = urllib.parse.urljoin(board_url.rstrip("/") + "/", post_path.lstrip("/"))

    payload = _http_get_json(poll_url)
    directives = _extract_directives(payload, worker_id)
    results: list[dict[str, Any]] = []
    for directive in directives:
        job_id = directive["job_id"]
        if job_id in seen:
            continue
        try:
            pointer = _execute_directive(orch, tenant, worker_id, directive, hmac_key=hmac_key)
        except Exception as exc:  # noqa: BLE001 - worker reports typed execution error outbound
            pointer = _sign_pointer(
                {
                    "schema": "mandala-cpr-pointer/0.5",
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "action": directive.get("action"),
                    "slot_id": directive.get("slot"),
                    "error": type(exc).__name__,
                    "detail": str(exc)[:200],
                },
                hmac_key,
            )
        _http_post_json(post_url, pointer)
        seen.add(job_id)
        _save_seen(seen_path, seen)
        results.append(pointer)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mandala-dialout-worker")
    parser.add_argument("--state", required=True)
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--board-url", default="http://127.0.0.1:8787")
    parser.add_argument("--poll-path", default="/api/inbox")
    parser.add_argument("--post-path", default="/api/post")
    parser.add_argument("--runner", default=None)
    parser.add_argument("--sandbox-class", default=None)
    parser.add_argument("--slice", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--interval-s", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    runner_path = args.runner or os.environ.get("WM_GATELITE_RUNNER")
    runner = build_runner(runner_path, slice_mode=args.slice, sandbox_class=args.sandbox_class)
    if runner is None and not args.demo:
        parser.error("refusing to start dialout worker without --runner or explicit --demo")

    state_dir = Path(args.state)
    state_dir.mkdir(parents=True, exist_ok=True)
    orch = Orchestrator(state_dir, runner=runner)
    hmac_key = os.environ.get("WM_CPR_HMAC_KEY")

    while True:
        out = poll_once(
            orch,
            tenant=args.tenant,
            worker_id=args.worker_id,
            board_url=args.board_url,
            poll_path=args.poll_path,
            post_path=args.post_path,
            state_dir=state_dir,
            hmac_key=hmac_key,
        )
        if out or args.once:
            print(json.dumps({"worker_id": args.worker_id, "dispatched": out}))
        if args.once:
            return 0
        time.sleep(max(args.interval_s, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
