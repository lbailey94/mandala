# MandalaOS Sovereign Edition — NixOS configuration

Declarative NixOS build of the **Sovereign Edition** form of MandalaOS:
a lean, local-first machine whose WhiteMagic cognitive substrate runs as a
sandboxed system service. Two targets: `mandala-sovereign` (x86_64
workstation/VM) and `mandala-arm-appliance` (aarch64 SD-image scaffold).

Companion docs live in `~/Desktop/MANDALA_OS/`:
- `PLATFORM_DIRECTION_2026-09-12.md` — why this form exists, threat-model
  honesty, and the corrections applied here.
- `MANDALA_NIXOS_FLAKE_SPEC.md` — the original architecture spec.

**New here? Read `GETTING_STARTED.md` first.**

## Status — VM boots; containment verified in-guest

**Current candidate (2026-09-28):** `flake.nix` and `flake.lock` pin
WhiteMagic **v9.2.9** (`30d61150558eeede577a52595c354ab771946bc7`). Its rooted
VM build booted on NixOS 26.05 and passed all 13 sandbox matrix checks;
Landlock is enforced at ABI v8, the daemon and loopback-only read-only MCP
service are active, and `wm doctor` reports all systems healthy. MCP access
from the host uses an SSH tunnel. See
[`docs/VM_REVERIFY_V929_2026-09-28.md`](docs/VM_REVERIFY_V929_2026-09-28.md)
for exact source, output, commands, and evidence. This is maintainer-VM
qualification; the v9.2.8 report below remains evidence for that older pin,
and unassisted stranger install and bare-metal checks remain open.

**2026-09-13:** `nix flake check` passes both targets; the first
`system.build.vm` build **boots to a login prompt** (KVM, NixOS 26.05), the
in-guest sandbox matrix is **8/8 green**, and the **WhiteMagic daemon starts**
under systemd. Evidence recipe: `scripts/run-vm-headless.sh` (works with
nix-portable, no root). Still open: disk headroom for bare metal, VM egress
probe reports unreachable (informational; VM DNS/slirp quirk), and a stock
`Logrotate configuration check` unit fails in the VM (non-blocking, likely
upstream VM quirk).

**2026-09-14:** the matrix grew to **13 checks** with the pure-Landlock
`landrun-sandbox` runner (executes, write-denied, scratch rw,
nested-under-Landlock, bwrap-blocked) — **13/13 green in-guest on the rebuilt
VM** (kernel 6.18). The daemon now keeps `WM_LANDLOCK=1` *and* its declared
spawns are contained (the either/or is resolved for Landlock stores).

**2026-09-24:** WM source pin bumped v9.2.0 → **v9.2.7** (`flake.lock` WM
revision `62140a6`), and the VM was rebuilt and **re-verified the same day**:
`nix flake check` passes, in-guest matrix **13/13 green**, `whitemagic-daemon`
and the read-only serve active, `wm 9.2.7`, `wm doctor` all-green, Landlock
**enforced** in-guest (ABI v8 — the 09-13 `partial` is resolved). Evidence:
[`docs/VM_REVERIFY_2026-09-24.md`](docs/VM_REVERIFY_2026-09-24.md).

Threat model, stated honestly: Bubblewrap + Landlock is **shared-kernel
containment**. It contains misbehaving tools/agents — the same trust class as
browser sandboxes — not kernel exploits or a hostile local user. It is not
Qubes-level isolation (that stays the funded high-assurance track). The full
one-pager, including disclosed gaps and the claim discipline:
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## Layout

| Path | Role |
|---|---|
| `flake.nix` | Inputs (nixpkgs 26.05, local WM v9.2.8 candidate source), overlays, both NixOS targets |
| `configuration.nix` | Shared system config (firewall, users, packages, boot) |
| `packages/whitemagic.nix` | `wm` binary built from the WM source input (`rustPlatform`) |
| `modules/kernel-hardening.nix` | Sysctls (dmesg, BPF, Yama, anti-spoofing, VM tuning) |
| `modules/landlock-isolation.nix` | `mandala-sandbox` (bwrap) + `landrun-sandbox` (pure-Landlock) runners, per-service wiring |
| `modules/whitemagic-service.nix` | `whitemagic-daemon` systemd unit (hardened), `WM_LANDLOCK=1` |
| `modules/zram-swap.nix` | zstd ZRAM, 50% |
| `modules/arm-hardware.nix` | aarch64 SD-image defaults (board support = TODO) |
| `docs/INSTALL_AND_BOOT.md` | Stage-by-stage install (Nix-on-Zorin → VM → dual-boot → removable media), extensive-modification workflow, boot/generation selection |
| `docs/THREAT_MODEL.md` | Threat model + honest gaps one-pager (containment ≠ hypervisor isolation; claim discipline) |
| `GETTING_STARTED.md` | Front door: the cast, orientation commands, boot paths, day-1 checklist, roadmap |
| `scripts/verify-sandbox.sh` | Sandbox self-test (`--` no args = 8-check matrix) or run a command under the profile |
| `scripts/landrun-sandbox` | Pure-Landlock B2 runner (same `--exec` contract; for stores that already run a Landlock domain) |
| `scripts/run-vm-headless.sh` | Headless VM smoke test: boots, captures matrix + daemon evidence (nix-portable friendly) |

