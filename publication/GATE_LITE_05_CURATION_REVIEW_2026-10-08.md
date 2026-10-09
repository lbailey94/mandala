# Gate-lite 0.5 — curation review (for the Codex / gate-lite lane)

**Date:** 2026-10-08
**Author:** opencode (T4800-S), for Lucas + Codex review
**Status:** Evidence review complete — **PASS on the 0.5 candidate (bounded same-host
maintainer exercise)**. Friction fixes + push state to resolve before curation.
**Related:** `GATE_LITE_OUTSIDER_EXERCISE.md` (protocol v1 — stale, see F8),
`GATE_EVIDENCE_PLAYBOOK.md`, board #776–#778, claim #775.

---

## 1. What was tested

| Run | Pin | Result | Evidence |
|---|---|---|---|
| A — main posture | `main` @ `6fd651c` | **Refused by design** (runner-profile hold): clean export, 110 tests OK / 6 runner-qualified skips, `exec` fail-closed `RunnerProfileError` before token/payload; no receipt | `gate-lite/evidence/outsider-2026-10-08/` |
| B — 0.5 candidate | `codex/gate-lite-05-profile` @ `8ea8c7e` | **PASS**: exec exit 0, `sandbox_class=bwrap`, $0 settle (`outsider-1008-05`), receipt `TRUSTED` (7 receipts), 3 verifiers `TRUSTED` exit 0, runner profile digest matches | `gate-lite/evidence/outsider-2026-10-08-05/` |

Environment (both runs): T4800-S, Python 3.12.3, bwrap `e3189038…` (0.9.0-1ubuntu0.3),
jq `59cfd58d…` (1.7.1-3ubuntu0.24.04.2), pinned wrapper
`f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e` (extracted from
`mandalaos-sovereign@9a0faf1:scripts/mandala-sandbox` — the installed
`~/.local/bin/mandala-sandbox` is a **different build**).

Bundle facts (run B): spec `continuity-receipt/0.5`; profile
`urn:mandala:runner-profile:bwrap-v1`; wrapper digest `f7da8d6c…96411e`; no token in
any evidence file.

**Disposition:** PASS for the bounded same-host maintainer exercise with the pinned
qualified wrapper. **NOT independent adoption** (same host as qualification, no
second machine installed/verified this candidate).

---

## 2. Findings and frictions (fix before curation)

| # | Finding | Severity | Recommended fix (owner) |
|---|---|---|---|
| F1 | **Pin drift.** `orchestrator.py` exact-checks `==0.5.0`; `pyproject.toml` + README allow `>=0.5.0,<0.6` → resolves 0.5.1 on PyPI → 72-error traceback cascade, `ctl.py` can't even run `tenant-add`. | **Blocker** | Make packaging + docs exact (`==0.5.0`) at the candidate pin, and make the runtime mismatch a **structured refusal** (one clear error: expected X, found Y). (Codex) |
| F2 | **Tested tip is unpushed.** Local `8ea8c7e`; `origin/codex/gate-lite-05-profile` is `1586e97` (1 behind). The tested tree exists only on T4800-S. | **Blocker for curation** | Push `8ea8c7e` (or rebase the intended tip) so the tested sha is public; then re-run the exercise on the frozen pushed sha. (Codex — the commit is yours; do not let the curation pin an unpushed tree) |
| F3 | **Non-hermetic tests.** Exporting `WM_GATELITE_RUNNER` breaks runner-guard tests (clean-env: 108 OK, skipped=6, exit 0; with runner env: 5F/0E/6S). | High | Neutralize env in guard tests (monkeypatch.clear) so a runner-configured host runs the same suite. (Codex) |
| F4 | **Hardcoded skip policy.** `HAS_QUALIFIED_RUNNER_PROFILE=False` → real-runner acceptance tests skip even with a qualified pinned wrapper. | High | Derive from qualification (env/profile check) or an explicit documented flag; disclose skip semantics in the report. (Codex) |
| F5 | **Wrapper acquisition missing.** Protocol assumes the runner is installed; the qualified build is not the one on `~/.local/bin`. | High | Ship the pinned wrapper (or its retrieval step from `mandalaos-sovereign@9a0faf1`) with expected sha in the snapshot + protocol. (Codex) |
| F6 | **Protocol v1 stale for 0.5.** Says CR 0.4, implies `bwrap-landlock`; 0.5 emits `sandbox_class=bwrap`. | Medium | Update `GATE_LITE_OUTSIDER_EXERCISE.md` to the 0.5 flow (exact pin, wrapper acquisition, class label, dispositions A/B above). (opencode can draft; Codex reviews) |
| F7 | **Token handling undocumented.** Single-use, unrecoverable; evidence runs must never persist it. | Medium | Document; optional `--token-stdin`; add to protocol notes. (Codex) |
| F8 | **`make_vectors.py` rewrites tracked vectors** (git churn during exercises). | Low | Document as expected, or generate into an evidence dir. (Codex) |
| F9 | **Structured errors.** Version/profile refusals surface as tracebacks/cascades. | Medium | Return one structured refusal object (class, expected, found, next step) from preflight. (Codex) |

