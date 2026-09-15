# Handoff — post-S4 (2026-09-15)

**For:** next session. Today closed the Yama bridge through evaluation, fixed
the read path, executed S4, and wrote the actuator contract.

## 0. State of the world (verified at close, 2026-09-15 ~16:15 UTC)

| Repo | Head | Unpushed | Dirty |
|---|---|---|---|
| `MANDALA_OS` | `fc09a7f` (+ this handoff) | local-only | clean |
| `MANDALA_OS/LAKSHMI` | `6cc03f6` | 0 | clean |
| `MANDALA_OS/MANDALAOS_SOVEREIGN` | `3d2db8a` | 0 | clean |
| `WHITEMAGIC/WMv9` | `a54b380` | 0 | clean — **v9.1.6 released** (`391e03f`) |

Live: fleet sampler runs the new bridge read path (`--bridge-feed` default);
the 72 h edge-galaxy soak sampler is untouched and active (gate fires
~Sep 16 23:36Z). Tetragon/VM are stopped; policies deleted.

## 1. Shipped today

- **Read-path fix (mirror-first, D6):** collector appends sent records to a
  bounded feed ring; Lakshmi merges ring + store deduped by
  `(ts, policy_id, metric)` and sums event `value`s. LAKSHMI `6cc03f6`
  (+7 commits incl. this); SOVEREIGN `98f0e30` (feed ring) — both pushed.
- **S4 executed:** real eBPF capture; `shadow.access.v1` → `observing`
  (value 5); evidence `session-notes/2026-09-15_s4-tetragon-observe.md`.
- **Y1 actuator contract:** `design/ACTUATOR_CONTRACT_2026-09-15.md`
  (subject identity, router, actuator catalog + undo/expiry,
  `WM_ACTUATION=0`; slices Y1.0–Y1.4).
- **Packaging fix:** `packages/whitemagic.nix` version derived from
  `Cargo.toml` (was hardcoded `9.1.3`); takes effect on the next VM rebuild.
- **Docs:** original-notes alignment annex (`CURRENT_REALITY` §9), post-S4
  reality update, runbook corrections (bundle install, NixOS unit, tetra pty).

## 2. Open board

1. **Y1.0 — router skeleton** (next build): notify-only, record v2 fields,
   `WM_ACTUATION` arm/disarm + disclosure, tests. Contract §9; ships no
   enforcement.
2. **S4 follow-ups:** child-denial parsing; egress/shadow-write/crypto-miner
   policies; `wm doctor` bridge-feed line (release-coupled, rides WMv9);
   collector systemd unit; Tetragon Nix packaging (deferred); subject
   attribution (`unix_chkpwd` vs `cat` → Y1 contract §2).
3. **Publication gates** (`CURRENT_REALITY` §7): edge-galaxy ≥72 h soak
   (fires ~Sep 16 23:36Z), stranger install (≥4/5), repo hygiene (sovereign
   pinned — flake is at v9.1.5; consider bumping to v9.1.6).
4. **Custody owner actions:** physical card labels; paper-passphrase
   placement note (private).
5. **Release lane (other session):** v9.1.6 is out; release-health
   reconciliation + site facts sync belong to that lane.

## 3. Notes for the next operator

- Restarting the sampler resets its bridge `since` cursor to the first new
  window; trigger once after restart if a transition is needed.
- `pkill -f` self-match killed the driving shell twice during teardown —
  use bracketed patterns or PIDs.
- Tetragon cache stays at `~/.cache/mandalaos-s4/tetragon` (sha verified).
- VM rebuild from a cold store: 585 derivations / ~14 min.

## 4. References

- S4 run evidence: `session-notes/2026-09-15_s4-tetragon-observe.md`
- Bridge design (S4 ✅, D6): `implementation/yama-v0-bridge-design.md`
- Contract: `design/ACTUATOR_CONTRACT_2026-09-15.md`
- Runbook: `MANDALAOS_SOVEREIGN/docs/S4_TETRAGON_RUNBOOK.md`
- Canonical status: `CURRENT_REALITY_2026-09-13.md` (§4 update, §8, §9)
