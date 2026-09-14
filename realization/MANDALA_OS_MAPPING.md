> **Archived 2026-07-12**: Fully implemented or superseded. See `docs/message_board/` for active strategies.
> **Reality check 2026-09-13:** mapping statuses are pre-Rust; verified
> current state: `CURRENT_REALITY_2026-09-13.md`.

# MandalaOS → WhiteMagic System Mapping

**Date**: 2026-07-06
**Purpose**: Map every MandalaOS concept to existing WhiteMagic code/systems, identify gaps, and track archive sources.

---

## 1. Original MandalaOS Vision (from CODEX/LIBRARY/---MandalaOS.txt)

The original Grok conversation (Sep 2025) proposed a full philosophical OS with two parts:
- **Part I**: Operating System Design (kernel, architecture, resource management, ethics, UI)
- **Part II**: Coding Language Design (SutraCode — effect system, karma management, gnosis)

### MandalaOS Module → WhiteMagic Code Mapping

| MandalaOS Module | Role | WhiteMagic Implementation | File/Path | Status |
|---|---|---|---|---|
| **Bindu (Kernel)** | Minimalist core, flow scheduler | PRAT dispatch pipeline (8-stage) | `tools/dispatch_table.py`, `tools/prat_router.py` | **Operational** |
| **Tiferet Engine** | Self-balancing, guna tagging | Harmony Vector (7-dim), Yin-Yang tracker | `core/harmony/vector.py`, `core/harmony/yin_yang.py` | **Operational** |
| **Vishnu Aspect** | Resilience, checkpointing, journaling | Dream cycle, session checkpoints, WAL | `core/intelligence/dream_*.py`, `core/consciousness/session_*.py` | **Operational** |
| **Harmony Vector** | Real-time system health | Harmony Vector (7-dim health scoring) | `core/harmony/vector.py` | **Operational** |
| **Ganas (Modules)** | Core service modules | 28 Gana meta-tools (PRAT) | `tools/prat_mappings.py`, `tools/gana_forge.py` | **Operational** |
| **Koshas (Layers)** | Layered abstraction | 5-layer architecture (substrate→tools→core→interfaces→config) | `config/paths.py`, `interfaces/` | **Operational** |
| **Gnosis Portals** | Introspection at each layer | `gnosis` tool, `capabilities`, `explain_this` | `tools/handlers/introspection.py` | **Operational** |
| **Indra's Net (IPC)** | Async message queues, pub/sub | GanYingBus (event bus) | `core/bridge/gan_ying_bus.py` | **Operational** |
| **Lakshmi (Monitor)** | Resource fairness, harmony metrics | GreenScore telemetry, Harmony Vector | `core/monitoring/green_score.py`, `core/monitoring/telemetry.py` | **Operational** |
| **Prana Allocation** | Dynamic resource balancing | Token economy, budget enforcement | `core/consciousness/token_economy.py` | **Operational** |
| **Samsara Patterns** | Cycle detection | Dream cycle, alchemical cycle | `core/intelligence/dream_synthesis.py` | **Operational** |
| **Dharma Engine (Yama)** | Kernel-level ethical interception | Dharma rules engine, 8-stage pipeline | `dharma/`, `tools/middleware.py` | **Operational** |
| **Karma Management** | Effect tracking, audit trail | Karma Ledger (Merkle, Ed25519, XRPL anchor) | `dharma/karma_ledger.py`, `dharma/karma_anchor.py` | **Operational** |
| **Malkuth Veil (UI)** | Adaptive, transparent interface | Next.js website, dashboard, CLI | `interfaces/`, `apps/site/` | **Operational** |
| **SutraCode** | Effect-typed language | Not implemented (vision only) | — | **Gap** |
| **Karmic<T,E> types** | Value + effects tracking | Karma Ledger records effects per tool call | `dharma/karma_ledger.py` | **Partial** |

---

## 2. Current MandalaOS Spec (docs/spec/MANDALA_OS.md)

The current spec (Apr 2026) is a more practical NixOS-based design:

| Spec Component | WhiteMagic Implementation | Status |
|---|---|---|
| **NixOS substrate** | Not implemented | **Gap** — spec only |
| **Mandalas (compartments)** | Shelter isolation tiers (5-tier) | **Partial** — `security/shelter.py` has isolation, but not NixOS-based |
| **mandala-dharmad** | Dharma rules engine | **Operational** — `dharma/` module |
| **mandala-karmad** | Karma Ledger (Merkle-sealed) | **Operational** — `dharma/karma_ledger.py` |
| **mandala-harmonyd** | 7-dim health metrics | **Operational** — `core/harmony/vector.py` |
| **mandala-cbd** | Circuit breaker for tool calls | **Operational** — `security/security_breaker.py`, `tools/middleware.py` |
| **Attestation** | Ed25519 audit signing, model signing | **Partial** — `security/audit_signing.py`, `security/model_signing.py` |
| **Default-deny egress** | Not implemented at OS level | **Gap** — Dharma rules can block, but not network-level |
| **mandala-ctl CLI** | `wm` CLI exists | **Partial** — `cli/` has commands, but no mandala management |
| **TPM measurement** | Not implemented | **Gap** — future |

---

## 3. Windsurf Prototype Plans (from WindsurfRips)

The Windsurf conversations produced a phased prototype plan:

