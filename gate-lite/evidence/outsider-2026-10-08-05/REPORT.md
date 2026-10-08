# gate-lite outsider exercise — 0.5 candidate — 2026-10-08 (run 05)

**Disposition: PASS for the bounded same-host maintainer exercise on the 0.5
candidate with the pinned qualified wrapper; NOT independent adoption.** The
full outsider flow (tenant-add → pass → exec → settle → terminate → receipt
--verdict) completed with a real sandboxed execution (`sandbox_class=bwrap`),
`verdict=TRUSTED`, and all three prescribed verifications returning TRUSTED
with exit 0. This remains a same-host exercise run by the maintainer side (not
an unassisted stranger install, not a new-machine test, not Sovereign VM
qualification): issuing more than a bounded PASS would overstate containment
evidence for the publication decision.

**Candidate pin (tested code):** `codex/gate-lite-05-profile` =
`8ea8c7eb17d576efdbfa0d311b007dd7b95f8389`
("chore(deps): bind gate-lite 0.5 candidate to published continuity-receipt
0.5.0", 2026-09-30T10:32:10-04:00), exported with `git archive` (tracked files
only).
**Runner:** `scripts/mandala-sandbox` from nested Sovereign repo commit
`9a0faf19fbebfd6a4c803822ed23e8ba6cf055b6`, SHA-256 verified below.
**Run window:** 2026-10-08, two sessions (~16:50Z → ~16:57Z).
**Run 1** stopped per protocol at the test step: the originally prescribed
dependency range resolved `continuity-receipt 0.5.1`, which this candidate
fail-closes on (`orchestrator.py:27,437` pins `==0.5.0`); captured in
`tests-0.5.1-prior-fail.log`. **Run 2** (continuation) installed the exact
published `continuity-receipt==0.5.0` (verified present on PyPI first; no git
source used) and completed the flow.

## Pin and runner verification (both runs)

| Artifact | Expected SHA-256 | Observed | Match |
|---|---|---|---|
| `runner/mandala-sandbox` (from `9a0faf1:scripts/mandala-sandbox`) | `f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e` | same | ✓ |
| `/usr/bin/bwrap` (bubblewrap 0.9.0) | `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71` | same | ✓ |
| `/usr/bin/jq` (jq 1.7) | `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566` | same | ✓ |

The candidate's qualified profile pins exactly these digests
(`orchestrator.py:28-31`), so `SandboxRunner` resolved the profile.
PyPI check (run 2): `pip index versions` and the PyPI JSON release list both
confirm `0.5.0` exists (`0.5.1, 0.5.0, 0.4.1, 0.4.0, ...`); installed exact:
`continuity-receipt==0.5.0`.

## Environment and results

| Check | Result |
|---|---|
| Host / OS | T4800-S · Zorin OS 18.1 · Linux 7.0.0-34-generic x86_64 |
| Python | 3.12.3 (venv; editable gate-lite 0.0.1 from the pinned export) |
| Dependencies | Run 1: `continuity-receipt==0.5.1` → blocked. Run 2: `continuity-receipt==0.5.0`, `cryptography==50.0.2`, `cffi==2.1.1`, `pycparser==3.1` |
| Tests (run 1, 0.5.1) | 108 run — FAILED, 6 failures · 66 errors · 6 skips, exit 1 (72× version `RuntimeError`); stopped per protocol |
| Tests (run 2, 0.5.0, prescribed env) | 108 run — 5 failures · 0 errors · 6 skips, exit 1; all 5 failures are runner-guard cases invalidated by exporting `WM_GATELITE_RUNNER` for the suite (they assume no runner configured). Diagnostic re-run with the var unset: **OK (skipped=6), exit 0** |
| Real execution (`exec`) | **exit 0** through the pinned wrapper; payload `echo hello from outsider 2026-10-08 r05`; stdout hash `sha256:7007f134...`, stderr empty hash `e3b0c442...` |
| `task.execution.sandbox_class` | **`bwrap`** |
| `runner_profile` | `profile_id=urn:mandala:runner-profile:bwrap-v1`; `executable_digest=sha256:f7da8d6c...96411e` (matches pinned wrapper); `invocation_digest=sha256:092c0d00...` |
| Settlement | **ok, exit 0** — rail `invoice`, ref `outsider-1008-05`, `$0.00` (`minor 0`), seq 5 |
| Termination | **ok, exit 0** — task_id `urn:uuid:01a11c71-9e6e-76f0-be0b-165051018244` |
| Receipt verdict | **TRUSTED** (7 receipts: pass.created, decision, execution, commitment, attestation, settlement, termination; terminated=true, settled=true) |
| Receipt spec / digest | spec `continuity-receipt/0.5`; bundle file sha256 `c2b19578520cfd76132510f0a33f54dc5955afdf1197a86a50f37871e70ac329`; `task.execution` receipt `urn:uuid:01a11c71-b1a3-7c26-a80b-75acd008691c`, committed-chain digest (state.commitment.prev) `sha256:17734557cdea...` |
| Verifier verdicts | console `continuity-receipt-verify` → TRUSTED, **exit 0**; `python -m continuity_receipt.verify` (task bundle) → TRUSTED, **exit 0** (benign runpy warning); `... vectors/02_happy_full.json` → TRUSTED, **exit 0** |
| Skipped tests | 6× `'runner profile is not qualified'` — from hardcoded `HAS_QUALIFIED_RUNNER_PROFILE = False` (`tests/test_acceptance.py:39`), i.e. test policy, not wrapper qualification. The qualified path was exercised by the CLI flow |

