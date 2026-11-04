# Sovereign VM re-verification — v9.2.7 pin (2026-09-24)

**Status: PASS.** The VM was rebuilt against the v9.2.7 WhiteMagic source pin
and re-verified in-guest the same day. This closes the "not rebuilt or
re-verified against this pin" note in `README.md`.

| Item | Value |
|---|---|
| Candidate | WM source pin `github:lbailey94/whitemagic/v9.2.7` (flake.lock WM revision `62140a6`; repo commit `681cc3d`) |
| Host / run | T4800-S · QEMU/KVM (`system.build.vm`) · 2026-09-24 18:34–18:46Z |
| Evaluation | `nix flake check` passed — `mandala-sovereign`, `mandala-vm`, `apps.x86_64-linux.vm` (aarch64-linux omitted, incompatible system) |
| Build | `.#nixosConfigurations.mandala-vm.config.system.build.vm` → `/nix/store/whxwz4wlkgny777c7fz0b17wcgmxxwdj-nixos-vm` |
| Guest | kernel `6.18.50` · bwrap `0.11.2` |
| Containment matrix | **13/13 PASS, 0 FAIL** (`/etc/mandala/verify-sandbox.sh`; bwrap + landrun runners) |
| Services | `whitemagic-daemon.service` active (running) · `wm-mcp-readonly.service` active (running) |
| WM | `wm 9.2.7` · `wm doctor` all OK: store 583 memories / 7 galaxies; LMDB 308 = Tantivy 308 (no drift); Yama budgets healthy; citta coherence 1.000 |
| Landlock | **enforced** — "write-class FS rights confined to the store root + /dev/null (Landlock ABI v8); no_new_privs=true". The 2026-09-13 in-VM `partial` outcome is resolved on this closure. |
| Quirks | egress probe (`https://example.com`) unreachable — informational (slirp/DNS), unchanged; the 09-13 `Logrotate configuration check` quirk now **passes** |

## Matrix evidence (verbatim)

```
MandalaOS sandbox matrix (bwrap 0.11.2)
matrix green
  PASS  write /usr denied
  PASS  write /tmp allowed
  PASS  /etc/shadow hidden
  PASS  home store hidden
  PASS  network isolated
  PASS  workspace readable
  PASS  workspace write denied
  PASS  network shared with --net
  PASS  landrun runner executes
  PASS  landrun write /usr denied
  PASS  landrun scratch writable
  PASS  landrun runner nests under Landlock
  PASS  bwrap runner blocked under Landlock
```

## In-guest checks (SSH, second boot)

```
$ wm --version
wm 9.2.7
$ systemctl is-active whitemagic-daemon
active
$ cat ~/.local/share/whitemagic/landlock_state.json
{ "enabled": true, "outcome": "enforced", "detail": "write-class FS rights
  confined to the store root + /dev/null (Landlock ABI v8); declared grants:
  /dev/null (WriteFile) (no_new_privs=true)", ... }
$ wm doctor
[OK] LMDB store · [OK] Galaxies with data: 7, total memories: 583
[OK] Tantivy index · [OK] Index consistency: LMDB=308 Tantivy=308 (no drift)
[OK] Index health · [OK] Resource budgets (Yama) · [OK] Brain-wave state
[OK] Subsystem flags · [OK] Citta coherence: 1.000 (COHERENT)
```

## Repro

```bash
cd MANDALAOS_SOVEREIGN
nix flake check
VM_SECONDS=300 scripts/run-vm-headless.sh        # matrix + daemon evidence
# deeper in-guest checks: keep the VM up, then over the forwarded port:
#   ssh -p 2222 -i ~/.ssh/id_mandala_vm mandala@127.0.0.1 \
#     'wm --version; wm doctor'
```

## Evidence files (local-only, per repo `.gitignore`)

`docs/evidence/vm-reverify-2026-09-24/` — `run1-boot.log`
(sha256 `45b63aa3…6503`), `run2-boot.log` (sha256 `73b2216a…9b29`). These are
ignored by design; rerun the recipe above to regenerate.

## Scope notes

- This is a maintainer re-verification against a pin bump, not the
  stranger-install gate (`publication/STRANGER_INSTALL_PROTOCOL.md`, ≥4/5
  unassisted testers) — that gate is separate and untouched.
- Containment class is unchanged: shared-kernel (bwrap + Landlock), not
  microVM isolation.
