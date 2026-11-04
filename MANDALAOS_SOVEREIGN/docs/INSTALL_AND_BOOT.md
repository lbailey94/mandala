# Install, Customize, and Boot Selection — MandalaOS Sovereign Edition

How to go from this repo to a bootable machine, how to modify the OS
extensively, and how to choose what boots.

---

## 0. Mental model (read this first)

Three different things people call "installing NixOS":

1. **Nix (the package manager) on Zorin** — for building and validating this
   repo without touching the current OS. Safe, reversible, ~1 GB.
2. **A NixOS VM built from this repo** — first real boot, zero risk.
3. **NixOS on bare metal** — dual-boot alongside Zorin. This is where the
   disk surgery happens; do it only after stages 1–2 prove out.

Once NixOS is installed, the workflow is simple: **the entire OS is this git
repo**. You modify files, rebuild, and reboot or switch. Every build is an
immutable *generation*; the boot menu lets you pick any of the last N —
rollback is selecting an older line at boot, not reinstalling.

### This machine (audited 2026-09-12)

| Fact | Value |
|---|---|
| Hardware | Lenovo laptop, UEFI, Secure Boot **disabled** (Platform in Setup Mode) |
| Disk | Single 238 GB NVMe: p1 = 511 MB ESP (`/boot/efi`, 6.3 MB used), p2 = 238 GB ext4 `/` (201 GB used, **21 GB free**) |
| Boot | `Boot0000 Zorin OS` → `\EFI\ubuntu\shimx64.efi` (Ubuntu-family GRUB) |
| Constraint | **21 GB free is not enough** for a NixOS root + build store. A disk pass (target ≥ 60 GB free) or an external SSD is required before bare metal. |

---

## 1. Stage 0 — Nix on Zorin (build & validate, today)

**No-root option (used for the first successful eval):** `nix-portable`
(a single binary that keeps its own store under `~/.nix-portable`):

```bash
curl -sL -o /tmp/opencode/nixp/nix-portable \
  https://github.com/DavHau/nix-portable/releases/latest/download/nix-portable-x86_64
chmod +x /tmp/opencode/nixp/nix-portable
cd ~/Desktop/projects/MANDALAOS_SOVEREIGN
/tmp/opencode/nixp/nix-portable nix --extra-experimental-features 'nix-command flakes' flake check
```

**Permanent option (sudo, recommended long-term):**

```bash
# Official multi-user install (Determinate Systems; clean uninstaller included)
curl -fsSL https://install.determinate.systems/nix | sh -s -- install

# Validate the flake (first run fetches nixpkgs 26.05: 49 MB tar -> 469 MB store)
cd ~/Desktop/projects/MANDALAOS_SOVEREIGN
nix flake check
nix build .#whitemagic                     # optional; heavy (Rust build)

# Uninstall later, if ever: /nix/nix-installer uninstall
```

**Verified 2026-09-13:** `nix flake check` passes both `mandala-sovereign`
and `mandala-arm-appliance` (Nix 2.20.6 via nix-portable, no root).
`flake.lock` pins nixpkgs 26.05 and the WM v9.1.3 source.

Space (see README table): install + eval ≈ **0.8–1.0 GB**; full system build
+4–6 GB; WM from source +4–7 GB. On 21 GB free, keep this stage to
eval/build-one-artifact until the disk pass.

Note: the repos are **private** on GitHub. For the live-ISO install either
clone with an authenticated `gh`/token, or copy the repo to a USB stick.

---

## 2. Stage 1 — bootable VM (first real boot, zero risk)

```bash
nix build .#nixosConfigurations.mandala-sovereign.config.system.build.vm
QEMU_OPTS="-m 4096 -smp 2" ./result/bin/run-mandala-node-vm
```

**Verified 2026-09-13:** the VM boots to a login prompt under KVM; the
in-guest sandbox matrix reports **8/8 PASS** and the **WhiteMagic daemon
starts** under systemd. Reproduce headlessly (no root, nix-portable
friendly):

