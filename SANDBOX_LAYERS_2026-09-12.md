# Sandbox Layers — Consolidation & Local Verification (2026-09-12)

One map of every containment layer across WhiteMagic and MandalaOS Sovereign:
what each actually enforces, where it lives, and what was verified on real
hardware tonight. Consolidates WM's two Landlock pathways (v0 whole-process,
v1 per-tool) with the OS layer's Bubblewrap wrapper and systemd hardening.

---

## 1. The layers

| # | Layer | Mechanism | Confinement unit | Enabled by | Artifact |
|---|---|---|---|---|---|
| 1 | WM Landlock v0 | Landlock LSM: write-class FS rights granted only beneath the store root + `/dev/null` | whole `wm` process (main thread, inherited by workers) | `WM_LANDLOCK=1` | `WMv9/crates/wm-mcp/src/landlock_sandbox.rs` |
| 2 | WM Landlock v1 | Same ruleset, applied per dispatch on a fresh scoped thread | one tool call (`Sandbox::StoreScoped` tools) | `WM_LANDLOCK_V1=1` | `WMv9/crates/wm-dispatch/src/sandbox_exec.rs` + wm-mcp callback |
| 3 | OS tool sandbox | Bubblewrap: ro system binds, tmpfs `/tmp`, net off by default, PID/IPC/user namespaces | any external process via `mandala-sandbox` | wrapper always on; WM spawns wired 2026-09-13 (B2); portable host twin in `mandalaos-sovereign/scripts/mandala-sandbox` | `MANDALAOS_SOVEREIGN/modules/landlock-isolation.nix` |
| 4 | Daemon confinement | systemd: `ProtectSystem=strict`, `ProtectHome=read-only` + `ReadWritePaths`, `RestrictAddressFamilies`, `NoNewPrivileges` | `whitemagic-daemon` service | unit | `MANDALAOS_SOVEREIGN/modules/whitemagic-service.nix` |
| 5 | *(future)* Policy / eBPF | Tetragon/OPA observe→enforce ladder | host-wide | sprint | `implementation/lakshmi-yama-sprint-plan.md` |

Design intent: 1–2 = *WM cannot lie about what it writes* (karmic accounting
enforced at the filesystem); 3 = *tools WM launches cannot see or touch the
rest of the machine*; 4 = *the daemon itself is bounded*; 5 = *the OS can
explain, and later enforce*.

## 2. Local verification (Zorin 18.1, kernel 7.0.0-31, bwrap 0.9.0)

### 2a. WM Landlock v0 — live, enforced

Run: scratch store `/tmp/opencode/ll-test-store`, `WM_LANDLOCK=1 wm serve
--transport sse --bind 127.0.0.1:19199 --profile minimal`, then `GET /status`:

```
"landlock": {
  "detail": "write-class FS rights confined to the store root + /dev/null
             (Landlock ABI v8); declared grants: /dev/null (WriteFile)
             (no_new_privs=true)",
  "enabled": true,
  "outcome": "enforced",
  "store_root": "/tmp/opencode/ll-test-store"
}
```

