{ config, pkgs, lib, modulesPath, ... }:

{
  # ARM appliance scaffold (Rockchip RK3588 / Raspberry Pi CM4 class).
  # For real boards, pin board support from github:NixOS/nixos-hardware —
  # this only provides the generic aarch64 SD-image defaults so the config
  # evaluates.
  imports = [
    (modulesPath + "/installer/sd-card/sd-image-aarch64.nix")
  ];

  # configuration.nix targets EFI/systemd-boot; SD-image ARM boards don't use it.
  boot.loader.systemd-boot.enable = lib.mkForce false;
  boot.loader.efi.canTouchEfiVariables = lib.mkForce false;

  hardware.enableRedistributableFirmware = true;
}
