# Session Note — 2026-09-14 evening: Yama v0 bridge S1+S2

**For:** the next session and the WM record. Companion docs: `implementation/yama-v0-bridge-design.md` (design), `CURRENT_REALITY_2026-09-13.md` §4 (the gap), `SESSION_HANDOFF_2026-09-14.md` (context).

## What was built

### S1 — sandbox drift → bus (WMv9, worktree `WHITEMAGIC/WMv9-yama-bridge` @ `yama/bridge-v0`, based on `c007ecb`)
- `wm-dispatch/src/subprocess_sandbox.rs` — bounded event ring (`SandboxEvent` {tool, kind, ts_ms}, cap 64, `drain_events()` exactly-once), recorded on `note_degraded` / `note_unconfined_spawn` only (happy path stays counter-only).
- `wm-cognitive/resonance/event_type.rs` — `EventType::SandboxObservation = 235` (Harmony category, OS-telemetry family), `COUNT` 235→236, `all()` 0..=235, name `sandbox_observation`; nervous-system map → Sensory.
- `wm-mcp/src/server.rs` — `emit_sandbox_observations()` drains after every dispatch and emits a `sandbox_observation` bus event `{tool, kind, counts, ts_ms}` (JSONL-persisted at serve like all bus events).
- **Evidence:** wm-dispatch 7/7 (4 new), wm-cognitive 714/714, whitemagic lib 298/298, clippy `-D warnings` clean (all in worktree). Diff: 4 files, +212/-10.
- **Uncommitted** — awaiting Lucas's commit decision (project rule: commit only files you touched).