Confirms on this machine: kernel enforces Landlock at **ABI v8** (the flake
spec's "ABI v4" was years stale); outcome reaches `/status`; writable servers
persist `landlock_state.json` in the store root for `wm doctor` grading.

### 2b. Bubblewrap profile matrix (script: `scripts/verify-sandbox.sh`)

| Check | Result |
|---|---|
| A0 exec inside sandbox | ok |
| A1 write `/usr` (ro-bind) | denied |
| A2 write `/tmp` (tmpfs) | ok |
| A3 `/etc/shadow` | not bound |
| A4 home WM store | not bound |
| A5 network, default profile | isolated (`curl` exit 7) |
| A6 visible processes (PID ns) | 6 |
| B1 loopback, `--net` | ok |
| B2 internet + DNS, `--net` | ok |
| C1 read ro workspace bind | ok |
| C2 write ro workspace bind | denied |

## 3. Findings fixed tonight

1. **`--share-net` bug in the wrapper.** The original `--net` variant merely
   skipped `--unshare-net`; because `--unshare-all` already unshares net,
   skipping it is a no-op — net stayed isolated. Fix: append `--share-net`
   (bwrap 0.9 semantics). Caught by test B failing.
2. **Loader compat binds.** Binding `/usr` alone cannot exec on Ubuntu-family
   hosts: `ld-linux` lives under `/lib64`. Added
   `--ro-bind-try /lib /lib --ro-bind-try /lib64 /lib64`. Harmless on NixOS
   (paths are store symlinks) and required on dev machines.
3. **DNS/CA binds for net mode.** `--net` now binds `/etc/resolv.conf`,
   `/etc/hosts`, `/etc/nsswitch.conf`, `/etc/ssl/certs` read-only; internet +
   DNS verified.
4. **Regression script**: `MANDALAOS_SOVEREIGN/scripts/verify-sandbox.sh`
   mirrors the module wrapper so the same matrix can run inside the VM after
   the first Nix build.
5. **(2026-09-13, B2) systemd services cannot discover the runner.** The
   in-guest `wm-mcp-readonly`/daemon services run with a minimal PATH and no
   `environment.variables`, so PATH-based detection loud-degraded (correct,
   but uncontained). Fix: `landlock-isolation.nix` sets
   `WM_SANDBOX_RUNNER` explicitly per service (and globally for shells).
6. **(2026-09-13, B2) name-based exec inside bwrap needs `/run/current-system`.**
   On NixOS the inherited PATH resolves through `/run/current-system/sw/bin`
   symlinks; without a bind, `bwrap: execvp sh: No such file or directory`.
   The wrapper and the matrix script now ro-bind `/run/current-system`.
7. **(2026-09-13) Landlock v0 × bwrap are mutually exclusive — documented
   Landlock limitation, not a bug or a missing grant.** Landlock denies
   *filesystem topology modification*: while a domain is active, mount
   operations are denied (go-landlock states "arbitrary mounts are always
   denied. These are Landlock limitations that will be resolved in future
   versions"). bwrap requires `mount(NULL, "/", MS_SLAVE)` for its mount
   namespace, so it fails with EPERM regardless of ruleset grants.
   Reproduced identically on host (kernel 7.0, bwrap 0.9) and VM (kernel
   6.18, bwrap 0.11) via `landrun`; a `/proc` write grant was prototyped,
   keeps the ruleset `enforced`, and does **not** unblock the mount step
   (not shipped). Precedent: Codex CLI hits the same and falls back to
   "legacy Landlock". Consequence: a store runs **whole-process Landlock OR
   the spawn runner** — unless the runner is itself pure-Landlock, because
   Landlock rulesets stack. **Resolved 2026-09-14:** shipped
   `scripts/landrun-sandbox` (sovereign repo), a pure-Landlock runner with
   the same `--exec` contract, and wired it in
   `modules/landlock-isolation.nix`: the daemon keeps `WM_LANDLOCK=1` and
   routes declared spawns through it, while the read-only serve (no
   Landlock) keeps the bwrap runner. Host fleet unchanged: it runs the
   runner path (wmv9's `landlock.conf` stays disabled, reversible — those
   stores are not Landlock stores). Evidence: nested runner works where
   bwrap fails under the same domain; a full dispatch chain (serve under an
   outer Landlock domain → landrun runner → `timeout 30 gh --version`)
   returned `gh_available: true` with the sandbox disclosure intact.
   Trade documented in the runner header: path confinement only, no private
   `/tmp`, no namespaces.
   Sources: Landlock limitation —
   <https://pkg.go.dev/github.com/landlock-lsm/go-landlock/landlock>
   ("arbitrary mounts are always denied"); Codex CLI issue #15434 (same
   failure, `use_legacy_landlock` fallback); bubblewrap issue #713 (request
   for integrated Landlock support).

## 4. Known gaps (honest)

- **v0 vs readonly servers**: preservation-readonly servers skip the ruleset
  by design (the report would modify the frozen store); status is in-memory only.
- **v1 taxonomy is early**: `StoreScoped` tools cannot yet spawn subprocesses
  or receive the `.git` lease-ledger grant (`sandbox_exec.rs` module docs).
- ~~**Wrapper not yet wired into WM dispatch**~~ **Resolved 2026-09-13 (B2):**
  `Sandbox::Subprocess` tools build spawns through `wm_core::sandbox::SpawnPolicy`
  (JSON envelope `wm-sandbox-exec-v1` → `mandala-sandbox --exec`). Live host
  proof: `oss.bounty.status` spawn carried `{"program":"timeout","net":false}`,
  `oss.bounty.scan` carried `net:true` (effect-row derived), `/status`
  disclosed `dispatches:2 degraded:0`, and a runner-less server loud-degraded
  (`WARN wm_dispatch::subprocess_sandbox` + `degraded:1`) with no false
  confinement claim. Tools declaring raw `spawns` without the contract are
  counted as `unconfined_spawns` (roll-out signal).
- **No unified policy file**: layers are configured in three places (env flags,
  systemd unit, wrapper). Future: one policy manifest mapping
  `EffectRow.sandbox` → runner selection.
- ~~**`landrun` not layered yet**~~ **Resolved 2026-09-14:** `landrun-sandbox`
  is a first-class B2 runner for Landlock stores (path confinement via
  stacked Landlock rulesets; same envelope contract). Non-WM external
  processes still use `mandala-sandbox` (bwrap).
- **Systemd unit untested**: first VM boot will validate `Protect*` /
  `AddressFamilies` choices (e.g. `AF_NETLINK` needed by some resolvers).

## 5. Next steps

1. First `nix flake check` + VM boot → run `verify-sandbox.sh` inside the VM.
2. ~~Wire `mandala-sandbox` as WM's external tool runner (dispatch seam).~~
   **Done 2026-09-13 (B2)** — see §3 items 5-6 and §4.
3. Optional third independent check: `go install` landrun locally and re-run
   the write-confinement matrix under kernel Landlock.
4. Feed layer telemetry into the Lakshmi/Yama sprint (layer 5 observes 1–4).
