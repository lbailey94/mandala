# Lakshmi v0 — Harmony Vector digestor

First runnable piece of the MandalaOS **Lakshmi** monitor: computes the 7-dim
OS-level Harmony Vector from the spec at
`~/Desktop/MANDALA_OS/feasibility/harmony-vector-spec.md`, using only
privilege-free kernel telemetry (`/proc`, PSI pressure, RAPL when readable).

Single file, Python 3 stdlib only. No eBPF, no daemons, no dependencies.

## Usage

```bash
./lakshmi.py --once                       # two samples (~4s), one vector, exit
./lakshmi.py --interval 5                 # continuous terminal bars
./lakshmi.py --once --json                # machine-readable snapshot
./lakshmi.py --count 3 --interval 2 --json
./lakshmi.py --window 300 --budget-watts 15
./lakshmi.py --no-wm --once               # stub dim 7 (no WM call)
./lakshmi.py --wm-mcp http://127.0.0.1:18790 --karma-max 150
./lakshmi.py --dharma-mcp http://127.0.0.1:28795 --once   # dim 6 via VM MCP
LAKSHMI_KARMA_DEBT=0.3 ./lakshmi.py --once
python3 -m unittest -v test_lakshmi        # 44 unit tests
```

## Dimension mapping (v0 proxies, all disclosed in output)

| # | Dim | Spec source | v0 implementation | Status |
|---|---|---|---|---|
| 1 | fairness | Gini of per-process CPU share, 300s | 1 − Gini over per-PID tick deltas in window | live |
| 2 | responsiveness | p95 wake-to-run latency + PSI | 1 − clamp(PSI cpu `some` avg10 / 40) | proxy |
| 3 | throughput | jobs/s vs baseline | ctx-switches/s, triangular around 0.5× session baseline | proxy |
| 4 | stability | error/crash/OOM rate | 1 − (PSI mem `full` avg10/50 + defunct×0.02) | proxy |
| 5 | energy | RAPL joules vs budget | RAPL watts when readable; **battery `power_now` fallback** (verified 25.3W on BAT0) | live |
| 6 | dharma | Yama decisions ratio | **wired**: POST `/mcp` → `dharma.status` → `decisions` counters; score = 1 − 5×(blocked/total since last poll) | live* |
| 7 | karma_debt | WM karma ledger | **wired**: POST `/mcp` → `karma.report` → `total_debt` (verified 137.5 live); `--karma-max` cap default 150; env override supported | live |

\* dim 6 requires a WM build carrying the B3 counters (`dharma.status`
`decisions` block; WMv9 commit `59dfbfc`) and `--dharma-mcp <endpoint>`;
without it the dim degrades to the 0.7 stub with a disclosure.

Weights per spec: fairness .15, responsiveness .15, throughput .10,
stability .20, energy .10, dharma .15, karma_debt .15. Cold start 0.7,
never 1.0. Guna tags (sattvic/rajasic/tamasic) are assigned per process
(≥15% CPU share → rajasic, ≤1% → tamasic, plus D/Z states).

## Local verification (2026-09-12, Zorin 18.1, kernel 7.0.0-31)

Quiet machine: `harmony_score 0.64` (fairness 0.28 over 48 active procs,
responsiveness 0.48 at PSI cpu avg10=20.8, stability 0.97, harmony 0.64).

Under 2-core synthetic load: responsiveness 0.48 → 0.35, fairness 0.28 →
0.21, both loaders tagged `rajasic` in top processes. The vector moves in the
right direction with the right attribution.

With both new seams live (battery + WM): energy 0.32 (25.3W vs 15W budget),
karma_debt 0.08 (WM ledger 137.5, cap 150). Under parallel NEON/VIOLET
workloads responsiveness pinned 0.00 at PSI cpu avg10=55.4 and the composite
read 0.43 — the machine really was that loaded; the vector says so.

94 unit tests green (2026-09-24, `python3 -m unittest discover -p 'test_*.py'`:
44 lakshmi + 32 dashboard + 18 actuator).

## Honest gaps

- **No eBPF:** this machine boots `kernel.unprivileged_bpf_disabled=2`
  (permanent). v0 is PSI-only by design; Tetragon/Falco arrive with the
  eBPF sprint (requires privileged collectors).
- **Dim 6 needs a WM build with the B3 counters** (`dharma.status` `decisions`
  block; WMv9 `59dfbfc`) and `--dharma-mcp`; without it the dim degrades to
  the 0.7 stub with a disclosure. The step-0 policy engine itself is live
  (see below) and now also consumes the Yama v0 bridge signals.
- **Energy source is a proxy:** RAPL is root-only here, so the battery
  `power_now` fallback carries the dim (whole-platform discharge watts, not
  per-process attribution). On AC or a desktop it degrades to neutral 0.5
  with a disclosure rather than faking a number.
- **Dim 7 cap is chosen, not measured:** WM's `total_debt` is cumulative
  (137.5 over 5,250+ entries); the spec's "debt < 1.0" is per-entry
  semantics. `--karma-max` (default 150) maps the cumulative ledger to
  [0,1]; the note discloses the raw total and per-session delta.
- **Window:** spec target is 300s; use `--window 300` for production and the
  short default only for demos. Output discloses when the window is short.
- **Guna rule simplified** from the spec (write-heavy detection wants
  `/proc/<pid>/io`, which is owner/root-gated).

