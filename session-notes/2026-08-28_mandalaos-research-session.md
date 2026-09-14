# MandalaOS Research Session — 2026-08-28 (evening)

**Recorded for:** the canonical WhiteMagic v5 store (via `wm ingest`) and as a project note for MANDALA_OS.

## What happened
1. **Project review** — read the full MANDALA_OS corpus (design spec, feasibility era, implementation exports, narrative).
2. **Internal sweep** (3 parallel explorations) — WHITEMAGIC code/docs; VIOLET, DEVICE_SYNC, XPRIZE, NARRATIVE_HOME; CODEX_VAULT/Antigravity origins.
3. **Online research pass** — seL4/rust-sel4 status, eBPF runtime security (Falco/Tetragon/Tracee), effect systems (Koka/OCaml eio/Unison), agent-OS wave (agentOS, OctantOS, AWS AgentCore Policy + Dogwood, AOS papers), Qubes 4.3.1, Redox.
4. **Consolidation** — 34 files copied into MANDALA_OS (originals untouched): `narrative/` (2 Grok convos), `design/` (concept genealogy, vaya-vida page), `implementation/` (5 Windsurf + 1 Claude session), `feasibility/antigravity-brain_fe5ed4b1/` (working history), `realization/` (7 WM-side Mandala specs). Log: `CONSOLIDATION_LOG.md`.
5. **New docs written** — `feasibility/harmony-vector-spec.md` (OS-level 7-dim vector), `implementation/lakshmi-yama-sprint-plan.md` (2026 eBPF+OPA plan), `implementation/wm-rust-effect-port-plan.md` (Rust effect-accounting gap).

## Key findings
- **WM is more complete than the folder implied.** The governance/mind layer shipped in Rust v5: `wm-core/effects.rs` (Koka-inspired EffectRow: Resource/Capability/CostEstimate, brain-wave gating, conflict checks), CI release gate `wm-mcp/effect_audit.rs`, `wm-governance` (karma ledger hash chain + dharma gate), `wm-memory/mandala.rs` (MandalaManager compartments), `wm-core/gana.rs` (28 Ganas), `wm-substrate` (HarmonyVector/Lakshmi), `wm-bicameral`.
- **The one real regression:** `karma_ledger.rs` still has only `mismatch: bool` — per-entry *typed* declared-vs-actual debt accounting is missing. Fix plan: `implementation/wm-rust-effect-port-plan.md` (reuses EffectRow; no new types).
- **By design, not started:** Koka enforcement (Phase C, stub only), dashboard (site backups only), OS-level work (explicitly deferred in INFRASTRUCTURE_THESIS).
- **External (Aug 2026):** seL4 MCS verified (RISC-V) + confidentiality proof (AArch64) done; direct competitors agentOS (seL4) and OctantOS (Rust kernel) building the Bindu vision; Yama layer commoditizing via AWS AgentCore Policy (Cedar, GA Mar 2026) + Dogwood (temporal policies); Koka still research-grade.
- **MCP memory servers are read-only** (`--readonly` governance). The working write path to WM's own systems is the `wm` CLI (`wm ingest`).

## Next steps (agreed)
1. Restore typed effect accounting in Rust `wm-governance` (port plan).
2. Run the Lakshmi/Yama eBPF+OPA sprint (gated by the HV spec).
3. Qubes/seL4 phases wait for agreed entry conditions — no new planning needed.
