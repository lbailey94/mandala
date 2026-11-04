#!/usr/bin/env bash
# Local verification for the MandalaOS sandbox wrapper
# (mirror of modules/landlock-isolation.nix).
#
#   verify-sandbox.sh                  # run the built-in containment matrix
#   verify-sandbox.sh <cmd> [args...]  # run <cmd> inside the default profile
#   verify-sandbox.sh --net <cmd> ...  # inside the net-enabled profile
#
# Env: WM_SANDBOX_WORKSPACE overrides the read-only workspace bind path.
set -euo pipefail

run_sandboxed() {
  local with_net=0
  if [ "${1:-}" = "--net" ]; then
    with_net=1
    shift
  fi

  local workspace="${WM_SANDBOX_WORKSPACE:-${HOME:-/root}/.local/share/whitemagic/safe_corpus}"

  local args=(
    --ro-bind /usr /usr
    --ro-bind-try /lib /lib
    --ro-bind-try /lib64 /lib64
    --ro-bind-try /nix /nix
    --ro-bind-try /bin /bin
    # NixOS: systemd PATH entries are symlinks under /run/current-system.
    --ro-bind-try /run/current-system /run/current-system
    --proc /proc
    --dev /dev
    --unshare-all
    --tmpfs /tmp
    --die-with-parent
  )

  if [ "$with_net" = 1 ]; then
    args+=( --share-net )
    args+=( --ro-bind-try /run/systemd/resolve /run/systemd/resolve )
    args+=( --ro-bind-try /etc/resolv.conf /etc/resolv.conf )
    args+=( --ro-bind-try /etc/hosts /etc/hosts )
    args+=( --ro-bind-try /etc/nsswitch.conf /etc/nsswitch.conf )
    args+=( --ro-bind-try /etc/ssl/certs /etc/ssl/certs )
  fi

  if [ -e "$workspace" ]; then
    args+=( --ro-bind "$workspace" /workspace )
  fi

  exec bwrap "${args[@]}" -- "$@"
}

