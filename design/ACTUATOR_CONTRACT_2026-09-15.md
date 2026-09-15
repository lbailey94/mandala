# Y1 Actuator Contract — subject identity, router, kill switch (2026-09-15)

**Status:** design for build; Y1.0 (skeleton) is the only slice that may ship
without S4 observation data. Companions: `design/ACTUATION_HYSTERESIS_2026-09-13.md`
(the policy-state contract this executes), `implementation/yama-v0-bridge-design.md`
(D2: evaluation stays step-0; D6: read path), `CURRENT_REALITY_2026-09-13.md` §4
("the open engineering gap … is the bridge"), handoff 2026-09-14 item 4 (Y1).

This document closes the gap named in the Yama deep dive: the ladder's steps 1–4
have **no executor**. It defines the contract so implementation cannot improvise
it — same discipline as the hysteresis doc.

---

## 1. The gap (verified 2026-09-15)

| Surface | State | Missing for actuation |
|---|---|---|
| Transition records (`telemetry.observation`) | Full hysteresis contract, live | No `subject`, no `step`, no `undo_token`, no `expires_at` |
| Sandbox drift (`SandboxEvent { tool, kind, ts_ms }`) | Subject = tool, already carried | Nothing — identity exists at the tool level |
| Tetragon evidence (`yama-collector.py`) | `pid/comm/binary` strings in `evidence` | No stable subject field; pid is volatile |
| `ResourceRules` budgets | Live (`BudgetExceeded { resource, used, limit }`), config in-memory | No per-subject tuning API, no undo, no expiry |
| `DharmaGate::evaluate` | Live (`Observe/Advise/Correct/Intervene/Panic`) | Dispatch-time verdicts; no cross-window actuation |
| Kill switch | **Does not exist** (`WM_ACTUATION` absent from the tree) | Arm/disarm + disclosure |
| Router | **Does not exist** | The contract below |

## 2. Subject identity

An actuator needs a stable target. `subject_id` is a string, captured at
evidence time, never a bare pid (pids recycle).

| Source | Scheme | Notes |
|---|---|---|
| Sandbox drift (`SandboxEvent.tool`) | `tool:<name>` | Already exact; **v0's primary subject class** |
| Tetragon (`comm`/`binary`) | `proc:<comm>:<basename(binary)>` | pid stays in `evidence` only; `comm` without `binary` is still usable |
| Telemetry dims | `dim:<name>` (e.g. `dim:energy`) | Global; applies to nudge/throttle classes, not process actions |
| Future compartments | `mandala:<id>` | Reserved; no capture path yet |

Rules:
1. **No pid-only subjects.** A record with no resolvable subject above stays
   observe/notify-only; steps ≥ nudge require a subject.
2. Subject identity must survive window boundaries — `comm`+binary, tool name,
   or dim name, never a kernel-assigned number.
3. Evidence keeps the volatile detail (pid, argv, path) for the human audit
   trail; the subject is the stable handle.

## 3. Decision record v2 (additive)

The existing `telemetry.record` validation contract stays; new optional fields
(default `null`/absent for v1 readers):

```json
{
  "kind": "telemetry.observation",
  "policy_id": "spawn.undeclared.v1",
  "version": 1,
  "metric": "sandbox_unconfined",
  "state": "observing" | "confirmed" | "clear",
  "action": "observe",
  "value": 3,
  "subject": "tool:oss.bounty.scan",
  "step": 0,                    // ladder step this record reports (0–4)
  "actuator": "none",           // none | notify | nudge | throttle | isolate-proposal
  "undo_token": null,           // set only when an actuator applied
  "expires_at": null,           // RFC3339; throttle states self-heal
  "evidence": ["bus:1757880000000"]
}
```

Only a `confirmed` transition may carry `step > 0`; `observing` records are
always `step: 0` (a single noisy window never actuates — the cardinal rule).
`clear` transitions must carry the `undo_token` of the action they retire.

## 4. The router

**Placement.** v0 router is a module beside the step-0 engine (LAKSHMI), same
process: it already owns the transitions and the hysteresis state. The Rust port
(`wm-governance`) is Y1.4 and consumes the same contract; no second evaluator
before then.

**Contract.**

```
tick:      transitions = engine.policy_observations(snapshot)
consume:   for t in transitions where t.state == "confirmed":
               policy = policies[t.policy_id]           # hysteresis record
               subj   = t.subject
               if !armed() or policy.actuator == "none": record(step=0); continue
               if step(t) > policy.max_step:            clamp + disclose
               if duplicate(t.policy_id, subj, step):   skip
               token = actuator.apply(policy, subj, t)
               record(step, actuator, undo_token=token, expires_at)
undo:      on t.state == "clear": actuator.undo(t.undo_token)
breaker:   on global trip (many policies stepping up in one window, or
           health < floor): apply(step=0) globally, expire active actions,
           write one disclosed reason record
```

Rules:
1. **Idempotent per transition.** One action per
   `(policy_id, version, subject, step, cooldown window)`; a replay of the same
   decision record must not re-apply.
2. **Safety asymmetry.** Step-down/undo may drop multiple steps at once;
   step-up advances at most one step per dwell (from the hysteresis contract).
