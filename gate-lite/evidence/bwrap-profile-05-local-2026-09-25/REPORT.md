# Local Bubblewrap / receipt 0.5 candidate run

Date: 2026-09-25. Scope: one laptop, unpublished candidate code. This is
maintainer qualification and does not close independent adoption.

## Identity

- Portable wrapper source: `MANDALAOS_SOVEREIGN` commit `9a0faf1`, copied to
  `/tmp/mandala-runner-candidate/mandala-sandbox` without editing.
- Wrapper SHA-256: `f7da8d6c3809ac5adbc4631c82fb9327abdb69638715bb0ea1493dc79996411e`.
- `/usr/bin/bwrap` SHA-256: `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71`,
  Debian package `bubblewrap 0.9.0-1ubuntu0.3`.
- `/usr/bin/jq` SHA-256: `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566`,
  Debian package `jq 1.7.1-3ubuntu0.24.04.2`.
- `dpkg -V bubblewrap jq` returned no discrepancies.
- Gate-lite branch `codex/gate-lite-05-profile` and unpublished Continuity
  Receipt `0.5.0a0` source at candidate commit `e4d2f8a3` were installed
  editable into an isolated venv.

## Observations

`probe.json` records a PASS for the fixed real Bubblewrap probe: separate
network and mount namespaces, a read-only `/workspace` bind, denied write
there, and a writable tmpfs `/tmp`. `network-check.json` records a same-host
loopback control: the payload connected with `net:true` and got connection
refused with `net:false`. The wrapper's exact argument and explicit writable
workspace tests passed (8 focused tests).
An additional real wrapper control attempted to write `/workspace/probe.txt`:
`rw:false` exited 1 with a read-only filesystem error and left no file;
`rw:true` exited 0 and created the file in the selected host workspace.

The fresh gate-lite execution ran `/usr/bin/python3 -c "print(42)"` via the
candidate wrapper, then emitted a termination receipt. `bundle.json` contains
the signed `task.execution.body.runner_profile` with the wrapper digest and
canonical invocation digest. `verdict.json` records `TRUSTED` from the local
Python 0.5 verifier after termination. Removing the profile or changing its
invocation digest without resigning yielded `UNTRUSTED`. Gate-lite's local
suite passed: 106 tests, 6 skipped. `rust-verdict.json` records `TRUSTED`
from the Rust 0.5 verifier on the same bundle.

For a WhiteMagic integration rehearsal, a clean `WMv9` worktree at
`251031e` had `wm-receipts`' Rust dependency temporarily pointed at the
unpublished local 0.5 source. An offline-built example using
`wm_receipts::verify_bundle` had SHA-256
`b2ba6f1ac6e6c5ff7d9598ec1048f60cd69d8b5cfc748bf7da49d386b931d0b9`.
Gate-lite copied that binary and the prior 0.5 bundle into a fresh slot
workspace, ran the binary through the profiled Bubblewrap wrapper, and
captured `wm-verdict.json` there. The WhiteMagic verdict was `TRUSTED`.
After termination, the fresh `wm-bundle.json` was `TRUSTED` by both Python
(`wm-gate-verdict.json`) and Rust (`wm-rust-verdict.json`). This is a source
integration rehearsal with a temporary dependency override, not evidence
for the current WhiteMagic tag or package.

## Limits

`TRUSTED` verifies this issuer's signed chain and the receipt shape. The
verifier does not observe Bubblewrap execution or independently recompute
the claimed runner profile. The network probe covers a loopback control, not
all outbound destinations. The wrapper and tool identities are pinned for
this laptop's candidate, not a portable profile for arbitrary installations.
The source is unpublished and awaits review; another host has not installed,
run, or verified this candidate.
