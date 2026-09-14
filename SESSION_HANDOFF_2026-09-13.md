# Session Handoff — 2026-09-13

**Thread:** MandalaOS Sovereign Edition — VM dogfooding, WM governance fixes, telemetry design
**Author:** opencode session `9a12e61d` (host) + VM session `32ff3e1a`
**Audience:** next session / another agent / Lucas
**Read first:** `MANDALA_OS/PLATFORM_DIRECTION_2026-09-12.md` (why the project is shaped this way), then this doc.

---

## 0. TL;DR

The Sovereign VM now boots, is SSH-able, runs the WM daemon **confined and alive**,
serves governance telemetry to the host, and its governance substrate gained two
real capabilities today (daemon Landlock, dharma decision counters). The next
major workstreams are: **B2 sandbox tool-runner**, **host release deployment of
B1/B3**, and the newly-designed **telemetry "edge galaxy"** (detailed in §5).

Everything below is verified unless labeled planned.

---

## 1. State of the world

### Host (Zorin OS 18.1, kernel 7.0.0-31, Secure Boot off)
- **Nix (real, Determinate 3.22.3 / Nix 2.35.2) installed 2026-09-13.** Binary at
  `/nix/var/nix/profiles/default/bin/nix`. The nix-portable era is over; its
  store was reclaimed (42G free on `/`).
- WMv9 dev checkout: `/home/lucas/Desktop/WHITEMAGIC/WMv9`, branch `fix/ci-green`,
  **14 commits ahead of origin/main** (concurrent session active — see §6 cautions).
- Host fleet still runs **v9.1.3** from `~/.local/bin/wm`; B1/B3 are NOT deployed
  to the host yet (release-cycle task, §4-C).

### Repos (all pushed)
| Repo | Branch | Head | Notes |
|---|---|---|---|
| `lbailey94/mandalaos-sovereign` (private) | `main` | `61bf2c0` | flake + modules + docs + scripts |
| `lbailey94/lakshmi` (private) | `main` | `1cb4c91` | 7-dim vector digestor, 19 tests |
| `lbailey94/whitemagic` | `fix/ci-green` | `7eabaec` (B1+B3 = `59dfbfc`) | daemon Landlock + dharma counters |

### VM (MandalaOS Sovereign, NixOS 26.05)
- **Persistent user unit:** `~/.config/systemd/user/mandala-vm.service` →
  `/nix/store/l7fhv994p06g6qahbvrqakskpv9hafwb-nixos-vm/bin/run-mandala-node-vm`
  (rebuilds change this path; update the unit when you rebuild).
- **State:** currently **stopped** (graceful ACPI poweroff); disk persists at
  `~/vms/mandala.qcow2` (8G sparse, ~62MB actual).
- **Access:** QEMU window on the desktop (X11, `DISPLAY=:1`), console autologin as
  `mandala`, and SSH on host port **2222** with dedicated passphrase-less key
  `~/.ssh/id_mandala_vm` (also `lucas@whitemagic` key is authorized).
- **Ports:** host `28795 → guest 18795` (WM MCP, read-only, in-guest unit
  `wm-mcp-readonly`, **full profile**).
- **Embedder bridge:** guest WM uses the host llama.cpp embedder via slirp alias
  `http://10.0.2.2:18899/v1/embeddings` (bge-small, dim 384) — hybrid recall
  verified 50–70ms in-guest.
- **VM-only conveniences** (in `vm.nix`, never on bare metal): autologin,
  passwordless sudo, strace, `~/.ssh/id_mandala_vm` authorized, port forwards.
- **In-guest services:** `whitemagic-daemon` (active), `wm-mcp-readonly` (active),
  `sshd` (active); boot-time sandbox self-test `mandala-sandbox-selftest` prints
  the 8/8 matrix to the serial console.

---

## 2. Verified today (evidence)

1. **VM boot + containment:** NixOS 26.05 boots to login; matrix 8/8 PASS in-guest
   (`/etc/mandala/verify-sandbox.sh`); WM daemon active after fixing a crash-loop
   (see §6-2).
2. **B1 — daemon Landlock (`59dfbfc`):** `wm daemon` applies Landlock v0 at init
   when `WM_LANDLOCK=1`, persists `~/.local/share/whitemagic/landlock_state.json`,
   exposes the report to the server. In-VM outcome: `partial` (VM kernel 6.18,
   ABI v8 — honest downgrade); host kernel reports `enforced` at ABI v8.
3. **B3 — dharma counters (`59dfbfc`):** process-global
   `observe/advise/correct/intervene/panic` counters + `total/blocked/blocked_ratio`;
   `dharma.status` now returns a `decisions` block. Unit-tested, clippy clean.
4. **Lakshmi dims 6+7 live:** `--dharma-mcp http://127.0.0.1:28795` produced
   baseline 0.70 → `1.00 (blocked 0/3)` → `1.00 (0/1)`; karma seam reads host
   ledger (`total_debt` 116.3 at check time).
5. **Dogfood lock-in:** session started/recorded/read back *inside the VM* over
   SSH (`32ff3e1a`) while the daemon ran; daemon journal shows live citta
   cycles, gardens, dreams, gan_ying recall through the host embedder.
6. **Disk pass:** 12G → 42G free; 30G regenerable build artifacts, 11G backups
   checksum-verified to SD, caches pruned, portable store reclaimed.

---

## 3. Command crib

