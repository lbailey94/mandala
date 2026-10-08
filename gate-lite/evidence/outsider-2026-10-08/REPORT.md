# gate-lite outsider exercise — 2026-10-08

**Disposition: REFUSED at `exec` — the prescribed "PASS" line is deliberately
not issued.** At the tested pin, real payload execution is fail-closed by
design under `continuity-receipt/0.4` (no reviewed runner profile), so
acceptance criterion 2 of `publication/GATE_LITE_OUTSIDER_EXERCISE.md` is
unsatisfiable here. Everything before `exec` reproduces cleanly. This is a
bounded same-host exercise (not an unassisted stranger install, not a
new-machine test, not Sovereign VM qualification); issuing "PASS" would
overstate containment evidence for the publication decision.

**Candidate pin (tested code):** `mandala-os` commit
`6fd651c3b86274fa3c9b740cd00b9f708d0a227b` (local `main` == `origin/main`,
clean tree at run time), exported with `git archive` (tracked files only).
**Run window:** 2026-10-08T16:46:51Z → ~16:49Z, host T4800-S.
No gate receipt bundle exists for this run (the flow halted at `exec`).

## Reproduction (as run; copy-paste order)

```bash
# 0. workspace + pinned export
mkdir -p /tmp/opencode/mandala-outsider-20261008/src
git -C "/home/lucas/Desktop/front burner/MANDALA_OS" \
    archive 6fd651c3b86274fa3c9b740cd00b9f708d0a227b | \
    tar -x -C /tmp/opencode/mandala-outsider-20261008/src

# 1. install (venv)
python3 -m venv /tmp/opencode/mandala-outsider-20261008/venv
/tmp/opencode/mandala-outsider-20261008/venv/bin/pip install -e \
    /tmp/opencode/mandala-outsider-20261008/src/gate-lite

# 2. quick start, from src/gate-lite
venv/bin/python tools/make_vectors.py
venv/bin/python -m unittest discover -s tests -v        # tee tests.log

# 3. outsider flow
export WM_GATELITE_RUNNER="$HOME/.local/bin/mandala-sandbox"
PY=venv/bin/python
$PY gate_lite/ctl.py --state ./state tenant-add --tenant dogfood \
    --agent did:key:zOutsiderAgent1
PASS=$($PY gate_lite/ctl.py --state ./state pass --tenant dogfood \
    --agent did:key:zOutsiderAgent1 --minutes 30 --spend-minor 1000)
SLOT=$(echo "$PASS" | jq -r .slot_id); TOKEN=$(echo "$PASS" | jq -r .token)
$PY gate_lite/ctl.py --state ./state exec --tenant dogfood --slot "$SLOT" \
    --payload-ref "echo hello from outsider 2026-10-08" --token "$TOKEN"
# >>> FAILED HERE: exit 1, RunnerProfileError (see table); flow stopped
#     per protocol. settle/terminate/receipt/verifiers were NOT run.
```

The single-use token is absent from this directory (held only in a mode-600
temp file during the run).

## Environment and results

| Check | Result |
|---|---|
| Host / OS | T4800-S · Zorin OS 18.1 · Linux 7.0.0-34-generic x86_64 |
| Python | 3.12.3 (venv; editable gate-lite 0.0.1 from the pinned export) |
| Dependencies | `continuity-receipt==0.4.0`, `cryptography==50.0.2`, `cffi==2.1.1`, `pycparser==3.1` |
| Runner | `~/.local/bin/mandala-sandbox`, SHA-256 `de273c62ae22147634164e84cc9b6f6ae83a7f25e05755b50bc7c1257f525641` (pre-existing); bubblewrap 0.9.0; jq 1.7 |
| Tests | **110 run, OK, 6 skipped** in 13.492 s (exit 0); all 6 skips are the real-runner acceptance tests: "runner profile is not qualified" (`tests.log`) |
| Real execution | **exit 1 — refused before spawn**: `gate_lite.orchestrator.RunnerProfileError: no reviewed runner profile is qualified for Continuity Receipt 0.4; real payload execution is disabled` (orchestrator.py:274 via exec_:968) |
| `task.execution.sandbox_class` | **no task.execution receipt emitted**; configured runner reports `class: unknown`, `profile_status: unqualified` — not `stub`, and not any contained class (fail-closed) |
| Settlement | **not reached** (flow stopped at `exec`); no $0 / `rail-ref` line was recorded |
| Receipt spec / digest | spec pinned `continuity-receipt/0.4` (dependency 0.4.0); **no receipt or bundle digest exists** for this run |
| Verifier verdicts | **not run** (no bundle); console and module verifier exit codes unavailable |
| Post-failure state | slot `slot-faeff89d93a1` remained `placed`; token not consumed (profile gate precedes jti consumption) |

The refusal is expected at this pin and documented in-tree: README line
"Configured real runners currently report `unknown` / `unqualified`, and
`mandala.exec` refuses them before token consumption or payload spawn";
commits `704a863` ("hold unqualified gate-lite runner execution"), `63af388`,
`4301245` ("refuse unreviewed runner hints"). The qualified bwrap profile for
the 0.5 candidate (`d7afa55`) exists only on branch `codex/gate-lite-05-profile`
and is **not** an ancestor of the tested pin (verified via
`git merge-base --is-ancestor`).

## Friction / scope notes

1. **Protocol v1 is stale against the pin.** `GATE_LITE_OUTSIDER_EXERCISE.md`
   still prescribes `WM_GATELITE_RUNNER` + `exec` expecting exit 0 and a
   non-stub class. At 6fd651c that path is held; the protocol needs a
   0.4-hold-aware variant (or must pin the 0.5-profile branch) before an
   outsider run can PASS. This is the blocking finding.
2. **The refusal surfaces as an unhandled traceback (exit 1)**, not the
   structured error style used elsewhere in `ctl.py` (which catches
   `KeyError/PermissionError/ValueError`); `RunnerProfileError` is a
   `RuntimeError`. A designed refusal should print a structured message and a
   stable exit code.
3. **Green-suite trap:** "OK (skipped=6)" hides that every real-runner
   acceptance test is skipped at this pin; a tester could misread the suite as
   covering real exec.
4. **Runner provenance remains outside the slice** (Sovereign Edition,
   `landlock-isolation.nix`); this host had it pre-installed. Unchanged from
   the 2026-09-24 friction list.
5. **Token handling is undocumented** (must be parsed from `pass` output).
   Unchanged from prior reports.
6. **Minor:** README says "86 tests"; actual count is 110. `tools/make_vectors.py`
   rewrites tracked vectors (expected in a throwaway export).
   `ResourceWarning` lines for unclosed subprocess handles in HTTP/MCP tests
   (cosmetic), as prior reports noted.

Out of scope (stated as such): unassisted stranger install, other-host /
new-machine testing, Sovereign VM re-verification, slice/systemd mode, MCP
transports, egress-L2, the 0.5-profile branch.

## Files in this directory

- `transcript.txt` — full command/output log; token redacted.
- `tests.log` — 110-test suite output (6 real-runner skips).
- `REPORT.md` — this report (written after the flow halted at `exec`).
- **Not produced:** `verdict.json`, `bundle-task.json`, receipt JSON — the
  protocol step failed before `terminate`/`receipt`, so no gate verdict or
  bundle exists; fabricating them would misstate the exercise.