Token handling: the single-use token was held in a mode-600 file only during
the run and is **not** present anywhere in this directory (grep-verified); the
earlier pass token from run session 1 was unrecoverable by design and never
used (orphan slot `slot-9d9ea10afd11` / pass bundle `27b4-7aa4` remain in the
throwaway `./state` only).

## Reproduction (as run)

Run 1 (blocked) and the full command/output sequence for run 2, including
redacted flow outputs, are in `transcript.txt`; the suite output is
`tests.log` (0.5.0) and `tests-0.5.1-prior-fail.log` (0.5.1). Key run-2 steps:

```bash
W=/tmp/opencode/mandala-outsider-05
W2="$W/src/gate-lite"
git -C "/home/lucas/Desktop/front burner/MANDALA_OS" rev-parse codex/gate-lite-05-profile   # 8ea8c7e...
git -C "/home/lucas/Desktop/front burner/MANDALA_OS" archive 8ea8c7e... | tar -x -C "$W/src"
git -C "/home/lucas/Desktop/front burner/MANDALA_OS/MANDALAOS_SOVEREIGN" show 9a0faf1:scripts/mandala-sandbox > "$W/runner/mandala-sandbox"
python3 -m venv "$W/venv"
"$W/venv/bin/pip" install -e "$W/src/gate-lite"
"$W/venv/bin/pip" install "continuity-receipt==0.5.0"          # exact, after PyPI check
cd "$W2" && "$W/venv/bin/python" tools/make_vectors.py
WM_GATELITE_RUNNER="$W/runner/mandala-sandbox" "$W/venv/bin/python" -m unittest discover -s tests -v  # see table
export WM_GATELITE_RUNNER="$W/runner/mandala-sandbox"
CTL="$W/venv/bin/python gate_lite/ctl.py --state ./state"
$CTL tenant-add --tenant dogfood --agent did:key:zOutsiderAgent05
$CTL pass --tenant dogfood --agent did:key:zOutsiderAgent05 --minutes 30 --spend-minor 1000   # tokens redacted
$CTL exec --tenant dogfood --slot slot-b02cfda75fb9 \
    --payload-ref "echo hello from outsider 2026-10-08 r05" --token <redacted>
$CTL settle --tenant dogfood --slot slot-b02cfda75fb9 --rail invoice --rail-ref outsider-1008-05 --minor 0
$CTL terminate --tenant dogfood --slot slot-b02cfda75fb9
$CTL receipt --task-id urn:uuid:01a11c71-9e6e-76f0-be0b-165051018244 --verdict
"$W/venv/bin/continuity-receipt-verify" "state/receipts/<task>.json"
"$W/venv/bin/python" -m continuity_receipt.verify "state/receipts/<task>.json"
"$W/venv/bin/python" -m continuity_receipt.verify vectors/02_happy_full.json
```

## Friction

1. **README range-vs-exact-pin drift (blocking until worked around).**
   `README.md:26` states `Dependency: continuity-receipt==0.5.0`, while
   `README.md:34` (and the exercise prescription) says
   `pip install "continuity-receipt>=0.5.0,<0.6"`. Since 0.5.1 exists, the
   range installs a version the candidate refuses; the exercise is dead on
   arrival unless read as an exact pin. README should use `==0.5.0` (or the
   candidate should accept 0.5.x).
2. **The prescribed test invocation is not hermetic to the runner env.**
   Exporting `WM_GATELITE_RUNNER` (as prescribed for the test run) makes 5
   runner-guard tests fail because subprocesses inherit a configured runner;
   the same suite is green with the var unset. The protocol should either run
   tests without the var or the guard tests should clear it.
3. **Qualified-profile path is excluded from the suite by policy:** 6
   real-runner acceptance tests stay skipped (`HAS_QUALIFIED_RUNNER_PROFILE =
   False`, `tests/test_acceptance.py:39`) even with the pinned qualified
   wrapper. Only the CLI flow exercised the qualified path; the suite gives
   no coverage signal for it.
4. **Token handling remains undocumented and non-recoverable.** The token is
   returned once (and only on the `pass` stdout); a lost token leaves an
   orphan slot/pass bundle and requires a fresh `pass` (as happened here when
   shell state did not persist). A documented, safe capture path (e.g.
   `--token-out` file) would make outsider runs reproducible.
5. **Minor:** `tools/make_vectors.py` rewrites tracked vectors in the export
   (expected); `README.md:203` says "86 tests" vs 108 actual; README's
   historical `sandbox_class=bwrap-landlock` claim (README:216) contrasts with
   the observed `bwrap` on this candidate — README itself flags the old label
   as an issuer claim, so this is noted, not a defect.

## Files in this directory

- `REPORT.md` — this report.
- `transcript.txt` — full command/output log (both runs; tokens redacted;
  none was ever written).
- `tests.log` — run-2 suite output on `continuity-receipt==0.5.0`
  (5 env-induced failures · 6 policy skips).
- `tests-0.5.1-prior-fail.log` — run-1 suite output on `0.5.1`
  (6 failures · 66 errors · 6 skips) preserved for provenance.
- `verdict.json` — `receipt --verdict` output (TRUSTED).
- `bundle-task.json` — full 7-receipt bundle for the task.
- `receipt-task-execution.json` — the `task.execution` receipt (sandbox_class
  + runner_profile).

Out of scope (stated as such): unassisted stranger install, other-host /
new-machine testing, Sovereign VM re-verification, slice/systemd mode, MCP
transports, egress-L2.