```bash
# Real Nix (add to PATH if needed)
export PATH=/nix/var/nix/profiles/default/bin:$PATH

# --- VM lifecycle ---
systemctl --user start mandala-vm        # boot (QEMU window on desktop)
systemctl --user stop  mandala-vm        # stop (prefer poweroff from guest)
systemctl --user status mandala-vm

# Graceful guest shutdown (cleaner than SIGTERM to QEMU)
ssh -p 2222 -i ~/.ssh/id_mandala_vm -o IdentitiesOnly=yes mandala@127.0.0.1 'sudo poweroff'

# --- In-guest (SSH or the QEMU console; autologin) ---
journalctl -u whitemagic-daemon -f       # live citta/dream/garden cycles
wm doctor                                # landlock (partial in VM), recall route
cat ~/.local/share/whitemagic/landlock_state.json
/etc/mandala/verify-sandbox.sh           # 8/8 containment matrix
wm session record --role user --turn-type question --content "..."
wm session continuity

# --- Host-side telemetry ---
python3 ~/Desktop/projects/LAKSHMI/lakshmi.py --once --dharma-mcp http://127.0.0.1:28795
curl -s -X POST http://127.0.0.1:28795/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"dharma.status","arguments":{}}}'

# --- Build the VM with a local WM tree (clean worktree pattern) ---
git -C ~/Desktop/WHITEMAGIC/WMv9 worktree add /tmp/wm-next <commit>
cd ~/Desktop/projects/MANDALAOS_SOVEREIGN
nix build .#nixosConfigurations.mandala-vm.config.system.build.vm \
  --override-input whitemagic-src path:/tmp/wm-next \
  --out-link /tmp/mandala-vm-next
# then update ExecStart in ~/.config/systemd/user/mandala-vm.service

# --- Headless boot + evidence capture (no GUI needed) ---
VM_SECONDS=150 ~/Desktop/projects/MANDALAOS_SOVEREIGN/scripts/run-vm-headless.sh
```

---

## 4. Open workstreams (prioritized)

### A. WM: B2 — sandbox runner for subprocess-spawning tools  *(next session, first)*
**Why:** today `mandala-sandbox` (bwrap) confines external tools only when a human
invokes it; tools that spawn subprocesses are not routed through it. This is the
last big consolidation before the OS sandbox is part of the agent loop.

**Where:** `crates/wm-dispatch/src/sandbox_exec.rs` handles `Sandbox::StoreScoped`
(per-tool Landlock on a scoped thread). Extend with an OS-runner path:
- Detect runner (`WM_SANDBOX_RUNNER` env or `mandala-sandbox` on PATH).
- For tools declaring a new `Sandbox::Subprocess` (or spawning `Resource::Process`),
  wrap the executed command with the runner; pass through a JSON args envelope.
- **Loud-degrade** like Landlock v0/v1: if runner unavailable, run unconfined with
  a WARN and a counter (never silent).
- Tests: fake spawn tool; assert wrap/args/env; degrade path; counter increments.

**Acceptance:** a tool that shells out runs contained in the VM; `wm doctor` (or a
status field) discloses runner + coverage; no behavior change when disabled.

### B. WM: daemon-hosted MCP / lock arbitration  *(design — decided 2026-09-13)*
**Finding:** a writable `wm serve` cannot coexist with `wm daemon` on one store —
Tantivy `IndexWriter` lock (`LockBusy`); error text suggests `--readonly`.
**Decision:** **Option 3 is the supported mode** (read-only split + documented
turn-taking), **Option 1 (daemon hosts MCP) is the intended next
architecture**, **Option 2 (serve queues writes to daemon) rejected**.
Written up with code-grounded evidence in
`WHITEMAGIC/WMv9/docs/DAEMON_SERVE_COEXISTENCE.md` (invariant, mode table,
readonly-is-a-snapshot caveat, Option 1 acceptance criteria, deployment map).

### C. WM: host fleet deployment of B1/B3  *(release cycle)*
The host fleet (`~/.local/bin/wm`, v9.1.3) lacks the daemon Landlock and the
`decisions` block. Deploy via the normal release flow (tag → CI → binaries →
unit restarts) after the concurrent session's work lands. Then point Lakshmi's
`--dharma-mcp` at the host MCP (18790) instead of the VM forward. Note:
B2 + the `telemetry` galaxy are also uncommitted in the WMv9 tree and ride
the same release.

### D. Telemetry / edge galaxy  *(first slice LIVE 2026-09-13)*
`Galaxy::Telemetry` shipped (excluded from `memory_galaxies`, dream,
lifecycle), `os_telemetry_threshold` bus event added, Lakshmi `--emit` with
bounded spool replay, docs at `WHITEMAGIC/WMv9/docs/EDGE_GALAXY_TELEMETRY.md`.
Live evidence: window landed (`memory.search galaxy=telemetry` → fts hit),
WM-down drill spooled 2 and replayed 3 on recovery (spool 0 bytes), bus event
returned by `bus.recent category=harmony`. Follow-ons: dashboard (§4-E),
`telemetry.record`/`sensor.push`, retention policy wiring, host deploy (§4-C).

### E. Lakshmi: dashboard + full-surface view  *(sprint Week 1 milestone)*
Tauri/Svelte 7-bar UI consuming `lakshmi.py --json`; add karma/dharma sparklines
once the edge galaxy (§5) provides history. Keep `--once` output stable for
scripts.

### F. WM polish
- `wm doctor` treats Landlock `partial` as WARN → exit 1. Decide WARN vs INFO
  (partial is expected on older ABIs).
- VM-only `Logrotate configuration check` unit fails (upstream VM quirk; verify
  on real hardware before chasing).
- Landlock ABI wording in docs: `landlock_sandbox.rs` ladder goes to V9; VM/kernel
  differences are normal.

### G. OS: bare-metal path  *(the old "select it on boot" goal)*
- Disk gate: ≥60G free (42G now) **or** a spare SD/USB/SSD (the archive SD_CARD1
  must NOT be repartitioned — exfat, cannot shrink, sole-copy archives).
- Install flow + boot selection: `docs/INSTALL_AND_BOOT.md` (systemd-boot menu,
  4-generation limit, Zorin chainload entry).
- Optional: `landrun` as a second sandbox layer; ARM board support
  (`nixos-hardware`); `offline-mesh.nix` / `local-ai.nix` modules (parked, §4-of
  platform-direction doc).

---

## 5. Telemetry / edge galaxy — design spec (new)

**Goal:** make OS telemetry durable, time-queryable, and legible to both low-layer
systems and AI — without flooding memory or polluting cognition.

**Insight:** WM already ships the pieces — `Sensor → SensorReading →
SensorimotorBus` (`wm-substrate/sensorimotor.rs`), `bus.emit/recent/stats`, the
galaxy lifecycle (`galaxy.taxonomy/stats/health/cold_rotate/purge/snapshot`), and
`harmony.history` (in-memory `VecDeque` ring). What's missing is the **durable
layer** and the schemas/cadence that keep it sane.

### Layering

