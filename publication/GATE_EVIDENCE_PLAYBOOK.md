# Gate evidence playbook (2026-09-15)

Source of truth for gate definitions: `CURRENT_REALITY_2026-09-13.md` §7
(Labs page / public sovereign repo). This playbook says how each gate is
verified, what counts as evidence, and where it is stored. Bundles live in
`publication/evidence_<YYYY-MM-DD>/`.

**Nothing is published ahead of these gates; each is checkable evidence, not a
vibe.**

---

## Gate 1 — Edge galaxy: ≥ 72 h of accumulated active soak time

**Definition (redefined 2026-09-15, public).** The soak passes when the
**current uninterrupted run** holds:

- **≥ 72 h of accumulated *active* soak time** — wall-clock minus declared
  host-suspend intervals;
- **no non-suspend gap > 150 s** within that run;
- cadence **≥ 95 %** of one window per active minute;
- suspend/resume **disclosed from the host journal** (`PM: suspend
  entry/exit`), with **resume latency ≤ 300 s**;
- replayed windows on wake are expected and exempted from the timestamp check
  (the replay itself is verified against the journal).

A sleeping machine is not a software stall, so suspend is excluded — but it is
*disclosed*, never hidden. Every other interruption (restart, crash, stall)
still **resets the run**. This definition is written here and in
`CURRENT_REALITY` §7 so it cannot be quietly redefined later.

**Runs on this machine (verified 2026-09-15, `publication/soak_check.py`):**

| Run | Producer | Store | Current run since | Active | Suspend excluded |
|---|---|---|---|---|---|
| Soak | `lakshmi-edge-sampler` | `127.0.0.1:18798` | 2026-09-14T18:27Z | 13.9 h | 8.25 h (Sep 15 04:12–12:27Z) |
| Fleet | `lakshmi-sampler` | `127.0.0.1:18790` | 2026-09-14T22:06Z | ~9.7 h | 16.5 h (two sleeps) |

Resume latency after the sleep: **23 s**; window `ts` matches `created_at`
within 0.6 s on live windows. History before each current run (writer
migration 2026-09-13T23:36Z → 09-14T18:27Z, early stumbles) stays in the
report but does not count — resetting the run is the point.

**Status: NOT MET — 13.9 h of 72 h active (soak run).** Projection: ≈
**2026-09-18 early UTC** if the host stays awake; ≈ **2026-09-19–20** with
normal night sleeps.

**Check (read-only):**

```bash
python3 publication/soak_check.py --endpoint http://127.0.0.1:18798 \
    --mirror ~/.local/share/lakshmi-edge/history.jsonl --suspend-journal \
    --json publication/evidence_<date>/soak_18798.json
python3 publication/soak_check.py --endpoint http://127.0.0.1:18790 \
    --mirror ~/.local/share/lakshmi/history.jsonl --suspend-journal \
    --json publication/evidence_<date>/soak_18790.json
```

PASS = run ≥ 72 h active, run active gaps ≤ 150 s, cadence ≥ 0.95, resume
≤ 300 s, mirror run clean, spot `ts` deltas ≤ 300 s (suspend-covered replays
exempt). Notes: the 18798 dev serve rate-limits bursty tool calls
(`--full-ts` is paced); the local mirror is bounded to ~2880 windows (~48 h),
which is why the store scan carries the span and the mirror carries
true-`ts` continuity for its window.

**Evidence bundle:** the two JSON reports, the journal suspend lines
(`journalctl -k --utc -o short-iso | grep "PM: suspend"`), sampler uptimes
(`systemctl --user show lakshmi-sampler lakshmi-edge-sampler -p ActiveEnterTimestamp`),
empty spools (`wc -l ~/.local/share/lakshmi*/telemetry_spool.jsonl`), and a
dashboard screenshot:

```bash
google-chrome --headless=new --disable-gpu \
  --screenshot=publication/evidence_<date>/dashboard.png --window-size=1440,900 \
  'http://127.0.0.1:3109/mandala'
```

---

## Gate 2 — Stranger install (≥ 4/5 unassisted)

Protocol + evidence template: `publication/STRANGER_INSTALL_PROTOCOL.md`.
Acceptance: ≥ 4/5 testers complete the install unassisted with **no data loss,
no silent corruption, and no undisclosed network transfer** (ADOPTION
Gate-2). Per-tester records go in the bundle as `stranger_<tester>.md`.

---

## Gate 3 — Repo hygiene

All items are textual and checkable:

- [x] **WM release tagged and certified** — v9.1.8 (`e1ea07f`); the
      release-health record is attached to the GitHub Release as the source of
      truth (run `35233273768`, 2026-09-17).
- [x] **Sovereign pinned to that tag** — `flake.nix` input
      `github:lbailey94/whitemagic/v9.1.8`, lock rev `e1ea07f` (bumped
      2026-09-17; `nix eval .#packages.x86_64-linux.whitemagic.drvPath` names
      the closure `whitemagic-9.1.8.drv`; commit `4cd05a6` pushed).
- [ ] **No unpushed commits** in `WHITEMAGIC/WMv9`, `LAKSHMI`,
      `MANDALAOS_SOVEREIGN` (0 at close 2026-09-15).
- [ ] **Public-surface guard clean on WMv9** (pre-push/CI check; run the repo's
      own guard before publishing).
- [ ] **Sovereign README "what works today / what's next"** derived from
      `CURRENT_REALITY_2026-09-13.md` (not from plans).
- [ ] **Threat model published with the repo** —
      `MANDALAOS_SOVEREIGN/docs/THREAT_MODEL.md` (containment, not hypervisor
      isolation; no kernel-exploit claims).
- [ ] **Docs dry-run** — front-door docs match the flake and live behavior
      (GETTING_STARTED paths/status corrected 2026-09-15).

---

## Bundle layout

```
publication/evidence_<YYYY-MM-DD>/
  soak_18798.json        # gate 1, soak store
  soak_18790.json        # gate 1, fleet store (corroborating)
  dashboard.png          # gate 1, /mandala rendered from the live mirror
  gate3_hygiene.txt      # SHAs, version_truth/guard output, uptimes
  stranger_<tester>.md   # gate 2, per tester
```

Commit the bundle with the gate decision in the session note; update
`CURRENT_REALITY` §7 checkboxes at the same time.
