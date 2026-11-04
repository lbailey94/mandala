{ config, pkgs, lib, ... }:

let
  cfg = config.services.whitemagic;
in
{
  options.services.whitemagic = {
    enable = lib.mkEnableOption "WhiteMagic cognitive substrate daemon";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.whitemagic;
      description = "WhiteMagic package providing the `wm` binary.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "mandala";
      description = "User running the WhiteMagic daemon.";
    };

    storeDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/mandala/.local/share/whitemagic";
      description = "WM store root (the daemon's read-write workspace).";
    };

    landlock = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Set WM_LANDLOCK=1 to confine write-class filesystem rights to the
        store root (WM's shipped Landlock v0; opt-in upstream).
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    # Create the store root and cache dirs before the service starts, so the
    # ReadWritePaths bind mounts have an existing target. systemd-tmpfiles
    # does not create intermediate parents for `d` entries, so each level is
    # listed explicitly.
    systemd.tmpfiles.rules = [
      "d /home/${cfg.user}/.local 0755 ${cfg.user} users -"
      "d /home/${cfg.user}/.local/share 0755 ${cfg.user} users -"
      "d ${cfg.storeDir} 0700 ${cfg.user} users -"
      "d ${cfg.storeDir}/sandbox_rw 0700 ${cfg.user} users -"
      "d /home/${cfg.user}/.cache 0755 ${cfg.user} users -"
    ];

    systemd.services.whitemagic-daemon = {
      description = "WhiteMagic Local Cognitive Substrate & Daemon";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        WorkingDirectory = "/home/${cfg.user}";
        ExecStart = "${cfg.package}/bin/wm daemon";
        Restart = "on-failure";
        RestartSec = "5s";

        Environment = [
          "WM_LANDLOCK=${if cfg.landlock then "1" else "0"}"
          # systemd system services do not inherit HOME; the landrun runner
          # resolves its scratch dir from HOME and fails loudly without one.
          # Pin both so contained spawns keep a writable scratch under the
          # store (already covered by ReadWritePaths).
          "HOME=/home/${cfg.user}"
          "WM_SANDBOX_RW=${cfg.storeDir}/sandbox_rw"
        ];

        # systemd sandboxing — the real "yama gatekeeper" seam for the daemon.
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        # `-` prefix: ignore missing paths at first start; the daemon creates
        # its store on boot (without it, mount-namespace setup fails and the
        # unit crash-loops in `activating`).
        ReadWritePaths = [
          "-${cfg.storeDir}"
          "-/home/${cfg.user}/.cache"
        ];
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectKernelTunables = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
          "AF_NETLINK"
        ];
      };
    };
  };
}
