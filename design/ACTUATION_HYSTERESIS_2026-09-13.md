# Actuation & Hysteresis — Tiferet ladder design (2026-09-13)

**Status:** design only **except step 0 — live 2026-09-13 (full contract).**
Four observe-only policies (`responsiveness`/`stability`/`energy` below,
`dharma.blocked` above) run with enter≠exit bands, per-policy
`min_dwell_windows`, a one-time `confirmed` transition, and `cooldown_windows`
gating on re-entry; every transition writes a `telemetry.observation`
decision record (policy id/version, value, enter/exit, dwell, cooldown,
evidence, `action: observe`) into the telemetry galaxy, surfaced in the
dashboard's **Policies** panel. Records use the typed `telemetry.record` path
where the fleet carries the observation kind (v9.1.5+; pushed to main
`38bf66e`), with a `memory.create` fallback on v9.1.4. No actuation code
ships in this pass — this doc defines the contract so the eventual
implementation cannot improvise it. Companions:
`CURRENT_REALITY_2026-09-13.md` §4 (Yama v0),
`implementation/lakshmi-yama-sprint-plan.md` (reality-adjusted section),
`feasibility/harmony-vector-spec.md` (7 dims + ladder).

## Why this exists (the rule)

> **No closed loop without hysteresis.** If telemetry drives actuation, every
> step needs observe-mode, hysteresis, rollback, and disclosed policy ids.
> — handoff §5 rule 5

The failure mode this prevents: a single noisy window (a build spike, a
battery reading, a grader's burst) nukes a process or denies a tool, and the
system oscillates. The cardinal Yama rule (observe ≥ 1 week, zero false
positives before any blocking) is the *entry* condition; hysteresis is what
keeps the loop stable once enforcement is earned.

## The ladder (steps, not states)

| Step | Name | Action | Human in loop |
|---|---|---|---|
| 0 | **Observe** | record only (window + bus event) | no |
| 1 | **Notify** | surface in dashboard / bus event with plain-language reason | no |
| 2 | **Nudge** | non-blocking pressure (slower cadence, deferred scheduling) | no |
| 3 | **Throttle** | bounded restriction (cgroup share, rate cap, runner denial) | review required |
| 4 | **Isolate** | deny/quarantine the subject | **always** |

- Steps 0–1 are live today (telemetry galaxy + `os_telemetry_threshold`).
- Step 3 is the first *enforcement* step and activates only per-policy after
  its observation window; the existing runner (B2) and bwrap/Landlock seams
  are the actuators.
- Step 4 never fires automatically: it opens an isolation *proposal* with
  evidence and waits for human confirmation.

## Hysteresis contract (per policy)

Every policy carries an explicit, versioned record — append-only in the
telemetry/dharma galaxy:

```json
{
  "policy_id": "energy.over_budget.v1",
  "version": 1,
  "metric": "dims.energy",
  "enter": 0.60,            // step-up threshold
  "exit": 0.80,             // step-down threshold (must differ from enter)
  "min_dwell_windows": 5,   // consecutive windows in-band before stepping
  "max_step": 3,            // this policy may never exceed throttle
  "cooldown_windows": 3,    // after a step-down, before re-entry
  "actuator": "notify",     // observe | notify | nudge | throttle
  "evidence": ["window:ts", "..."]
}
```

Rules:

1. **Enter ≠ exit.** A step-up requires `metric < enter` for
   `min_dwell_windows` consecutive windows; step-down requires `metric >
   exit` for the same dwell. Values between `enter` and `exit` hold state —
   that band *is* the hysteresis.
2. **No step skipping in one window.** A policy advances at most one step
   per dwell period; regression can drop multiple steps (safety is
   asymmetric).
3. **Cooldown after step-down.** `cooldown_windows` calm windows before the
   policy may step up again; prevents sawtoothing.
4. **Global circuit breaker.** The Stoic breaker (rapid-fail loops, step-ups
   across many policies in one window) forces the whole ladder back to
   Observe with a disclosed reason; a single policy bug cannot cascade.
5. **Every action is attributable.** Each step-up/down writes a decision
   record: policy id + version, metric value(s), thresholds, the windows
   used as evidence, action taken, reversal path, actor
   (`system:policy` vs `user`).
6. **Rollback is a first-class path.** Every actuator has `undo`; throttle
   states expire automatically after a bounded window (self-healing), and a
   kill switch (`WM_ACTUATION=0`) forces Observe globally.
7. **Observe-mode is a property of the policy, not the software.** Promotion
   from notify → nudge → throttle is a config change with a version bump,
   reviewed against its own observation log.

## First candidates (mapped to Yama v0 policies)

| Policy | Evidence (live) | First step | Actuator when earned |
|---|---|---|---|
| `shadow.access.v1` | Tetragon `security_file_open /etc/shadow` (feasibility PASS) | notify | **never auto-isolate**; alert only, human decides |
| `spawn.undeclared.v1` | runner `unconfined_spawns` counter + `sandbox-denial` events | notify | throttle = declare `Sandbox::Subprocess` (config fix, not kill) |
| `energy.over_budget.v1` | `dims.energy < 0.6` (battery/RAPL only — never the neutral proxy) | notify | nudge = dashboard alert + advisory to shed load |
| `write.budget_exceeded.v1` | resource-rules budget rejections (observed live 2026-09-13 during host stress) | observe → notify | throttle = lower-priority budget class |

Isolation (step 4) has **no automation candidate** and should stay that way
until there is a real adversarial scenario with a human review path.

## Acceptance for the eventual implementation

- [ ] A policy that steps up and down once, with the decision records
      showing enter/exit separation and dwell respected.
- [ ] Forced oscillation test: a metric toggling across `enter` never
      produces more than one step-up per dwell + cooldown.
- [ ] `WM_ACTUATION=0` returns the system to Observe within one window.
- [ ] Every action's decision record names the policy id + version and
      citations to the exact windows used.
- [ ] The dashboard shows the current step per policy and the reason
      (plain language, no Rego).

## Non-goals (this pass)

No actuators wired; no OPA/Cedar; no automatic isolation; no hidden time
constants — every threshold, dwell, and cooldown is declared and versioned.
