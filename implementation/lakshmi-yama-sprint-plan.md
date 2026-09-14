# Lakshmi + Yama Behavioral Prototype — Sprint Plan

**Status:** Draft (2026-08-28). Supersedes `feasibility/prototype-sprint-plan.md` (the 2025-era Qubes-centric plan) with the 2026 tooling reality confirmed by research.
**Goal:** A working Dharma-Engine slice on real Linux — observe, explain, and (carefully) enforce — feeding the Harmony Vector from `harmony-vector-spec.md`, with WM as first consumer.

## Stack decision (validated Aug 2026)

| Role | Tool | Why |
|---|---|---|
| Broad detection (Lakshmi ears) | **Falco** (CNCF-graduated) | Mature, community rules, alert routing |
| Narrow enforcement (Yama hand) | **Tetragon** (observe-first) | In-kernel, but enforcement is earned path-by-path |
| Forensics (Karmic trace) | **Tracee** or Falco events into SQLite | Rich event depth for the ledger |
| Policy decision point (Dharma rules) | **OPA** (Rego) — Cedar acceptable alternative | Self-hosted, sub-ms; Cedar if we want forbid-wins + later formal analysis |
| Metrics/vector (Lakshmi) | Prometheus + node-exporter + a small Rust/Python digestor | Computes the 7-dim vector per the spec |
| Dashboard (Tiferet/Maya) | **Tauri** shell + Svelte | Lightweight; matches Wu-Wei constraint |
| Consumer | **WHITEMAGIC** | Ingest vector dims; WM publishes dharma/karma dims back |

Drop from the 2025 plan: Qubes as the *starting* base (comes later for compartment isolation; eBPF prototyping on bare Linux is simpler and 80% of the learning). Koka/SutraCode: untouched this sprint.

## The cardinal rule (from Tetragon field practice)

**Enforcement is earned.** Every policy ships in observe mode for ≥ 1 real workload week with zero false positives before ANY blocking action. A false positive in observe mode is a log line; in enforcement mode it's a killed process. This IS the Gevurah/Chesed balance, stated operationally.

## Weeks

### Week 1 — Ears (Lakshmi v0)
1. Verify kernel: need ≥ 5.8 with BTF/CO-RE for modern eBPF (`uname -r` first — this gates everything).
2. Install Falco + node-exporter + Prometheus; confirm < 2% CPU overhead.
3. Write the vector digestor: 7 dims per `harmony-vector-spec.md` (Gini via per-process CPU, PSI for responsiveness, RAPL for energy).
4. **Milestone:** live 7-bar dashboard (Tauri) showing the vector updating every 5s; guna tags on the top 10 processes.

### Week 2 — Consent (Yama v0, observe-only)
1. OPA sidecar with 3 starter policies (Rego): new process phoning home (network egress), unexpected `/etc/shadow` write, crypto-miner signature (high sustained CPU + mining pool ports).
2. Wire Falco events → OPA decisions → "Karmic trace" into SQLite.
3. Consent dialog in the Tauri shell: "Process X wants network: [Allow once | Deny] — Why: <plain-language Rego explanation>."
4. **Milestone:** the demo from the 2025 sprint plan, actually working — a Rajasic process's egress attempt pops the dialog, decision logged, nothing blocked yet.

### Week 3 — The hand (Yama enforcement, narrow)
1. ONE Tetragon TracingPolicy, chosen from the observe-mode logs (e.g., deny writes to a credential path), enabled with `SIGKILL` only after zero-false-positive confirmation.
2. Stoic circuit-breaker (30 lines of shell): rapid-fail loops → degraded mode + "Stoic card" in the UI.
3. **Milestone:** first blocked action with a logged explain-link; enforcement stats surface in vector dim 6 (dharma).

### Week 4 — Integration & test
1. WM integration: WM reads vector dims 1–5; WM's karma ledger feeds dim 7 back. One shared JSON/gRPC endpoint.
2. Scenario tests: Rajasic app (VS Code render job), mining-signature replay, crash-loop app.
3. Tune the Gevurah/Chesed knobs: alert cadence, dialog intrusiveness.
4. **Milestone:** sprint report with measured overhead (target: ≤ 2% CPU, ≤ 200MB RAM) vs. the May-2025 cost table.

## Success criteria (exit tests)
- [ ] Vector spec's 7 dims computed from real telemetry, not mocks.
- [ ] A non-Dharmic egress attempt produces a consent dialog in < 1s and a signed decision record.
- [ ] One enforcement policy live with zero false positives over its observation window.
- [ ] WM reads the vector and publishes karma debt back.
- [ ] Overhead within budget on a 16GB machine.

## Risks & mitigations
- **Old kernel / no BTF** → Falco kernel-module fallback exists; Tetragon needs ≥ 4.19 (module-restricted environments may eliminate Tetragon).
- **Event flooding** (eBPF ring-buffer loss) → "Quiet Mind" selective monitoring from the 2025 plan: full-fidelity only on Rajasic processes.
- **OPA Rego learning curve** → start with 3 policies; Regrettably, Rego ≠ "readable by mortals" — keep the explain-layer in plain language, generated per policy.
- **SIGKILL danger** → enforcement never ruleset-wide; path-by-path promotion only.

## Relationship to the larger map
This sprint = Phase 2 (Lakshmi) + Phase 3 (Yama) of `feasibility/mandalaos-feasibility-roadmap.md`. Qubes compartmentalization (Phase 1 of that roadmap) becomes relevant only when we need per-VM isolation for the policy engine itself. DEVICE_SYNC can later adopt the same OPA policy grammar as its "Dharma layer" — one Rego dialect across projects.

---

## Reality-adjusted v0 (2026-09-13)

See `CURRENT_REALITY_2026-09-13.md` §4 for the canonical version.

- **Feasibility answered (PASS):** Tetragon v1.7.1 ran in the Sovereign VM
  (kernel 6.18.50, BTF present); the `observe-etc-shadow` TracingPolicy
  loaded and captured `security_file_open` hits from `unix_chkpwd`/`cat`,
  plus process-exec events (16 events / 12 s). Overhead 0.03 % CPU idle,
  66 MB RSS — far inside the ≤2 %/≤200 MB budget. Cleanly removed after.
- **v0 scope (shape C):** observe-only over existing telemetry — (1)
  `/etc/shadow` access, (2) sandbox-denial / undeclared-spawn events from
  the runner and bus, (3) process-egress observation once the decision
  layer exists. Enforcement stays on the shipped seams (bwrap/Landlock
  runner); no blocking without a zero-false-positive window (cardinal rule
  unchanged).
- **Deferred to the next pass:** the original three (egress block, shadow
  write block, crypto-miner), Falco detection breadth, the OPA/Cedar consent
  layer, Prometheus/node-exporter, and Nix packaging of Tetragon.
- **Open engineering gap:** the bridge — Tetragon/runner/bus events → WM
  (telemetry galaxy or bus) → a policy evaluation point. Collection is
  cheap (proven); the bridge is the work.
- **Week mapping:** W1 now = dashboard over the existing vector (thread 3);
  W2 = observe policies + decision records in the galaxy; W3 = first narrow
  Tetragon enforcement after its observation window; W4 = WM read-back of
  dims 6/7 (already partially live via `dharma.status` / `karma.report`).
