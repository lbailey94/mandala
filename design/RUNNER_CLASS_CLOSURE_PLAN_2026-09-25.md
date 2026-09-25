# Runner class closure plan — 2026-09-25

**Status: proposed plan; classification gap remains OPEN.** This document does not qualify a runner, alter any signed receipt, or close an adoption/release gate.

Drafted by GPT-6 Luna; reviewed and corrected against source and the captured status output by Codex.

## Evidence and precise problem

The 2026-09-25 rehearsal report identifies the discrepancy directly: gate-lite receipts/status reported `bwrap-landlock`, but the measured runner was `/home/lucas/.local/bin/mandala-sandbox`, a shell wrapper that assembles Bubblewrap namespace flags and ends with `exec bwrap ...`; it contains no `landrun` or Landlock invocation. The report binds that runner to SHA-256 `de273c62ae22147634164e84cc9b6f6ae83a7f25e05755b50bc7c1257f525641`. The report explicitly leaves runner classification OPEN.

Current gate-lite source has a second truth gap beyond the label: `SandboxRunner.sandbox_class` is a class constant (`bwrap-landlock`) independent of the configured executable. The runner is selected by `WM_GATELITE_RUNNER` or `--runner`; `_emit` signs that constant into `task.execution`. `runner_info()` reports the configured `runner_path` (confirmed in the 2026-09-25 run), but does not verify the executable's identity or mechanism. A renamed or replaced executable can therefore inherit the same class without verification. The configuration does not bind runner bytes, version, or a declared mechanism profile to the receipt.

The Sovereign module and docs distinguish two implementations. `modules/landlock-isolation.nix` builds `mandala-sandbox` with Bubblewrap and says Landlock can be layered separately; it builds `landrun-sandbox` as pure Landlock for services already inside a Landlock domain. The module routes the ordinary read-only service to Bubblewrap and the Landlock daemon to pure Landlock because Bubblewrap mount setup fails under an active Landlock domain. The threat model describes active runner alternatives as Bubblewrap or pure Landlock. This supports keeping those classes separate; it does not substantiate a combined class for the rehearsal wrapper.

Continuity Receipt has an important version boundary. Published `SPEC.md` 0.4 names `bwrap-landlock|microvm-ch|microvm-fc`; its JSON schema only says `sandbox_class` is a string, so schema acceptance is broader than spec conformance. The 0.4.0 package/tag is the published verifier boundary. The local checkout's `SPEC_0.5_DRAFT.md`, schema, Python, and Rust are development candidate artifacts: 0.5 schema and Python/Rust validation constrain values to `bwrap-landlock`, `microvm-ch`, `microvm-fc`, and `none`. The 0.5 draft does **not** add Bubblewrap-only or pure-Landlock values. The rehearsal's successful 0.4 verification therefore establishes verifier acceptance and signature/policy validity, not truth of an unobserved runner mechanism. Do not cite the 0.4 schema's `type: string` as permission to mint an undocumented value.

## Protocol decision required before implementation

Adopt mechanism-specific classes in a new, explicitly versioned receipt vocabulary. Proposed vocabulary:

- `bwrap`: Bubblewrap namespace runner; do not imply Landlock.
- `landlock`: pure Landlock runner; do not imply namespaces.
- `bwrap-landlock`: only when both mechanisms are actually applied to the execution being attested.
- Preserve `microvm-ch` and `microvm-fc` only for their corresponding measured VM runners.
- `none`: issuer claims no OS confinement; retain this only where that meaning is useful and specified.

**Recommendation:** amend the **unpublished** 0.5 draft/schema/vectors/dual implementations with `bwrap` and `landlock` before its freeze. If 0.5 has been frozen or published by the time this work lands, use the next version instead. Do not revise published 0.4 semantics or reinterpret its `bwrap-landlock` value. Treat the combined value as legacy for new production emissions unless one execution demonstrably enforces both mechanisms. Require the same exact enum and semantics in prose, schema, Python, Rust, and conformance vectors. A version number alone does not prove enforcement; it identifies the vocabulary whose issuer claims still need evidence.

