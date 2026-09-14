# MandalaOS v0.1 — Cognitive Compartment Architecture

**Version**: 0.1.0
**Date**: 2026-07-31
**Status**: Active — implementation wired across Shelter, Dharma, and Karma systems

---

## 1. Overview

MandalaOS is WhiteMagic's compartment-based execution architecture. It provides
progressive isolation, per-compartment ethical governance, and karmic effect
tracking for agentic AI operations.

The name draws from the Sanskrit *mandala* — a sacred circle representing
cosmic order. Each compartment is a self-contained execution space with its
own Dharma profile, Karma scope, and capability set.

### Design Principles

- **Progressive isolation**: 5 tiers from thread-level to WASM sandbox
- **Per-compartment Dharma**: Each shelter carries its own ethical rules profile
- **Karmic scoping**: Effects are tracked per-shelter, enabling debt accounting
- **Template-driven creation**: Pre-configured templates for common use cases
- **Graceful degradation**: Falls back to lighter tiers when heavier isolation unavailable

---

## 2. Shelter Tiers (Isolation)

| Tier | Name | Mechanism | Use Case |
|------|------|-----------|----------|
| 0 | THREAD | Python ThreadPool + resource limits | Default tool execution |
| 1 | NAMESPACE | Linux unshare + chroot | Untrusted code execution |
| 2 | CONTAINER | Rootless podman/nerdctl | Untrusted packages |
| 3 | MICROVM | Firecracker / Cloud Hypervisor | Strong isolation workloads |
| 4 | WASM | wasmtime (WASI) | Portable sandboxed compute |

Selection: `auto` picks the heaviest available tier. Configurable via
`WM_SHELTER_TIER` environment variable.

---

## 3. Shelter Templates

| Template | Dharma Profile | Network | FS | Resources | Description |
|----------|---------------|---------|-----|-----------|-------------|
| `research` | creative | read | /tmp rw | 2GB, 600s | Research with network access |
| `sandbox` | default | none | /tmp w | 512MB, 60s | Default sandboxed execution |
| `production` | secure | read | /data r | 1GB, 300s | Production read-only |
| `secure` | secure | none | none | 256MB, 30s | Maximum restriction |
| `violet` | violet | rw | /tmp+data r | 1GB, 180s | Purple-team operations |

Templates are defined in `SHELTER_TEMPLATES` in `shelter/manager.py`.

---

## 4. Dharma Profiles

Each profile is a set of declarative rules evaluated against action dicts.

| Profile | Strictness | Key Rules |
|---------|-----------|-----------|
| `default` | Moderate | Do No Harm, Transparency, Privacy Guard |
| `creative` | Relaxed | Writes allowed, privacy logged not blocked |
| `secure` | Strict | All writes blocked, external access blocked |
| `research` | Permissive | Memory CRUD allowed, privacy logged |
| `violet` | Engagement-gated | Offensive ops require engagement token |
| `economic` | Transaction-aware | Spend limits, recipient trust, rate limiting |

### 4-Tier Evaluation Model

Rules are tagged with a `DharmaTier` (L0–L3). The effective tier is determined
by the action context, and only rules at or below that tier are evaluated.

| Tier | Name | What It Adds |
|------|------|-------------|
| L0 | None | No validation (bootstrap only) |
| L1 | Basic | Keyword matching + severity scoring |
| L2 | Moderate | + Taint tracking + egress policy enforcement |
| L3 | Strict | + Formal verification intent + kernel sandboxing |

Current L2 rules:
- `tier2_block_untrusted_taint` — blocks actions with untrusted data taint
- `tier2_deny_unknown_egress` — default-deny network egress for untrusted sources

Current L3 rules:
- `tier3_strict_seccomp` — strict seccomp profile for exec/shell/subprocess

---

## 5. Karma Scoping

Each shelter has its own Karma scope. Karmic effects (declared and actual)
are tracked per-shelter via `KarmaEntry.shelter_id`.

