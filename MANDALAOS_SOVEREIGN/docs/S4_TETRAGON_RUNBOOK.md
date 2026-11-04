# S4 — Tetragon observe runbook (Yama v0 bridge, in-guest)

**Goal:** run the real eBPF capture leg — guest Tetragon events → host collector
→ WM observation records → Lakshmi `shadow.access.v1` decision records.

**Scope:** observe-only. No TracingPolicy action, no enforcement. Feasibility
PASS in-guest 2026-09-13 (0.03 % CPU / 66 MB; `CURRENT_REALITY` §4).

**Artifacts (this repo):**
- Policy: `scripts/tetragon/observe-etc-shadow.yaml`
- Collector: `scripts/yama-collector.py` (run on the host; spools when WM is down)

## 1. Boot the VM

```bash
systemctl --user start mandala-vm          # QEMU window; or:
VM_SECONDS=1800 scripts/run-vm-headless.sh # headless, serial log at /tmp
ssh -p 2222 -i ~/.ssh/id_mandala_vm mandala@127.0.0.1
```

## 2. Tetragon in the guest (v1.7.1, the feasibility-tested release)

The guest's default profile has no egress, so fetch on the host and copy in.
Cache once (the release ships per-asset `.sha256sum` files, not a combined
`checksums.txt`):

```bash
# host
mkdir -p ~/.cache/mandalaos-s4/tetragon && cd ~/.cache/mandalaos-s4/tetragon
curl -fsSLO https://github.com/cilium/tetragon/releases/download/v1.7.1/tetragon-v1.7.1-amd64.tar.gz
curl -fsSLO https://github.com/cilium/tetragon/releases/download/v1.7.1/tetragon-v1.7.1-amd64.tar.gz.sha256sum
sha256sum -c tetragon-v1.7.1-amd64.tar.gz.sha256sum   # must print OK
scp -P 2222 -i ~/.ssh/id_mandala_vm tetragon-v1.7.1-amd64.tar.gz \
    mandala@127.0.0.1:/tmp/
```

The tarball is a full install bundle (`tetragon-v1.7.1-amd64/` with
`usr/local/…`, the BPF objects, and `install.sh`). NixOS has no
`/usr/lib/systemd/system`, so `install.sh` aborts at the unit copy — install
manually and run under `systemd-run` with the bundle's `bpf-lib` (the default
`/var/lib/tetragon/` contains no BPF objects, and `/usr/local/bin` may not
exist yet):

```bash
# in-guest
cd /tmp && tar xzf tetragon-v1.7.1-amd64.tar.gz && cd tetragon-v1.7.1-amd64
sudo mkdir -p /usr/local/bin
sudo cp -R usr/local/* /usr/local/
sudo systemd-run --unit=tetragon --collect /usr/local/bin/tetragon \
  --btf /sys/kernel/btf/vmlinux --bpf-lib /usr/local/lib/tetragon/bpf
sleep 4 && systemctl is-active tetragon && sudo /usr/local/bin/tetra version
```

## 3. Load the observe policy

```bash
# from the host: copy the YAML in, then add it
scp -P 2222 -i ~/.ssh/id_mandala_vm scripts/tetragon/observe-etc-shadow.yaml \
    mandala@127.0.0.1:/tmp/
ssh -p 2222 -i ~/.ssh/id_mandala_vm mandala@127.0.0.1 \
    'sudo /usr/local/bin/tetra tracingpolicy add /tmp/observe-etc-shadow.yaml && \
     sudo /usr/local/bin/tetra tracingpolicy list'
```

## 4. Run the collector (host side)

```bash
# `tetra getevents` only streams to a pty-connected client (with a piped /
# closed stdin it exits without events); -tt + `stty -onlcr` keeps the JSON
# clean over ssh.
ssh -tt -p 2222 -i ~/.ssh/id_mandala_vm mandala@127.0.0.1 \
    'stty -onlcr 2>/dev/null; sudo /usr/local/bin/tetra getevents -o json' \
  | python3 scripts/yama-collector.py --endpoint http://127.0.0.1:18790 --follow
# streams a flush line to stderr every --flush-interval (default 5s) while the
# pipeline stays open; the summary line prints on exit (Ctrl-C/SIGTERM flushes
# buffered records first): {"events":N,...,"sent":k,"spooled":0}
# Sent records are also appended to the bounded feed ring (--sent-log, default
# ~/.local/share/yama-collector/sent.jsonl) that Lakshmi reads mirror-first.
```

