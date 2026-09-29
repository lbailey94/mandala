# Second laptop independent adoption packet

Run on a different laptop with a fresh checkout and environment. Preserve
the command transcript, package metadata, binary hashes, probe JSON, bundle,
both verifier verdicts, and any failures. Do not copy the first laptop's
virtual environment, probe result, generated bundle, or gate state.

## Source pins

- Sovereign portable wrapper: `lbailey94/mandalaos-sovereign`, commit `9a0faf1`.
- Continuity Receipt unpublished 0.5 candidate: `lbailey94/continuity-receipt`,
  commit `73c2086f3421ba4e8ce11bbacfe6ad39e0fff309` (draft PR #8 head).
- Gate-lite candidate: `lbailey94/mandala-os`, commit
  `a7116fc5aa0d1893c3bf56d8c7d4955055fd0e53` (candidate code pin; the
  packet update changes documentation only).

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
   Run the full `gate-lite/tests` suite and confirm any skipped cases are
   explicitly runner-qualified skips. If bwrap or jq hashes differ from the current
   gate-lite profile, expect a fail-closed `unknown` status. Review a new
   exact profile before retrying; do not change the hardcoded pins just to
   force a passing receipt.
4. From a new gate state, issue a pass, execute a fixed no-network payload
   through the candidate wrapper, terminate the task, and export the bundle.
   Verify it offline with Python and Rust 0.5. Recompute the wrapper and
   canonical invocation digest from the captured execution arguments and
   compare them with the signed `runner_profile` claim. Recompute
   `state.commitment` from the captured registry state and verify the count,
   head, and ordering. Check missing and altered profile/commitment negatives.
5. Inject a controlled emitter failure after `task.execution` and before
   `state.commitment`. Confirm status reports terminal `receipt_incomplete`,
   no success result is cached, the partial bundle ends at `task.execution`,
   and another call cannot rerun the payload. Preserve the incomplete bundle
   and registry state; treat any deviation as a failed acceptance gate.
6. Separately build a small WhiteMagic `wm-receipts` consumer against this
   exact unpublished 0.5 source and run it through a new gate-lite slot.
   Export the consumer verdict and final gate bundle. Label this as source
   integration, since WhiteMagic's current tag still pins 0.4.

The acceptance record must distinguish: host mechanism checks, signed
receipt conformance, state commitment recomputation, failure recovery, source
integration, and unassisted installation. A same-host replay of the first
laptop's artifacts does not count as independent adoption.
