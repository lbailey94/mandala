# Mandala project status — 2026-09-24

This is the cross-repository status map. A code pin, a tested pin, and a public
pin are separate claims. Historical reports retain the version they tested.

| Component | Working code | Public state | Direct evidence | Next gate |
|---|---|---|---|---|
| gate-lite | private `mandala-os` `033e5ce`; emits `continuity-receipt/0.4` | `mandalaos-gate-lite` PR #3 merged as `bd8eee3`, curated 0.4 review snapshot; 0.3 evidence retained as historical | local and clean-export 86-test suites; 0.4 real-runner clean-export evidence in `gate-lite/evidence/outsider-2026-09-24-04/`; public PR CI passed | independent other-host tester is a separate gate |
| Continuity Receipt | separately maintained protocol and verifier | public `continuity-receipt` v0.4.0 published on PyPI and crates.io; hosted verifier reports 0.4.0 | release evidence in the protocol repo; gate-lite uses the published Python dependency | pin the exact verifier version in every evidence bundle |
| Sovereign Edition | private `mandalaos-sovereign` local `5752f93` pins WM v9.2.8; one commit ahead of origin/main as inspected | private repo | v9.2.7 VM re-verification: `MANDALAOS_SOVEREIGN/docs/VM_REVERIFY_2026-09-24.md`; it does not qualify v9.2.8 | flake check, VM build and in-guest verification on the v9.2.8 pin, then publish exact candidate/evidence |
| Lakshmi / Yama | private `lakshmi` `35f93ed` | private repo | 94 local tests; telemetry and observe policy path; notify-only actuator | collect promotion windows and false-positive review before any enforcement |
| eval endpoint | private hub `eval-endpoint/` | hosted evaluation route, not a Mandala product release | 24 local tests; deployment status requires a separate live check | confirm exact external evaluation wire contract before a scored run |
| WhiteMagic substrate | separate project | public `whitemagic` v9.2.8 release | release is not Sovereign VM qualification | reverify each Sovereign pin in its VM |

## Boundary for future projects

Gate-lite currently offers cooperative-agent governance with a required,
single-use pass token and shared-kernel bwrap/Landlock containment. `--demo`
explicitly selects simulation. It does not establish isolation for untrusted
tenants. The microVM floor, external anchor issuance, WM store/karma ledger
integration, and Yama enforcement are distinct future lanes. See
`gate-lite/README.md`, `MANDALAOS_SOVEREIGN/docs/THREAT_MODEL.md`, and
`publication/GATE_EVIDENCE_PLAYBOOK.md` for their respective contracts.

## Evidence rule

For each future candidate record the source commit and tree state, dependency
versions, runner path and hash, test result, real-runner result, verifier
version and verdict, and which public revision carries the evidence. Do not
carry a result forward across a code, dependency, or Sovereign source-pin
change without a fresh qualification run.
