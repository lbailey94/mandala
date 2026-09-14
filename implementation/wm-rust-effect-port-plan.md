# Port Plan: Typed Effect Accounting (Phase A gap) → Rust `wm-governance`

> **EXECUTED — landed 2026-09-12 as PLAN_F F-3 (`a9f25ce`).** `KarmaEntry` now
> carries `declared_writes`/`actual_writes`/`debt_delta` (`karma_ledger.rs`), the
> chain-deep verify is the default, and `wm doctor` §9 grades it. This document
> is retained as the historical plan; verification steps in §"Verification" are
> satisfied by the WMv9 test suites.

**Status:** Executed (retained for history)

## Corrected premise

Phase A did **not** die in the Rust rewrite. The Koka-inspired effect system is shipped in Rust, in a more granular form than the Python original:

- **`wm-core/src/effects.rs`** — `EffectRow` { reads, writes, invokes, spawns, destructive, cost }, built from `Resource` (Galaxy, KarmaLedger, DharmaRules, SearchIndex, VectorStore, Network, Filesystem, Process, Inference, Session, EventBus) and `Capability` enums. Brain-wave gating (`is_available_in`) and parallel-conflict checks included.
- **`wm-mcp/src/effect_audit.rs`** — a CI release gate: static declaration checks, a behavioral sweep asserting "no tool mutates without declaring it", and mutator spot-checks. This is Phase A's *enforcement half*, shipped.

**The actual gap is narrow:** `wm-governance/src/karma_ledger.rs` records only `mismatch: bool` — per-entry debt is not weighted by *which* declared effect was violated, unlike the archived Python (`EffectType` weights: undeclared DESTRUCTIVE 2.0, NETWORK 1.5, LOCAL_WRITE 1.0; declared-but-unused 0.1; OBSERVATION exempt).

## Target: reuse EffectRow, add delta accounting

No new types. Extend `KarmaEntry` (in `karma_ledger.rs`) to carry the declared row and the observed delta:

```rust
use wm_core::effects::EffectRow;

/// Per-resource severity weights for undeclared *actual* effects.
/// Mirrors the archived Python EffectType table.
pub fn undeclared_debt(actual: &Resource) -> f32 {
    match actual {
        Resource::Process | Resource::Filesystem => 2.0,   // DESTRUCTIVE class
        Resource::Network => 1.5,                           // NETWORK class
        Resource::Galaxy(_) | Resource::SearchIndex
            | Resource::VectorStore | Resource::KarmaLedger
            | Resource::EventBus | Resource::Session => 1.0, // LOCAL_WRITE class
        Resource::DharmaRules | Resource::Inference => 0.5, // read/invoke-only
    }
}

impl KarmaEntry {
    /// Declared effects at call time (from the tool registry's EffectRow).
    pub declared: EffectRow,
    /// Actually-observed writes (from the behavioral sweep / dispatch audit).
    pub actual_writes: Vec<Resource>,
    /// Debt for this entry: sum of undeclared_debt over actual_writes
    /// not covered by declared.writes; 0.1 per declared write not performed.
    pub debt_delta: f32,
}

impl KarmaLedger {
    pub fn record_with_effects(
        &self,
        tool: &str,
        success: bool,
        guna: Guna,
        declared: &EffectRow,
        actual_writes: &[Resource],
    ) -> Result<KarmaEntry>;
}
```

**Backward compatibility:** `record()` remains, deriving `declared = EffectRow::pure()` (or from the registry when available) and `actual_writes` from the existing bool mismatch path, so current call sites and tests stay green.

## Integration points

1. **`wm-mcp` dispatch hook** — the per-tool `EffectRow` already exists in the registry; pass it through to `record_with_effects()`.
2. **`effect_audit.rs` behavioral sweep** — it already computes *actual* writes per tool; expose that result to the ledger so `actual_writes` is measured, not guessed.
3. **`wm-substrate`** — feed `effect_mismatch_count` into the karma-debt dim of the harmony vector (`harmony-vector-spec.md` dim 7).

## Steps (ordered, each independently testable)

1. Add `undeclared_debt()` + unit tests (weights table, coverage semantics).
2. Extend `KarmaEntry` with `declared`/`actual_writes`/`debt_delta`; LMDB round-trip test. Keep `mismatch` as derived (`!undeclared.is_empty()`) for one release.
3. Add `record_with_effects()`; reimplement `record()` on top.
4. Wire `wm-mcp` dispatch → `record_with_effects()` using the registry `EffectRow`; new test: READ-declared tool that writes accrues 1.0.
5. Expose the audit sweep's observed writes to the ledger (shared helper in `wm-mcp` or a small `wm-core` API).
6. Substrate karma-debt dim update.

## Verification

- `cargo test -p wm-governance -p wm-mcp` — all existing + new tests green, including the effect-audit release gate.
- Manual: issue one read tool that performs a write; confirm `debt_delta == 1.0` and the harmony-vector karma dim drops.

## Explicit non-goals

- **Phase C** (Koka compile-time enforcement) stays stubbed — this plan completes runtime *accounting* only.
- No ledger schema rewrite: new fields are additive; the SHA-256 chain history remains valid.
- No new effect taxonomy — `EffectRow` is canonical.
