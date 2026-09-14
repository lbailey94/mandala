# MandalaOS Harmony Vector — OS-Level Specification v0.1

**Status:** Draft (2026-08-28). The one design doc that must exist before Lakshmi/Tiferet code is written.
**Anchored to:** the 2025 spec's Lakshmi/Tiferet sections; the OpenAI review's "Harmony Vector spec" open question; WHITEMAGIC's shipped 7-dim vector (`archives/og_whitemagic/core/whitemagic/harmony/vector.py`), which this spec extends rather than replaces.

## Design principles

1. **≤ 7 scalars.** Every dimension normalized to [0.0, 1.0], 1.0 = ideal. A single composite `harmony_score` is the weighted mean — but the *vector* is the artifact; the scalar is just its shadow.
2. **Cold start = 0.7, never 1.0.** (WM already does this — avoids the "perfect system" illusion.)
3. **One vector, two scopes.** The OS-level vector (Lakshmi, eBPF-fed) and the WM app-level vector (tool-call-fed) share dimension names; WM's `dharma`/`karma_debt` dims roll up into the OS vector's dims 6/7 when WM runs on the machine.
4. **Readable, not just machine feed.** Every dimension must map to a plain-language sentence for the "Explain this" UI (Anti-Maya).

## The 7 dimensions

| # | Dimension | Definition | Units / source | Healthy range |
|---|---|---|---|---|
| 1 | **fairness** | Resource distribution equity across processes/agents | Gini coefficient of per-process CPU share over 300s window (eBPF scheduler events / `/proc`); score = 1 − Gini | Gini < 0.5 → ≥ 0.5 |
| 2 | **responsiveness** | How fast interactive work gets scheduled | p95 wake-to-run latency for interactive-class tasks + runqueue pressure (PSI avg10) | p95 < 50ms |
| 3 | **throughput** | Useful work volume relative to capacity | completed jobs/s vs. recent baseline; syscall/user-visible event rate (eBPF) | 20–80% of baseline (both extremes penalized — "sufficient, not maximal") |
| 4 | **stability** | Absence of errors and restarts | error rate, crash/OOM count, rapid-fail loops per 300s | < 2% errors |
| 5 | **energy** | Power draw vs. budget | RAPL/ACPI joules per window vs. user-set budget (Permacounter) | within budget |
| 6 | **dharma** | Policy health: violations, denials, unexplained actions | Yama decisions per window: ratio of explained allows / unexplained denials; count of blocked-by-default events | denials < 5%, all explained |
| 7 | **karma_debt** | Declared-vs-actual side-effect mismatches | WM karma ledger (`karma_ledger.rs`) when present; otherwise `LD_PRELOAD`/eBPF stub until SutraCode exists | debt < 1.0 |

Weights (from WM, carried over): fairness .15, responsiveness .15, throughput .10, stability .20, energy .10, dharma .15, karma_debt .15. Tunable per profile ("Secure Transaction" raises dharma/stability; "Deep Reflection" raises energy/fairness).

## Guna tagging (process temperament)

Assigned by Lakshmi from behavior over the 300s window, matching WM's `Guna` enum:
- **Sattvic** — interactive/light: low CPU, frequent wakeups, GUI/agent-interactive. Scheduler favoritism for responsiveness.
- **Rajasic** — active/heavy: sustained CPU or write-heavy I/O. Fair-share, gentle throttle at extremes.
- **Tamasic** — blocked/idle/read-only: rare wakeups, waiting on I/O. Deprioritize opportunistically; wake promptly when it becomes interactive.

Classification rule (v0.1, simple and auditable): CPU time > 70% of window + write-heavy → Rajasic; blocked > 80% of window → Tamasic; else Sattvic. Per-guna distribution is reported in the vector snapshot (WM parity).

## Sampling & cadence

| Layer | Rate | Why |
|---|---|---|
| eBPF collectors | continuous, ring-buffer | raw events |
| Lakshmi digest | every 5s | vector recompute (matches WM's 300s rolling window) |
| Tiferet action loop | every 30s | policy application; avoids thrash |
| UI update | every 5s pull | dashboard pulse |

Overhead budget: < 2% CPU, < 200MB RAM (per the May 2025 review's measured targets).

## Tiferet action ladder

Response is a ladder, never a leap — this is the Gevurah/Chesed balance and the operational lesson from the Tetragon community ("earn your way into enforcement"):

1. `observe` — log only (always on).
2. `notify` — a "Stoic card": plain-language explanation to the user (dim < 0.6).
3. `nudge` — adjust scheduling/resource weights by ≤ 10% (dim < 0.4 sustained 2 windows).
4. `throttle` — rate-limit or freeze idle-heavy processes (dim < 0.2, or a Yama escalation).
5. `isolate` — sandbox escalation, human-in-the-loop required.

Every step ≥ 3 is logged with a **Karmic trace** (the causal chain that led to it).

## What this enables

- The Tauri dashboard renders 7 bars + guna distribution + a Sankey of resource flow (per the Tiferet-dashboard concept).
- WM's `HarmonyVector` can consume dims 1–5 and publish 6–7, closing the OS↔app loop.
- The XPRIZE "prescience" claim gets an executable definition: harmony is no longer a metaphor, it's a vector with units.

## Explicit non-goals (v0.1)

- No Fourier/Samsara cycle prediction (v0.2).
- No cross-device or neighbour-view (Ubuntu layer) roll-up (v0.3).
- No ML anomaly scoring (v0.3; v0.1 uses simple thresholds).
