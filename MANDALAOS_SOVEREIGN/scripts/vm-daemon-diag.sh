#!/usr/bin/env bash
# VM-only diagnosis for the whitemagic-daemon EROFS crash-loop.
# Shipped to /etc/mandala/daemon-diag.sh by vm.nix.
set -x

id
echo "HOME=$HOME"
ls -ld /home/mandala/.local/share/whitemagic /home/mandala/.cache

sudo systemctl stop whitemagic-daemon || true

echo "=== T1: full sandbox (reproduces unit settings) ==="
sudo systemd-run --wait --pipe --collect \
  -p User=mandala -p ProtectSystem=strict -p ProtectHome=read-only \
  -p ReadWritePaths=/home/mandala/.local/share/whitemagic \
  -p NoNewPrivileges=yes -p PrivateTmp=yes \
  -- /bin/sh -c 'timeout 6 wm daemon 2>&1 | head -6'

echo "=== T2: no ProtectHome ==="
sudo systemd-run --wait --pipe --collect \
  -p User=mandala -p ProtectSystem=strict \
  -p ReadWritePaths=/home/mandala/.local/share/whitemagic \
  -p NoNewPrivileges=yes -p PrivateTmp=yes \
  -- /bin/sh -c 'timeout 6 wm daemon 2>&1 | head -6'

echo "=== T3: strace inside sandbox ==="
sudo systemd-run --wait --pipe --collect \
  -p User=mandala -p ProtectSystem=strict -p ProtectHome=read-only \
  -p ReadWritePaths=/home/mandala/.local/share/whitemagic \
  -p NoNewPrivileges=yes \
  -- /bin/sh -c 'strace -f -e trace=openat -o /home/mandala/.local/share/whitemagic/trace.txt timeout 6 wm daemon >/dev/null 2>&1; grep EROFS /home/mandala/.local/share/whitemagic/trace.txt | head -6'

echo "=== T4: manual unsandboxed (initializes store if healthy) ==="
timeout 6 wm daemon 2>&1 | head -6

echo "=== doctor after ==="
wm doctor 2>&1 | tail -14

echo DIAG_SCRIPT_DONE
