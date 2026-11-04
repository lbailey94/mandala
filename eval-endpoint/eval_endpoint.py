#!/usr/bin/env python3
"""eval_endpoint — participant-hosted Add/Search endpoint for memory evaluations.

Built for the evaluation lane (AML Cycle 2-shaped harnesses and the PAR
reliability audits): a synchronous Add/Search HTTP contract with per-user
isolation, an unauthenticated health check, declared limits, and eval-data
deletion. Evaluation infrastructure only — take it down after the window
(see README.md).

Contract (all JSON; auth via `Authorization: Bearer <token>` or `X-Api-Key`):

- `GET  /health`            keyless -> {"ok": true, "backend": ...}
- `GET  /info`              keyless -> declared contract/limits
- `POST /add`               {"user_id", "content", "metadata"?} or {"items": [...]}
                            -> {"ok": true, "ids": [...]}  (200 only after persist)
- `POST /search`            {"user_id", "query", "top_k"?} -> {"results": [...]}
- `POST /delete`            {"user_id"} or {"user_id", "ids": [...]} -> {"ok": true, "deleted": n}

Isolation: `user_id` is the sole retrieval boundary. Each user gets its own
store directory and (for the WM backend) its own `wm serve` process; no
cross-user retrieval is possible by construction.

Backends:
- `lexical` — stdlib, deterministic token-overlap search (tests, smoke runs).
- `wm`      — a real WM instance per user (`wm serve` over stdio JSON-RPC,
              memory.create / memory.search via the meta-tool). This is the
              evaluation backend that scores the real system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import select
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 1_048_576
MAX_TOP_K = 100
MAX_CONCURRENT = 4
WM_CALL_TIMEOUT_S = 60.0
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/=-]{8,}$")


def user_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class LexicalBackend:
    """Per-user JSONL store with deterministic token-overlap scoring."""

    name = "lexical"

    def __init__(self, state: pathlib.Path):
        self.state = state
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict]] = {}

    def _path(self, user: str) -> pathlib.Path:
        directory = self.state / "users" / user_key(user)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "memories.jsonl"

    def _load(self, user: str) -> list[dict]:
        if user not in self._cache:
            rows = []
            path = self._path(user)
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            rows.append(json.loads(line))
                        except ValueError:
                            pass
            self._cache[user] = rows
        return self._cache[user]

    def add(self, user: str, items: list[dict]) -> list[str]:
        with self._lock:
            rows = self._load(user)
            ids = []
            path = self._path(user)
            with path.open("a", encoding="utf-8") as handle:
                for item in items:
                    memory_id = item.get("id") or hashlib.sha256(
                        f"{user}:{len(rows)}:{item['content']}".encode()
                    ).hexdigest()[:24]
                    rows.append({"id": memory_id, "content": item["content"],
                                 "metadata": item.get("metadata") or {}})
                    handle.write(json.dumps(rows[-1]) + "\n")
                    ids.append(memory_id)
            return ids

    def search(self, user: str, query: str, top_k: int) -> list[dict]:
        with self._lock:
            rows = list(self._load(user))
        terms = set(tokenize(query))
        scored = []
        for row in rows:
            tokens = tokenize(row["content"])
            if not tokens:
                continue
            overlap = len(terms & set(tokens))
            if overlap:
                scored.append((overlap / len(tokens), row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {"id": row["id"], "content": row["content"], "score": round(score, 6)}
            for score, row in scored[:top_k]
        ]

    def delete(self, user: str, ids: list[str] | None) -> int:
        with self._lock:
            rows = self._load(user)
            if ids is None:
                deleted = len(rows)
                self._cache[user] = []
                path = self._path(user)
                if path.exists():
                    path.unlink()
                return deleted
            keep = [row for row in rows if row["id"] not in set(ids)]
            deleted = len(rows) - len(keep)
            self._cache[user] = keep
            path = self._path(user)
            path.write_text("".join(json.dumps(row) + "\n" for row in keep), encoding="utf-8")
            return deleted


class WmBackend:
    """One `wm serve` process per user, driven over stdio JSON-RPC."""

    name = "wm"

    def __init__(self, state: pathlib.Path, binary: str = "wm", max_users: int = 4):
        self.state = state
        self.binary = binary
        self.max_users = max_users
        self._lock = threading.Lock()
        self._users: dict[str, dict] = {}

    def _store_dir(self, user: str) -> pathlib.Path:
        directory = self.state / "users" / user_key(user) / "store"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _start(self, user: str) -> dict:
        store = self._store_dir(user)
        process = subprocess.Popen(
            [self.binary, "serve", "--store", str(store), "--profile", "curated"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        entry = {"process": process, "lock": threading.Lock(), "next_id": 1, "used": time.time()}
        with entry["lock"]:
            self._rpc(entry, "initialize", {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "eval-endpoint", "version": "0.1"},
            })
        return entry

    def _entry(self, user: str) -> dict:
        with self._lock:
            entry = self._users.get(user)
            if entry is None:
                if len(self._users) >= self.max_users:
                    oldest = min(self._users, key=lambda key: self._users[key]["used"])
                    self._shutdown(oldest)
                entry = self._start(user)
                self._users[user] = entry
            entry["used"] = time.time()
            return entry

    def _shutdown(self, user: str) -> None:
        entry = self._users.pop(user, None)
        if entry is None:
            return
        try:
            entry["process"].stdin.close()
        except OSError:
            pass
        try:
            entry["process"].terminate()
            entry["process"].wait(timeout=5)
        except Exception:
            try:
                entry["process"].kill()
            except OSError:
                pass

    def _rpc(self, entry: dict, method: str, params: dict) -> dict:
        request_id = entry["next_id"]
        entry["next_id"] += 1
        payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        entry["process"].stdin.write(payload + "\n")
        entry["process"].stdin.flush()
        deadline = time.monotonic() + WM_CALL_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"wm {method} timed out")
            ready, _, _ = select.select([entry["process"].stdout], [], [], remaining)
            if not ready:
                raise TimeoutError(f"wm {method} timed out")
            line = entry["process"].stdout.readline()
            if not line:
                raise RuntimeError("wm process exited")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(str(message["error"])[:300])
                return message.get("result", {})

    @staticmethod
    def _tool_text(result: dict) -> dict:
        try:
            return json.loads(result["content"][0]["text"])
        except (KeyError, IndexError, ValueError):
            return {}

    def add(self, user: str, items: list[dict]) -> list[str]:
        entry = self._entry(user)
        ids = []
        with entry["lock"]:
            for item in items:
                result = self._rpc(entry, "tools/call", {
                    "name": "wm",
                    "arguments": {"route": "memory.create", "args": {
                        "content": item["content"],
                        "title": item.get("metadata", {}).get("title", "eval add"),
                        "tags": ["eval", f"user:{user_key(user)}"],
                        "galaxy": "codex",
                    }},
                })
                parsed = self._tool_text(result)
                ids.append(parsed.get("id") or parsed.get("memory_id") or "")
        return ids

    def search(self, user: str, query: str, top_k: int) -> list[dict]:
        entry = self._entry(user)
        with entry["lock"]:
            result = self._rpc(entry, "tools/call", {
                "name": "wm",
                "arguments": {"route": "memory.search", "args": {"query": query, "limit": top_k}},
            })
        parsed = self._tool_text(result)
        rows = parsed.get("results") or []
        return [
            {"id": row.get("id", ""), "content": row.get("content", ""),
             "score": float(row.get("score") or 0.0)}
            for row in rows[:top_k]
        ]

    def delete(self, user: str, ids: list[str] | None) -> int:
        with self._lock:
            self._shutdown(user)
        directory = self.state / "users" / user_key(user)
        if directory.exists():
            shutil.rmtree(directory)
        return -1 if ids is None else 0  # WM backend deletes whole-user stores


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "wm-eval-endpoint"
    backend = None
    token = ""
    active = 0
    active_lock = threading.Lock()

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        self.send_header("Connection", "close")
        super().end_headers()
        self.close_connection = True

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            header = header[7:].strip()
        supplied = header or self.headers.get("X-Api-Key", "").strip()
        return supplied == self.token

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send(400, {"error": "empty body"})
            return None
        if length > MAX_BODY:
            self._send(413, {"error": f"body exceeds {MAX_BODY} bytes"})
            return None
        try:
            document = json.loads(self.rfile.read(length))
        except ValueError as error:
            self._send(400, {"error": f"invalid JSON: {error}"})
            return None
        if not isinstance(document, dict):
            self._send(400, {"error": "body must be an object"})
            return None
        return document

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send(200, {"ok": True, "backend": self.backend.name})
        elif path == "/info":
            self._send(200, {
                "service": "wm-eval-endpoint",
                "backend": self.backend.name,
                "contract": {
                    "GET /health": "keyless liveness",
                    "POST /add": {"user_id": "str", "content": "str", "metadata": "object?"},
                    "POST /search": {"user_id": "str", "query": "str", "top_k": f"int <= {MAX_TOP_K}"},
                    "POST /delete": {"user_id": "str", "ids": "list[str]?"},
                },
                "isolation": "user_id is the sole retrieval boundary; per-user store",
                "limits": {"max_body_bytes": MAX_BODY, "max_top_k": MAX_TOP_K,
                           "max_concurrent": MAX_CONCURRENT, "wm_call_timeout_s": WM_CALL_TIMEOUT_S},
                "deletion": "POST /delete removes a user's eval data (whole-user for the wm backend)",
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/add", "/search", "/delete"):
            self._send(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"error": "missing or invalid token"})
            return
        with Handler.active_lock:
            if Handler.active >= MAX_CONCURRENT:
                self._send(503, {"error": "concurrency limit reached; retry"})
                return
            Handler.active += 1
        try:
            document = self._read_json()
            if document is None:
                return
            if path == "/add":
                self._add(document)
            elif path == "/search":
                self._search(document)
            else:
                self._delete(document)
        finally:
            with Handler.active_lock:
                Handler.active -= 1

    def _add(self, document: dict):
        items = document.get("items")
        if not isinstance(items, list):
            items = [document]
        normalized = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("user_id"), str) \
                    or not isinstance(item.get("content"), str) or not item["user_id"]:
                self._send(400, {"error": "each item needs user_id and content"})
                return
            normalized.append(item)
        grouped: dict[str, list[dict]] = {}
        for item in normalized:
            grouped.setdefault(item["user_id"], []).append(item)
        ids = []
        for user, group in grouped.items():
            ids.extend(self.backend.add(user, group))
        self._send(200, {"ok": True, "ids": ids})

    def _search(self, document: dict):
        user = document.get("user_id")
        query = document.get("query")
        top_k = document.get("top_k", 10)
        if not isinstance(user, str) or not user or not isinstance(query, str):
            self._send(400, {"error": "search needs user_id and query"})
            return
        if not isinstance(top_k, int) or top_k < 1 or top_k > MAX_TOP_K:
            self._send(400, {"error": f"top_k must be 1..{MAX_TOP_K}"})
            return
        try:
            results = self.backend.search(user, query, top_k)
        except (TimeoutError, RuntimeError) as error:
            self._send(503, {"error": f"backend error: {error}"})
            return
        self._send(200, {"results": results, "count": len(results)})

    def _delete(self, document: dict):
        user = document.get("user_id")
        ids = document.get("ids")
        if not isinstance(user, str) or not user:
            self._send(400, {"error": "delete needs user_id"})
            return
        if ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
            self._send(400, {"error": "ids must be a list of strings"})
            return
        deleted = self.backend.delete(user, ids)
        self._send(200, {"ok": True, "deleted": deleted, "scope": "all" if ids is None else "ids"})


def main():
    parser = argparse.ArgumentParser(prog="eval_endpoint")
    parser.add_argument("--listen", default="127.0.0.1:18796")
    parser.add_argument("--state", required=True)
    parser.add_argument("--backend", choices=("lexical", "wm"), default="lexical")
    parser.add_argument("--wm-binary", default="wm")
    parser.add_argument("--max-users", type=int, default=4)
    parser.add_argument("--token", default=os.environ.get("WM_EVAL_TOKEN", ""))
    args = parser.parse_args()

    state = pathlib.Path(args.state)
    state.mkdir(parents=True, exist_ok=True)
    if args.backend == "wm":
        Handler.backend = WmBackend(state, binary=args.wm_binary, max_users=args.max_users)
    else:
        Handler.backend = LexicalBackend(state)
    if args.token and not TOKEN_RE.match(args.token):
        print("refusing: token must be 8+ chars of [A-Za-z0-9._~+/=-]", file=sys.stderr)
        raise SystemExit(2)
    Handler.token = args.token
    host, port = args.listen.rsplit(":", 1)

    class Server(ThreadingHTTPServer):
        request_queue_size = 32

    server = Server((host, int(port)), Handler)
    print(f"eval-endpoint listening on {host}:{port} (backend {Handler.backend.name})", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