### S2 — Tetragon collector (sovereign, `MANDALAOS_SOVEREIGN/scripts/yama-collector.py` + fixtures/)
- Reads Tetragon JSONL/array (stdin or `--input`), liberal string-walk mapper (`shadow.access.v1` ← `security_file_open` + `/etc/shadow`), aggregates per policy per batch into one `telemetry.observation` record (`state: observed`, `action: observe`, evidence = up to 3 identity samples), typed `telemetry.record` with `memory.create` fallback (mirrors Lakshmi's emit pattern), bounded spool (`~/.local/share/yama-collector/spool.jsonl`, 2000 cap) with oldest-first replay, `--dry-run`.
- **Evidence (2026-09-14):** dry-run on fixture = 4 events → 2 matched → 1 record (correct exclusions); live send to scratch `wm serve` (temp store, port 28912) → record verifiable via `memory.search`; dead endpoint → spooled; recovery run → replayed + spool emptied.
- **Uncommitted** (sovereign repo, clean otherwise).

## Publication gates — status
- **Edge-galaxy 72 h soak: RUNNING and healthy.** Gateway retention planner (18790): windows 1072, oldest `2026-09-13T23:36:23Z`, newest `2026-09-14T22:36:36Z`; rollups 19 (hourly); observations 132 (step-0 records, actively written — newest minutes old, never pruned by design). Gate fires **~2026-09-16 23:36Z**.
- **Repo hygiene: pin bumped.** `MANDALAOS_SOVEREIGN/flake.nix` v9.1.4 → v9.1.5; `flake.lock` updated via `nix flake update whitemagic-src`; locked rev `52fb0b7…` = signed `v9.1.5` tag commit (verified). Uncommitted.
- **Stranger install (≥4/5):** not started (manual acceptance; needs a clean machine/HOME pass).

## Environment notes
- The concurrent session **consolidated the repos into MANDALA_OS**: `LAKSHMI/` and `MANDALAOS_SOVEREIGN/` now live inside this project folder (were `~/Desktop/projects/`). Paths in older docs are stale.
- Concurrent WMv9 work continues in the main tree (dirty files: context.rs, pipeline.rs, dharma_gate.rs, resource_rules.rs, claims_tools.rs, nlu.rs) — hence the S1 worktree isolation.
- MCP `wmv9` meta-tool hit its per-connection request budget (10k/10k) this session; bus/telemetry reads were done via the gateway HTTP endpoint and `wm` CLI instead.

### S3 — Lakshmi policy inputs (`MANDALA_OS/LAKSHMI`)
- `fetch_bridge_inputs(endpoint, since)` polls `bus.recent category=harmony` (filters `sandbox_observation` by kind) and `memory.search` in the telemetry galaxy (filters `tetragon.shadow_access` records) with an explicit per-window cursor — no double counting, no gaps.
- Three event-driven step-0 policies: `spawn.undeclared.v1` (unconfined spawns), `sandbox.degraded.v1` (runner-less declared spawns), `shadow.access.v1` (Tetragon `/etc/shadow` accesses); dwell 1, cooldown 0, `action: observe`. Feed outage = source unavailable → state held, never silently cleared.
- Window records carry a `bridge` counts block; dashboard `/api/events` now includes `sandbox_observation`.
- **Evidence:** 49/49 tests green (38 lakshmi + 11 dashboard); live transport check against the fleet gateway: `bus_ok: true`, `tetragon_ok: true`, counts 0 (correct — S1 not yet deployed to the release binary; no Tetragon collector records in production yet). Full behavioral test happens at S4 in-guest.
- **Uncommitted** at the time of writing; committed with the session's follow-up.

## S4 — in-guest live run (2026-09-14 late; partial)

**Done:**
- **Merged S1 to main** (`WMv9` merge commit `3384dfb`) — no conflicts; main rides v9.1.6 (unreleased section already open). Push/release pending Lucas.
- **Unit paths fixed:** 5 `~/.config/systemd/user/lakshmi-*.service` files still pointed at `~/Desktop/projects/LAKSHMI` (stale after the folder move); sed'd to `~/Desktop/MANDALA_OS/LAKSHMI` + `daemon-reload`. Running services were left untouched (they keep their inode; next restart now works).
- **Full pipeline proven live on a scratch store** (temp `wm serve`, no production writes):
  1. `yama-collector.py` on the Tetragon fixture → `shadow.access.v1 | tetragon.shadow_access | observed | value=2`.
  2. `fetch_bridge_inputs()` → `{tetragon_shadow: 1, bus_ok: true, tetragon_ok: true}`.
  3. `policy_observations()` → transition `shadow.access.v1 | observing | value=1.0 | action=observe`, emitted as a typed decision record.
  Both records verified via `memory.search` in the scratch store.

**Blocked (needs a decision):**
- **True in-guest Tetragon capture deferred:** the Nix store was GC'd (2.0 GB; no VM runner path `v5kjrw43…`, no `whitemagic` paths), so booting requires a full cold `nix build` of the VM (nixpkgs from cache + **WM Rust release build locally**). Host pressure is high right now: ~2 GB RAM free, zram 8 GB used, several active agent sessions (1.8 GB+ `solc`, multiple `opencode`).
- No Tetragon binary exists on the host; the in-guest copy may survive on `~/vms/mandala.qcow2` (disk persists) — verifiable once the VM boots.
- S1 live behavior on the fleet waits for the v9.1.6 release (host/guest binaries predate the merge), so the `sandbox_observation` bus leg was proven by unit tests + code only; the Tetragon leg was proven end-to-end above.

**Next actions (awaiting go):**
1. VM rebuild when the machine is quiet (recommended) → in-guest Tetragon observe + collector over SSH → real `/etc/shadow` capture.
2. **Done 2026-09-14 23:48Z: `lakshmi-sampler` restarted** — S3 is live in the production loop. First windows (`23:48:49Z`, `23:49:51Z`) carry `bridge: {sandbox_degraded: 0, sandbox_unconfined: 0, tetragon_shadow: 0}`; the edge soak gap was one emit cycle. The first real bridge event (sandbox drift or Tetragon record) will now produce decision records automatically.
3. Push main + release v9.1.6 (S1 rides it; 10 commits).

## Next
1. **S3** ✅ (above).
2. **S4** ◐ — pipeline live-proven; in-guest eBPF capture pending VM rebuild.
3. Stranger-install pass; then decide Y1 (Rust evaluation engine) vs keeping step-0 in Lakshmi.