---

## 3. Curation plan (recommended)

**Shape A — curate the 0.5 snapshot from the branch tip (recommended).**
1. Apply fixes F1/F3/F4/F7/F8 (+F9 if quick) on the branch.
2. Push the frozen tip (F2); freeze the sha in the snapshot.
3. Re-run the exercise once on the frozen pushed sha → final evidence set
   (`outsider-<date>-05-final/`).
4. Curate the public snapshot around: branch tip sha, wrapper pin + acquisition,
   runs A+B evidence, disclosed skips, claim boundaries below.
5. New PR on the public `mandalaos-gate-lite` repo (0.4 stack PR #6/#7 remains the
   current public posture; 0.5 becomes the next cut).

**Shape B — wait for 0.5 promotion to main.** Cleaner lineage, but couples the
snapshot to a merge decision; not required when the snapshot can pin the branch.
**Main promotion of 0.5 is a separate owner decision.**

**Public claim boundaries (do not exceed):** shared-kernel containment (bwrap) —
containment-class, never untrusted multi-tenant; pass → exec → settle → terminate
with per-transition receipts; fail-closed on unqualified runners; verifier proves
the issuer-signed chain and receipt shape, not that the issuer used the claimed
wrapper; no custody. State the pinned-laptop limits and "not independent adoption"
verbatim.

**Dual-host (next gate):** `SECOND_LAPTOP_PACKET.md` (wrapper `9a0faf1`, CR draft
PR #8 head `73c2086`, gate candidate `a7116fc`) + the Mac arm64 profile draft
(`SharedWorkspace/mac-stranger-ops/.../2026-10-05-D1-arm64-profile/`) → the
independent-adoption gate after this snapshot.

---

## 4. Pre-publish checklist

- [ ] F1 exact pin + structured refusal (Codex)
- [ ] F2 push frozen tip (Codex)
- [ ] F3/F4 hermetic + skip policy (Codex)
- [ ] F5/F7 wrapper acquisition + token handling in protocol/snapshot (Codex)
- [ ] F6 protocol v1 → v2 update (opencode draft, Codex review)
- [ ] Freeze sha; final exercise re-run; evidence review sign-off (Lucas)
- [ ] PR + public copy review (Codex/Lucas)

## 5. Open questions for Codex

1. Is `8ea8c7e` the intended tip to push, or should the binding commit be
   re-created on top of `1586e97` with a clean message?
2. Accept exact `==0.5.0` packaging everywhere, or relax the runtime check to
   0.5.x pending verifier compatibility evidence?
3. Should the snapshot include run A (main hold refusal) as proof of fail-closed
   posture? (Recommended: yes, clearly labeled.)
