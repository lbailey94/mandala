# Gate-lite outsider exercise — protocol v2 (2026-10-08)

**Status:** local review candidate. Publication qualification requires a frozen,
pushed source SHA, an independently reviewed public tree and wrapper distribution,
and human sign-off. A local run remains a local rehearsal.

This protocol covers the 0.5 candidate's exact `bwrap` profile. Main's 0.4 hold,
Sovereign VM qualification, unassisted stranger installation, MCP transports,
destination allowlisting, and hostile-tenant isolation are separate scopes.
[V1 is preserved](GATE_LITE_OUTSIDER_EXERCISE_V1_2026-09-24.md), including its
historical classification correction. The older second-laptop packet is historical.

## Source and environment

Record the full tested source SHA, source visibility, remote reachability, export
method and tree status. Pushing a private source SHA makes it retrievable only to
authorized collaborators. A public snapshot must carry the actual reviewed code
and wrapper; it must not require an outsider to fetch either private repository.

Use a fresh tracked-file export and a new virtual environment. For example, after
reviewing and filling the source SHA:

```bash
REPO=/path/to/source-checkout
SOURCE_SHA=<full-reviewed-40-character-sha>
W=$(mktemp -d)
mkdir "$W/src"
git -C "$REPO" archive "$SOURCE_SHA" | tar -x -C "$W/src"
python3 -m venv "$W/venv"
"$W/venv/bin/pip" install -e "$W/src/gate-lite"
PY="$W/venv/bin/python"
cd "$W/src/gate-lite"
"$PY" -c 'import continuity_receipt; assert continuity_receipt.__version__ == "0.5.0"'
"$W/venv/bin/pip" check
```

Package, runtime and install instructions all pin `continuity-receipt==0.5.0`.
Published 0.5.1 exists but is outside this qualified lane. Record host OS/kernel,
Python, package versions, and exact wrapper, bwrap and jq SHA-256 values.

## Included qualified wrapper

Use `runners/bwrap-v1/mandala-sandbox`, a byte-identical copy from Sovereign
`9a0faf19fbebfd6a4c803822ed23e8ba6cf055b6:scripts/mandala-sandbox`. Its SHA-256 is
`f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e`.
[PROVENANCE.json](../gate-lite/runners/bwrap-v1/PROVENANCE.json) records exact bwrap
and jq hashes too. Public license declaration and distribution sign-off remain
open in this local candidate. Do not claim public acquisition has shipped yet.

```bash
RUNNER=$(realpath runners/bwrap-v1/mandala-sandbox)
sha256sum "$RUNNER" /usr/bin/bwrap /usr/bin/jq
bash -n "$RUNNER"
"$PY" runners/bwrap-v1/test_sandbox_argv.py -v > "$W/wrapper-tests.log" 2>&1
"$PY" tools/qualify_bwrap_runner.py --wrapper "$RUNNER" \
  --expected-wrapper-sha256 sha256:f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e \
  --expected-bwrap-sha256 sha256:e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71 \
  > "$W/mechanism-probe.json"
```

Check every exit. A different tool build needs a reviewed new exact profile;
never edit hashes to force a passing receipt. The fixed mechanism probe checks
namespace/filesystem properties; its limitations include no outbound reachability
qualification. Its class remains an evidence conclusion for human review.

## Tests and explicit skips

Run the ordinary suite and retain full logs:

```bash
"$PY" tools/make_vectors.py  # historical spec-0.4 fixtures; disposable export only
env -u WM_GATELITE_RUNNER -u WM_GATELITE_SLICE -u GATE_LITE_REAL_RUNNER_TESTS \
  -u GATE_LITE_QUOTA_TESTS "$PY" -m unittest discover -s tests -v > "$W/unit-clean.log" 2>&1
WM_GATELITE_RUNNER="$RUNNER" WM_GATELITE_SLICE=1 \
  "$PY" -m unittest discover -s tests -v > "$W/unit-configured.log" 2>&1
GATE_LITE_REAL_RUNNER_TESTS=1 WM_GATELITE_RUNNER="$RUNNER" \
  "$PY" -m unittest discover -s tests -p test_acceptance.py -v > "$W/acceptance-bwrap.log" 2>&1
```

