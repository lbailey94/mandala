{ config, pkgs, lib, ... }:

let
  mandalaSandbox = pkgs.writeShellApplication {
    name = "mandala-sandbox";
    runtimeInputs = [
      pkgs.bubblewrap
      pkgs.coreutils
      pkgs.jq
    ];
    text = ''
      # Unprivileged containment for external tools dispatched by WhiteMagic.
      #
      #   mandala-sandbox <command> [args...]         # no network (default)
      #   mandala-sandbox --net <command> [args...]   # egress + DNS + CA certs
      #   mandala-sandbox --exec '<json envelope>'    # WM B2 protocol
      #
      # Envelope schema `wm-sandbox-exec-v1`, built by wm-core's SpawnPolicy:
      #   {"schema":"wm-sandbox-exec-v1","program":"gh",
      #    "args":["issue","list"],"net":true}
      # `program`/`args` are executed directly (no shell interpolation);
      # `net` selects the network profile. Unknown fields are ignored so the
      # protocol can grow without breaking deployed runners.
      #
      # Mechanisms: bubblewrap user/mount/net namespaces, read-only system,
      # ephemeral /tmp, die-with-parent. Compat binds (/lib, /lib64, /etc/...)
      # let non-store binaries (dev machines) and DNS work; on NixOS the store
      # bind carries its own loader. For kernel-enforced filesystem rules on
      # kernels >= 6.7, layer `landrun` on top (see README).
      #
      # Network is OFF by default; WM's dharma gate remains the policy layer
      # for egress that is allowed.

      with_net=0
      workspace_override=""
      workspace_rw=0

      if [ "''${1:-}" = "--exec" ]; then
        envelope="''${2:?mandala-sandbox: --exec requires a JSON envelope}"
        shift 2
        coproc parsed_stream { jq -j 'if type != "object" or (.program | type) != "string" or .program == "" or (.program | index("\u0000")) != null or (has("args") and (.args | type) != "array") or any((if has("args") then .args else [] end)[]; type != "string" or index("\u0000") != null) or (has("net") and (.net | type) != "boolean") or (has("workspace") and ((.workspace | type) != "string" or (.workspace | index("\u0000")) != null)) or (has("rw") and (.rw | type) != "boolean") then error("invalid sandbox envelope") else ([.program, (if has("net") then .net else false end | tostring), (if has("workspace") then .workspace else "" end), (if has("rw") then .rw else false end | tostring)] + (if has("args") then .args else [] end))[] | ., "\u0000" end' <<<"$envelope"; }
        mapfile -d $'\0' -t fields <&"''${parsed_stream[0]}"
        # shellcheck disable=SC2154 # Bash assigns this PID for the named coprocess.
        if ! wait "''${parsed_stream_PID}"; then
          echo "mandala-sandbox: invalid JSON envelope or argument types" >&2
          exit 64
        fi
        program="''${fields[0]}"
        if [ "''${fields[1]}" = "true" ]; then
          with_net=1
        fi
        workspace_override="''${fields[2]}"
        if [ "''${fields[3]}" = "true" ]; then
          workspace_rw=1
        fi
        exec_args=("''${fields[@]:4}")
        set -- "$program" "''${exec_args[@]}"
      elif [ "''${1:-}" = "--net" ]; then
        with_net=1
        shift
      fi

      # HOME may be unbound under systemd (`set -u`) — default to a path
      # that will not exist, so the workspace bind is skipped, not fatal.
      workspace="''${workspace_override:-''${WM_SANDBOX_WORKSPACE:-''${HOME:-/nonexistent}/.local/share/whitemagic/safe_corpus}}"

      args=(
        --ro-bind /usr /usr
        --ro-bind-try /lib /lib
        --ro-bind-try /lib64 /lib64
        --ro-bind-try /nix /nix
        --ro-bind-try /bin /bin
        # NixOS: systemd's PATH entries (/run/current-system/sw/bin) are
        # symlinks; bind the target so name-based execvp works in-guest
        # (learned live 2026-09-13 — `bwrap: execvp sh: No such file`).
        --ro-bind-try /run/current-system /run/current-system
        --proc /proc
        --dev /dev
        --unshare-all
        --tmpfs /tmp
        --die-with-parent
        --setenv WM_SANDBOXED 1
      )

      if [ "$with_net" = 1 ]; then
        # --share-net undoes --unshare-all's net namespace; skipping
        # --unshare-net is NOT enough (bwrap 0.9 behavior).
        args+=( --share-net )
        # On systemd-resolved systems /etc/resolv.conf is a symlink into
        # /run/systemd/resolve — bind the target dir first so DNS resolves.
        args+=( --ro-bind-try /run/systemd/resolve /run/systemd/resolve )
        args+=( --ro-bind-try /etc/resolv.conf /etc/resolv.conf )
        args+=( --ro-bind-try /etc/hosts /etc/hosts )
        args+=( --ro-bind-try /etc/nsswitch.conf /etc/nsswitch.conf )
        args+=( --ro-bind-try /etc/ssl/certs /etc/ssl/certs )
      fi

      if [ -e "$workspace" ]; then
        if [ "$workspace_rw" = 1 ]; then
          args+=( --bind "$workspace" /workspace )
        else
          args+=( --ro-bind "$workspace" /workspace )
        fi
      elif [ "$workspace_rw" = 1 ]; then
        echo "mandala-sandbox: writable workspace does not exist" >&2
        exit 64
      fi

      exec bwrap "''${args[@]}" -- "$@"
    '';
  };

  runnerPath = "${mandalaSandbox}/bin/mandala-sandbox";

  # Pure-Landlock runner for stores that already run a Landlock domain
  # (rulesets stack; no namespaces, path confinement only). Single source:
  # scripts/landrun-sandbox is also installed standalone on non-NixOS hosts.
  landrunSandbox = pkgs.writeShellApplication {
    name = "landrun-sandbox";
    runtimeInputs = [
      pkgs.landrun
      pkgs.jq
      pkgs.coreutils
    ];
    text = builtins.readFile ../scripts/landrun-sandbox;
  };
  landrunRunnerPath = "${landrunSandbox}/bin/landrun-sandbox";