```bash
scripts/run-vm-headless.sh                 # boots ~150s, prints evidence
VM_SECONDS=420 scripts/run-vm-headless.sh  # longer window
cat /tmp/mandala-vm-boot.log               # full serial console
```

In-guest evidence excerpt:

```
Started WhiteMagic Local Cognitive Substrate & Daemon.
MandalaOS sandbox matrix (bwrap 0.11.2)
  PASS  write /usr denied / write /tmp allowed / /etc/shadow hidden
  PASS  home store hidden / network isolated / workspace readable
  PASS  workspace write denied / network shared with --net
matrix green
```

Known VM quirks (non-blocking): the informational egress probe reports
unreachable (VM DNS/slirp — the matrix network check is route-based), and the
stock `Logrotate configuration check` unit fails in the VM.

What else to verify inside the VM:

1. Log in as `mandala` (no password is declared; set one with `passwd`).
2. `systemctl status whitemagic-daemon` — unit active, `WM_LANDLOCK=1` set.
3. `wm doctor` — store, embedder, landlock outcome.
4. `/etc/mandala/verify-sandbox.sh` — the same containment matrix on demand.

The VM is also where "extensive modification" should happen first — you can
rebuild, break, and recover with no stakes.

---

## 3. Stage 2 — bare metal, dual-boot with Zorin

### 3a. Prerequisites

- **Disk headroom:** free at least 60 GB on the Zorin side (move archives to
  the SD card / external drives). You cannot shrink a 201 GB-used partition
  into less than its used size.
- Backup anything irreplaceable (the WHITEMAGIC disk-scouting docs already
  established the archive strategy).
- A USB stick for the NixOS ISO (≥ 2 GB).

### 3b. Partitioning (from the NixOS live ISO, GParted)

1. Shrink `nvme0n1p2` by 60 GB → 58 GB unallocated after it.
2. Create `nvme0n1p3` (ext4, 58 GB) → NixOS root.
3. ESP: two valid options —
   - **Share the existing 511 MB ESP (recommended):** mount `p1` at `/boot`
     during install, **do not format it**. NixOS kernels land there; the repo
     sets `configurationLimit = 4` (~90 MB/generation ⇒ ~360 MB, fits the
     505 MB free).
   - **Create a second 1 GB ESP** (`p4`) and set
     `boot.loader.efi.efiSysMountPoint = "/boot"` to it. More generation
     headroom, slightly more firmware fiddling.
4. No swap partition needed — the config ships zstd ZRAM at 50%.

### 3c. Install

```bash
# On the live ISO (network up; repo committed and pushed, or copied from USB)
git clone <this-repo> /tmp/mandalaos && cd /tmp/mandalaos

# Mount target (example: p3 root + shared ESP p1)
mount /dev/nvme0n1p3 /mnt
mkdir -p /mnt/boot && mount /dev/nvme0n1p1 /mnt/boot     # never format it

nixos-generate-config --root /mnt --no-filesystems        # optional reference
nixos-install --flake .#mandala-sovereign
```

Set the `mandala` password on first boot (`passwd mandala`).

### 3d. What boot looks like afterward

```
systemd-boot menu (5s timeout)
  NixOS (Generation 1)      <- default, from this repo
  NixOS (Generation 0)      <- rollback target
  Zorin OS                  <- chainloads \EFI\ubuntu\shimx64.efi
```

- **Arrows + Enter** select; the last N generations are kept
  (`configurationLimit = 4`).
- The firmware boot menu (Lenovo: **F12 at power-on**) still lists
  `Zorin OS` and `Linux Boot Manager` independently — your escape hatch if a
  NixOS generation ever fails to boot.
- Zorin's GRUB is untouched; the Zorin entry can equally be chosen from
  systemd-boot or firmware.

### 3e. Alternative: install to SD card / USB stick / external SSD

For a hardware trial without partition surgery, install to removable media.
The target medium simply replaces the internal partition layout:

