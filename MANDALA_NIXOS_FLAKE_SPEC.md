# MandalaOS NixOS Flake Specification & Hardening Blueprint

**Project**: MandalaOS Sovereign Edition  
**Substrate**: NixOS 26.05 (Declarative, Bit-for-Bit Reproducible)  
**Target Profile**: Minimalist, sub-500MB idle RAM, zero-cloud egress, hardware-isolated WhiteMagic runtime  
**Date**: September 2026  

> **Implementation reality & corrections (2026-09-12).** This is an
> **architecture spec, not a working build**. Verified corrections before
> scaffolding the real flake — see `PLATFORM_DIRECTION_2026-09-12.md` §4:
> `pkgs.whitemagic` does not exist (package WM from source with
> `rustPlatform.buildRustPackage`); `landlock-sandbox` is not a nixpkgs package
> (use `landrun` or bwrap); Landlock ABIs run to V9 now, not v4; the module
> descriptions below are aspirational in places (a NixOS module cannot do
> syscall interception); SX1262 LoRa has no mainline driver; the §7 performance
> numbers are **targets, not measurements**. Canonical module set:
> `kernel-hardening.nix`, `landlock-isolation.nix`, `whitemagic-service.nix`,
> `zram-swap.nix`, `arm-hardware.nix`.

---

## 1. Executive Summary

MandalaOS Sovereign Edition replaces legacy virtualization (e.g. Qubes OS Xen hypervisors, which demand 16GB+ RAM and drain battery) with **declarative Linux user-namespaces, Bubblewrap containment, and Linux Landlock ABI sandboxing**. 

This document provides the concrete Nix Flake architecture, system configurations, and security profiles required to build a bootable ISO and installable disk image.

---

## 2. Flake Architecture (`flake.nix`)

```nix
{
  description = "MandalaOS: Sovereign, local-first cognitive operating system";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs: {
    nixosConfigurations.mandala-sovereign = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        ./modules/kernel-hardening.nix
        ./modules/landlock-isolation.nix
        ./modules/whitemagic-service.nix
        ./modules/zram-swap.nix
      ];
    };

    # ARM64 appliance configuration (Rockchip RK3588 / Raspberry Pi CM4)
    nixosConfigurations.mandala-arm-appliance = nixpkgs.lib.nixosSystem {
      system = "aarch64-linux";
      modules = [
        ./configuration.nix
        ./modules/arm-hardware.nix
        ./modules/kernel-hardening.nix
        ./modules/landlock-isolation.nix
        ./modules/whitemagic-service.nix
      ];
    };
  };
}
```

---

## 3. Core Declarative Configuration (`configuration.nix`)

```nix
{ config, pkgs, lib, ... }:

{
  networking.hostName = "mandala-node";
  networking.firewall = {
    enable = true;
    allowPing = false;
    # Strictly bind WhiteMagic MCP only to local loopback (127.0.0.1:18795)
    allowedTCPPorts = [ ]; 
    allowedUDPPorts = [ ];
  };

  # Zero telemetry & clean baseline
  environment.defaultPackages = lib.mkForce [ ];
  environment.systemPackages = with pkgs; [
    bubblewrap
    landrun          # Landlock CLI sandbox (real nixpkgs package; replaces 'landlock-sandbox')
    lmdb
    clang
    rustc
    cargo
    git
    htop
    tmux
    curl
  ];

  # Fast, atomic rollbacks & bit-for-bit reproducibility
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Sub-5s boot with quiet splash
  boot.kernelParams = [
    "quiet"
    "splash"
    "loglevel=3"
    "rd.systemd.show_status=false"
    "lsm=landlock,lockdown,yama,apparmor,bpf"
  ];

  # Memory optimization: ZRAM swap allows 8GB models to run smoothly on 8-15GB RAM
  zramSwap = {
    enable = true;
    algorithm = "zstd";
    memoryPercent = 50;
  };

  # User isolation
  users.users.mandala = {
    isNormalUser = true;
    extraGroups = [ "wheel" "video" "audio" ];
    shell = pkgs.bashInteractive;
  };

  system.stateVersion = "26.05";
}
```