3. **Expiry.** Every applied action has `expires_at` (`cooldown_windows` +
   bounded max) and lapses on its own if the evaluator dies — no permanent
   state without a live renewer.
4. **Attribution.** Every apply/undo writes a decision record naming
   `policy_id + version`, `subject`, thresholds, the exact windows used, and
   `actor: system:policy | user`.

## 5. Actuator catalog (v0) and undo

| Step | Actuator | Mechanism | Undo | Auto? |
|---|---|---|---|---|
| 0 | none | record only | — | yes |
| 1 | notify | bus event + dashboard card + policy inbox | — (advisory) | yes |
| 2 | nudge | advisory on that tool's next dispatch response (WM already discloses the sandbox policy) + dashboard; `dim:` subjects get dashboard-only advisories | remove advisory flag | yes |
| 3 | throttle | **per-subject `ResourceRules` class**: `spawn.undeclared.v1` → default that tool through the runner (config fix, not kill); `write.budget_exceeded.v1` → lower-priority per-subject multiplier. **Never a process kill.** | restore prior config (token carries before/after) | yes, per-policy after observation window |
| 4 | isolate-proposal | opens a proposal record with evidence; waits for human confirmation | proposal withdrawn/denied | **never** |

No actuator in this catalog kills or denies a dispatch; enforcement beyond
budget-class shaping (cgroup share, runner denial) stays future work and
requires its own contract.

## 6. Kill switch — `WM_ACTUATION=0`

House doctrine follows `WM_FIREBREAK=0` (`firebreak.rs`: *"disarming is
discoverable … never silent doctrine — but availability stays up"*):

- Set on the evaluator **and** any separate actuator process; unset = armed.
- Effect: within **one window**, all policies stay at step 0; active throttles
  are not renewed and lapse at `expires_at`; nudges clear.
- Disclosure: `armed: false` appears in the policy snapshot, the dashboard
  bridge/policies strip, and the window record; a single decision record
  explains the trip (`actor: user`).
- Test: disarm mid-observation → no apply; already-applied throttle lapses ≤
  its `expires_at`; re-arm resumes only on the next `confirmed` dwell.

## 7. Data flow

```
runner drift / Tetragon / bus
   → observation records (subject captured at source)
   → step-0 evaluation (Lakshmi; hysteresis; confirmed-only)
   → router (policy.actuator, max_step, armed, duplicate guard)
   → actuator backend (ResourceRules config | advisory channel | proposal)
   → actuation record (step, actuator, undo_token, expires_at)
   → dashboard Policies panel + policy inbox
```

## 8. Acceptance (extends `ACTUATION_HYSTERESIS` §acceptance)

- [ ] Forced oscillation: metric toggling across `enter` produces ≤1 step-up
      per dwell + cooldown, and a matching undo on the clear.
- [ ] Duplicate suppression: replaying a transition set applies nothing new.
- [ ] `WM_ACTUATION=0` within one window: no new apply; throttle lapses by
      `expires_at`; `armed: false` disclosed everywhere it matters.
- [ ] Undo fidelity: budget/config value after undo equal to before apply.
- [ ] Subject stability: a `proc:` subject survives pid reuse (same comm +
      binary across windows resolves to the same subject).
- [ ] Breaker: >N policies stepping up in one window trips global step 0 with
      one reason record; a single policy bug cannot cascade.
- [ ] Every action's record names policy id + version, subject, and the exact
      windows used.

## 9. Slices

| # | Slice | Repo | Gate |
|---|---|---|---|
| **Y1.0** ✅ | Router skeleton + record v2 fields + `WM_ACTUATION` arm/disarm + notify only + tests — implemented 2026-09-15 (`Lakshmi/actuator.py`, 16 tests; the `actuation_notify` bus event needs WM ≥ 9.1.7 and degrades to the decision record on older fleets) | LAKSHMI | none — no enforcement |
| **Y1.1** | Subject capture: collector maps `comm`/`binary` → `proc:`; eval maps `tool:`/`dim:`; dashboard shows subject | SOVEREIGN + LAKSHMI | none |
| **Y1.2** | Nudge: advisory channel for `spawn.undeclared.v1` + dims | LAKSHMI (+ WM response disclosure) | S4 data + zero-FP review per policy |
| **Y1.3** | Throttle: per-subject `ResourceRules` class + undo + expiry; first candidate `write.budget_exceeded.v1` | WMv9 | policy observation window clean |
| **Y1.4** | Port evaluation + router into `wm-governance`; Python engine demoted to producer (Y1 proper) | WMv9 | Y1.3 stable one release |

## 10. Non-goals and security notes

- No automatic isolation, no OPA/Cedar, no cgroup writer, no process kill.
- The router is privileged (it can change budgets). v0 keeps it in-process;
  if it ever becomes a service: authenticated channel, append-only action
  records, and the kill switch read at the actuator boundary — not only at the
  evaluator.
- Observation records are trusted-local today; signing/provenance is a
  separate decision (bridge trust-model gap, deep dive item 7).
- Thresholds, dwell, cooldown, `max_step`, and `expires_at` are declared and
  versioned — no hidden time constants (hysteresis rule 7).