- **Do not repartition the current SD_CARD1.** It is the archive vault
  (24 GB of whitemagic archives on exfat, some likely sole copies), and exfat
  has **no safe shrink** support — GParted/exfatprogs cannot resize it and
  there is no upstream implementation (see exfatprogs issue #134).
- Use a **spare** SD card (≥ 64 GB) or USB stick/SSD. USB flash works for
  boot trials; it is slow and write-wearing for daily Nix builds. An external
  SSD is the performant choice.
- Install flow is identical to §3c, substituting the device:
  partition the spare medium with an ESP (~1 GB, vfat) + root (rest, ext4),
  mount as `/mnt` + `/mnt/boot`, `nixos-install --flake .#mandala-sovereign`.
- Boot it via the firmware menu (Lenovo: **F12**). The USB reader here is a
  USB mass-storage device, so it appears as a USB boot target.
- The installed system is fully self-contained on the medium; Zorin's ESP and
  disk stay untouched.

---

## 4. Extensive modification — the workflow

All changes are edits to this repo. Three rebuild verbs, different blast radii:

| Command | Effect | Use when |
|---|---|---|
| `nixos-rebuild test --flake .#mandala-sovereign` | activates now, **reverts on reboot** | trying risky config |
| `nixos-rebuild switch --flake .#mandala-sovereign` | activates now and persists | everyday changes |
| `nixos-rebuild boot --flake .#mandala-sovereign` | applies on next reboot only | kernel/bootloader changes |

Rollback: pick an older generation in the boot menu, or
`nixos-rebuild switch --rollback`.

### Adding our capabilities (the intended shape)

Everything is a module; examples to build out:

- `modules/local-ai.nix` — llama.cpp server (Vulkan), model directory,
  embedder endpoint (`WM_EMBEDDER_ENDPOINT=127.0.0.1:18899`).
- `modules/offline-mesh.nix` — OFFGRID_MESH_TERMINAL daemon + spidev/DT
  overlay for SX1262 (no mainline driver; userspace path).
- `modules/observability.nix` — Lakshmi as a systemd service feeding a local
  dashboard (`projects/LAKSHMI/lakshmi.py --json`).
- `services.whitemagic.settings` — extend the WM unit: mesh bind, tool
  profile, token enforcement (`WM_SANGHA_REQUIRE_TOKENS=1`).

### Versioning our software

- Release pin: `whitemagic-src.url = "github:lbailey94/whitemagic/vX.Y.Z"`.
- Local iteration: `nix build .#whitemagic --override-input whitemagic-src path:/home/lucas/Desktop/WHITEMAGIC/WMv9`.
- `nix flake update` advances nixpkgs; commits of `flake.lock` are the OS
  upgrade history.

### Hygiene

- Secrets stay out of the repo; add `sops-nix`/`agenix` when the first real
  secret lands (mesh keys, tokens).
- `nix-collect-garbage -d` reclaims old generations' store paths when disk
  gets tight.
- Keep `/etc/nixos` (if the installer wrote one) as a fallback seed.

---

## 5. Command cheat sheet

```bash
# Validate / build
nix flake check
nix build .#whitemagic
nix build .#nixosConfigurations.mandala-sovereign.config.system.build.vm

# Modify the OS
nixos-rebuild test   --flake .#mandala-sovereign
nixos-rebuild switch --flake .#mandala-sovereign
nixos-rebuild boot   --flake .#mandala-sovereign
nixos-rebuild switch --rollback

# Boot selection mechanics
bootctl list                      # generations + other boot entries
bootctl set-default <entry-id>    # default entry
efibootmgr -v                     # firmware entries; -o reorders
# Lenovo: F12 = firmware boot menu (Zorin OS / Linux Boot Manager)

# Reclaim
nix-collect-garbage -d
```

---

## 6. Recommended sequence from here

1. Disk pass → ≥ 60 GB free, **or** a spare SD/USB/SSD for a removable install
   (see §3e; the archive SD stays untouched).
2. Stage 0 (Nix on Zorin or nix-portable) → `nix flake check` → first VM boot.
3. Iterate modules in the VM until the feel is right.
4. Bare-metal dual-boot, spare-medium install, or external SSD — keep Zorin
   as recovery OS indefinitely.