| Layer | Stock | Edge-galaxy addition |
|---|---|---|
| Real-time | `bus.emit/recent/stats` | threshold + state-change events (`os.telemetry.*`) |
| Recent | `VecDeque` rings (volatile) | — (raw samples never leave the ring) |
| Durable | — | `telemetry` galaxy: 1-min windows + rollups, tagged, queryable |
| Retention | galaxy `cold_rotate`/`purge` | policy: ring 5 min / windows 7 d / hourly 90 d |
| Actuation | actuator trait | Tiferet ladder steps as actuators (future) |
| Consumers | `harmony.history`, `dharma.status`, `karma.report` | low-layer via MCP; AI reads bus + galaxy together |

### Window record schema (1-min rollup, written to the `telemetry` galaxy)

```json
{
  "kind": "telemetry.window",
  "ts": "2026-09-13T19:23:00Z",
  "window_seconds": 60,
  "source": "laksmi",
  "tags": ["telemetry", "edge", "laksmi", "window"],
  "harmony_score": 0.66,
  "dims": {"fairness": 0.21, "responsiveness": 0.72, "throughput": 0.74,
           "stability": 0.98, "energy": 0.78, "dharma": 1.0, "karma_debt": 0.23},
  "guna": {"sattvic": 15, "rajasic": 3, "tamasic": 48},
  "top": [{"comm": "llama-server", "share": 0.15, "guna": "rajasic"}],
  "events": ["dharma:blocked 0/1", "energy:over_budget 18.3W>15W"],
  "karma": {"total": 116.3, "delta": -0.0},
  "dharma": {"total": 10, "blocked": 0, "delta_total": 1, "delta_blocked": 0}
}
```

**Bus events (ephemeral, low-latency):** emit only on change/threshold crossing —
`responsiveness < 0.3`, `stability < 0.8`, `energy` over budget, `dharma.blocked
delta > 0`, sandbox denial, service transitions. Payload:
`{"topic": "os.telemetry.responsiveness", "value": 0.28, "threshold": 0.3, "window": "60s"}`.

### Rules (the ones that keep this from rotting)
1. **No raw samples in memory.** Raw → ring; windows → galaxy; aggregates →
   longer TTL. (5s cadence = ~17k entries/day otherwise.)
2. **Evidence, not cognition.** Dedicated galaxy + `source=laksmi` trust label;
   exclude/short-retain telemetry in dream/consolidate cycles; keep it out of
   default agent recall (filter by galaxy/tags).
3. **Append-only + attribution.** Write-audit or hash-chain the telemetry stream
   (karma-ledger precedent); version any policy/threshold change so effects are
   attributable. Anti-Maya is a telemetry property.
4. **Fail-soft.** If WM is down, telemetry spools locally (ring file) and replays;
   OS safety never depends on WM being up.
5. **No closed loop without hysteresis.** If telemetry later drives actuation
   (Tiferet), every step needs observe-mode, hysteresis, rollback, and disclosed
   policy ids.

### First slice (small, end-to-end — **LIVE 2026-09-13**)
1. ✅ `lakshmi.py --emit --emit-every 60`: window record → `memory.create`
   (galaxy `telemetry`); raw stays in the producer ring, windows spool to a
   bounded local ring file before send (fail-soft rule 4).
2. ✅ Verify: `memory.search {query: "laksmi responsiveness", galaxy:
   "telemetry"}` returns the window (fts lane; telemetry is excluded from
   default recall by design).
3. ✅ `bus.emit` threshold events: new `os_telemetry_threshold` EventType
   (Harmony category) with `{topic, value, threshold, window, state}`;
   live-verified round-trip via `bus.recent category=harmony`.
4. ◐ WM additions: `Galaxy::Telemetry` shipped; `telemetry.record` /
   `sensor.push` and `harmony.history` galaxy fallback still deferred.
5. ✅ Docs: `WHITEMAGIC/WMv9/docs/EDGE_GALAXY_TELEMETRY.md` (schema, spool,
   bus, retention current+planned, consumer examples, verification).

---

## 6. Pitfalls and lessons (hard-won today)

1. **qemu-vm options live in `virtualisation.vmVariant`** (26.05). `memorySize`,
   `cores`, `graphics`, `forwardPorts` are invisible in the main config —
   set them in the variant or they fail eval.
2. **systemd-tmpfiles `d` does not create intermediate parents.** List every
   level; `ReadWritePaths` targets must exist or carry a `-` prefix, else
   systemd fails with status `226/NAMESPACE`. (This caused the daemon crash-loop.)
3. **Unit PATH is minimal.** Declare `path = [ ... ]` at the *service* level, not
   inside `serviceConfig`; scripts also hit `HOME` unbound under `set -u`.
4. **Bubblewrap:** `--unshare-all` includes net (`--share-net` to re-enable);
   resolved hosts need `/run/systemd/resolve` bound; Ubuntu-family needs
   `/lib64`; use the same profile mirror in `verify-sandbox.sh`.
5. **Durable background processes:** launch with `systemd-run --user` (a plain
   `setsid nohup` from an agent shell gets reaped), and prefer
   `systemctl --user poweroff`-style clean guest shutdown before stopping the VM.
6. **Flakes see only git-tracked files** — stage new files (`git add vm.nix`)
   before `nix build`, or eval fails "path does not exist".
7. **Concurrent sessions on WMv9:** commit only the files you touched; for Nix
   builds use `git worktree add /tmp/x <your-commit>` + `--override-input` so
   uncommitted work from others is excluded.
8. **Trust:** Determinate Nix trusts only root for unsigned paths — `nix copy
   --no-check-sigs` into the daemon store requires sudo. nix-portable's store had
   root-owned immutable dirs (reclaim needed `sudo chattr -i` then `rm`).
9. **Ports:** the host fleet owns 18789–18797 — the VM MCP forward uses 28795.
10. **Profiles:** `dharma.status` is not in `curated` — the VM serve uses `full`.
11. **Tantivy lock:** daemon + writable serve cannot share one store (§4-B).
12. **Landlock ABIs differ by kernel:** host 7.0 → `enforced`; VM 6.18 → `partial`.
    Both are correct and disclosed.

---

## 7. File map

