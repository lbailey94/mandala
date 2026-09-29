# Mandala project status — 2026-09-28

This is the cross-repository status map. A code pin, a tested pin, and a public
pin are separate claims. Historical reports retain the version they tested.

| Component | Working code | Public state | Direct evidence | Next gate |
|---|---|---|---|---|
| gate-lite main | private `mandala-os` main `735b007`; emits `continuity-receipt/0.4`; dependency pinned to published `0.4.0` | `mandalaos-gate-lite` PR #3 merged as `bd8eee3`, curated 0.4 review snapshot; 0.3 evidence remains historical | main's prior local/clean-export evidence is pinned below; this review ran no new main tests | main stays the supported 0.4 lane pending reviewed candidate integration |
| gate-lite 0.5 candidate | `codex/gate-lite-05-profile` code pin `a7116fc5aa0d1893c3bf56d8c7d4955055fd0e53`; PR #1 head `1586e97`; exact local Bubblewrap profile, `state.commitment`, and terminal `receipt_incomplete` handling | PR #1 remains open; current head's pinned-dependency CI passed | same-host profile capture `gate-lite/evidence/bwrap-profile-05-local-2026-09-25/`; same-host second-producer capture `gate-lite/evidence/state-commitment-05-local-2026-09-28/`; this review ran 108 tests (6 runner-qualified skips) and independently recomputed the capture's executable, invocation, commitment count, and head (`ALL MATCH`) | independently test the updated packet on another administered host; host-specific runner digest must be explicitly reviewed |
| Continuity Receipt | separate repo: local `codex/continuity-05-adoption` `2ef890a`, four commits ahead of remote PR branch `73c2086`; those local commits include unpublished 0.6 authority work | v0.4.0 remains the published version. Draft PR #8 is the 0.5 candidate at `73c2086`; local 0.6 commits are not part of PR #8 | PR #8's Python 3.11/3.12, package, and Rust checks passed at its remote head. The local 0.6 work was not tested or published in this review. The CR checkout has uncommitted edits of unverified provenance; they remain untouched and were not reviewed | independently review the dirty CR diff and local 0.6 continuation; preserve version separation and record interop draft version drift before claiming compatibility |
| Sovereign Edition | private repo main `3819af6` (v9.2.9 loopback fix `26bc2f4`); flake input and lock pin WhiteMagic v9.2.9 | private repo; v9.2.9 is now maintainer-VM qualified | rooted output `/nix/store/li61sdzdpbjx4xfh3fgbf26qc0xad4a4-nixos-vm`; 13/13 containment checks, daemon and loopback-only read-only MCP active, Landlock enforced ABI v8, `wm doctor` healthy; report `MANDALAOS_SOVEREIGN/docs/VM_REVERIFY_V929_2026-09-28.md` | separate unassisted stranger-install and bare-metal gates remain open; preserve `docs/evidence/` untracked local files |
| Lakshmi / Yama | private `lakshmi` `35f93ed`; private Sovereign observation bridge source | private repos | observe-only policy path and per-policy report tooling exist; current checkout review found no fresh promotion-window evidence | retain observe/notify-only state until per-policy observation and false-positive review support a bounded promotion decision |
| WhiteMagic Gen3 | separate `WMgen3` main `33fe4eb` has the Rust Mandala bridge and `wm3 mandala` CLI | separate project; no Mandala integration release asserted here | `NEXT_PROJECT_GATES.md` records gate-lite 0.4 receipt #403873 in Gen3's LMDB substrate; this review did not repeat that integration test | run a fresh end-to-end consumer/replay test against exact current pins before advancing the integration claim |
| WhiteMagic substrate | separate `WMv9` working tree is on main, eight commits ahead of origin; tag `v9.2.9` resolves to `30d6115` | public v9.2.9 tag exists | tag existence does not qualify the Sovereign build; this review did not requalify the published binary or hosted service | preserve component-specific pin and qualification boundaries |
| eval endpoint | private hub `eval-endpoint/` | hosted evaluation route, not a Mandala product release | prior health probe only; no scored-run evidence gathered in this review | confirm exact external evaluation wire contract before a scored run |

The live pull request states above were checked on 2026-09-28. PR #1's
current head `1586e97` and PR #8's remote 0.5 head both have green CI. Neither
a green PR nor the same-host captures qualify an independent installation.
Do not carry the v0.4 published state onto either unpublished candidate.

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
