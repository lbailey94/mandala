{
  description = "MandalaOS Sovereign Edition — declarative NixOS configuration (x86_64 workstation/VM + ARM appliance)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # WhiteMagic source for the `wm` binary package. Override locally while
    # iterating:
    #   nix ... --override-input whitemagic-src path:/home/lucas/Desktop/WHITEMAGIC/WMv9
    whitemagic-src.url = "github:lbailey94/whitemagic/v9.2.9";
    whitemagic-src.flake = false;
  };

  outputs =
    { self, nixpkgs, whitemagic-src, ... }@inputs:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      whitemagicOverlay = final: prev: {
        whitemagic = final.callPackage ./packages/whitemagic.nix {
          src = whitemagic-src;
        };
      };
    in
    {
      overlays.default = whitemagicOverlay;

      packages.${system} = {
        whitemagic = pkgs.callPackage ./packages/whitemagic.nix {
          src = whitemagic-src;
        };
        default = self.packages.${system}.whitemagic;
      };

      apps.${system}.vm = {
        type = "app";
        program = "${self.nixosConfigurations.mandala-vm.config.system.build.vm}/bin/run-mandala-node-vm";
      };

      nixosConfigurations.mandala-sovereign = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          ./configuration.nix
          { nixpkgs.overlays = [ whitemagicOverlay ]; }
        ];
      };

      # Same system plus VM-only conveniences (autologin, resources); used by
      # `nix run .#vm` and scripts/run-vm-headless.sh. Never install this one.
      nixosConfigurations.mandala-vm = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          ./configuration.nix
          ./vm.nix
          { nixpkgs.overlays = [ whitemagicOverlay ]; }
        ];
      };

      nixosConfigurations.mandala-arm-appliance = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          ./configuration.nix
          ./modules/arm-hardware.nix
          { nixpkgs.overlays = [ whitemagicOverlay ]; }
        ];
      };
    };
}
