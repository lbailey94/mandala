#!/usr/bin/env bash
# Headless VM smoke test for MandalaOS Sovereign.
#
# Boots the VM with a serial console, captures the in-guest evidence
# (sandbox matrix + WM daemon start), and stops after VM_SECONDS.
#
#   scripts/run-vm-headless.sh            # default 240s
#   VM_SECONDS=420 scripts/run-vm-headless.sh
#   VM_LOG=/tmp/my-boot.log scripts/run-vm-headless.sh
#
# Works with a real Nix install (/nix/store present) or with nix-portable
# (store under ~/.nix-portable, VM launched inside a bwrap namespace).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SECS="${VM_SECONDS:-240}"
LOG="${VM_LOG:-/tmp/mandala-vm-boot.log}"
NP="${NIX_PORTABLE:-/tmp/opencode/nixp/nix-portable}"
NP_STORE="${NP_STORE:-$HOME/.nix-portable/nix/store}"

cd "$REPO"

# Prefer a real Nix install; nix-portable is the no-root fallback.
if [ -x /nix/var/nix/profiles/default/bin/nix ]; then
  PATH="/nix/var/nix/profiles/default/bin:$PATH"
  export PATH
fi

if command -v nix >/dev/null 2>&1; then
  VM_PATH=$(nix build .#nixosConfigurations.mandala-vm.config.system.build.vm \
    --no-link --print-out-paths)
else
  VM_PATH=$("$NP" nix --extra-experimental-features 'nix-command flakes' build \
    .#nixosConfigurations.mandala-vm.config.system.build.vm \
    --no-link --print-out-paths)
fi

KERNEL_PARAMS="loglevel=4 systemd.show_status=true console=ttyS0,115200n8"
QEMU_PARAMS="-nographic"

echo "VM: $VM_PATH" >&2
echo "log: $LOG" >&2

run_direct() {
  QEMU_KERNEL_PARAMS="$KERNEL_PARAMS" QEMU_OPTS="$QEMU_PARAMS" \
    timeout -k 10 "$SECS" "$VM_PATH/bin/run-mandala-node-vm"
}

run_via_bwrap() {
  local rundir
  rundir=$(mktemp -d)
  trap 'rm -rf "$rundir"' RETURN
  QEMU_KERNEL_PARAMS="$KERNEL_PARAMS" QEMU_OPTS="$QEMU_PARAMS" \
    timeout -k 10 "$SECS" bwrap \
    --ro-bind "$NP_STORE" /nix/store \
    --ro-bind /sys /sys \
    --dev-bind /dev /dev \
    --proc /proc \
    --tmpfs /run \
    --ro-bind /usr /usr \
    --ro-bind-try /lib /lib \
    --ro-bind-try /lib64 /lib64 \
    --ro-bind-try /bin /bin \
    --bind "$rundir" "$rundir" \
    --share-net \
    --setenv HOME "$rundir" --setenv TMPDIR "$rundir" --setenv PATH /usr/bin:/bin \
    -- "$VM_PATH/bin/run-mandala-node-vm"
}

if [ -d /nix/store ]; then
  run_direct > "$LOG" 2>&1 || true
else
  run_via_bwrap > "$LOG" 2>&1 || true
fi

echo "--- evidence ---"
grep -aE "MandalaOS sandbox matrix|PASS|FAIL|matrix green|matrix FAILED|info  egress|Started WhiteMagic" "$LOG" || true