- **Effect types**: reads, writes, network, concurrency, dharma, pure
- **Effect registry**: Auto-infers signatures for 692+ tools
- **Karmic debt**: Tracked per-shelter, can be verified via `karmic.verify`
- **Mandala compartments**: `dharma_profile` + `template` on `Shelter`

---

## 6. MCP Tools

### Shelter Management
- `mandala.create` — Create a shelter with template + tier + dharma_profile
- `mandala.status` — Query shelter status, capabilities, and karmic state
- `mandala.destroy` — Tear down a shelter and settle karmic debt
- `mandala.templates` — List available shelter templates
- `mandala.list` — List all active shelters

### Karmic Effects
- `karmic.effects` — Query declared vs actual effects for a tool/shelter
- `karmic.debt` — Query outstanding karmic debt for a shelter
- `karmic.verify` — Verify that actual effects match declared effects

### Effect Visualization
- `effect.trace` — Trace effect chain for a specific action
- `effect.visualize` — DOT/Mermaid/JSON visualization of effect graph

---

## 7. Warp Agent Integration

Warp agents carry a `dharma_profile` field that determines which Dharma rules
apply to their actions. Pre-configured warps:

| Warp | Dharma Profile | Inference Tier | Galaxies |
|------|---------------|----------------|----------|
| Researcher | research | local_large | codex, research, universal, sessions |
| Companion | standard | local_small | universal, codex, journals, tutorial |
| Guardian | strict | edge | universal |
| Dreamweaver | permissive | local_large | dreams, codex, universal, sessions |
| Diplomat | diplomatic | local_small | universal, codex |
| Evolver | research | local_small | codex, research, dreams, universal |

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    MandalaOS v0.1                    │
├─────────────┬───────────────┬───────────────────────┤
│   Shelter    │    Dharma     │       Karma           │
│   Manager    │    Rules      │      Ledger           │
├─────────────┼───────────────┼───────────────────────┤
│ 5 tiers     │ 6 profiles    │ Effect registry       │
│ 5 templates │ 4 tiers (L0-3)│ 692+ tool signatures  │
│ Per-shelter │ Per-profile   │ Per-shelter scoping   │
│ capabilities│ rules         │ Karmic debt tracking  │
├─────────────┴───────────────┴───────────────────────┤
│              Warp Agent Layer                        │
│  Researcher │ Companion │ Guardian │ Dreamweaver     │
│  Diplomat   │ Evolver   │ Custom warps              │
├─────────────────────────────────────────────────────┤
│              MCP Tool Interface                      │
│  mandala.* │ karmic.* │ effect.* │ dharma.*         │
└─────────────────────────────────────────────────────┘
```

---

## 9. Implementation Status

| Component | Status | Files |
|-----------|--------|-------|
| Shelter Manager | ✅ Complete | `shelter/manager.py` |
| Shelter Templates | ✅ 5 templates | `shelter/manager.py` |
| Dharma Rules Engine | ✅ Complete | `dharma/rules.py` |
| Dharma 4-Tier Model | ✅ L0-L3 defined | `dharma/rules.py` |
| Dharma L2 Rules | ✅ 2 rules | taint tracking, egress deny |
| Dharma L3 Rules | ✅ 1 rule | strict seccomp |
| Karma Ledger | ✅ Complete | `dharma/karma_ledger.py` |
| Effect Registry | ✅ 692+ tools | `dharma/effect_registry.py` |
| Warp Agents | ✅ 6 presets | `agents/warps.py` |
| MCP Tools | ✅ Wired | `tools/registry_defs/mandala.py` |
| Mandala Dashboard | ✅ Next.js | `/mandala` page |

---

## 10. Future Directions (v0.2+)

- **Koka effect enforcement**: Compile-time effect checking via `karmic_effects.kk`
- **Shelter chaining**: Allow shelters to spawn sub-shelters with inherited constraints
- **Formal verification**: L3 tier with SMT solver integration for safety proofs
- **Cross-shelter karma settlement**: Automatic debt reconciliation on shelter teardown
- **MandalaOS NixOS spec**: Declarative system configuration for reproducible compartments
