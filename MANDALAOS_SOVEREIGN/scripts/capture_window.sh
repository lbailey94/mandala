#!/usr/bin/env bash
# capture_window.sh — repeatable instrumented Tetragon observe window.
#
# One command: boot the sovereign VM headless, start Tetragon with the observe
# policy, run the Yama collector against the host gateway, fire the standard
# trigger set, tear everything down, and write a self-contained run report.
# Observe-only: no enforcement, no policy actions.
#
# Usage:
#   scripts/capture_window.sh                    # 15 min window, endpoint 18790
#   CAPTURE_SECONDS=1800 scripts/capture_window.sh
#   scripts/capture_window.sh --no-build         # reuse VM_PATH (required)
#
# Env:
#   CAPTURE_SECONDS     total window seconds (default 900)
#   CAPTURE_ENDPOINT    collector target (default http://127.0.0.1:18790)
#   CAPTURE_REPORT_ROOT report dir (default ~/.local/share/mandala-captures)
#   CAPTURE_RUN_DIR     explicit report dir (overrides root+timestamp)
#   VM_PATH             prebuilt VM runner path (skips the nix build)
#   TETRAGON_CACHE      tarball dir (default ~/.cache/mandalaos-s4/tetragon)
#
# Output: $RUN_DIR/{vm.log,collector.log,summary.json,summary.md,sent-log.jsonl}
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SECS="${CAPTURE_SECONDS:-900}"
ENDPOINT="${CAPTURE_ENDPOINT:-http://127.0.0.1:18790}"
ROOT="${CAPTURE_REPORT_ROOT:-$HOME/.local/share/mandala-captures}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${CAPTURE_RUN_DIR:-$ROOT/$STAMP}"
SSH_PORT="${SSH_PORT:-2222}"
KEY="$HOME/.ssh/id_mandala_vm"
KNOWN="$RUN_DIR/known_hosts"
TETRAGON_CACHE="${TETRAGON_CACHE:-$HOME/.cache/mandalaos-s4/tetragon}"
TARBALL="$TETRAGON_CACHE/tetragon-v1.7.1-amd64.tar.gz"
POLICY="$REPO/scripts/tetragon/observe-etc-shadow.yaml"
COLLECTOR="$REPO/scripts/yama-collector.py"
LAKSHMI_REPORT="$(dirname "$REPO")/LAKSHMI/bridge_report.py"
NO_BUILD=0
[[ "${1:-}" == "--no-build" ]] && NO_BUILD=1

mkdir -p "$RUN_DIR"
SSH="ssh -p $SSH_PORT -i $KEY -o UserKnownHostsFile=$KNOWN -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes mandala@127.0.0.1"
SSH_T="ssh -tt -p $SSH_PORT -i $KEY -o UserKnownHostsFile=$KNOWN -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes mandala@127.0.0.1"
SCP="scp -P $SSH_PORT -i $KEY -o UserKnownHostsFile=$KNOWN -o StrictHostKeyChecking=accept-new"
VM_PID=""
COLLECTOR_PID=""
STATUS="ok"

log() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }

cleanup() {
  set +e
  log "cleanup: stopping collector"
  if [[ -n "$COLLECTOR_PID" ]] && kill -0 "$COLLECTOR_PID" 2>/dev/null; then
    kill -TERM "$COLLECTOR_PID" 2>/dev/null
    sleep 3
  fi
  # Any ssh from this run (identified by its unique known_hosts path) goes too.
  for pid in $(pgrep -f "UserKnownHostsFile=$KNOWN" 2>/dev/null); do
    kill -TERM "$pid" 2>/dev/null
  done
  log "cleanup: stopping tetragon + guest"
  $SSH 'sudo /usr/local/bin/tetra tracingpolicy delete observe-etc-shadow >/dev/null 2>&1; sudo systemctl stop tetragon >/dev/null 2>&1; sudo poweroff >/dev/null 2>&1' >/dev/null 2>&1
  sleep 2
  if [[ -n "$VM_PID" ]] && kill -0 "$VM_PID" 2>/dev/null; then
    kill -TERM "$VM_PID" 2>/dev/null
    sleep 3
    kill -KILL "$VM_PID" 2>/dev/null
  fi
}
trap cleanup EXIT