in
{
  environment.systemPackages = [
    mandalaSandbox
    landrunSandbox
    pkgs.bubblewrap
    pkgs.landrun
  ];

  # B2 — WM's declared-subprocess spawns must route through a runner.
  # systemd services do NOT inherit `environment.variables` and run with a
  # minimal PATH, so the path is set explicitly per service. (Learned live
  # 2026-09-13: in-guest PATH detection failed and loud-degraded — honest,
  # but not contained; the OS module must wire it.)
  #
  # Landlock × namespaces (2026-09-13, resolved 2026-09-14): bwrap needs
  # mount topology changes, and an active Landlock domain always denies
  # mounts — so a Landlock store cannot run the bwrap runner (reproduced
  # host + VM; SANDBOX_LAYERS §3-7). Landlock rulesets *stack*, so the fix
  # is the pure-Landlock runner: the daemon keeps WM_LANDLOCK=1 and routes
  # its declared spawns through `landrun-sandbox`; the read-only serve has
  # no Landlock and keeps the bwrap runner. Both are contained; neither
  # needs both mechanisms at once.
  environment.variables.WM_SANDBOX_RUNNER = runnerPath;
  systemd.services.whitemagic-daemon.environment.WM_SANDBOX_RUNNER = landrunRunnerPath;
  systemd.services.wm-mcp-readonly.environment.WM_SANDBOX_RUNNER = runnerPath;

  # Ship the containment self-test in the system ...
  environment.etc."mandala/verify-sandbox.sh" = {
    source = ../scripts/verify-sandbox.sh;
    mode = "0755";
  };

  # ... and run it at boot so a headless serial console shows the matrix
  # result (first-boot evidence without login). A FAIL leaves the unit in a
  # failed state — visible, honest, non-blocking.
  systemd.services.mandala-sandbox-selftest = {
    description = "MandalaOS sandbox containment self-test";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    path = [
      pkgs.bash
      pkgs.bubblewrap
      pkgs.curl
      pkgs.coreutils
      pkgs.gawk
      pkgs.gnugrep
      pkgs.gnused
      # The matrix's pure-Landlock section runs both directly.
      landrunSandbox
      pkgs.landrun
    ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      # systemd system services do not inherit HOME; landrun-sandbox needs a
      # writable scratch dir and fails loudly without one (the matrix's
      # "landrun scratch writable" check). Pin HOME so the boot-time matrix
      # matches an interactive run.
      Environment = [ "HOME=/root" ];
    };
    script = ''
      set -o pipefail
      ${pkgs.bash}/bin/bash /etc/mandala/verify-sandbox.sh 2>&1 | tee /dev/console
    '';
  };
}
