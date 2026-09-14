# Cross-lane note — release train, security handoff, card custody (2026-09-14)

**Why:** parallel security lane delivered a handoff (`Documents/ChatGPT/whitemagic v9.3 development/work/SECURITY_LANE_HANDOFF_ITEMS_8_9_12_20260914.md`) plus a card-verification addendum. This note records how it relates to the Yama bridge work and what it changes.

## 1. Git — one linear main, no divergence

`main` (local, origin/main = `36c83a9`) contains, in order:

| Commits | Lane | Content |
|---|---|---|
| `e7128a9` + `3384dfb` | ours (bridge) | **S1**: sandbox drift → `sandbox_observation` bus events (merge) |
| `942981b`, `0925882`, `29042c0` | security lane | item 10 (dispatch timeout inside the scoped sandbox executor), item 11 (`sandbox.set_limits` atomic validation), 9.1.6 changelog note |
| `2c74a56`, `c251013`, `ba9f684`, `73459a0`, `ee140e5` | third lane | 9.1.6 governance slice (destructive-confirm gate bypass, claims effects, NLU session profiles, Yama budget floors, curated smoke gate) |

**10 commits ahead of origin/main**; the next shared push carries S1 plus both lanes' fixes — i.e. the v9.1.6 release push. No rebase/merge needed.

**Complementarity:** items 10/11 harden the *happy-path* containment semantics (timeout parity in the scoped executor; atomic limit validation) in adjacent-but-disjoint files from S1. The released subsystem will thus both time-out correctly and surface drift.

## 2. Coordination warning (honored)

The security handoff warns that backlog items 8/9 must land **after** the working-tree 9.1.6 slice, because the AHIMSA gate change overlaps `crates/wm-governance/src/dharma_gate.rs`. Remaining dirty files (not ours, untouched): `context.rs`, `pipeline.rs`, `dharma_gate.rs`, `resource_rules.rs`, `bin/wm.rs`, `claims_tools.rs`, `nlu.rs`, `scripts/curated_smoke_test.py`.

## 3. Card / signing-key custody — verified where it counts

Addendum 3 evidence confirmed: only card `sda1` (LABEL `SD_CARD1`, **UUID FA99-F6E6**) is attached; the receipted card `FEEC-FCE2` is absent; the mount point was recreated after the receipt; three cards share the label.

**But the artifact is intact:** `wm-release-signing.key.2026-09-13.gpg` (184 B) sits on the attached card and its sha256 is

```
17713cf55fd5cd5e326c9dd3ff614c07cbe3a88a1ef6004d9020b4ec1fd9b757
```

which **matches the receipted `17713cf5…`** in `CURRENT_REALITY_2026-09-13.md` §8. The off-machine key backup is therefore verifiable today; the anchor mismatch is a receipt-method lesson (UUID anchoring is the only reliable identity), exactly as the verifier named.

**Pending custody decision (owner):** an encrypted release-signing key on removable media with three identically-labelled cards. Recommendation: physically label cards by UUID, keep the ciphertext as-is, and add a custody line to the release checklist before the v9.1.6 push.

**Repro gap noted:** the key-set comparison used an unreproducible `python-lmdb 2.3.0` environment; future receipts should pin the environment (e.g. `nix shell nixpkgs#python3Packages.lmdb`) so verification is repeatable.

## 4. Effect on the bridge work

- S1 rides the next push/release; nothing to re-do.
- Our three pending decisions stand: (1) push + v9.1.6, (2) `lakshmi-sampler` restart (S3 activation), (3) VM rebuild timing for the in-guest Tetragon leg — the card/custody item (4) joins the release checklist.
