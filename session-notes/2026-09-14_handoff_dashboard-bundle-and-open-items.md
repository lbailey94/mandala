# Handoff — dashboard bundle + open items (2026-09-14 evening)

**For:** next session. This captures what's committed, what the dashboard pass
should change (agreed in discussion, not yet built), and the open board.

## 0. State of the world (verified at handoff, ~01:00 UTC 2026-09-15)

| Repo | Head | Unpushed | Dirty |
|---|---|---|---|
| `WHITEMAGIC/WMv9` | `b63b527` | 7 commits (ours + other lanes') | 2 files |
| `MANDALA_OS/LAKSHMI` | `1baa310` | 2 commits (includes S3) | clean |
| `MANDALA_OS/MANDALAOS_SOVEREIGN` | `2fad625` | 4 commits (includes S4 kit) | clean |
| `MANDALA_OS` | `ceb3fce` | local-only repo | clean |

- `v9.1.5` tagged; **9.1.6 unreleased**; planned ceremony ≈**06:00 EDT** (10:00
  UTC) — the moment UTC+14 (Kiribati) enters Sep 16.
- **Bridge:** S1 merged (`3384dfb`) and pushed (origin `634b3fe`); worktree
  removed. S2 collector committed. S3 **live in production** (lamplighter
  restarted 23:48Z; window records carry `bridge` counts; dashboard shows all 7
  policies, bridge trio `clear` with feeds available). S4 kit committed
  (policy + runbook), in-guest run pending the VM rebuild.
- **Custody:** register + four copies verified across both cards (A1+B1 on
  `FA99-F6E6`; B2+C1 on `FEEC-FCE2`); B's identity/signature chain proven
  (`aade884b…` verifies the v9.1.5 manifest); rotation runbook + pre-release
  gate live. Owner actions left: physical card labels, paper-passphrase
  placement note (private).
- **Ops:** weekly bus JSONL retention live (`6cc0a9e`; timer Sun 05:20);
  `install.sh` pin wording corrected (`4f11e50`).

## 1. Dashboard bundle (to build next session)

**Diagnosis:** `dashboard.py:200 galaxy_observations()` sources from
`memory.search` (FTS-ranked), so "newest" is not guaranteed as volume grows.
`/api/events` is also empty-by-design until a 9.1.6 binary can emit
`sandbox_observation`.

**Fix A (recommended, LAKSHMI-only):** the sampler keeps a bounded
`observations` ring (last ~50 emitted records) in the mirror
(`mirror.write(...)` call in `lakshmi.py` `do_emit`, ~L1099); the dashboard
merges mirror-first + store search, deduped by `(ts, policy_id)`. Deep history
stays store-backed. **Fix B (deferred):** WM-side time-ordered listing tool
(release-coupled).

| # | Item | Touch points | Original-concept lineage |
|---|---|---|---|
| 1 | Recency fix (A) + dedupe | `lakshmi.py` mirror write; `dashboard.py` `galaxy_observations`, `/api/observations` | Lakshmi compactness: "compact Harmony Vector"; "no raw samples in memory" |
| 2 | Freshness disclosure (`written_at` age) | `/api/live` + panel | **Anti-Maya** / "Reflection of State": UI accurately renders Lakshmi's status |
| 3 | Bridge strip (latest `bridge` counts + newest `sandbox.*`/`shadow.*` records) | new `/api/bridge` or fold into `/api/live` | **Gnosis Portals**: "read-only introspection at every layer"; Karmic-trace surface |
| 4 | Events-feed disclosure ("no events yet" vs feed error) | `/api/events` | **Stoic card** + "no silent zeros" |
| 5 | **Explain-this per policy** (plain-language sentence from enter/exit/direction/version) | policies panel render | explain-first (Gevurah/Chesed: "every deny carries an explain link") |
| 6 | **Samma-Meter bands** (render hysteresis band + position; colour either extreme incl. under-use) | policies panel render | Middle Way: "sufficiency within bounds", flags under-utilisation |
| 7 | Collector `--follow` (stream stdin line-by-line; systemd-friendly) | `MANDALAOS_SOVEREIGN/scripts/yama-collector.py` | IndraNet/sensorimotor streaming; fail-soft spool unchanged |
| 8 | *Deferred:* `wm doctor` bridge line (feed reachability) | WMv9, release-coupled | "Real-time Awareness"; Vishnu degrade-loud |

**Tests:** extend `test_dashboard.py` (merge/dedupe, freshness age, empty-state
labelling, explain text, band classification).

## 2. Open items board

1. **9.1.6 ceremony (~06:00 EDT)** — freeze first (2 dirty WMv9 files now);
   run `security/custody_gate.sh` (expect exit 2 → disclose per-card
   verification); release-health reconciliation; site facts sync.
2. **Stranger-install gate** (ADOPTION Gate-2: ≥4/5 unassisted installs).
3. **VM rebuild → S4 execution** (`docs/S4_TETRAGON_RUNBOOK.md`), quiet window.
4. **Y1 decision** after S4 data: Rust evaluation engine vs Lakshmi step-0.
5. Other lanes: v9.1.6 nits (grimoire host-step, teach quiz, embedder probe),
   `release.sh` tag-before-CI ordering guard.
6. Custody owner actions: card labels; paper passphrase placement (private).

## 3. References

- Bridge design + slices: `implementation/yama-v0-bridge-design.md`
- Harmony Vector spec: `feasibility/harmony-vector-spec.md`
- Custody: `security/KEY_CUSTODY_REGISTER.md`, `ROTATION_RUNBOOK.md`,
  `custody_gate.sh`, `evidence/`
- Session notes: `2026-09-14_yama-bridge-s1-s2.md`,
  `2026-09-14_cross-lane-release-and-custody.md`
- Key commits: S1 `e7128a9`/merge `3384dfb`; collector sovereign `52b1347`;
  S3 LAKSHMI `1baa310`; custody `bff793a`/`9ca69e4`/`5b13f6a`; ops `6cc0a9e`;
  S4 kit sovereign `2fad625`; docs `ceb3fce`
