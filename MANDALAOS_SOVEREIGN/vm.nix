# VM-only conveniences for hands-on sessions and diagnosis.
#
# NEVER import this into a bare-metal target: passwordless console autologin,
# passwordless sudo, SSH with a forwarded port, and a forwarded MCP port.
{ lib, pkgs, ... }:

{
  services.getty.autologinUser = lib.mkForce "mandala";
  security.sudo.wheelNeedsPassword = false;

  environment.systemPackages = [ pkgs.strace ];

  environment.etc."mandala/daemon-diag.sh" = {
    source = ./scripts/vm-daemon-diag.sh;
    mode = "0755";
  };

  # --- VM runtime (qemu-vm options live in the nested vmVariant evaluation) ---
  virtualisation.vmVariant = {
    virtualisation = {
      memorySize = 4096;
      cores = 2;
      diskSize = 8192;
      diskImage = "/home/lucas/vms/mandala.qcow2";
      graphics = true;
      forwardPorts = [
        { from = "host"; host.port = 2222; guest.port = 22; }
      ];
    };

    services.openssh = {
      enable = true;
      settings.PasswordAuthentication = true;
    };

    # Read-only MCP surface, loopback-only per WhiteMagic's SSE policy.
    # Use an SSH local tunnel from the host instead of a QEMU port forward.
    # A writable serve cannot coexist with the daemon on one store (Tantivy
    # writer lock); writes go through the `wm` CLI over SSH.
    systemd.services.wm-mcp-readonly = {
      description = "WhiteMagic read-only MCP serve (VM dogfood surface)";
      wantedBy = [ "multi-user.target" ];
      after = [ "whitemagic-daemon.service" ];
      serviceConfig = {
        User = "mandala";
        WorkingDirectory = "/home/mandala";
        ExecStart = "${pkgs.whitemagic}/bin/wm serve --readonly --transport sse --bind 127.0.0.1:18795 --store /home/mandala/.local/share/whitemagic --profile full";
        Restart = "on-failure";
        RestartSec = "5s";
      };
      # Hybrid recall needs the host embedder bridge here too — without
      # WM_EMBEDDER_* the read-only surface falls back to FTS even when the
      # store has vectors (found live 2026-09-13 after the reembed backfill).
      environment = {
        WM_EMBEDDER_ENDPOINT = "http://10.0.2.2:18899/v1/embeddings";
        WM_EMBEDDER_MODEL = "bge-small";
        WM_EMBEDDER_DIM = "384";
        WM_EMBEDDER_TIMEOUT_MS = "15000";
      };
    };

    # Bridge to the host's live embedder (slirp host alias 10.0.2.2): hybrid
    # recall works in-guest without a local model.
    environment.variables = {
      WM_EMBEDDER_ENDPOINT = "http://10.0.2.2:18899/v1/embeddings";
      WM_EMBEDDER_MODEL = "bge-small";
      WM_EMBEDDER_DIM = "384";
      WM_EMBEDDER_TIMEOUT_MS = "15000";
    };
    systemd.services.whitemagic-daemon.environment = {
      WM_EMBEDDER_ENDPOINT = "http://10.0.2.2:18899/v1/embeddings";
      WM_EMBEDDER_MODEL = "bge-small";
      WM_EMBEDDER_DIM = "384";
      WM_EMBEDDER_TIMEOUT_MS = "15000";
    };

    # Key-based SSH for lucas. Password auth is also on: set one in-guest with
    # `passwd mandala` if you prefer.
    users.users.mandala.openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINanCfx0ASiZcc3dJUT+JeHieJfRoSWCYkj/yHlalyPJ lucas@whitemagic"
      # Passphrase-less key for VM dogfooding/automation (host: ~/.ssh/id_mandala_vm)
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKkM8VpJvqlYUnkLaHgEqBBpbuZD2Gsi5LahptI6VZgC mandala-vm"
    ];
  };
}