## Building (once Nix is installed)

Full walkthrough in `docs/INSTALL_AND_BOOT.md`. Quick version:

```bash
nix flake check                                # evaluate both configs + package
nix build .#whitemagic                         # just the wm binary

# x86_64 toplevel
nixos-rebuild build --flake .#mandala-sovereign

# bootable VM (no spare hardware needed)
nix build .#nixosConfigurations.mandala-sovereign.config.system.build.vm
./result/bin/run-mandala-node-vm

# aarch64 SD image
nix build .#nixosConfigurations.mandala-arm-appliance.config.system.build.sdImage
```

Local WM iteration without pushing a tag:

```bash
nix build .#whitemagic --override-input whitemagic-src path:/home/lucas/Desktop/WHITEMAGIC/WMv9
```

Set the user password on first boot: `passwd mandala`.

## Space budget (measured / high-confidence estimates)

| Step | Growth in `/nix` |
|---|---|
| Install Nix (official installer, multi-user) | ~0.3 GB |
| nixpkgs 26.05 flake input (measured 49 MB tar → 469 MB extracted) | ~0.5 GB |
| Eval caches (`~/.cache/nix`) | ~0.05 GB |
| **Install + evaluate** | **~0.8–1.0 GB** |
| Build headless toplevel (incl. rustc/clang from `systemPackages`) | +4–6 GB |
| Build `whitemagic` from source (toolchain + crates + target) | +4–7 GB |
| VM image | +2–4 GB |
| ISO | +5–8 GB |

Free space 2026-09-13: ~18 GB on `/` before the first VM build (drops during
builds). Plan a disk pass or removable storage before building WM + VM + ISO
together; `nix-collect-garbage -d` reclaims generations.

## Known TODOs

1. **WM: daemon vs serve lock contention** — a writable `wm serve` cannot run
   beside `wm daemon` on one store (Tantivy index lock). Options: daemon-hosted
   MCP surface, lock arbitration, or documented read-only serve (current VM
   setup forwards a read-only serve; writes go via the CLI).
2. **WM: Landlock on the daemon path** — landed in WMv9 (`59dfbfc`, B1):
   `wm daemon` applies v0 at init when `WM_LANDLOCK=1` and persists the
   report. **Verified in the VM 2026-09-24** — `landlock_state.json` reports
   `enforced` (ABI v8).
3. Stock `Logrotate configuration check` unit failed in the VM on 09-13 —
   upstream VM quirk, non-blocking. **Passes as of the 2026-09-24 closure**;
   real hardware is still unverified.
4. WM package may need extra native inputs (`pkg-config`, `openssl`) depending
   on resolved features; the default feature set has no pyo3.
5. ~~`landrun` integration into `mandala-sandbox` as a second layer~~ —
   **resolved 2026-09-14** as a separate pure-Landlock runner instead:
   `scripts/landrun-sandbox` (packaged by `landlock-isolation.nix`) is the
   B2 runner for Landlock stores; the daemon keeps `WM_LANDLOCK=1` and uses
   it, the read-only serve keeps bwrap. Nested domains stack; bwrap cannot
   (SANDBOX_LAYERS §3-7).
6. ARM board support: pin `github:NixOS/nixos-hardware` for the real board.
7. `offline-mesh.nix` and `local-ai.nix` are deliberately absent — they wait
   on userland plans (LoRa has no mainline driver; see direction doc §4).
8. Dual-boot scaffolding is in `configuration.nix` (`timeout`, 4-generation
   limit, Zorin chainload entry) — validated in the VM; apply at install time.
9. Disk pass to unlock bare-metal / build headroom (see INSTALL_AND_BOOT §3a).