| Path | What |
|---|---|
| `MANDALA_OS/PLATFORM_DIRECTION_2026-09-12.md` | three-form strategy, threat model, corrections |
| `MANDALA_OS/SANDBOX_LAYERS_2026-09-12.md` | containment map + live evidence |
| `projects/MANDALAOS_SOVEREIGN/` | the OS: `flake.nix`, `configuration.nix`, `vm.nix`, `modules/*`, `packages/whitemagic.nix`, `docs/INSTALL_AND_BOOT.md`, `GETTING_STARTED.md`, `scripts/*` |
| `projects/LAKSHMI/` | `lakshmi.py`, `test_lakshmi.py`, README |
| `WHITEMAGIC/WMv9/crates/wm-governance/src/dharma_gate.rs` | verdict counters (B3) |
| `WHITEMAGIC/WMv9/crates/wm-mcp/src/bin/wm.rs` | daemon Landlock wiring (B1) |
| `WHITEMAGIC/WMv9/crates/wm-tools/src/lib.rs` | `dharma.status` decisions block |
| `WHITEMAGIC/WMv9/crates/wm-mcp/src/landlock_sandbox.rs` | v0 ruleset, reports, ABI ladder |
| `WHITEMAGIC/WMv9/crates/wm-dispatch/src/sandbox_exec.rs` | per-tool Landlock path (B2 target) |
| `~/.config/systemd/user/mandala-vm.service` | host-side VM unit |
| `~/vms/mandala.qcow2` | persistent VM disk |
| `~/.ssh/id_mandala_vm(.pub)` | dedicated VM key |

---

## 8. Continuity

- Host WM session `9a12e61d` contains the day's turns: reconciliation, sandbox
  evidence, Lakshmi v0, VM boot, VM fixes, GUI/dogfood infra, B1+B3, portable
  reclaim.
- VM WM session `32ff3e1a` contains the first in-guest dogfood turn.
- Next session: **read this doc, run `session.continuity`, then start with §4-A
  (B2 sandbox runner)**; the edge galaxy (§5) is the natural follow-on, and §4-C
  (host deploy) can happen whenever the release window opens.

---

## 9. B2 close-out — sandbox runner wired (2026-09-13, later session)

**Status: implemented, host-verified, VM-verified; committed + pushed** to
`origin/fix/ci-green` (WMv9 shas `51b0635`, `0e69a7d`, `abf6171`, `c2d837c`,
tip `c2d837c`; §11). The **OS-side companion changes are still uncommitted**
in `MANDALAOS_SOVEREIGN` (`modules/landlock-isolation.nix`,
`scripts/verify-sandbox.sh`) — that is Mandala OS scope, commit with the
other OS work.

### What shipped

- **wm-core** `sandbox.rs`: `Sandbox::Subprocess` variant + `SpawnPolicy`
  (runner resolution: `WM_SANDBOX_RUNNER` → PATH `mandala-sandbox`; explicit
  off tokens `""/0/false/off/none`), JSON envelope `wm-sandbox-exec-v1`
  (`program`, `args`, `net`), `Context::spawn` (default inert). `net_grant()`
  derives the network profile from `Resource::Network` in the effect row.
- **wm-dispatch** `subprocess_sandbox.rs` + pipeline step 4e: declared tools get
  the policy injected pre-call; active runner ⇒ response gains
  `"sandbox": {"runner","net","envelope"}`; missing runner ⇒ WARN (once per
  tool) + `degraded` counter, **no false confinement claim**; tools declaring
  raw `spawns` without the contract increment `unconfined_spawns` (roll-out
  signal). `/status` gained `subprocess_sandbox` + `landlock_v1` counter blocks.
- **wm-tools** `oss_bounty.rs`: both tools marked `Subprocess`; every `gh`
  spawn builds through `ctx.spawn` (same `timeout 30 gh` fallback shape).
- **wm-mcp** doctor §11d-2: live runner detection (`wm doctor`); server startup
  logs runner/source or the explicit no-runner state.
- **OS** `mandala-sandbox --exec '<json>'` envelope mode (jq-parsed, no shell
  interpolation, legacy `--net` path untouched); `WM_SANDBOXED=1` marker;
  explicit `WM_SANDBOX_RUNNER` per service + global shell env; ro-bind
  `/run/current-system`; matrix script mirrored.

### Evidence

- Host E2E (scratch store, fake runner): `oss.bounty.status` envelope
  `program=timeout args=[30,gh,--version] net=false`; `oss.bounty.scan`
  `net=true`; disclosure on response; `/status` `dispatches:2 degraded:0`.
  Runner-less server: tool ran, no disclosure, `degraded:1` +
  `WARN wm_dispatch::subprocess_sandbox` with `RUST_LOG=warn`.
  Doctor printed OK/INFO for runner present/absent.
- VM (rebuilt via `--override-input whitemagic-src path:/tmp/wm-next-plain`):
  envelope containment check → `sandboxed=1`, `WRITE_DENIED`, `NET_ISOLATED`;
  `oss.bounty.status` over 28795 disclosed the real
  `/nix/store/...-mandala-sandbox` runner, `net:false`; `/status` `source:env,
  dispatches:1, degraded:0`; probe-runner log captured the live envelope
  `{"args":["30","gh","--version"],...}` and delegated to the real runner.
- Suites: wm-core 170, wm-dispatch 170, wm-tools 814 green; clippy
  `--all-targets` clean on all four touched crates.

### New pitfalls (learned live)

1. **systemd services don't inherit `environment.variables` and have a
   minimal PATH** — runner discovery must be set explicitly per unit
   (this produced an honest loud-degrade in-guest before the fix).
2. **NixOS name-based exec inside bwrap requires `/run/current-system`** —
   the matrix passed only because it uses absolute `/bin/sh`; a PATH-resolved
   `sh` fails with `bwrap: execvp sh: No such file or directory`.
3. `RUST_LOG` unset ⇒ EnvFilter drops WARN in CLI servers; set
   `RUST_LOG=warn` when proving loud-degrade live.
4. gh-via-hosts.yml auth does not survive the default sandbox (no `$HOME`
   bind); token env (`GH_TOKEN`) does. `oss.bounty.*` in a runner-present
   environment may therefore report `gh_available:false` until a credential
   ro-bind or token is provided — documented, not silent.