If protocol work cannot land first, gate-lite's safe interim behavior is to refuse real execution when the selected runner cannot be bound to a class permitted by the active receipt spec. Do not write a guessed `bwrap-landlock`, an undocumented 0.4 string, or `none` to make the execution appear conformant. Stub/demo behavior remains explicitly simulated and must never be represented as a real contained execution.

## Gate-lite configuration and signed evidence binding

Replace inferred/hard-coded classification with an explicit, fail-closed runner profile. Configuration should identify the runner path, expected SHA-256, protocol version, class, and required mechanism checks. At startup, resolve the executable once, hash the bytes actually invoked, validate the profile against the active receipt version, and fail startup/real-run readiness on missing, unreadable, changed, unknown, or incompatible inputs. Avoid hashing a path and later invoking a different path; pin the resolved executable and reject symlink/path changes or verify again immediately before exec.

Pin the gate-lite emitter to an explicit receipt spec and tested dependency version during this migration. Today `pyproject.toml` allows `continuity-receipt>=0.4.0`, while `Orchestrator._chain()` creates a new `TaskChain` without a `spec` argument; installing a newer package could change new bundle versions before gate-lite deliberately selects and qualifies them. A clean install must report the resolved package version, and a dependency upgrade must require an explicit spec choice plus renewed tests.

The profile must not be an operator-provided free-form string that is copied into a signed receipt. Each supported profile needs a reviewed binding from a known runner build/hash (or an independently verifiable package identity) to its declared mechanism. Receipt evidence should bind at least: profile identifier/version, class, executable digest, runner protocol, and the exact invocation/config digest. If the current receipt schema cannot carry these fields, keep them in a signed/hash-bound companion attestation referenced from the receipt or add a versioned receipt field before rollout. Do not silently add unvalidated JSON to a signed body and assume old verifiers enforce it.

For the rehearsal's Bubblewrap-only script, either implement and qualify the new `bwrap` profile, or select the Sovereign pure-Landlock runner only in an environment where its preconditions and requested workspace/scratch semantics are met. Never label one runner with the other's class. `bwrap-landlock` is unavailable until a single invocation demonstrably applies both controls. Gate-lite must report the effective verified profile, path, digest and simulated state in status; missing/unknown profiles must be visible and prevent real execution. Remove default expressions that silently turn unknown runner state into `bwrap-landlock`.

## Required implementation and negative cases

After protocol decision, implement and verify the following in the gate-lite and receipt repositories under their own owners:

1. **Protocol parity:** positive vectors for `bwrap`, `landlock`, `bwrap-landlock`, both microVM classes, and `none` where applicable; negatives for unknown class and empty/non-string class under the new version. Run Python and Rust verifiers against identical vectors and compare disposition/reason. Keep published 0.4 vectors byte-identical. Record explicitly that published 0.4 schema/verifier acceptance of a new string would not make it a defined 0.4 class; do not change or assume a new rejection from the published verifier.
2. **Runner profile selection:** configured executable absent, not executable, hash mismatch, unknown profile id, class/spec mismatch, unsupported protocol, malformed profile, symlink retarget after initial verification, and digest changed between setup and invocation all fail closed before payload spawn and before an execution receipt is emitted.
   Also prove a newer installed receipt package cannot silently change gate-lite's emitted spec or make a previously valid runner class invalid without an explicit migration.
3. **Receipt/status agreement:** each real execution's status and signed receipt identify the exact configured profile/class and digest; stub/demo stays explicitly simulated. Assert no unknown runner falls back to `bwrap-landlock`, the configured path remains visible in status, and status and emitted evidence cannot disagree.
4. **Mechanism proof:** Bubblewrap positive/negative checks verify namespace properties used by the profile and the runner binary identity; Landlock checks verify ruleset application and actual denial behavior for writes outside the declared writable scope. Combined class requires both sets to pass in the same process tree. Include negative tests where Bubblewrap is blocked under active Landlock and where a Landlock profile runs without Landlock available. Any failed capability/probe blocks the claimed class rather than silently downgrading.
5. **Capture-to-verifier chain:** produce a fresh real execution under the resolved profile; capture status, configuration, binary identity, mechanism-probe output, invocation, and bundle. Verify exact hashes, verify the bundle with the published verifier for its declared version, and verify companion attestation binding. Demonstrate tampering with profile, executable, class, mechanism evidence, and referenced hashes causes rejection or explicit untrusted/insufficient disposition.