selftest() {
  echo "MandalaOS sandbox matrix (bwrap $(bwrap --version | awk '{print $2}'))"
  export SANDBOX_NET_PROBE="${SANDBOX_NET_PROBE:-https://example.com}"
  local workspace
  workspace=$(mktemp -d)
  echo "sovereign test corpus" > "$workspace/note.txt"

  local failures=0
  check() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
      echo "  PASS  $label"
    else
      echo "  FAIL  $label (expected=$expected actual=$actual)"
      failures=$((failures + 1))
    fi
  }

  # Default profile: deny writes outside tmpfs, hide host state, isolate net.
  local default_out
  default_out=$(run_sandboxed /bin/sh -c '
    if touch /usr/ll-probe 2>/dev/null; then echo usr_writable; else echo usr_denied; fi
    if touch /tmp/ll-probe 2>/dev/null; then echo tmp_ok; else echo tmp_denied; fi
    if [ -e /etc/shadow ]; then echo etc_visible; else echo etc_hidden; fi
    if [ -e "$HOME/.local/share/whitemagic" ]; then echo home_visible; else echo home_hidden; fi
    if grep -q "00000000" /proc/net/route 2>/dev/null; then echo net_open; else echo net_closed; fi
  ')
  check "write /usr denied"        usr_denied   "$(echo "$default_out" | sed -n 1p)"
  check "write /tmp allowed"       tmp_ok       "$(echo "$default_out" | sed -n 2p)"
  check "/etc/shadow hidden"       etc_hidden   "$(echo "$default_out" | sed -n 3p)"
  check "home store hidden"        home_hidden  "$(echo "$default_out" | sed -n 4p)"
  check "network isolated"         net_closed   "$(echo "$default_out" | sed -n 5p)"

  # Workspace: read-only bind is readable, not writable.
  local ws_out
  ws_out=$(WM_SANDBOX_WORKSPACE="$workspace" run_sandboxed /bin/sh -c '
    cat /workspace/note.txt >/dev/null 2>&1 && echo ws_read || echo ws_unreadable
    if touch /workspace/evil 2>/dev/null; then echo ws_writable; else echo ws_denied; fi
  ')
  check "workspace readable"       ws_read      "$(echo "$ws_out" | sed -n 1p)"
  check "workspace write denied"   ws_denied    "$(echo "$ws_out" | sed -n 2p)"

  # Net profile: the network namespace is shared when explicitly requested
  # (route-table signal; DNS/internet independent).
  local net_out
  net_out=$(run_sandboxed --net /bin/sh -c '
    if grep -q "00000000" /proc/net/route 2>/dev/null; then echo net_ok; else echo net_blocked; fi
  ') || net_out=net_blocked
  check "network shared with --net" net_ok       "$net_out"

  # Informational egress probe (not a pass/fail check).
  local egress
  egress=$(run_sandboxed --net /bin/sh -c '
    curl -s -m 8 -o /dev/null "$SANDBOX_NET_PROBE" && echo reachable || echo unreachable
  ' 2>/dev/null) || egress=unreachable
  echo "  info  egress probe ($SANDBOX_NET_PROBE): $egress"

  # Pure-Landlock runner (B2 for Landlock stores). Present on NixOS after the
  # 2026-09-14 rebuild; skipped on hosts that do not ship it.
  if command -v landrun-sandbox >/dev/null 2>&1 && command -v landrun >/dev/null 2>&1; then
    # The boot service runs as root with no HOME, so the runner's default
    # scratch ($HOME/...) is unavailable; pass an explicit scratch dir
    # (WM_SANDBOX_RW) exactly as an operator would.
    local lr_scratch
    lr_scratch=$(mktemp -d)
    local lr_out
    lr_out=$(WM_SANDBOX_RW="$lr_scratch" landrun-sandbox --exec '{"schema":"wm-sandbox-exec-v1","program":"sh","args":["-c","echo lr_exec_ok; if touch /usr/lr-probe 2>/dev/null; then echo lr_write_leak; else echo lr_write_denied; fi; if touch \"$TMPDIR/lr-ok\" 2>/dev/null; then echo lr_scratch_ok; else echo lr_scratch_denied; fi"],"net":false}' 2>/dev/null) || lr_out=""
    rm -rf "$lr_scratch"
    check "landrun runner executes"   lr_exec_ok      "$(echo "$lr_out" | sed -n 1p)"
    check "landrun write /usr denied" lr_write_denied "$(echo "$lr_out" | sed -n 2p)"
    check "landrun scratch writable"  lr_scratch_ok   "$(echo "$lr_out" | sed -n 3p)"

    # Landlock × namespaces regression pair: under a real outer domain the
    # bwrap runner must fail (mounts are always denied) and the landrun
    # runner must still work (rulesets stack).
    local outer=()
    local outer_path
    for outer_path in /nix/store /run/current-system /usr; do
      [ -e "$outer_path" ] && outer+=( --rox "$outer_path" )
    done
    [ -e /etc ] && outer+=( --ro /etc )
    for outer_path in /dev/null /tmp; do
      [ -e "$outer_path" ] && outer+=( --rw "$outer_path" )
    done
    # The nested runner itself must be executable from inside the domain.
    local runner_bin
    runner_bin=$(command -v landrun-sandbox)
    [ -n "$runner_bin" ] && outer+=( --rox "$(dirname "$runner_bin")" )
    local nested_out
    nested_out=$(landrun "${outer[@]}" --env PATH -- landrun-sandbox \
      --exec '{"program":"sh","args":["-c","echo nested_ok"],"net":false}' 2>/dev/null) || nested_out=""
    check "landrun runner nests under Landlock" nested_ok "$(echo "$nested_out" | tail -1)"
    local bwrap_nested
    if landrun "${outer[@]}" -- bwrap --ro-bind /usr /usr --dev /dev -- /bin/true 2>/dev/null; then
      bwrap_nested="bwrap_worked"
    else
      bwrap_nested="bwrap_blocked"
    fi
    check "bwrap runner blocked under Landlock" bwrap_blocked "$bwrap_nested"
  else
    echo "  info  landrun runner not installed — skipping pure-Landlock checks"
  fi

  rm -rf "$workspace"
  if [ "$failures" -eq 0 ]; then
    echo "matrix green"
    return 0
  fi
  echo "matrix FAILED ($failures)"
  return 1
}

if [ "$#" -eq 0 ]; then
  selftest
else
  run_sandboxed "$@"
fi
