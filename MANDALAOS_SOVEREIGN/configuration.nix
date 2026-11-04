{ config, pkgs, lib, ... }:

{
  imports = [
    ./modules/kernel-hardening.nix
    ./modules/landlock-isolation.nix
    ./modules/whitemagic-service.nix
    ./modules/zram-swap.nix
  ];

  networking.hostName = "mandala-node";

  networking.firewall = {
    enable = true;
    allowPing = false;
    # WM MCP (18795) and the embedder (18899) bind to loopback only; no
    # externally reachable ports by design.
    allowedTCPPorts = [ ];
    allowedUDPPorts = [ ];
  };

  # Clean baseline (the Sovereign spec's aggressive choice). Comment this out
  # if a tool turns out to need a default package (e.g. `perl` for scripts).
  environment.defaultPackages = lib.mkForce [ ];

  environment.systemPackages = with pkgs; [
    bubblewrap
    landrun
    lmdb
    clang
    rustc
    cargo
    git
    htop
    tmux
    curl
    whitemagic
  ];

  # Atomic rollbacks & reproducibility
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.loader.timeout = 5;
  # ESP is 511M on this laptop (505M free; Zorin keeps only shim/grub there).
  # ~90MB per NixOS generation => 4 generations fits with room to spare.
  boot.loader.systemd-boot.configurationLimit = 4;
  # Dual-boot: keep Zorin OS reachable from the systemd-boot menu by
  # chainloading its shim (audited 2026-09-12: Boot0000 -> \EFI\ubuntu\shimx64.efi,
  # Secure Boot disabled). The entry dangles harmlessly in the VM.
  boot.loader.systemd-boot.extraEntries."zorin.conf" = ''
    title Zorin OS
    efi /EFI/ubuntu/shimx64.efi
    sort-key z_zorin
  '';

  # Quiet boot. The LSM stack is managed by NixOS modules (AppArmor below;
  # Yama and Landlock are always-on kernel defaults) — do not hand-set `lsm=`.
  boot.kernelParams = [
    "quiet"
    "splash"
    "loglevel=3"
    "rd.systemd.show_status=false"
  ];

  # No ZFS here; silence the 26.05 default-change warning explicitly.
  boot.zfs.forceImportRoot = false;

  security.apparmor.enable = true;

  # Placeholder for evaluation/VM builds. At install time the real layout
  # comes from `nixos-generate-config` (import its fileSystems block) or this
  # is edited on the target. mkDefault keeps it overridable; the VM and
  # sd-image modules both override it.
  fileSystems."/" = lib.mkDefault {
    device = "/dev/disk/by-label/nixos";
    fsType = "ext4";
  };

  users.users.mandala = {
    isNormalUser = true;
    extraGroups = [ "wheel" "video" "audio" ];
    shell = pkgs.bashInteractive;
    # No password is declared here; set one on first boot: `passwd mandala`.
  };

  services.whitemagic.enable = true;

  system.stateVersion = "26.05";
}
