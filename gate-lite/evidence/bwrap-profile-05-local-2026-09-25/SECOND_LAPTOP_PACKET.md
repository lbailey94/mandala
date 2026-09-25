# Second laptop independent adoption packet

Run on a different laptop with a fresh checkout and environment. Preserve
the command transcript, package metadata, binary hashes, probe JSON, bundle,
both verifier verdicts, and any failures. Do not copy the first laptop's
virtual environment, probe result, generated bundle, or gate state.

## Source pins

- Sovereign portable wrapper: `lbailey94/mandalaos-sovereign`, commit `9a0faf1`.
- Continuity Receipt unpublished 0.5 candidate: `lbailey94/continuity-receipt`,
  commit `e4d2f8a3a564eb3af85c472eaed0cdc70eb65e88`.
- Gate-lite candidate: use the commit identified by the gate-lite PR for
  `codex/gate-lite-05-profile` once created.

## Required independent checks

1. Record host OS/kernel, `bwrap --version`, package ownership and package
   verification for Bubblewrap and jq, and SHA-256 of wrapper, bwrap, jq,
   Python/Rust verifier sources, and the probe binary. Record whether the
   platform can run unprivileged Bubblewrap; a refusal is a finding.
2. Install the wrapper in an isolated candidate path from the pinned source.
   Run wrapper unit tests, Bash syntax check, the fixed
   `gate-lite/tools/qualify_bwrap_runner.py` probe with the wrapper and
   Bubblewrap digests pinned, an enabled/disabled network control, and
   read-only/writable workspace controls. Preserve raw JSON and exits.
3. Install Continuity Receipt 0.5 source and gate-lite in a fresh venv.
   Run their focused tests. If bwrap or jq hashes differ from the current
   gate-lite profile, expect a fail-closed `unknown` status. Review a new
   exact profile before retrying; do not change the hardcoded pins just to
   force a passing receipt.
4. From a new gate state, issue a pass, execute a fixed no-network payload
   through the candidate wrapper, terminate the task, and export the bundle.
   Verify it offline with Python and Rust 0.5. Recompute the wrapper and
   canonical invocation digest from the captured execution arguments and
   compare them with the signed `runner_profile` claim. Check missing and
   altered profile negatives.
5. Separately build a small WhiteMagic `wm-receipts` consumer against this
   exact unpublished 0.5 source and run it through a new gate-lite slot.
   Export the consumer verdict and final gate bundle. Label this as source
   integration, since WhiteMagic's current tag still pins 0.4.

The acceptance record must distinguish: host mechanism checks, signed
receipt conformance, source integration, and unassisted installation. A
same-host replay of the first laptop's artifacts does not count as
independent adoption.
