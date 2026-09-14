# Receipt verification addendum 3 — card archive overlap analysis

Verifier: opencode (second instance), 2026-09-14 ~19:40 EDT. Read-only; no card
content, store, or backup written.

## Outcome: not reproducible — the anchored card is not the one mounted

- Receipt anchors: card LABEL `SD_CARD1`, UUID `FEEC-FCE2`; files
  `whitemagic-archives/v26-heritage-20260911.tar.zst` (320 MB) and
  `whitemagic-archives/vault-data-pre-redactstore-20260911.mdb` (2.5 GB).
- Currently mounted `SD_CARD1` (`/media/lucas/SD_CARD1`, `sda1`): UUID
  **FA99-F6E6** — a different card instance; the mount point was (re)created
  at 19:32 EDT, after the 19:05 receipt.
- `whitemagic-archives/` on the mounted card holds a different set
  (`codex-vault-20260912.tar.zst` 4.0 GB, `sd-wave2-laptop-dev-20260912` 3.4 GB,
  `v26-store-20260912` 971 MB, `v4-store`, `whitemagic-vault-20260912`,
  `windsurf-…`, plus `cold-tier-20260901/`, `local-backups-20260913/`,
  `og_whitemagic/`, `wm-historical-20260903/`). Neither receipted file exists
  anywhere under `/media/lucas` (depth ≤ 3); the other mount-point directories
  (`SD_CARD`, `3C44-E4B5`) hold no matches.
- Root cause is named by the receipt itself: it is the "third distinct card
  with this label." Three cards share LABEL `SD_CARD1`; UUID anchoring is the
  only reliable identity — which is how this mismatch is visible at all.

## Secondary observations

- Default `python3` has no `lmdb` module and there is no `~/.venvs`; the
  receipted "python-lmdb 2.3.0" environment was not identified, so the key-set
  method cannot be re-run here even with the card mounted.
- The claimed scratch `/tmp/opencode/v26-heritage` (~1.7 GB) is absent
  (already cleaned) — consistent with the receipt's "safe to delete" note.
- Operational note (unrelated to this receipt): the mounted card carries
  `wm-release-signing.key.2026-09-13.gpg` at its root — a release-signing key
  on removable media; worth a deliberate custody decision.

## Verdict

The overlap-analysis claims cannot be independently reproduced at the current
mount state — an environment/mount mismatch, not a method finding. Re-verify
when the `FEEC-FCE2` card is mounted again (or its exact paths are provided).