## Next steps

1. Tauri/Svelte 7-bar dashboard consuming `--json` (sprint Week 1 milestone).
2. Yama observe-only policies feeding dim 6 (`--window 300` production mode).
3. **Yama v0 bridge S3 (2026-09-14): done** — the policy engine now consumes
   `sandbox_observation` bus events (S1) and Tetragon observation records (S2)
   as `spawn.undeclared.v1`, `sandbox.degraded.v1`, and `shadow.access.v1`
   (dwell 1, cooldown 0). Feed outages hold state instead of clearing; window
   records carry a `bridge` counts block. The Tetragon read-back merges the
   collector's bounded sent-log ring mirror-first (`--bridge-feed`, default
   `~/.local/share/yama-collector/sent.jsonl`; collect with `--sent-log`), so
   recency does not depend on FTS ranking, and counts sum each record's
   `value` instead of collapsing bursts.
4. Optional: tiny privileged collector for RAPL (setcap or systemd unit) to
   restore true per-platform energy on AC.
5. **Y1.0 actuator router (2026-09-15): done** — notify-only skeleton
   (`actuator.py`): record v2 fields (`subject`/`step`/`actuator`/`undo_token`/
   `expires_at`), confirmed-transition notify with duplicate suppression, and
   the `WM_ACTUATION=0` kill switch disclosed in window records
   (`actuation.armed/applied`) and per-policy rows
   (`actuator_armed`/`actuator_max_step`). No enforcement; steps 2–4 wait on
   the contract's per-policy observation windows. The `actuation_notify` bus
   event needs WM v9.1.7+; on older fleets notify degrades to the decision
   record (drop disclosed on stderr).
6. **Y1.1 subject capture (2026-09-15): done** — the collector derives
   `proc:<comm>:<binary>` subjects (never pid-only), bridge records carry
   `tool:`/`proc:` subjects, dim records carry `dim:<metric>`, and the
   dashboard shows the subject chip on each observation row.
7. **`bridge_report.py` (2026-09-15)** — per-policy observation summary for
   promotion reviews (`--hours`, `--json`): decisions by state, first/last,
   per-day counts, input records, and **false-positive candidates** (observing
   decisions whose window has no matching input). The capture routine
   (`MANDALAOS_SOVEREIGN/scripts/capture_window.sh`) runs it automatically
   after each instrumented window.

## Dashboard (thread 3, 2026-09-13)

Static page + stdlib reader — no Tauri, no JS deps, no writes.

```bash
python3 dashboard.py --port 3109 \
  --galaxy-wm http://127.0.0.1:18798   # soak store; omit for the fleet store (18790, the v9.1.4+ default)
# open http://127.0.0.1:3109
```

- `/mandala` — living-Mandala view (P0 of
  `MANDALA_OS/design/GNOSIS_PORTAL_UI_2026-09-14.md`): bindu + 7 rings, spec
  floors, freshness fade, click-through to decision records, ambient mode
  (`?ambient=1`, 30 s cadence, pauses when hidden)
- `/api/live` — latest `~/.local/share/lakshmi/latest.json` (sampler mirror),
  annotated with freshness (`age_seconds`/`stale`) and per-policy
  `explain`/`samma_zone`
- `/api/history?hours=6` — mirror windows merged with the telemetry galaxy
- `/api/observations` — mirror observation ring merged with the galaxy
  (deduped by `ts`+`policy_id`; recency no longer depends on FTS ranking)
- `/api/bridge` — Yama bridge strip: last window counts, bus/tetragon feed
  reachability, newest sandbox/shadow records
- `/api/events` — `os_telemetry_threshold` events via WM (`--galaxy-wm`), with
  `feed_ok` so "no events" is never confused with "feed down"
- `/api/healthz` — dashboard + WM link state

The sampler writes the mirror when `--emit` is on (`--state-dir`,
`latest.json`, bounded `history.jsonl`, bounded `observations.jsonl` ring of
the last 50 decision records). The galaxy stays the durable record; the mirror
keeps the UI live when WM is down (fail-soft rule 4) and guarantees the newest
observations reach the page as volume grows. The Policies panel renders each
policy's hysteresis band (Samma-Meter) and a plain-language `explain` line.

### User units

```bash
cp systemd/lakshmi-sampler.service systemd/lakshmi-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lakshmi-sampler lakshmi-dashboard
```

Fleet wiring (v9.1.4+): `lakshmi-sampler` emits to the home gateway store
(18790) and reads dharma locally (the MandalaOS VM MCP at 28795 is optional);
`lakshmi-dashboard` reads the fleet store by default.

Soak wiring (2026-09-14, until the telemetry writer is promoted): the
dedicated `lakshmi-edge-sampler` + `lakshmi-edge-rollup` units feed the dev
edge-galaxy serve (18798) for the 72-hour gate, with their own state dir and
spool (`~/.local/share/lakshmi-edge`) so the two samplers never share the
mirror. The fleet sampler keeps running untouched.

```bash
cp systemd/lakshmi-edge-sampler.service systemd/lakshmi-edge-rollup.service \
   systemd/lakshmi-edge-rollup.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lakshmi-edge-sampler lakshmi-edge-rollup.timer
```

Retire the edge units once the gate passes and the writer is promoted.

## Tests

```bash
python3 -m unittest discover -p 'test_*.py'   # 94 tests
```