Tests must exercise all supported ways to configure the runner (`--runner`, `WM_GATELITE_RUNNER`, service/container configuration) so alternate entry points cannot bypass profile selection.

## Treatment of already signed 0.4 bundles

Keep the 2026-09-25 bundle and prior bundles immutable. Do not edit body fields, regenerate signatures under the original receipt identity, or imply a later profile retroactively proves the earlier process. Preserve their 0.4 verifier result as a statement about structural/policy verification. Annotate the rehearsal's mechanism classification as OPEN/overstated in the evidence index and any derivative summary; use the exact limitation from its report. If a corrected historical description is needed, issue a separate, newly signed correction/supersession record that references the original bundle digest and clearly says it is a later correction, subject to the receipt protocol's supported semantics. It must not replace the original bytes or turn the old `TRUSTED` verdict into proof of Landlock.

For new runs, use the new versioned class and exact runner evidence. If an interim run is needed before that version exists, block real-run publication/qualification rather than emitting a 0.4 receipt whose class cannot accurately represent the configured mechanism.

## Rollout, ownership, and gates

| Order | Owner | Deliverable / exit condition |
|---|---|---|
| 0. Contain current claim | Gate-lite maintainer + publication owner | Mark existing `bwrap-landlock` receipts from the portable runner as historically signed but mechanically overstated in the public review snapshot, README, outsider protocol, and evidence index. Do not qualify a new portable-runner execution under that class. Preserve all original bundle bytes. |
| 1. Freeze semantic decision | Continuity Receipt maintainer + gate-lite maintainer | Decide 0.5 draft amendment vs next version; publish exact class definitions, evidence binding, and verifier compatibility policy in a reviewable protocol change. |
| 2. Implement receipt protocol | Continuity Receipt maintainer | Schema, Python, Rust, docs, manifests and vectors agree; parity/negative cases pass; published 0.4 bytes and behavior remain unchanged. |
| 3. Implement fail-closed profiles | Gate-lite maintainer | Explicit profiles bind class, supported receipt version, invocation protocol and executable identity; status/receipts agree; unknown/mismatch cases refuse before spawn. |
| 4. Qualify mechanism profiles | Sovereign runner owner + gate-lite maintainer | Exact build-level Bubblewrap and/or Landlock tests pass; combined class only if both are enforced in one execution; archive raw outputs and hashes. |
| 5. Maintainer-host integration | Gate-lite + WhiteMagic adapter owner | Fresh exact-candidate probe and bundle; validate complete evidence chain; record limitations separately from verifier `TRUSTED`. |
| 6. Independent other-host adoption | Tester not involved in implementation, on a separately administered host | From clean checkout/package instructions, acquire the runner without a pre-installed maintainer copy, independently install exact candidate, verify pinned hashes, run positive and negative mechanism cases, produce a project artifact and offline-verifiable evidence bundle, record operator help, and have gate-lite/receipt maintainers review. No maintainer-host evidence can substitute. This is the gate-lite adoption test, separate from the Sovereign VM stranger-install threshold. |
| 7. Public claims/release review | Release/site owner, after gates 1–6 | Update claims only to the mechanism and version actually evidenced; run required site route/discovery checks if public text changes. Keep adoption gate OPEN until independent evidence is accepted. |

Each gate remains OPEN until its named artifact and reviewer disposition are recorded. A plan, passing unit suite, same-host rehearsal, 0.4 `TRUSTED` verdict, or public wording change alone does not close runner classification or independent adoption. No release closure is claimed here.
