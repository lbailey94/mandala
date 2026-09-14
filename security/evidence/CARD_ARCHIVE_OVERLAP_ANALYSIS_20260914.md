# Card archive overlap analysis (2026-09-14)

Card: LABEL `SD_CARD1` / UUID `FEEC-FCE2` (third distinct card with this
label). Contents: `whitemagic-archives/` only — `v26-heritage-20260911.tar.zst`
(320 MB, sha256 verified OK) and `vault-data-pre-redactstore-20260911.mdb`
(2.5 GB). Method: read-only. No store, service, or card content was written.
LMDB compared with a concurrent read-only reader (python-lmdb 2.3.0,
msgpack values); key sets compared per DBI.

## 1. v26-heritage tar → heritage store: 100% duplicate

`wm ingest --dry-run` against the heritage store (58,432 memories, ledger
79,877 entries):

```
found=60459 unchanged=60454 ingested=0 chunks=0 redactions=0 skipped=45 errors=0
```

Every non-skipped file is byte-identical to an entry already in the store's
ingest ledger — **zero unique content**. The 45 skipped files have
credential-shaped names (`id_rsa`, `token`, `passwords`, …), which the
ingester refuses by design; they were not and should not be ingested
un-redacted.

## 2. vault pre-redactstore `.mdb` → live vault: ~99.95% overlap

Live vault baseline: 319,823 memories / 7 galaxies. Per-DBI key comparison
(card vs live):

| DBI | card | live | overlap | uniq card | uniq live |
|---|---|---|---|---|---|
| codex | 12,493 | 12,493 | 12,493 | 0 | 0 |
| karma | 94,887 | 94,887 | 94,887 | 0 | 0 |
| sessions | 53,320 | 75,696 | 53,320 | 0 | 22,376 |
| research | 132,899 | 134,823 | 132,821 | **78** | 2,002 |
| associations | 1,601 | 1,601 | 1,601 | 0 | 0 |
| aria / dreams | 106 / 217 | 106 / 217 | all | 0 | 0 |
| idx_content_hash | 180,948 | 201,684 | 180,338 | **610** | 21,346 |
| idx_tags | 49,870 | 59,131 | 49,864 | 6 | 9,267 |
| idx_importance | 2,742 | 2,738 | 2,738 | 4 | 0 |
| idx_temporal | 3,239 | 3,296 | 3,237 | 2 | 59 |
| revisions | 23 | 703 | 23 | 0 | 680 |

**Unique-to-card totals: 78 research records, 610 content-hash entries
(267 sessions + 258 research + 85 codex), and a trivial dozen
tag/importance/temporal entries.** Everything else is a strict subset; the
live store has grown well beyond the Sep-11 snapshot.

### Interpretation

- Same-ID/different-hash entries (267 sessions + 85 codex) are the
  **redactstore signature**: those records still exist in live, but their
  content changed — the card preserves the **pre-redaction versions**.
- 258 research hashes + 78 research records are superseded/deleted chunks
  (`source:CODEX_VAULT` 56-chunk ingest and `source:codex-cat`) — an earlier
  chunking generation no longer present in live.
- The 45 skipped tar files and the 350 pre-redaction records are exactly the
  material that should **not** be blindly re-ingested — re-uploading would
  partially undo the redaction.

## Recommendation

Keep the card as the pre-redaction archive; do not ingest wholesale.
Optional next step (owner decision): a selective review of the ~350
pre-redaction records (session/codex) to confirm whether the redaction
should stand, per-record — read-only until a decision. The heritage tar
needs no action (already fully present).

## Caveats

Key-set comparison proves identity/overlap, not byte-equality of values;
content-hash index deltas are the content-level signal used above. The
2.5 GB `.mdb` has no checksum; its integrity is evidenced by opening and
reading cleanly (no LMDB errors across ~800k key reads). Card remains
mounted; extraction scratch (~1.7 GB at /tmp/opencode/v26-heritage) is
re-derivable and safe to delete.