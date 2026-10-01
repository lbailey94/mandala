# Public snapshot curation backlog — 2026-09-30

Tracks the gap between private `mandala-os` main and the curated public
snapshot `mandalaos-gate-lite`. The public repo is deliberately divergent (its
own history), so every port is a review act — never a fast-forward.

## Landed 2026-09-30

- **Egress-truth vocabulary** (private `0b6929f` → public PR #6,
  `curation/2026-09-30-egress-truth`): per-entry `"enforced"` flag, whole-network
  disclosure, design note, 4 tests. Public CI green; local clean-venv run
  against published `continuity-receipt==0.4.0`: 89 passed, 1 skipped.
- **Runner-profile hold + receipt pinning** (private `7fd8d54`, `704a863`,
  `63af388`, `4332d55` → public PR #7,
  `curation/2026-10-01-runner-profile-hold`, stacked on PR #6): hold with
  `unknown`/`unqualified` refusal before token/payload/cache, `==0.4.0`
  pinning, qualifier tool + tests. Public CI green; clean-venv:
  102 passed, 6 skipped (all explicit runner-qualified skips).

## Private → public backlog (not yet ported)

1. **Evidence refresh choices:** `evidence/bench-2026-09-18*/` updates,
   `bwrap-probe-2026-09-25/`, `wm-probe-2026-09-25/`. Decide case by case
   whether they are public-review material; keep version labels on all
   historical captures.
2. **Doc drift:** `gate-lite/INTEGRATION_CONTRACT.md` (and the historical
   `HANDOFF_2026-09-18.md` if it should be refreshed; pyproject drift was
   resolved in PR #7).
3. **L2 egress slice → public** after private PR #2 review: proxy, helper,
   egress wrapper, enforced receipt outcomes, probe evidence.

## Public → private backports needed

1. **POSIX kill fallback** (public `f9b3b1f`, PR #5): the systemd-absent /
   refusing fallback in the terminate path exists in the public snapshot but
   not in private `mandala-os` main. Public PR #7 deliberately kept the public
   behavior and documented the divergence; the backport into private main is
   still pending.
2. Public runner-class claim review (`470b53c`) vs private
   `7fd8d54` — likely the same intent done independently in both histories;
   verify equivalence when touching the runner slice.

## Rules that held

- No fast-forward; the snapshot states its own provenance pin.
- Evidence keeps the version it was tested with; no reinterpretation.
- Privacy scan before any public push; no credentials, no host identifiers
  beyond what earlier snapshots already publish.
