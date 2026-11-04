# Integrating a project with gate-lite (0.5 candidate)

This contract describes the intended integration for a cooperating agent
whose workload will run through the reviewed `mandala-sandbox` runner profile.
The private `mandala-os` 0.5 candidate provides the reviewed baseline profile:
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

The separate L2 candidate adds proxy-only destination enforcement under
`bwrap-egress-v1`; the baseline remains a whole-network grant. Both profiles
are limited to their exact qualified source, binaries, sidecars, and host.

## Version and ownership boundaries

| Boundary | Owner | Record per run |
|---|---|---|
| Project workload | integrating project | source revision, payload or envelope digest |
| Pass and lifecycle | gate-lite | gate-lite commit, tenant, agent DID, slot and task IDs |
| Runner | Sovereign runner | profile ID, executable path and SHA-256, dependencies, containment class |
| Receipt format and verification | `continuity-receipt` | installed package metadata version, imported runtime version, emitted `spec`, verifier verdict |

Use an isolated environment with Python 3.11+ and install `gate-lite` from a
pinned source revision. This candidate pins `continuity-receipt==0.5.0` in
package metadata and refuses startup with structured `dependency_*` errors
unless the installed distribution and the imported runtime both match exactly.
Record that resolved version in evidence. Do not silently reuse qualification
evidence after a dependency or runner change.

## Runner qualification profiles

### Bubblewrap-only baseline (`bwrap-v1`)

The baseline profile is bound to the portable `mandala-sandbox` wrapper and
the host Bubblewrap and `jq` executables. The gate-lite source pins these
SHA-256 digests:

| Component | SHA-256 |
|---|---|
| `mandala-sandbox` | `f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e` |
| `bwrap` | `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71` |
| `jq` | `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566` |

The receipt runner profile uses
`urn:mandala:runner-profile:bwrap-v1`. This qualifies the pinned wrapper and
dependencies for the tested Bubblewrap path. It does not establish that an
issuer actually used that runner, nor does it provide destination-level
network mediation. Do not describe this baseline as L2 enforced egress.

### Proxy-only L2 candidate (`bwrap-egress-v1`)

L2 uses a distinct wrapper and profile. The sandbox has no raw network; its
only network path is the host-side Unix-socket proxy and fetch helper. The
gate-lite runner requires exact identity matches for all shared dependencies
and these L2 components:

| Component | SHA-256 |
|---|---|
| `mandala-sandbox-egress` | `0a0720955e135ec2a6b31a74fcdb1a9c8ecfb372177fb8f6d925d48379b17a43` |
| `mandala-egress-proxy.py` | `73826dcc2390fa55b5e78cc1f5ceece99c52a73d20a2573240aaf39b7abc6227` |
| `mandala-fetch.py` | `d1ce7db2a926d80174319582e047f87d1f65672d4f22661dfd71b13f404bfb33` |
| `bwrap` | `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71` |
| `jq` | `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566` |

The signed runner profile uses
`urn:mandala:runner-profile:bwrap-egress-v1`. Its executable digest binds the
L2 wrapper, and its invocation digest binds the invocation, proxy/helper
sidecar digests, and declared allowlist. A missing or mismatched component
prevents the L2 profile from qualifying. Missing, malformed, or incomplete
proxy evidence makes execution fail and holds the slot as `receipt_incomplete`;
it must not be treated as proof that no egress occurred.

The proxy resolves DNS on the host and enforces declared destinations at the
HTTP `CONNECT` host-and-port boundary. It does not pin DNS answers to IP
addresses or filter URL paths, HTTP methods, TLS contents, or application
behavior. Treat the allowlist as a destination boundary, not application
policy. The current acceptance probe is
`python3 tools/egress_l2_probe.py`; its evidence is a local, same-host
qualification result. It is not independent-host, VPS, production, or broad
tenant-isolation evidence.

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
   version beside the bundle. `TRUSTED` means the protocol and configured
   policy checks passed; it does not establish that the issuer's factual
   claims were honest or independently prove execution under the claimed
   runner.

The copyable CLI flow is in [`README.md`](README.md#quick-start). MCP exposes
the same lifecycle over stdio or loopback HTTP through `mandala.pass`,
`mandala.exec`, `mandala.settle`, `mandala.terminate`, and `mandala.receipt`.
`mandala.exec` requires `token` in its schema. Treat the token as a secret;
exclude it from logs, bundles, and support tickets.

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
- A clean install from the stated gate-lite revision passes the exact
  `continuity-receipt==0.5.0` metadata/imported-version/spec guard.
- A baseline claim records the matching wrapper, Bubblewrap, and `jq` hashes
  and reports `bwrap-v1`. An L2 claim additionally records the exact egress
  wrapper and both sidecar hashes, reports `bwrap-egress-v1`, and passes the
  L2 acceptance probe on the identified host.
- Missing or wrong agent, slot, tenant, or token is refused before execution;
  restart and concurrent replay behavior are covered by gate-lite's suite.
- The project captures its output artifact, receipt bundle, dependency and
  runner identities, and offline verifier result without copying the pass
  token.
- Missing or incomplete L2 evidence fails closed. Record the host and scope
  of the qualification; do not generalize same-host evidence to other hosts
  or to production.
- The project and operator treat this as cooperative-tenant containment on a
  shared kernel. Use a separately qualified microVM boundary when workloads
  or tenants are untrusted relative to one another.

Start with one project adapter and its evidence bundle. Promote additional
runner capabilities only after the corresponding containment and recovery
checks pass on the exact candidate.