---

## 4. Kernel Hardening & Sysctl Isolation (`modules/kernel-hardening.nix`)

```nix
{ config, pkgs, ... }:

{
  boot.kernel.sysctl = {
    # Restrict kernel dmesg to root
    "kernel.dmesg_restrict" = 1;
    # Disable unprivileged BPF to prevent side-channel exploits
    "kernel.unprivileged_bpf_disabled" = 1;
    # Hardened ptrace scope (Yama LSM)
    "kernel.yama.ptrace_scope" = 2;
    # Prevent IP spoofing
    "net.ipv4.conf.all.rp_filter" = 1;
    "net.ipv4.conf.default.rp_filter" = 1;
    # Ignore ICMP echo broadcasts
    "net.ipv4.icmp_echo_ignore_broadcasts" = 1;
    # Swap aggression tuned for LMDB mmap & fast vector retrieval
    "vm.swappiness" = 10;
    "vm.vfs_cache_pressure" = 50;
  };
}
```

---

## 5. Bubblewrap Sandbox Profile for AI Tools (`modules/landlock-isolation.nix`)

Every external tool dispatched by WhiteMagic runs inside an unprivileged Bubblewrap namespace:

```bash
#!/usr/bin/env bash
# /usr/local/bin/mandala-sandbox
# Invokes external binaries in an ephemeral, unprivileged sandbox

exec bwrap \
  --ro-bind /usr /usr \
  --ro-bind /nix /nix \
  --ro-bind /bin /bin \
  --proc /proc \
  --dev /dev \
  --unshare-all \
  --unshare-net \
  --tmpfs /tmp \
  --dir /run/user/$(id -u) \
  --ro-bind-try ~/.local/share/whitemagic/safe_corpus /workspace \
  --die-with-parent \
  "$@"
```

---

## 6. WhiteMagic Daemon Systemd Unit (`modules/whitemagic-service.nix`)

```nix
{ config, pkgs, ... }:

{
  systemd.services.whitemagic-daemon = {
    description = "WhiteMagic Local Cognitive Substrate & Daemon";
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "simple";
      User = "mandala";
      WorkingDirectory = "/home/mandala";
      # WM is packaged from source in this flake as `whitemagic` (rustPlatform);
      # there is no `pkgs.whitemagic` in nixpkgs.
      ExecStart = "${whitemagic}/bin/wm daemon";
      Restart = "on-failure";
      RestartSec = "5s";

      # Systemd sandboxing
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [ "/home/mandala/.local/share/whitemagic" ];
      NoNewPrivileges = true;
      PrivateTmp = true;
      ProtectKernelTunables = true;
      ProtectControlGroups = true;
      RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" ];
    };
  };
}
```

---

## 7. Performance & Resource Envelope

| Dimension | Standard Linux Distro | Qubes OS (Xen) | MandalaOS (NixOS) |
| :--- | :--- | :--- | :--- |
| **Idle RAM** | 1.8 GB – 3.2 GB | 6.0 GB – 12.0 GB | **420 MB – 580 MB** |
| **Boot Time** | 18s – 35s | 45s – 90s | **3.8s – 5.2s** |
| **Process Isolation** | Shared global kernel | Heavy hardware hypervisor | **Kernel Landlock + Bubblewrap** |
| **Disk Overhead** | 20 GB – 40 GB mutable | 60 GB – 120 GB VMs | **4.2 GB Immutable Store** |
| **Battery Life Impact**| Baseline | -40% (Virtualization cost) | **+15% (Aggressive eco-modes)** |
| **Reproducibility** | Ad-hoc package state | High but fragile configs | **100% Bit-for-bit Flake Pinning** |