# ── 1. VM image ────────────────────────────────────────────────────────
VM_LINK="${VM_LINK:-$HOME/.local/state/mandalaos/vm-image}"
if [[ -n "${VM_PATH:-}" ]]; then
  log "using VM_PATH=$VM_PATH"
elif [[ "$NO_BUILD" == "1" ]]; then
  log "ERROR: --no-build requires VM_PATH"
  exit 1
else
  log "resolving VM build (rooted at $VM_LINK so GC cannot evict it)"
  mkdir -p "$(dirname "$VM_LINK")"
  BUILD_START=$(date +%s)
  VM_PATH=$(nix build "$REPO#nixosConfigurations.mandala-vm.config.system.build.vm" \
    --out-link "$VM_LINK" --print-out-paths) || { log "ERROR: VM build failed"; exit 1; }
  log "VM build resolved in $(( $(date +%s) - BUILD_START ))s"
fi
[[ -x "$VM_PATH/bin/run-mandala-node-vm" ]] || { log "ERROR: $VM_PATH is not a VM runner"; exit 1; }

# ── 2. Boot the VM ─────────────────────────────────────────────────────
log "booting VM for ${SECS}s (log: $RUN_DIR/vm.log)"
QEMU_KERNEL_PARAMS="loglevel=4 systemd.show_status=true console=ttyS0,115200n8" \
QEMU_OPTS="-nographic" \
  setsid timeout -k 10 "$SECS" "$VM_PATH/bin/run-mandala-node-vm" \
  > "$RUN_DIR/vm.log" 2>&1 < /dev/null &
VM_PID=$!

log "waiting for guest ssh"
SSH_OK=0
for _ in $(seq 1 60); do
  if $SSH true 2>/dev/null; then SSH_OK=1; break; fi
  sleep 3
done
[[ "$SSH_OK" == "1" ]] || { STATUS="vm-ssh-timeout"; log "ERROR: guest ssh never came up"; exit 1; }
log "guest up: $($SSH 'uname -r; wm --version 2>/dev/null' 2>/dev/null | paste -sd' ' -)"