## 5. Trigger + verify

```bash
# in-guest triggers (all generate security_file_open on /etc/shadow)
cat /etc/shadow                       # denied open attempt, logged
sudo cat /etc/shadow >/dev/null       # allowed root open
sudo head -2 /etc/shadow >/dev/null   # unix_chkpwd-style helper path
```

Verification chain (host):
1. Collector flush lines show `sent > 0` (final summary: `events > 0`, `sent > 0`).
2. The sent-log feed ring exists and carries the newest records
   (`~/.local/share/yama-collector/sent.jsonl`; bounded 1000).
3. `memory.search` in the `telemetry` galaxy returns
   `shadow.access.v1 | tetragon.shadow_access | observed`.
4. Within ≤2 sampler windows (1–2 min), Lakshmi writes the decision record
   `shadow.access.v1 | observing` (action `observe`).
5. Dashboard (`127.0.0.1:3109`) Policies panel shows `shadow.access.v1`
   leave `clear`.

## 6. Stop + record

```bash
# in-guest
sudo /usr/local/bin/tetra tracingpolicy delete observe-etc-shadow
sudo systemctl stop tetragon
sudo poweroff
# host: confirm the qemu wrapper exited (the headless timeout also reaps it)
pgrep -f "run-[m]andala-node-vm" || echo "VM down"
```

Record the run (collector summary, `tetra getevents` sample, decision record
id, `wm doctor` snapshot) in `MANDALA_OS/session-notes/` and update the bridge
design doc S4 row.

## 7. Routine captures (scripted)

For repeatable instrumented windows use `scripts/capture_window.sh`: it boots
the VM headless, installs + starts Tetragon, loads the observe policy, runs the
collector against the host gateway, fires the standard trigger set (denied /
root / helper shadow opens plus a benign read), then tears down and writes a
self-contained report to `~/.local/share/mandala-captures/<UTC>/` (`vm.log`,
`collector.log`, `sent-log.jsonl`, `summary.json`, and `bridge_report.json`
when LAKSHMI's `bridge_report.py` is present).

```bash
scripts/capture_window.sh                      # 15 min window (default)
CAPTURE_SECONDS=420 scripts/capture_window.sh  # short validation run
```

- `CAPTURE_ENDPOINT` (default `http://127.0.0.1:18790`), `CAPTURE_REPORT_ROOT`,
  `CAPTURE_RUN_DIR`, `VM_PATH` (skip the build), `TETRAGON_CACHE` are
  overridable; `--no-build` requires `VM_PATH`.
- The VM build is rooted at `~/.local/state/mandalaos/vm-image` (`--out-link`)
  so a store GC cannot evict it; the first run after a flake change rebuilds
  (~15 min cold), later runs resolve in seconds.
- The collector keeps using the shared sent-log feed ring, so the policy
  engine sees the capture like any other instrumented window.

## Notes

- The host gateway (18790) is writable; the VM's own MCP is read-only, so the
  collector always targets the host endpoint (or a scratch store for tests).
- Tetragon needs root + BTF (`/sys/kernel/btf/vmlinux`); the VM provides both.
- This bundle is the reference to install by hand on NixOS (no
  `/usr/lib/systemd/system`); pin `--bpf-lib /usr/local/lib/tetragon/bpf`
  explicitly or tetragon exits with "struct alignment checks failed".
- `tetra` requires a pty for `getevents`; with a closed/piped stdin it exits
  silently. Use `ssh -tt` + `stty -onlcr` (§4).
- Restarting the Lakshmi sampler resets its bridge `since` cursor to the first
  new window — trigger once after a restart if a transition is needed within
  that window. (The run path itself is restart-safe: an unreachable feed holds
  policy state, per the hysteresis contract.)
- If the download asset name differs, list the release assets and pick the
  matching `amd64` tarball; keep the checksum verification mandatory.
