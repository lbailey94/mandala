# Yama v0 Bridge — Design (2026-09-14)

**Status:** draft for build. Implements the gap named in `CURRENT_REALITY_2026-09-13.md` §4:
*"Tetragon/runner/bus events → WM (galaxy or bus) → a policy evaluation point."*

## 1. The gap (recon-verified 2026-09-14)

| Surface | State | Missing for the bridge |
|---|---|---|
| Telemetry galaxy + typed records (`telemetry.record` incl. `telemetry.observation`) | Shipped; written by Lakshmi, read by dashboard + retention only | No WM-internal producer of observations for OS events |
| Gan Ying bus (`EventType`, 235 variants, JSONL at serve) | Shipped; `OsTelemetryThreshold` precedent | No sandbox/Tetragon event type |
| Subprocess sandbox (B2) | Shipped; counters only (`dispatches/degraded/unconfined_spawns`), surfaced in `/status` + `wm doctor` | No event emission — drift is silent until someone reads status |
| Policy evaluation (step 0, hysteresis contract) | Live in Lakshmi; writes decision records | Consumes only its own 7-dim digest — not the new sources |
| `DharmaGate::evaluate` / `ResourceRules` | Shipped, effect-based | No `observation → verdict` entry point |
| Tetragon | Feasibility PASS (in-guest, documented) | No collector code anywhere |

## 2. Architecture — three legs

```
Events                     WM ingestion                    Evaluation → records
─────────────────────      ────────────────────────       ─────────────────────────
runner drift (B2)     →    SandboxObservation bus    →    Lakshmi step-0 engine
  degraded / unconfined      event (new, persisted          (existing hysteresis:
                             JSONL at serve)                 enter≠exit, dwell,
Tetragon eBPF         →    Tetragon collector →           cooldown, decision
  security_file_open         telemetry observation          records)
  etc.                       (typed, durable)                  │
                                                               ▼
bus thresholds        →    already live                   telemetry.observation
  os.telemetry.*                                              (dashboard Policies)
```

### Event / record schemas

**Bus event (ephemeral + `resonance_events.jsonl`) — new `EventType::SandboxObservation` (=235, Harmony category, OS-telemetry family):**

```json
{
  "tool": "session.record",
  "kind": "degraded" | "unconfined_spawn",
  "counts": {"dispatches": 12, "degraded": 1, "unconfined_spawns": 3},
  "ts_ms": 1757880000000
}
```

**Durable observation record (telemetry galaxy) — existing `telemetry.observation` kind, new policy ids:**

```json
{
  "kind": "telemetry.observation",
  "policy_id": "spawn.undeclared.v1" | "shadow.access.v1",
  "metric": "sandbox.unconfined_spawns" | "tetragon.shadow_access",
  "state": "entered" | "held" | "exited",
  "action": "observe" | "notify",
  "value": 3,
  "evidence": ["bus:1757880000000", "tetragon:pid=4242,comm=cat"],
  "source": "sandbox" | "tetragon"
}
```

This reuses the exact validation contract of `telemetry.record` (policy_id, metric, state, action, value required) — no new record type.

## 3. Decisions

- **D1 — Landing zone: bus for ephemeral drift, galaxy for durable decisions.**
  `CURRENT_REALITY` says "(galaxy or bus)". Bus events are cheap, ordered, and JSONL-persisted at serve; decision records belong in the telemetry galaxy. Sandbox incidents land as bus events; policy transitions land as observation records (written by the evaluator, as today).
- **D2 — Evaluation point stays Lakshmi step-0 for v0.**
  It already implements the full ACTUATION_HYSTERESIS contract and is live. Building a second engine in Rust now would create two sources of truth. The WM-side *seam* is the bus event; moving evaluation into `wm-governance` (Yama v1) is gated on v0 experience — noted, not built.
- **D3 — Observe-only for all new policies.** Enforcement remains the existing runner/bwrap/Landlock seam. Promotion follows the ladder (notify → nudge → throttle) only after zero-false-positive windows.
- **D4 — Tetragon collector is a Sovereign-side script** (JSON event stream → observation records via the writable MCP), with fail-soft spool. Nix packaging of Tetragon and Falco/OPA/Cedar stay deferred per `CURRENT_REALITY` §4.
- **D5 — Sandbox drift signals are `degraded` (declared tool, no runner) and `unconfined_spawn` (spawn-declared tool without the contract).** Child-level runner *denials* (stderr/exit conventions) are a later slice; the counters cover the policy's stated evidence.

## 4. Slices

| # | Deliverable | Where | Test |
|---|---|---|---|
| **S1** ✅ | Sandbox incident ring (`drain_events`) + `SandboxObservation` event type + server emit post-dispatch | WMv9 (`wm-dispatch`, `wm-cognitive`, `wm-mcp`); built in worktree `WHITEMAGIC/WMv9-yama-bridge` @ `yama/bridge-v0` | ✅ 2026-09-14: wm-dispatch 7/7, wm-cognitive 714/714, whitemagic lib 298/298, clippy `-D warnings` clean |
| **S2** ✅ | `yama-collector.py`: Tetragon JSON (file/stdin) → observation records via MCP, spool + fail-soft | `MANDALAOS_SOVEREIGN/scripts/yama-collector.py` + `scripts/fixtures/tetragon-shadow-sample.jsonl` | ✅ 2026-09-14: dry-run maps 2/4 events; live send to scratch store verified; dead endpoint spools; replay empties spool |
| **S3** | Lakshmi consumes sandbox bus events + tetragon observations into `spawn.undeclared.v1` / `shadow.access.v1`; decision records on transitions; dashboard | `LAKSHMI` (now `MANDALA_OS/LAKSHMI`) | policy unit tests (replay fixtures) |
| **S4** | In-guest live run (VM rebuild @ current slice, Tetragon policy, collector wired) | sovereign VM | observe log + decision records in-guest |
| **Y1** | (Later, gated) move evaluation into `wm-governance` Rust engine | WMv9 | ACTUATION acceptance checklist |

## 5. Acceptance (S1)

- [ ] A `degraded` or `unconfined_spawn` incident pushed to the registry is drained exactly once and emitted as one `SandboxObservation` bus event.
- [ ] No event on the happy path (`note_confined`); counters unchanged in `status()`.
- [ ] Ring is bounded (no unbounded memory under a storm).
- [ ] `EventType::all().len() == 236`; `parse_event_type("sandbox_observation")` round-trips; `bus.recent` returns it.
- [ ] Existing tests (wm-dispatch, wm-cognitive, wm-mcp sandbox tests) stay green.

## 6. Non-goals (this pass)

No enforcement/actuator changes; no OPA/Cedar; no Rust policy engine; no Tetragon packaging; no child-stderr denial parsing; no dashboard work (S3).
