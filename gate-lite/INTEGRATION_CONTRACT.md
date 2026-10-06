# Integrating a project with gate-lite (candidate 0.4)

This contract describes the intended integration for a cooperating agent
whose workload will run through a reviewed `mandala-sandbox` runner profile.
The private `mandala-os` 0.4 candidate currently has no reviewed real-runner
profile, so configuring a wrapper permits startup but real exec remains held
before token consumption or payload spawn. Executable identity and adapter
selection alone do not establish containment. A future qualified runner will
provide shared-kernel containment, not an untrusted-tenant boundary. The
public `mandalaos-gate-lite` main branch is a curated 0.4 review snapshot; its
historical 0.3 exercise remains separate from the 0.4 clean-export evidence.

## Version and ownership boundaries

| Boundary | Owner | Record per run |
|---|---|---|
| Project workload | integrating project | source revision, payload or envelope digest |
| Pass and lifecycle | gate-lite | gate-lite commit, tenant, agent DID, slot and task IDs |
| Sandbox | Sovereign runner | executable path and SHA-256, containment class, slice setting |
| Receipt format and verification | `continuity-receipt` | installed package version, emitted `spec`, verifier verdict |

Use an isolated environment with Python 3.11+ and install `gate-lite` from a
pinned source revision. This candidate pins `continuity-receipt==0.4.0` in
package metadata and checks for exactly 0.4.0 at startup. Record that resolved
version in evidence. Do not silently reuse qualification evidence after a
dependency or runner change.

## Minimum lifecycle

1. Configure a runner (`--runner`/`--slice` or `WM_GATELITE_RUNNER`). Startup
   refuses without a configured runner unless `--demo` explicitly opts into a
   simulated runner. A configured real runner currently remains unqualified
   and exec refuses it; `--demo` results must be labeled simulation.
2. Register a tenant and its allowed agent DID. `mandala.pass` rejects an
   unregistered agent. Supply time and spend bounds appropriate to the
   project; retain the returned `slot_id` and single-use `token` securely.
3. Once a profile is qualified, execute with the matching tenant, slot,
   payload, and token. A successful execution consumes the token; retry with a
   new pass or a matching `idempotency_key` for an already completed request.
   Reusing a key for a changed request is rejected. Inspect `mandala.status`
   for adapter selection, qualified runner class, simulation flag, and path
   before interpreting results. Until then, status reports class `unknown`
   and `profile_status=unqualified`.
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

- The current 0.4 candidate has no reviewed real-runner profile, so real exec
  is intentionally unavailable. `mandala.status` may show an `adapter_id`
  selected by an executable name or configuration hint, while `class` remains
  `unknown` and `profile_status` remains `unqualified`. These fields do not
  qualify a mechanism, and real exec must fail before token consumption or
  payload spawn.
- Before enabling a real-runner flow, qualification evidence must bind the
  exact executable digest and runner/dependency versions to mechanism-specific
  checks, and a reviewed mapping must establish that those checks justify a
  class in the pinned receipt vocabulary. Names, class hints, a successful
  wrapper exit, and a trusted receipt alone do not meet this requirement.
- After that profile is implemented and reviewed, a clean install from the
  stated gate-lite commit must complete the real-runner flow and record the
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
