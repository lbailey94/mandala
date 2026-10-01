# Public snapshot curation backlog — 2026-09-30

Tracks the gap between private `mandala-os` main and the curated public
snapshot `mandalaos-gate-lite`. The public repo is deliberately divergent (its
own history), so every port is a review act — never a fast-forward.

## Landed 2026-09-30

- **Egress-truth vocabulary** (private `0b6929f` → public PR #6,
  `curation/2026-09-30-egress-truth`): per-entry `"enforced"` flag, whole-network
  disclosure, design note, 4 tests. Public CI green; local clean-venv run
  against published `continuity-receipt==0.4.0`: 89 passed, 1 skipped.

## Private → public backlog (not yet ported)

1. **Runner-profile hold** (the largest slice): private `7fd8d54`, `704a863`,
   `63af388`, `4332d55` and the accompanying tests
   (`test_runner_profile.py`, `test_qualify_bwrap_runner.py`),
   `tools/qualify_bwrap_runner.py`, `tools/README.md`, pyproject pinning and
   `RunnerProfileError`/`sandbox_class = "unknown"` machinery. Requires an
   exact diff review plus privacy scan; the public snapshot must keep its own
   tested-pin provenance updated when this lands.
2. **Receipt version pinning** in orchestrator (`RECEIPT_SPEC`,
   `RECEIPT_PACKAGE_VERSION`) and the related `test_vectors` /
   `test_lifecycle_race` adjustments — coordinate with 1.
3. **Evidence refresh choices:** `evidence/bench-2026-09-18*/` updates,
   `bwrap-probe-2026-09-25/`, `wm-probe-2026-09-25/`. Decide case by case
   whether they are public-review material; keep version labels on all
   historical captures.
4. **Doc drift:** `gate-lite/HANDOFF_2026-09-18.md`,
   `gate-lite/INTEGRATION_CONTRACT.md`, `gate-lite/pyproject.toml`.

## Public → private backports needed

1. **POSIX kill fallback** (public `f9b3b1f`, PR #5): the systemd-absent /
   refusing fallback in the terminate path exists in the public snapshot but
   not in private `mandala-os` main. Reconcile deliberately (port into private
   or document why private differs) before the next curation, so the two trees
   do not silently diverge on the kill path.
2. Public runner-class claim review (`470b53c`) vs private
   `7fd8d54` — likely the same intent done independently in both histories;
   verify equivalence when touching the runner slice.

## Rules that held

- No fast-forward; the snapshot states its own provenance pin.
- Evidence keeps the version it was tested with; no reinterpretation.
- Privacy scan before any public push; no credentials, no host identifiers
  beyond what earlier snapshots already publish.
