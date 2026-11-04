# Getting Started — MandalaOS Sovereign Edition

The front door. Everything a new session (human or agent) needs to pick this
up cold.

**Status as of 2026-09-15:** VM **boots** (NixOS 26.05, KVM); in-guest sandbox
matrix **13/13 green** (2026-09-14 rebuild, guest kernel 6.18); WhiteMagic
daemon **starts** under systemd; the Yama observe bridge is live through
evaluation (S4 executed 2026-09-15). Reproducible
with `scripts/run-vm-headless.sh` (real Nix or nix-portable, no root needed).
Nothing has
run on bare metal yet. The threat model is stated honestly in
`~/Desktop/MANDALA_OS/PLATFORM_DIRECTION_2026-09-12.md` (shared-kernel
containment, not hypervisor isolation).

---

## 0. Stranger checklist (before you build)

Three actions; nothing else in this repo assumes the author's machine:

1. **Install Nix** (Determinate installer, sudo, reversible) — see §2.
2. **Add your SSH key** to the VM's authorized keys (`vm.nix`,
   `users.users.mandala.openssh.authorizedKeys.keys`) — or use the console
   instead (autologin).
3. **Point the VM disk at your own directory** — `vm.nix` defaults to
   `/home/lucas/vms/mandala.qcow2`; change it to e.g. `~/vms/mandala.qcow2`.

Expected network: `cache.nixos.org` (substituters) and `github.com` (flake
inputs). Nothing else.

---

## 1. The cast — what lives where

| Piece | Path | Role |
|---|---|---|
| **Direction + docs** | `~/Desktop/MANDALA_OS/` | Why this exists: `PLATFORM_DIRECTION_2026-09-12.md` (three forms, corrections), `SANDBOX_LAYERS_2026-09-12.md` (containment map + live evidence) |
| **The OS** | `~/Desktop/MANDALA_OS/MANDALAOS_SOVEREIGN/` | NixOS flake: WM service, sandbox module, kernel hardening, boot config |
| **The monitor** | `~/Desktop/MANDALA_OS/LAKSHMI/` | 7-dim Harmony Vector digestor (PSI/proc/RAPL/battery + WM karma seam) |
| **The substrate** | `~/Desktop/WHITEMAGIC/WMv9/` | WhiteMagic governance: dharma gate, karma ledger, scope tokens, mesh |
| **Memory** | WM session store | Sessions `start`/`record`/`checkpoint` via the `wm` CLI or MCP |

Repos on GitHub (private): `lbailey94/mandalaos-sovereign`, `lbailey94/lakshmi`.

## 2. Orientation commands (on the host, no root needed once Nix is installed)

```bash
# See the machine through Lakshmi's eyes
python3 ~/Desktop/MANDALA_OS/LAKSHMI/lakshmi.py --once

# Run the containment matrix (13 checks; green on the author's laptop, kernel 7.0)
~/Desktop/MANDALA_OS/MANDALAOS_SOVEREIGN/scripts/verify-sandbox.sh

# Boot the VM headlessly and capture in-guest evidence (~150s)
VM_SECONDS=150 ~/Desktop/MANDALA_OS/MANDALAOS_SOVEREIGN/scripts/run-vm-headless.sh

# Evaluate the OS configuration
cd ~/Desktop/MANDALA_OS/MANDALAOS_SOVEREIGN
nix flake check
```

For a permanent Nix install (sudo, ~1 GB, reversible):

```bash
curl -fsSL https://install.determinate.systems/nix | sh -s -- install
# later, if ever: /nix/nix-installer uninstall
```

## 3. Boot paths — pick one

**A. VM (recommended first).** Zero risk to the current system. Use the
`mandala-vm` configuration — it adds the VM conveniences (SSH key injection,
port forwards, console autologin, persistent disk). `mandala-sovereign` is the
installable/workstation config and has none of those.

```bash
nix build .#nixosConfigurations.mandala-vm.config.system.build.vm
QEMU_OPTS="-m 4096 -smp 2" ./result/bin/run-mandala-node-vm
# or simply:
nix run .#vm
```

**B. SD card (the "boot from SD" idea).** *Reality check:* the current
SD_CARD1 is the archive vault — 24 GB of whitemagic archives (v4/v26 stores,
codex vault, laptop-dev wave) that may be sole copies, on exfat which cannot
be shrunk safely. Do not repartition it. Use a **spare card (≥ 64 GB) or USB
stick/SSD**; then follow `docs/INSTALL_AND_BOOT.md` §3b–3c, pointing
partitioning at the spare medium. USB flash = fine for boot trials, slow and
wear-prone for daily Nix builds.

**C. Dual-boot on the internal NVMe.** Requires a disk pass to ≥ 60 GB free
(currently ~18 GB). Then the systemd-boot menu offers NixOS generations +
Zorin OS (already scaffolded in `configuration.nix`).

**D. External SSD.** Cleanest hardware path: its own ESP and root, no
partition surgery, fast enough for real builds.

