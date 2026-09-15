# S4 — Tetragon observe run, live in the sovereign VM (2026-09-15)

**Result:** the Yama v0 bridge's real eBPF leg is proven end-to-end. Guest
kernel eBPF events → collector → WM observation records → sent-log feed →
Lakshmi step-0 transition → dashboard, all on the live fleet store (18790).

## What ran

| Step | Result |
|---|---|
| VM rebuild | `nix build .#nixosConfigurations.mandala-vm.config.system.build.vm` — 585 derivations, 1.7 GiB download, ~14 min; store had been GC'd |
| Boot | headless QEMU (host port 2222 → guest 22), kernel 6.18.50, `wm 9.1.5` in-guest, sudo NOPASSWD |
| Tetragon | v1.7.1 bundle installed by hand (NixOS has no `/usr/lib/systemd/system`); `systemd-run --unit=tetragon --collect … --bpf-lib /usr/local/lib/tetragon/bpf`; `active` |
| Policy | `observe-etc-shadow` added (generic_kprobe, monitor_only, enabled); NPOST 30 after triggers |
| Collector | `tetra getevents -o json` (pty, `ssh -tt` + `stty -onlcr`) → `yama-collector.py --follow --endpoint 18790`; final summary `{"events": 67, "sent": 3, "spooled": 0, "flushes": 3}` |
| Feed ring | `~/.local/share/yama-collector/sent.jsonl` written (new in this pass); first record evidence `binary=…/unix_chkpwd pid=1430` |
| Store | `memory.search` in the `telemetry` galaxy returns `shadow.access.v1 | tetragon.shadow_access | observed` |
| Policy | fleet sampler (restarted onto the new read path) transitioned `shadow.access.v1` → `observing`, value 5 (feed-summed), `source_available: true`, window `2026-09-15T15:51:19Z` |
| Dashboard | `/api/observations` source `{galaxy: 3, mirror: 3}` (merged), both transition records visible |
| Teardown | policy deleted, tetragon stopped, guest powered off; wrapper/qemu confirmed down; **edge soak sampler untouched (active)** |

## Corrections found by running it

1. **Runbook asset names** — the release has no `checksums.txt`; use
   `tetragon-v1.7.1-amd64.tar.gz.sha256sum`. The guest has no egress: fetch on
   the host, scp in. (Fixed in `docs/S4_TETRAGON_RUNBOOK.md`.)
2. **`install.sh` fails on NixOS** (no `/usr/lib/systemd/system`) — install
   manually and pass `--bpf-lib /usr/local/lib/tetragon/bpf`, else tetragon
   exits with `struct alignment checks failed`. (Fixed in the runbook.)
3. **`tetra getevents` needs a pty** — with piped/closed stdin it exits
   without streaming. `ssh -tt` + `stty -onlcr` works. (Fixed in the runbook.)
4. **`packages/whitemagic.nix` version was hardcoded `9.1.3`** — the VM
   closure was named `whitemagic-9.1.3.drv` while building the pinned v9.1.5
   source. Now derived from `Cargo.toml` (`workspace.package.version`); eval
   returns `9.1.5`, and the next rebuild picks up the correct name.

## Operational notes

- Restarting the Lakshmi sampler resets its bridge `since` cursor to the first
  new window; trigger once after a restart if a transition is needed that
  window.
- The fleet sampler now runs the mirror-first feed merge (`--bridge-feed`
  default read path); the edge soak sampler was not restarted.
- `pkill -f` footgun encountered twice during teardown: pattern self-match
  killed the driving shell. Use bracketed patterns (`run-[m]andala…)` or PIDs.

## S4 follow-ups (not blockers)

- Child-level runner denial parsing; egress/shadow-write/crypto-miner policies
  from the original three.
- `wm doctor` bridge-feed line (release-coupled).
- Collector as a systemd unit; Tetragon Nix packaging (designer-deferred).
- `unix_chkpwd` vs `cat` attribution (subject identity — Y1 contract §2).

## References

- `implementation/yama-v0-bridge-design.md` (S4 row now ✅; D6 read path)
- `design/ACTUATOR_CONTRACT_2026-09-15.md` (Y1: subject identity, router)
- Runbook: `MANDALAOS_SOVEREIGN/docs/S4_TETRAGON_RUNBOOK.md`
- Session: WM session `a7923857-241a-4664-8e66-95a7ede410e6`