### Remaining after B2

- §4-B daemon-MCP/lock design, §4-D edge galaxy, §4-C host fleet deploy
  (B1/B3 + this B2 need a release), §4-E dashboard, §4-F doctor polish.
- Optional: migrate other spawn tools (session/geneseed/coordination git) to
  the contract — they show up in `unconfined_spawns` when dispatched.
- VM unit now points at the B2 closure
  (`/nix/store/q6mss54wl6pklkyvmacfrn9xv91jz3yn-run-nixos-vm`); the previous
  path is the one in §1.

---

## 10. 4B + 4D close-out — daemon/serve decision + edge galaxy live (2026-09-13, later session)

**Status:** both done; WMv9 slices committed + pushed to
`origin/fix/ci-green` (see §11). Concurrent-session work in the same tree
remains WIP (see caution there).

### 4B — daemon × serve coexistence (decision)

- Deliverable: `WHITEMAGIC/WMv9/docs/DAEMON_SERVE_COEXISTENCE.md`.
- Invariant documented with code refs: one Tantivy writer
  (`wm-memory/src/search.rs:409`), read-only opens create none (`:431`);
  LMDB is not the constraint; `store_busy` is advisory only.
- Decision: **Option 3 supported now** (readonly split + explicit
  turn-taking), **Option 1 intended next** (daemon hosts MCP; needs a shared
  `Arc<Mutex<McpServer>>`-style refactor of the `&mut self` transport loops +
  cycle scheduler, watchdog-aware), **Option 2 rejected** (duplicates
  Option 1's transport plus a new protocol).
- Read-only serves are **snapshots** (no `reload()`): restart after a write
  window. Documented as a rule, not a footnote.

### 4D — edge galaxy first slice (live)

- `Galaxy::Telemetry` added (`wm-core/galaxy.rs`): Memory galaxy excluded
  from `memory_galaxies()` (default recall/list/reindex/embeddings), dream
  scan/cycles, and lifecycle consolidation. `parse_galaxy`, legacy migrate
  mapping, `galaxy.taxonomy` (16 total / 11 memory) updated; parity test
  fixes in `wm-tools/expansion/galaxy.rs` and `event_type.rs`.
- New EventType `OsTelemetryThreshold` (Harmony category, Sensory
  nervous-system mapping; taxonomy 234 → 235).
- Lakshmi `--emit/--emit-url/--emit-galaxy/--emit-every/--emit-spool/
  --emit-no-thresholds`: window record per §5 schema (+`dim_notes` honesty),
  change-based threshold events, bounded spool written before send and
  replayed oldest-first on recovery. 25 unit tests green.
- Docs: `WHITEMAGIC/WMv9/docs/EDGE_GALAXY_TELEMETRY.md`.

### Evidence

- Window live: `emit: 1 window(s) → telemetry (spool 0)`;
  `memory.search {query:"laksmi responsiveness", galaxy:"telemetry"}` →
  count 1, `recall_mode: fts`.
- Fail-soft drill: WM stopped → 2 windows spooled ("Connection refused"
  disclosed); WM up → `emit: 3 window(s) → telemetry (spool 0)`; galaxy count
  4; spool file 0 bytes.
- Bus: `bus.emit os_telemetry_threshold` accepted; `bus.recent
  {category:"harmony"}` returned the event with payload intact.
- Suites in the verification worktree: wm-core 170, wm-dispatch 171,
  wm-memory 511, wm-cognitive 714, wm-tools 814 — all green; clippy
  `--all-targets` shows only two pre-existing warnings from the concurrent
  session's in-flight files.

### New pitfalls (learned live)

1. **Spool must be re-saved after a successful flush** — the first cut saved
   only pre-flush, so sent windows would replay on the next load (caught in
   live E2E, fixed).
2. **Never threshold on proxy values**: RAPL-unreadable energy is a neutral
   0.5 with `source="energy"`; the crossing check now requires a real source
   (`rapl`/`battery`), else an "unavailable" proxy would fire every window.
3. **Concurrent WMv9 sessions collided in-tree**: another session's mid-edit
   (`wm-tools/src/lib.rs`, `write_gate.rs`) broke workspace checks. Recovery
   per §6-7: `git worktree add /tmp/wm-eg 7eabaec`, copy only your changed
   files, verify there, copy back only your hunks. Do not `cargo check
   --workspace` while another session is typing.

### Remaining after 4B/4D

- §4-C host deploy (release) — B2 + telemetry galaxy + the concurrent
  session's work all ride it.
- §4-E dashboard: 7-bar UI + karma/dharma sparklines from the galaxy.
- Edge galaxy follow-ons: `telemetry.record` / `sensor.push`, retention
  policy wiring, hourly rollups, `harmony.history` galaxy fallback.
- Optional: migrate other spawn tools to `Sandbox::Subprocess`.

### Commit caution (mixed tree)

**Resolved for our slices 2026-09-13**: the concurrent session's sweeps had
grabbed `wm.rs` (doctor block) and `common.rs` (telemetry parse) mid-flight,
leaving the tree referencing uncommitted neighbours; the four integration
commits (§11) restored a green tip and pushed. Still true going forward:
the concurrent session continues to work in this tree, so stage your own
hunks (`git add -p` / clean worktree), never `git add -A`, and re-check
`git rev-parse fix/ci-green` before moving refs.

---

## 11. Whitemagic integration + push (2026-09-13, integration session)

**Outcome:** our B2 + edge-galaxy slices are committed and pushed.
`origin/fix/ci-green` moved `59dfbfc..c2d837c`; the branch is now **37
commits ahead of origin/main** (pre-push public-surface guard: clean).

### Audit of the branch before integration

The 31 local commits (origin/main..HEAD) were audited: PLAN_F governance
work, B1/B3, capability gate, CLI first-run bundle (setup/status/update/
selftest), lossless session replay, contract suite + schema ratchet, signed
release manifest + update key wiring, trust/ops scripts, eval matrix, disk
hygiene. 10 new files, no credential/secret-shaped paths, no large binaries.

### Incident found during audit (and repaired)

The concurrent session's clippy sweeps had partially committed our
in-flight sources: `crates/wm-mcp/src/bin/wm.rs` (doctor block, commit
`9130fee`) and `crates/wm-tools/src/expansion/common.rs` (telemetry parse +
`galaxy_name` delegation, commit `62b1337`). That left **HEAD transiently
non-compiling** — `common.rs` referenced `Galaxy::Telemetry` and `wm.rs`
referenced `wm_core::sandbox::detect_runner()` while the defining sources
were still uncommitted. Repair = commit `51b0635` (sandbox module +
telemetry galaxy variant + consistency index + taxonomy test counts).

### Integration commits (pushed)

| Sha | Slice |
|---|---|
| `51b0635` | `fix(core)`: restore green — sandbox module + telemetry galaxy sources |
| `0e69a7d` | `feat(...)`: B2 subprocess sandbox runner (policy, envelope, disclosure, counters) |
| `abf6171` | `feat(...)`: edge-galaxy policy — dream/lifecycle exclusions, `os_telemetry_threshold`, migrate mapping |
| `c2d837c` | `docs`: daemon/serve coexistence decision + edge galaxy runbook |

Built on a clean worktree (`/tmp/wm-int` at `37003d4`, rebased onto the
concurrent session's later commits; worktree removed after push). Note for
bisect: the two sweep commits above remain red intermediate history; the
tip is green.

### Verification (worktree, pre-push)

- `cargo check --workspace --all-targets` → exit 0 (one pre-existing
  dead-code warning in the concurrent session's `session_ops.rs`).
- Suites: wm-core 170, wm-dispatch 172, wm-memory 511 (+2 ignored),
  wm-cognitive 714, wm-tools 824, whitemagic 267 — all green.
- After `update-ref`, the main tree index was resynced with `git reset`
  (working tree untouched); the only remaining dirty files are the
  concurrent session's `cold_storage.rs`, `store.rs`, `memory_ops.rs`,
  `wm-tools/lib.rs`, `tools/tests/cold_discovery_experiment.rs`.

### Still outside whitemagic (Mandala OS scope, uncommitted)

- `MANDALAOS_SOVEREIGN`: `modules/landlock-isolation.nix` (`--exec`
  envelope mode, explicit `WM_SANDBOX_RUNNER` per unit, `/run/current-system`
  bind) + `scripts/verify-sandbox.sh` mirror.
- `LAKSHMI` (`lbailey94/lakshmi`): `lakshmi.py` `--emit` + spool + threshold
  events, `test_lakshmi.py` (25 tests). Commit these when the OS scope
  resumes.

---

## 12. Night session close-out (VM dogfood → dashboard → policy step 0)

**Status:** all wired, tested, committed, pushed. Repos: whitemagic
`fix/ci-green`/main (see commits below), mandalaos-sovereign `main`,
lakshmi `main`. VM running (guest wm 9.1.4, 242 vectors, hybrid recall).

### Delivered tonight

1. **Thread 5 — VM dogfood complete.** Guest rebuilt from the v9.1.4-based
   tip; matrix green; 301 tools incl. telemetry surface; B2 runner active;
   reembed backfill 244 embedded / 0 errors; hybrid recall verified. The
   read-only serve lacked `WM_EMBEDDER_*` (FTS fallback despite vectors) —
   fixed in `vm.nix` (`cb3cb91`).
2. **Host containment wrapper + fleet wiring** (`2d56146`): portable
   `scripts/mandala-sandbox` (bwrap+jq, same envelope contract), installed
   at `~/.local/bin`, wired via instance env files + gateway/mesh drop-ins;
   live spawn verified (`gh_available: true`).
3. **Landlock × bwrap — root-caused and closed as by-design.** Landlock
   denies all mount topology changes while a domain is active; bwrap needs
   `mount(MS_SLAVE)`. Reproduced host (7.0/bwrap 0.9) + VM (6.18/0.11);
   upstream-documented. Either/or policy stands; no fix shipped for a
   non-fix. Optional future: landrun-based pure-Landlock runner.
4. **Mixer slices:** wavelength strips (fast 5 m live + slow windows),
   band selector incl. 7 d rollups, EMA smoothing, pause, cue markers,
   karma Δ flow lane, full readout.
5. **Policy step 0 live** (`78f3c8b`): four observe-only policies with
   enter≠exit bands + `min_dwell` + one-time `confirmed` + cooldown;
   `telemetry.observation` decision records; dashboard **Policies** panel.
   Typed record path pushed (`38bf66e`, rides v9.1.5) with memory.create
   fallback.
6. **v9.1.4 fleet deploy verified from this side**; telemetry repointed to
   the real gateway (`39dffd3`); edge-galaxy stand-in retired.
7. **Signing key** backed up off-machine (gpg AES-256 on SD_CARD1 +
   paper passphrase).

### Commits (highlights)

- whitemagic: `16de9ae` dim_notes hardening, `3c6eb1b` fmt, `38bf66e`
  observation kind + typed rollups, `31eafd2` clippy
- sovereign: `cb3cb91` embedder env, `2d56146` host wrapper, `93bc3c2`
  daemon either/or, `9dc0b20` v9.1.4 pin
- lakshmi: `c902bb6` spool semantics, `0c2cfb6` waves, `f7247fc` mixer,
  `c65987b` rollup lane + timer, `39dffd3` fleet repoint, `78f3c8b` step 0

### Open queue (see CURRENT_REALITY §8)

Release-eng lane: release-health record, selftest in smoke gate, first live
`wm update` at 9.1.5, setup JSONC/TOML. MandalaOS lane: ~~fleet telemetry
hygiene (weekly prune timer + retention planner)~~ **done — see §13**,
honest-gaps one-pager, landrun runner (optional), website facts (other
session). Gates: fleet ✅, guest parity ✅, recall ✅; edge-galaxy 72 h clock
restarted on the fleet store ~23:36Z 2026-09-13.

---

## 13. Telemetry retention close-out (2026-09-14 early UTC)

**Status:** planner committed in whitemagic `main`, timer installed and
live-verified on the fleet. First scheduled pass: Sun 2026-09-20 05:10 local.

### Delivered

1. **`telemetry.retention` (read-only planner)** in
   `crates/wm-tools/src/expansion/telemetry_tools.rs` — per-tier
   counts/bytes/oldest-newest/eligible under the exact horizons
   `telemetry.prune` uses (7 d windows / 90 d rollups), plus `managed: false`
   observation inventory (decision records are governance evidence).
   Declares no writes + not destructive, so it is never confirm-gated and the
   dharma gate cannot veto it. 5 telemetry tests green; clippy clean.
2. **Weekly operator timer** `ops/telemetry/wm-telemetry-retention.{service,
   timer}` + `retention_run.sh`: planner first (evidence always logged), then
   confirmed prune; on pre-9.1.5 fleets the planner answers `Unknown tool` and
   the script proceeds with prune alone. Installed to
   `~/.config/systemd/user/`, enabled, ran once (77 scanned / 0 candidates /
   exit 0).
3. **E2E** on a scratch debug serve: planner registered, recorded a window,
   planner showed `count: 1, eligible: 0, next_eligible_since: +7 d`; a 0-day
   horizon projected `prune_due: true`; a wet prune under current load was
   dharma-vetoed (`VIOLATION_AHIMSA`) — the exact failure the planner exists
   to make visible.
4. **Docs:** `EDGE_GALAXY_TELEMETRY.md` retention section rewritten (planner
   + timer + install snippet); CURRENT_REALITY §5/§8 updated.

### Honest deltas

- The planner only exists live once the fleet runs **v9.1.5** (today's
  gateway is 9.1.4) — until the first live `wm update`, the weekly script logs
  the planner as unavailable and prunes blindly (dry-run evidence for the run
  is in the journal).
- A wet prune can still be vetoed under stress (observed); the weekly failure
  is red in the journal by design, and the next week retries.

---

## 14. Release-engineering lane close-out (2026-09-14 early UTC)

**Status:** committed in whitemagic `main` (`0a408ce`, local — push pending);
nothing machine-local was installed. Queue items 1 and 2 are done; 3 and 4
remain.

### Delivered

1. **Release-health record + registry reconciliation** —
   `scripts/release_health.py` (stdlib; allowlisted into the public surface)
   probes GitHub Release required assets, all 15 workspace crates on
   crates.io in dependency order, npm, Docker Hub, and the official MCP
   registry for one `--version`; writes `release-health.json` (kind
   `wm.release-health`, `status: healthy|lagging`; exit 0/1).
   `.github/workflows/release-health.yml` runs on Release-workflow
   completion + daily 04:10 UTC + dispatch: initial probe → idempotent retry
   of laggards (npm / cargo / docker / mcp-publisher) → re-probe → **install
   certification** (`npm install -g whitemagic-mcp@X` + `whitemagic-mcp
   selftest --json`; `docker run lbailey94/whitemagic:X selftest --json`) →
   merge `install_certification` → upload the record to the GitHub Release
   (`release-health.json`, clobber) → red gate while any surface lags or a
   certified install fails (next daily run retries).
2. **`wm selftest` in the release smoke gate** — `release.yml` build matrix
   now runs `wm selftest --json` on all five targets (linux gnu/musl, macos
   x86/arm, windows) before rename/checksum/publish; curated smoke test stays
   the deeper Linux check. Certification of the npm/Docker install funnels
   lives in the health workflow (above).

### Verified locally (no CI run yet)

- `release_health.py --version 9.1.4` → HEALTHY: 33 GitHub assets (12
  required), 15/15 crates, npm, docker (`sha256:14fa683d…`),
  MCP registry (7 versions seen incl. 9.1.4).
- `--version 9.9.9` → LAGGING, exit 1, per-surface missing detail.
- Both workflow YAML files parse; the certification-merge + red-gate `jq`
  logic exercised with pass/fail fixtures (fails red on a failed docker
  selftest, as intended).

### Notes / deltas

- `docs/RELEASE_CADENCE.md` gained a “Release health (the reconciliation
  clock)” section — it is intentionally outside the public archive
  (`.gitignore`), so the in-repo contract lives in the script docstring and
  workflow comments.
- `.gitignore` gained `!/scripts/release_health.py` (the `/scripts/*`
  default-deny allowlist).
- The health workflow is inert until `0a408ce` is pushed to `main`; its first
  automatic run is the next daily 04:10 UTC tick (probing v9.1.4, expected
  healthy) unless a Release completes first. Nothing it does is destructive:
  retries are idempotent and the record upload only clobbers its own asset.

### Remaining release-eng queue

3. First live `wm update` install at 9.1.5 — needs the tag; the store
   retention/observation work rides it.

---

## 15. `wm setup` JSONC/TOML close-out (2026-09-14 early UTC)

**Status:** committed in whitemagic `main` (`721b114`, local — push pending);
queue item 4 is done. Release-eng lane now has only item 3 left (first live
`wm update` at 9.1.5).

### Delivered

1. **OpenCode `opencode.jsonc`** — write support via a small
   string/comment-aware structural scanner (`upsert_member`): inserts or
   replaces `mcp.whitemagic` in place, preserving comments, sibling members,
   and formatting; comment-free configs take the existing pretty-JSON path.
   The edited document must re-parse to the intended merged value before the
   write (verified in code), then read-back verified again.
2. **Codex `config.toml`** — write support via `toml_edit` (new direct
   dependency; already in the lock transitively): preserves comments and
   unrelated tables; new files emit only `[mcp_servers.whitemagic]`.
3. **Safety shape (all kinds):** timestamped backup before write, refuse to
   clobber a non-object `mcp` / non-table `mcp_servers`, idempotent
   (`already configured`), no modification on parse error.
4. **Onboarding contract:** `wm setup` (listing and per-client output) now
   states “explicit routes are the contract — call the wm meta-tool with
   route=...”; `docs/MCP_CONFIG_GUIDE.md` gained a “One-command setup”
   section with the contract examples.

### Verified

- 11 setup tests (comment preservation incl. comments-in-strings and braces
  inside comments, trailing commas, replace + insert, idempotency,
  refuse-to-clobber, create-missing-file); wm-mcp lib 279 passed; clippy
  `-p whitemagic --all-targets` clean.
- CLI E2E on a temp `HOME`/`XDG_CONFIG_HOME`: codex + opencode writes,
  comments preserved, backups made, re-run says `already configured`.

### Pitfall noted

- The main tree had a concurrent-session in-flight `server.rs` that did not
  compile for a window; verification ran in a clean worktree at `HEAD` with
  `CARGO_TARGET_DIR` pointed at the shared target dir (the §6-7 pattern),
  then the final run happened in-tree once the other session’s commit
  (`80a884d`) landed.

---

## 16. 9.1.5 release prep — parked, not deployed (2026-09-14 early UTC)

**Status:** prep committed in whitemagic `main` (`f62c790`, `c08b982`, local —
push pending). **No version bump, no tag, no registry deploy** — Lucas has
more changes to land before the release clock starts.

### Delivered

1. **Version truth tooling** — `scripts/version_truth.py --check/--set`
   covers all 15 version-bearing surfaces (16 Cargo.toml references incl.
   internal pins, npm package/server/MCPB, hosted server-card, CITATION,
   Dockerfile ARG + label, QUICKSTART/MCP_CONFIG_GUIDE/DOCKER_HUB_RUNBOOK,
   skill.md, README, install.sh examples, SECURITY.md,
   rust-toolchain.toml comment). It preserves `v` prefixes, exempts
   historical mentions (`SECURITY.md`’s removed 9.0.0), re-reads every file
   after writing, and refuses non-semver input. 8 unit tests.
2. **`release.sh` integration** — preflight now refuses version-truth drift;
   the bump stage uses `--set` instead of the old three-file inline edit; the
   crates.io order is derived from `cargo metadata`
   (`scripts/crates_publish_order.py`) like release.yml, killing the stale
   hand-maintained list.
3. **CHANGELOG.md draft `[9.1.5]` section** (marked *unreleased; finalize at
   tag time*) assembled from `v9.1.4..main`: telemetry retention +
   observation kind, setup JSONC/TOML, release health + selftest gates,
   version truth, distribution fixes, 9-tool catalog trim + tool annotations.
4. **Dry-run verification:** `scripts/release.sh 9.1.5 --dry-run` → preflight
   ok, version truth green (33 references across 15 files), full channel plan
   prints cleanly. No side effects.

### What 9.1.5 will unlock when it ships

- Fleet first live `wm update` install (queue item 3) and, with it,
  `telemetry.retention` on the gateway (the weekly timer already logs a
  graceful `Unknown tool` until then).
- The typed observation records for the live policy layer (currently
  falling back to `memory.create` on 9.1.4).

### Parked deliberately

- The release ceremony (bump → gates → tag → fan-out) is unchanged in shape;
  run `scripts/release.sh <version>` once the remaining changes land, or let
  the automated path handle the tag. The health workflow will then reconcile
  and certify the release automatically.

---

## 17. Landrun runner close-out — pure-Landlock B2 for Landlock stores (2026-09-14 early UTC)

**Status:** implemented, host-verified end-to-end, packaged + wired and
Nix-evaluated. Commits: sovereign `d1a31b0` (local — push pending),
whitemagic `c0a4c49` (local — push pending; doc-only). VM rebuild is the only
remaining verification.

### Delivered

1. **`scripts/landrun-sandbox`** (sovereign) — same `--exec` contract as
   `mandala-sandbox` (program/args/net/workspace, `WM_SANDBOXED=1`), built on
   landrun 0.1.15 and nothing else. Path confinement only: system paths rox,
   scratch dir rw (becomes `TMPDIR`), `/dev/null` rw, env passed through a
   fixed allowlist (PATH, locale, cert vars, `GH_TOKEN`/`GITHUB_TOKEN`,
   proxies; `WM_SANDBOX_ENV` adds more; `WM_SANDBOX_EXTRA_RO/ROX/RW` add
   paths). Rules for paths a stricter parent already denies are skipped, so
   nested rules never fail outright. Documented trade: no namespaces, no
   private `/tmp`, no `/proc` — path confinement only.
2. **Module wiring** (`modules/landlock-isolation.nix`) —
   `landrunSandbox` packaged via `writeShellApplication` (single source:
   `builtins.readFile ../scripts/landrun-sandbox`); daemon gets
   `WM_SANDBOX_RUNNER=landrun-sandbox` (keeps `WM_LANDLOCK=1`), read-only
   serve keeps bwrap, global shells keep bwrap. Nix eval verified for all
   three, and the packaged wrapper built and ran
   (`/nix/store/rgwbqzgg…-landrun-sandbox`).
3. **Matrix +5 checks** (`scripts/verify-sandbox.sh`): landrun runner
   executes / write-denied / scratch-rw; **nested-under-Landlock works**;
   **bwrap blocked under the same domain**. Host run: **13/13 green**.

### Evidence (host, kernel 7.0)

- Negative control: bwrap fails under an active Landlock domain
  (`overflowuid`/mount denial); landrun-sandbox succeeds under the same
  domain — rulesets stack, namespaces do not.
- Full WM chain: a scratch `wm serve` started under an **outer Landlock
  domain** (simulating the daemon) dispatched `oss.bounty.status` through
  `landrun-sandbox` → `gh_available: true` with
  `sandbox: {envelope: wm-sandbox-exec-v1, net: false, runner:
  …/landrun-sandbox}` and no degradation warnings in the serve log.
- Confinement spot-checks: scratch writable, host `/tmp` denied, `$HOME`
  denied, `/etc/passwd` readable, network deny is a fast Landlock refusal
  (not a timeout), `net:true` reaches example.com (HTTP 200).

### Honest deltas

- **VM boot not yet rerun** — kernel 6.18 in-guest should behave the same
  (Landlock stacks there too), but the matrix's new checks are host-verified
  only until the next `nix build` + boot.
- The runner grants no `/proc`; tools needing procfs fail loudly by design.
- `landrun`'s `--unrestricted-filesystem` skips the domain entirely (found
  while testing) — the matrix's domain is a real ruleset, not that flag.

### Queue effect

- CURRENT_REALITY §8 item 5's "optional future" and §6's either/or note are
  resolved; SANDBOX_LAYERS §3-7/§4 updated; sovereign README updated.
- Release-eng lane item 3 (first live `wm update` at 9.1.5) remains the only
  open release item; the 9.1.5 prep is parked per Lucas.