# ── 3. Tetragon + policy ───────────────────────────────────────────────
[[ -f "$TARBALL" ]] || { STATUS="tetragon-cache-missing"; log "ERROR: missing $TARBALL"; exit 1; }
log "installing tetragon in guest"
$SCP "$TARBALL" mandala@127.0.0.1:/tmp/ >/dev/null || { STATUS="tetragon-copy-failed"; exit 1; }
$SSH 'bash -s' <<'GUEST' || { STATUS="tetragon-install-failed"; log "ERROR: tetragon install failed"; exit 1; }
set -euo pipefail
sudo mkdir -p /usr/local/bin
cd /tmp && rm -rf tetragon-v1.7.1-amd64 && tar xzf tetragon-v1.7.1-amd64.tar.gz
sudo cp -R tetragon-v1.7.1-amd64/usr/local/* /usr/local/
sudo mkdir -p /usr/local/lib/tetragon
sudo systemd-run --unit=tetragon --collect /usr/local/bin/tetragon \
  --btf /sys/kernel/btf/vmlinux --bpf-lib /usr/local/lib/tetragon/bpf >/dev/null
sleep 4
systemctl is-active tetragon
GUEST
log "loading observe policy"
$SCP "$POLICY" mandala@127.0.0.1:/tmp/ >/dev/null || { STATUS="policy-copy-failed"; exit 1; }
$SSH 'sudo /usr/local/bin/tetra tracingpolicy add /tmp/observe-etc-shadow.yaml' >/dev/null \
  || { STATUS="policy-load-failed"; log "ERROR: policy load failed"; exit 1; }

# ── 4. Collector ───────────────────────────────────────────────────────
log "starting collector → $ENDPOINT"
$SSH_T 'stty -onlcr 2>/dev/null; sudo /usr/local/bin/tetra getevents -o json' \
  | python3 "$COLLECTOR" --endpoint "$ENDPOINT" --follow \
  > "$RUN_DIR/collector.log" 2>&1 &
COLLECTOR_PID=$!
sleep 8
if ! kill -0 "$COLLECTOR_PID" 2>/dev/null; then
  STATUS="collector-exited-early"
  log "ERROR: collector exited immediately (see $RUN_DIR/collector.log)"
  exit 1
fi

# ── 5. Standard trigger set ────────────────────────────────────────────
trigger() {
  local label="$1" cmd="$2"
  log "trigger: $label"
  $SSH "$cmd" >/dev/null 2>&1 || true
}
for offset in 25 150 275 400; do
  [[ $((offset + 45)) -gt "$SECS" ]] && break
  sleep $((offset - ${LAST:-0})).0
  case "$offset" in
    25)  trigger "denied-shadow-open" 'cat /etc/shadow >/dev/null 2>&1' ;;
    150) trigger "root-shadow-open" 'sudo cat /etc/shadow >/dev/null' ;;
    275) trigger "helper-shadow-open" 'sudo head -2 /etc/shadow >/dev/null' ;;
    400) trigger "benign-baseline" 'ls -la /etc | head -1' ;;
  esac
  LAST=$offset
done
log "triggers done; holding the window open for the tail observation"
sleep $(( SECS > 480 ? 90 : 20 ))

# ── 6. Stop + collect artifacts ────────────────────────────────────────
log "stopping collector (flush)"
kill -TERM "$COLLECTOR_PID" 2>/dev/null
sleep 4
SENT_RING="$HOME/.local/share/yama-collector/sent.jsonl"
[[ -f "$SENT_RING" ]] && cp "$SENT_RING" "$RUN_DIR/sent-log.jsonl"
cp "$RUN_DIR/collector.log" "$RUN_DIR/collector.log.snapshot" 2>/dev/null || true

log "stopping guest"
$SSH 'sudo /usr/local/bin/tetra tracingpolicy delete observe-etc-shadow >/dev/null 2>&1; sudo systemctl stop tetragon >/dev/null 2>&1; sudo poweroff' >/dev/null 2>&1
sleep 3
for _ in $(seq 1 10); do kill -0 "$VM_PID" 2>/dev/null || break; sleep 2; done
kill -0 "$VM_PID" 2>/dev/null && kill -KILL "$VM_PID" 2>/dev/null
VM_PID=""
COLLECTOR_PID=""
trap - EXIT

# ── 7. Summary ─────────────────────────────────────────────────────────
python3 - "$RUN_DIR" "$STATUS" "$SECS" "$ENDPOINT" "$VM_PATH" <<'PY'
import json, os, sys
run_dir, status, secs, endpoint, vm_path = sys.argv[1:6]
collector = []
log_path = os.path.join(run_dir, 'collector.log')
if os.path.exists(log_path):
    collector = [ln for ln in open(log_path, encoding='utf-8').read().splitlines() if ln.strip()]
final = None
for line in reversed(collector):
    try:
        obj = json.loads(line)
    except ValueError:
        continue
    if 'events' in obj:
        final = obj
        break
sent_path = os.path.join(run_dir, 'sent-log.jsonl')
sent_records = 0
if os.path.exists(sent_path):
    sent_records = sum(1 for ln in open(sent_path, encoding='utf-8') if ln.strip())
summary = {
    'run_dir': run_dir,
    'status': status,
    'window_seconds': int(secs),
    'endpoint': endpoint,
    'vm_path': vm_path,
    'collector_summary': final,
    'feed_ring_records_total': sent_records,
    'artifacts': {name: os.path.join(run_dir, name) for name in
                  ('vm.log', 'collector.log', 'sent-log.jsonl')},
}
json.dump(summary, open(os.path.join(run_dir, 'summary.json'), 'w', encoding='utf-8'),
          indent=2, sort_keys=True)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

if [[ -x "$LAKSHMI_REPORT" || -f "$LAKSHMI_REPORT" ]]; then
  log "bridge report → $RUN_DIR/bridge_report.json"
  python3 "$LAKSHMI_REPORT" --endpoint "$ENDPOINT" --hours 1 \
    --json "$RUN_DIR/bridge_report.json" > "$RUN_DIR/bridge_report.txt" 2>&1 || true
fi

log "capture complete: $RUN_DIR (status: $STATUS)"
