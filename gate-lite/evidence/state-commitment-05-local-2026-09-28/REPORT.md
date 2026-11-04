# Gate-lite second-producer capture — 0.5 state commitment (same host, 2026-09-28)

**Status:** same-host maintainer capture on the unpublished 0.5 candidate.
Not independent adoption; not authorization to tag, publish, or deploy.

## What this closes

The 0.5 candidate's second-producer gate (`continuity-receipt`
`INTEGRATION_READINESS.md`, row "Second producer capture"): a named runtime
outside the continuity-receipt reference tooling emits its own 0.5 bundle.
Gate-lite now emits a `state.commitment` record after `task.execution`
(vectors 22 ordering), committing the orchestrator registry state at
emission time.

## Producer identity

- Runtime: gate-lite, branch `codex/gate-lite-05-profile`; capture commit =
  the commit containing this report (branch tip; SHA published in the board
  post and the CR-side example README).
- Changed source: `gate_lite/orchestrator.py` sha256
  `599dde2c5f723a4c95d3dfb1edebb43ac7234b50b72c169286ad0ad3892a8447`
  (adds `_state_commitment()` plus the emission and receipt-id wiring);
  `gate_lite/registry.py` unchanged, sha256
  `715c164294774d4c7751acf47c48223945816613058f35a72177645b5f56a156`.
- Continuity-receipt runtime: `0.5.0a0` from source at
  `codex/continuity-05-adoption` (`d34c499`), installed editable.
- Runner profile (pinned): wrapper
  `MANDALAOS_SOVEREIGN_runner_argv/scripts/mandala-sandbox` sha256
  `f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e`
  (source `mandalaos-sovereign 9a0faf1`); `/usr/bin/bwrap` sha256
  `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71`
  (bubblewrap 0.9.0); `/usr/bin/jq` sha256
  `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566` (jq-1.7).
- Host: Linux 7.0.0-34-generic x86_64; Python 3.12.3.
- Key custody: the gate key was generated into the capture state directory
  (`gate.key`, mode 0600, not published); issuer DID
  `did:key:z6MksimyjJhBvzyrB3Z5CMHDte8Ubvk1jx5P12ffRa4JptD2`.

## Capture

Commands (full transcript in `transcript.txt`): fresh state dir;
`tenant-add`; `pass --minutes 30`; `exec` of the fixed no-network payload
`/usr/bin/python3 -c "print(42)"` through the pinned wrapper; registry
snapshot copied immediately after `exec` returned; `terminate`.

Artifacts:

- `bundle.json` — sha256
  `1c1947cb6da8f46fd85bbde57713ddfccdbc9f84281bc17361d4821ebb9774a2`;
  5 receipts: `session.pass.created`, `task.decision`, `task.execution`,
  `state.commitment`, `task.termination`; exec exit 0.
- `verdict.json` — Python verifier `TRUSTED` (rc 0).
- `rust-verdict.json` — Rust verifier `TRUSTED` (rc 0).
- `registry-after-exec.db` — sha256
  `a65a784f2919cb24f215d8c83c176a89c08615bc98e81e30dbafae9d2164267c`.
- `recompute.py` — independent recomputation, `ALL MATCH` (rc 0):
  executable digest, invocation digest (canonical argv with the exact
  envelope and workspace path), commitment count (3) and head digest.

## Semantics and limits

- `state_kind = gate-lite.registry-head`, `scope = gate-lite.registry`;
  count and head cover the `Registry.reload()` snapshot (tenants, slots,
  passes, snapshots, idempotency) — never raw SQLite bytes.
- The commitment is taken at emission time — inside `exec_`, right after
  `task.execution` and before the slot's `starting -> active` CAS. The
  snapshot here was taken when `exec` returned, so recomputation reverts
  exactly that one documented mutation.
- Verifier limits unchanged: signatures and shape only; it does not observe
  Bubblewrap execution, recompute digests, or prove state completeness.
- Same host, unpublished candidate: this capture satisfies the evidence
  shape of the second-producer gate; independent adoption (a different
  host/operator) remains open.