Ordinary absence/demo guard tests neutralize ambient runner configuration and
must not spawn it. Acceptance requires an explicit real-runner opt-in and exact
profile qualification. A requested invalid profile is a failed preflight, not a
successful suite with silently skipped integration cases. Quota tests require a
ready systemd user manager and the separate quota opt-in; the memory drill can
trigger an OOM event and remains explicitly gated. Record each group's actual
skip reason, tests discovered, executed, failed and skipped. An echo flow is not
operator-kill, egress, quota or snapshot/restore coverage.

## Token-safe lifecycle and commitment capture

The bounded tool drives tenant-add, unkeyed pass, fixed no-network exec, $0 invoice
settlement, termination and verification as separate CLI processes. It retains
the exact registry snapshot consumed by the original commitment method, without
altering its value. It keeps the issuance token in memory, sends it on stdin,
redacts issuance output and never copies the runtime database or signing key.

```bash
"$PY" tools/capture_outsider_05.py --out "$W/outsider-05" \
  --runner "$RUNNER" --source-sha "$SOURCE_SHA" --source-status local-reviewed
"$W/venv/bin/continuity-receipt-verify" "$W/outsider-05/bundle-task.json" \
  > "$W/outsider-05/console-verdict.json"
"$PY" -m continuity_receipt.verify "$W/outsider-05/bundle-task.json" \
  > "$W/outsider-05/module-verdict.json" 2> "$W/outsider-05/module-stderr.txt"
```

Use `--source-status pushed-frozen` only after verifying the exact SHA is pushed
and using an export of those bytes. That flag records an operator assertion; it
does not itself prove remote provenance. Record remote/CI checks separately.

Direct CLI use supports mutually exclusive `--token` and `--token-stdin`. Disable
shell tracing and do not tee raw pass output. A token lost after unkeyed issuance
requires a fresh pass. Keyed issuance caches the complete result including the
plaintext token in the private SQLite registry; repeat keyed calls can recover it.
Single-use means successful execution burns the JTI, with replay rejected across
restart. It does not mean tokens never persist in private runtime state.

## Acceptance and public claims

Require all capture checks to pass: fixed payload exit zero; class `bwrap`;
wrapper and canonical invocation digests match; state commitment count/head
recompute from the captured exact snapshot; settlement minor zero; recorded
delivery response matches recorded execution; termination; bundle TRUSTED.

The console/module/API share one Python implementation. Historical vector
verification is fixture compatibility coverage. If Rust parity is claimed,
record the actual independently versioned Rust verifier and its verdict on the
new task bundle. Keep mechanism tests, receipt conformance and recomputation as
separate evidence views.

A local/collaborator exercise is bounded same-host reproducibility, not
independent adoption. Shared-kernel `bwrap` is not a VM or hostile-tenant boundary.
TRUSTED verifies the issuer-signed chain and policy/shape, not factual issuer
honesty or actual enforcement. The issuer's delivery response binding is not an
external delivery attestation. $0 invoice settlement is not payment qualification.
Declared granted destinations remain whole-network intent, not an allowlist.

Keep the historical October 8 run A as expected 0.4 execution refusal (before
token consumption/spawn, with a pass receipt already issued). Keep run B as the
old `8ea8c7e` bounded PASS with disclosed frictions. Run A used installed wrapper
`de273…`; run B used pinned wrapper `f7da…`. Never rewrite their signed bundles.

## Evidence and sign-off

Retain full clean/configured/acceptance logs, mechanism JSON, wrapper tests,
source/tool/package identities, token-free transcript, signed task bundle,
verdicts, invocation JSON, and commitment-state JSON with recomputation results.
Review every artifact for secrets and unnecessary host details before curation.
Do not redact a commitment-bound snapshot and still claim its hash recomputes;
if unsuitable for publication, preserve it privately and narrow the public claim.

Review the final source diff and exercise before human sign-off. Public curation
selectively applies accepted 0.5 changes against current public main, preserving
its egress disclosure and POSIX termination behavior. Independently verify that
curated tree. Main promotion and a fresh other-host exercise remain separate.
