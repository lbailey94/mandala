# Integrating a project with gate-lite (0.5 candidate)

This contract describes the intended integration for a cooperating agent
whose workload will run through the reviewed `mandala-sandbox` runner profile.
The private `mandala-os` 0.5 candidate provides one exact reviewed profile:
the byte-identical wrapper at `gate-lite/runners/bwrap-v1/mandala-sandbox`
with pinned Bubblewrap and `jq` dependencies reports class `bwrap` and
`profile_status=locally_qualified`. Any other configured executable, or a
contradictory class hint on the reviewed wrapper, is refused before token
consumption or payload spawn; adapter selection and filenames are never
qualification evidence. Containment here is shared-kernel support for
cooperative agents, not a boundary for untrusted tenants. The public
`mandalaos-gate-lite` main carries this reviewed 0.5 runtime (published
2026-10-09); historical 0.3/0.4 evidence remains separate and keeps its own
labels.

## Version and ownership boundaries

| Boundary | Owner | Record per run |
|---|---|---|
| Project workload | integrating project | source revision, payload or envelope digest |
| Pass and lifecycle | gate-lite | gate-lite commit, tenant, agent DID, slot and task IDs |
| Sandbox | Sovereign runner | executable path and SHA-256, containment class, slice setting |
| Receipt format and verification | `continuity-receipt` | installed package version, emitted `spec`, verifier verdict |

Use an isolated environment with Python 3.11+ and install `gate-lite` from a
pinned source revision. This candidate pins `continuity-receipt==0.5.0` in
package metadata and refuses startup with structured `dependency_*` errors
unless the installed distribution and the imported runtime both match exactly.
Record that resolved version in evidence. Do not silently reuse qualification
evidence after a dependency or runner change.

## Minimum lifecycle

1. Configure the reviewed runner (`--runner`/`--slice` or
   `WM_GATELITE_RUNNER`). Startup refuses without a configured runner unless
   `--demo` explicitly opts into a simulated runner. Only the exact reviewed
   wrapper and dependency identities qualify; other configured identities and
   contradictory class hints are refused before token consumption or payload
   spawn. `--demo` results must be labeled simulation.
2. Register a tenant and its allowed agent DID. `mandala.pass` rejects an
   unregistered agent. Supply time and spend bounds appropriate to the
   project; retain the returned `slot_id` and single-use `token` securely.
3. Execute with the matching tenant, slot, payload, and token. A successful
   execution consumes the token; retry with a new pass or a matching
   `idempotency_key` for an already completed request. Reusing a key for a
   changed request is rejected. Inspect `mandala.status` for `adapter_id`,
   runner class (`bwrap` / `locally_qualified` for the reviewed wrapper),
   simulation flag, path, and executable digest before interpreting results;
   anything else reports `unknown` / `unqualified`.
4. Settle and terminate the slot, including a zero-value settlement when no
   charge applies. Preserve the resulting `task_id`.
5. Export the receipt bundle and verify it offline with the published
   `continuity-receipt-verify` command. Record the verdict and exact verifier
   version beside the bundle. A `TRUSTED` verdict validates the protocol and
   configured policy checks; it does not establish that the issuer's factual
   claims were honest or that the workload ran in a microVM.

The copyable CLI flow is in [`README.md`](README.md#quick-start). MCP exposes
the same lifecycle over stdio or loopback HTTP through `mandala.pass`,
`mandala.exec`, `mandala.settle`, `mandala.terminate`, and `mandala.receipt`.
`mandala.exec` requires `token` in its schema. The project should treat a
token as a secret and avoid including it in logs, bundles, or support tickets.

## Acceptance for a new project adapter

- Only the exact reviewed wrapper and dependency identities have a real-runner
  profile; every other configured identity (and any contradictory class hint)
  is refused before token consumption or payload spawn. `mandala.status` may
  show an `adapter_id` selected by an executable name or configuration hint
  while `class` remains `unknown` and `profile_status` remains `unqualified`;
  these fields do not qualify a mechanism by themselves.
- Before enabling a real-runner flow, qualification evidence must bind the
  exact executable digest and runner/dependency versions to mechanism-specific
  checks, and a reviewed mapping must establish that those checks justify a
  class in the pinned receipt vocabulary. Names, class hints, a successful
  wrapper exit, and a trusted receipt alone do not meet this requirement.
- The reviewed profile implements this requirement: a clean install from the
  stated gate-lite commit completes the real-runner flow and records the
  qualified `task.execution.sandbox_class` with its evidence bundle.
- Missing or wrong agent, slot, tenant, or token is refused before execution;
  restart and concurrent replay behavior are covered by gate-lite's suite.
- The project captures its own output artifact, receipt bundle, dependency
  versions, and offline verifier result without copying the pass token.
- Any project-specific resource binds, network destinations, or store access
  are declared and tested in the runner envelope before claiming support.

Start with one project adapter and its evidence bundle. Promote additional
runner capabilities only after the corresponding containment and recovery
checks pass on the exact candidate.
