# eval-endpoint — participant-hosted Add/Search for memory evaluations

**Evaluation infrastructure only.** This service exists to be scored by an
external harness (AML Cycle 2-shaped competitions, PAR reliability audits).
Run it for the evaluation window, then take it down (checklist below). It is
not part of any product surface.

## Contract

All JSON. Auth via `Authorization: Bearer <token>` or `X-Api-Key`; `/health`
and `/info` are keyless. `user_id` is the **sole retrieval isolation
boundary** — each user gets its own store (and its own `wm serve` process on
the WM backend), so cross-user retrieval is impossible by construction.

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/health` | — | `{"ok": true, "backend": "wm"}` |
| GET | `/info` | — | declared contract, limits, isolation, deletion policy |
| POST | `/add` | `{"user_id", "content", "metadata"?}` or `{"items": [...]}` | `{"ok": true, "ids": [...]}` — 200 only after persist |
| POST | `/search` | `{"user_id", "query", "top_k"?}` (top_k ≤ 100) | `{"results": [{"id","content","score"}], "count": n}` |
| POST | `/delete` | `{"user_id"}` or `{"user_id", "ids": [...]}` | `{"ok": true, "deleted": n}` |

Limits: 1 MiB body, ≤100 top_k, 4 concurrent requests, 60 s WM call timeout.
Errors: 400 shape, 401 token, 404 path, 413 body, 503 concurrency/backend.

## Backends

- **`lexical`** — stdlib, deterministic token-overlap search. For tests and
  plumbing smoke runs (no WM dependency).
- **`wm`** — the real system: one `wm serve` process per user (stdio JSON-RPC,
  `memory.create` / `memory.search` via the meta-tool), store under
  `<state>/users/<sha256(user_id)[:16]>/store`, capped at `--max-users` with
  LRU shutdown. This is the backend an evaluation should score.

## Run locally

```bash
python3 eval_endpoint.py --state /tmp/eval-state --backend wm --token "$(openssl rand -hex 16)"
python3 -m unittest test_eval_endpoint -v     # lexical + wm suites
```

## Deploy (box)

```bash
# files
install -d -m 755 /opt/whitemagic-eval /srv/whitemagic/eval-state
install -m 644 eval_endpoint.py /opt/whitemagic-eval/eval_endpoint.py
install -m 644 whitemagic-eval.service /etc/systemd/system/whitemagic-eval.service
# token (operator-held; give it to the harness)
printf 'WM_EVAL_TOKEN=%s\n' "$(openssl rand -hex 24)" > /etc/whitemagic-eval.env
chmod 600 /etc/whitemagic-eval.env
chown whitemagic:whitemagic /srv/whitemagic/eval-state
systemctl daemon-reload && systemctl enable --now whitemagic-eval
# public route (TLS terminated by Caddy; path avoids a DNS change)
#   handle_path /eval/* { reverse_proxy 127.0.0.1:18796 }
systemctl reload caddy
```

Public endpoint: `https://api.whitemagic.dev/eval/health` (keyless), with
`/eval/add`, `/eval/search`, `/eval/delete` behind the token.

## Take-down checklist

1. `systemctl disable --now whitemagic-eval`.
2. `rm -rf /srv/whitemagic/eval-state` (eval data deleted within the window
   required by the harness — deletion is also available per user via `/delete`).
3. Remove the Caddy `handle_path /eval/*` block and reload.
4. `rm /etc/whitemagic-eval.env /opt/whitemagic-eval -rf`.
5. Note the window + deletion in the evaluation record.

## Honest gaps

- AML's exact wire schema (field names for Add/Search) must be confirmed from
  their participation guide; this contract is the generic shape and the
  adapter layer can map it.
- `POST /delete` with `ids` is id-level on the lexical backend; the WM backend
  deletes the whole per-user store (`deleted: -1` means whole-user) because WM
  exposes no per-memory delete route.
- No SLA; the service is a thin stdlib server behind Caddy. Concurrency and
  timeouts are declared and enforced, not tuned for large harness runs.
- Scoring fairness: the harness should score the `wm` backend; `lexical` is
  plumbing only.