## 4. Day-1 on a booted NixOS

```bash
passwd mandala                      # no password is declared in the config
systemctl status whitemagic-daemon  # WM daemon, WM_LANDLOCK=1
wm doctor                           # store, embedder, landlock outcome
~/verify-sandbox.sh || scripts/verify-sandbox.sh   # containment matrix
```

## 4b. Dogfooding the VM (SSH, verified 2026-09-13)

```bash
systemctl --user start mandala-vm   # boot the VM (QEMU window on your display)
systemctl --user stop mandala-vm
systemctl --user status mandala-vm

# With your key added to vm.nix (stranger checklist #2):
ssh -p 2222 -i ~/.ssh/<your-key> -o IdentitiesOnly=yes mandala@127.0.0.1
# Without SSH: the console autologins as `mandala`; use it instead.

# To reach the read-only MCP surface, open a separate SSH tunnel:
ssh -N -L 28795:127.0.0.1:18795 -p 2222 -i ~/.ssh/<your-key> \
  -o IdentitiesOnly=yes mandala@127.0.0.1
```

- Host port map: **2222→22** (SSH only). WhiteMagic's unauthenticated SSE
  surface binds to guest loopback per v9.2.9 policy; use the SSH tunnel above
  to reach host `127.0.0.1:28795` while the tunnel remains open.
- The VM's WM uses the **host embedder** via `10.0.2.2:18899` — hybrid recall
  verified during the 2026-09-28 v9.2.9 requalification; `wm doctor` reports
  healthy and Landlock is enforced at ABI v8. The old partial report applied
  to the earlier VM candidate.
- Disk state persists at the path set in `vm.nix` (default
  `/home/lucas/vms/mandala.qcow2`, 8G — change it per the stranger checklist);
  autologin on the console.
- Writes go through the `wm` CLI over SSH (session/memory tools). A *writable*
  `wm serve` cannot run beside the daemon on one store (Tantivy index lock),
  so the forwarded MCP is read-only.
- Lakshmi can read the VM's dharma dimension live:
  `python3 ~/Desktop/MANDALA_OS/LAKSHMI/lakshmi.py --once --dharma-mcp http://127.0.0.1:28795`

## 5. The modify → rebuild → rollback loop

```bash
nixos-rebuild test   --flake .#mandala-sovereign   # this boot only
nixos-rebuild switch --flake .#mandala-sovereign   # persist (normal)
nixos-rebuild boot   --flake .#mandala-sovereign   # next boot (kernel/boot changes)
```

- Boot selection: systemd-boot menu (5s) lists `NixOS (Generation N)` and
  `Zorin OS`; keep 4 generations. Roll back by picking an older line, or
  `nixos-rebuild switch --rollback`.
- Firmware fallback: Lenovo **F12** at power-on still lists `Zorin OS` /
  `Linux Boot Manager` even if the NixOS menu misbehaves.
- WM iteration without a release tag:
  `--override-input whitemagic-src path:/home/lucas/Desktop/WHITEMAGIC/WMv9`.
- Disk reclamation: `nix-collect-garbage -d`.

## 6. Where to look when things break

| Symptom | First move |
|---|---|
| NixOS won't boot | F12 → Zorin; fix from there; generation N-1 is still in the menu |
| WM daemon dead | `systemctl status whitemagic-daemon`; `journalctl -u whitemagic-daemon` |
| Sandbox degraded | `cat ~/.local/share/whitemagic/landlock_state.json`; re-run the matrix |
| Flake eval errors | `nix flake check --show-trace`; fix module; commit |
| Disk full | `nix-collect-garbage -d`; check `/nix` usage; see README space budget |

## 7. Where this is going (current, not historical)

1. **Yama observe bridge — live.** S4 executed 2026-09-15: real eBPF capture →
   collector → telemetry galaxy → step-0 policies → dashboard. Routine capture
   windows: `scripts/capture_window.sh`.
2. **Actuator ladder (Y1).** Notify-only router shipped; nudge/throttle wait on
   per-policy observation windows (`MANDALA_OS/design/ACTUATOR_CONTRACT_2026-09-15.md`).
3. **Publication gates.** Soak (≥72 h accumulated active time, redefined
   2026-09-15), stranger install (this checklist is the dry run), repo hygiene
   (`MANDALA_OS/publication/GATE_EVIDENCE_PLAYBOOK.md`).
4. **Bare metal** — blocked on a spare medium / disk pass (`docs/INSTALL_AND_BOOT.md`).
5. **Mesh + local-AI modules** — when OFFGRID_MESH_TERMINAL and llama.cpp
   integration plans land (direction doc §4 caveats).

## 8. House rules

- Docs state what is verified vs. target — keep that discipline (the
  direction doc's corrections section exists because of it).
- No secrets in repos; use sops-nix/agenix when the first one lands.
- Record meaningful sessions to WM (`wm session record/checkpoint`) so the
  next cold start has continuity.