| Phase | Goal | WhiteMagic Equivalent | Status |
|---|---|---|---|
| **Phase 1: Simulation (Maya)** | Tauri-based Mandala UI | Next.js website + dashboard | **Partial** — website exists, no radial UI |
| **Phase 2: Monitoring (Lakshmi)** | eBPF-based telemetry | Telemetry system + GreenScore | **Operational** (software-level, not eBPF) |
| **Phase 3: Ethical Layer (Yama)** | OPA/qrexec policy interception | Dharma rules engine | **Operational** (software-level, not kernel) |
| **Phase 4: Language Spike** | SutraCode compiler | Not started | **Gap** |
| **Phase 5: Bindu Core** | seL4/Redox microkernel | Not started | **Gap** |

### Hybrid Stack Analysis Mapping

| Tech | Guna Alignment | MandalaOS Purpose | WhiteMagic Equivalent |
|---|---|---|---|
| **Astro** | Sattva | Documentation, Gnosis Portals | `docs/`, `llms.txt` |
| **Next.js** | Rajas | Dashboard, interactive agents | `apps/site/` (Next.js) |
| **Tauri** | Vayu | Lightweight utility tools | Not implemented |
| **Electron** | Prithvi | Heavy desktop tools | Not implemented |

---

## 4. Archive Sources

| Source | Location | Content |
|---|---|---|
| **Original MandalaOS text** | `CODEX/LIBRARY/---MandalaOS.txt` (1660 lines) | Full OS + SutraCode design from Sep 2025 Grok conversation |
| **MandalaOS v0.1 Spec** | `docs/spec/MANDALA_OS.md` (191 lines) | Practical NixOS-based spec (Apr 2026) |
| **Archive v0.1 Spec** | `whitemagic-archives/2026-05_may/other/MandalaOS_v0.1_SPEC.md` | Earlier version with WhiteMagic→MandalaOS mapping table |
| **Feasibility Roadmap** | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_mandalaos-feasibility-roadmap.md` | Qubes vs Linux vs App Simulation analysis |
| **Hybrid Stack Analysis** | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_hybrid-stack-analysis.md` | eBPF + Tauri/Next.js/Astro/Electron mapping |
| **Sprint Plan** | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_prototype-sprint-plan.md` | 4-week prototype sprint |
| **Implementation Plan** | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_implementation_plan.md` | Document audit + feasibility steps |
| **Grok: Kabbalistic AI Golems** | `CODEX/Grok/imported/2026-01-31_grok_Kabbalistic_AI_Golems_Meet_MandalaOS_43a4ea45.md` | Comparison with Mat Moura's OpenClaw golem project |
| **Grok: Whitemagic in Mandala OS** | `CODEX/Grok/imported/2026-03-09_grok_Whitemagic_Project_in_Mandala_OS_71bea6c3.md` | Grok's recollection of WhiteMagic as "mind" of MandalaOS |
| **Grok: Mandala Civilization** | `CODEX/Grok/imported/2026-03-04_grok_Mandala_Civilization_Regenerative_Conscious_Future_d463c04c.md` | Civilizational vision |
| **OpenCode convos** | `opencodeconvos/writing-creative/Read full MandalaOS texts __general subagent_.md` | Full text reading session |
| **Archive strategy** | `whitemagic-archives/2026-04_april/strategy/MANDALA_OS.md` | Earlier version of the spec |
| **SFW2 spec** | `docs/SFW2/MandalaOS_v0.1_SPEC.md` | SFW2 grant application version |
| **CODEX website text** | `CODEX/WEBSITES/vaya-vida/writing3/mandalaos.md` | Website writing draft |
| **alltexts** | `alltexts/2_AI_Computing_Systems/mandalaos.txt` | Categorized copy |

---

## 5. Gap Analysis

### What WhiteMagic already has (no MandalaOS needed):
- **Dharma Engine** → `dharma/` module with rules, profiles, 8-stage pipeline
- **Karma Ledger** → Merkle-chained, Ed25519-signed, XRPL-anchored audit trail
- **Harmony Vector** → 7-dim health scoring with rolling window
- **Ganas** → 28 Gana meta-tools mapped to 587 dispatch entries
- **Gnosis Portals** → `gnosis`, `capabilities`, `explain_this` tools
- **Indra's Net (IPC)** → GanYingBus event bus with Rust cascade backend
- **Shelter (isolation)** → 5-tier isolation system
- **Circuit breaker** → `security_breaker.py` with rate limiting, anomaly detection
- **Audit signing** → Ed25519 signatures on every audit record
- **Model signing** → OMS-compatible model provenance

### What MandalaOS would add (gaps):
1. **NixOS declarative configuration** — pin all packages, single source of truth
2. **Mandala compartments** — per-workload namespace + cgroup isolation
3. **eBPF kernel-level monitoring** — syscall interception at kernel speed
4. **TPM attestation** — hardware root of trust
5. **Default-deny network egress** — per-mandala allowlists
6. **mandala-ctl CLI** — compartment lifecycle management
7. **SutraCode** — effect-typed language with karma management
8. **Reproducible builds** — SLSA level 3+ provenance

### Recommended near-term actions:
1. **Publish a NixOS `configuration.nix`** that runs Dharma + Karma as systemd units (spec says this is the 6-month goal)
2. **Docker/Podman prototype** — lighter than NixOS, demonstrates mandala concept
3. **eBPF probe prototype** — Falco rules that map to Dharma rules
4. **Keep the spec current** — update with WhiteMagic v24 features
