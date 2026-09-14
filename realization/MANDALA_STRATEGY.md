> **Archived 2026-07-12**: Fully implemented or superseded. See `docs/message_board/` for active strategies.

# MandalaOS Strategy: Synthesis & Implementation Plan

**Date**: 2026-07-06
**Status**: Strategy document for future implementation
**Related**: `MANDALA_OS_MAPPING.md`, `docs/spec/MANDALA_OS.md`

---

## 1. Executive Summary

WhiteMagic already implements 12 of 15 MandalaOS modules at the software level. The remaining gaps are not "build from scratch" — they are **wiring gaps** between existing systems. The Koka polyglot core (50 `.kk` files with typed effects) IS SutraCode. The Shelter system IS the mandala compartment system. The Karma Ledger IS the effect tracker. What's missing is connecting them more deeply.

**Three implementation phases**:
- **Phase A**: Expand Karmic types (EffectSignature) — 1-2 days
- **Phase B**: Upgrade Shelters to true Mandala compartments — 1-2 days
- **Phase C**: Wire Koka effect handlers for compile-time enforcement — 2-3 days
- **Phase D**: Mandala Dashboard UI — 1 day

**New MCP tools** this will add to the WM meta-tool:
- `mandala.create` / `mandala.execute` / `mandala.inspect` / `mandala.destroy` (shelter aliases)
- `mandala.list` / `mandala.templates` / `mandala.chain`
- `karmic.effects` / `karmic.debt` / `karmic.verify`
- `effect.trace` / `effect.visualize`

---

## 2. Karmic Types: Current State → Target State

### Current (3-level safety)

`@/home/lucas/Desktop/WHITEMAGIC/core/whitemagic/dharma/karma_ledger.py:67-82`:
```python
@dataclass
class KarmaEntry:
    tool: str
    declared_safety: str  # READ, WRITE, DELETE
    actual_writes: int
    success: bool
    mismatch: bool
    debt_delta: float
```

Only tracks writes. No network, concurrency, purity, or Dharma interaction tracking.

### Target (full EffectSignature)

```python
@dataclass
class EffectSignature:
    reads: list[str]           # state/filesystem paths read
    writes: list[str]          # state/filesystem paths written
    network: str               # none | read_only | filtered | full
    network_targets: list[str] # URLs/domains contacted
    concurrency: str           # none | shared | exclusive
    dharma: bool               # whether Dharma rules evaluated
    pure: bool                 # zero side effects
    shelter_id: str            # which mandala executed this
```

### MandalaOS Effect Type Mapping

| MandalaOS Effect | Koka Effect Module | Python Equivalent | Karma Ledger Field |
|---|---|---|---|
| `IO[Network]` | (not yet defined) | Shelter `network` capability | `network`, `network_targets` |
| `IO[State]` | `state_effects.kk` | `declared_safety` | `reads`, `writes` |
| `IO[Concurrency]` | (not yet defined) | Not tracked | `concurrency` |
| `IO[DharmaLog]` | (not yet defined) | Dharma rules engine | `dharma` |
| `Pure` | (not yet defined) | Not tracked | `pure` |
| `Karmic<T,E>` | `tool_effects.kk` | `KarmaEntry` | full `EffectSignature` |

### Implementation Steps

1. **Define `EffectSignature`** in `karma_ledger.py`
2. **Create effect registry** — map each of 587 tools to its declared `EffectSignature`
   - Auto-infer from `WRITE_TOOLS` set + shelter capabilities + Dharma rules
   - Manual overrides for special cases (browser tools = network, dream tools = state+concurrency)
3. **Expand `KarmaEntry`** with `declared_effects: EffectSignature` and `actual_effects: EffectSignature`
4. **Expand `record()` method** to compare full signatures, not just write counts
5. **New debt rules**:
   - Declared `network=none` but made network call → debt += 2.0 (deceptive)
   - Declared `pure=True` but had side effects → debt += 3.0 (severe)
   - Declared `concurrency=exclusive` but ran concurrently → debt += 1.0
6. **Add `karmic.effects` MCP tool** — query effect signatures and mismatches
7. **Add `karmic.debt` MCP tool** — per-tool, per-shelter, per-session debt reports
8. **Add `karmic.verify` MCP tool** — verify Merkle chain + effect signature integrity

### Koka-Side Extensions

Extend `@/home/lucas/Desktop/WHITEMAGIC/polyglot/whitemagic-koka/tool_effects.kk`:

```koka
effect karmic-tools
  fun dispatch-with-effects(tool-name: string, params: string,
                            declared: effect-sig): karmic-result
  fun verify-effects(declared: effect-sig, actual: effect-sig): karmic-verdict

struct effect-sig
  reads: list<string>
  writes: list<string>
  network: string
  concurrency: string
  dharma: bool
  pure: bool

struct karmic-result
  output: string
  actual-effects: effect-sig
  mismatch: bool
  debt: float64
```

New Koka files needed:
- `karmic_effects.kk` — effect signature types and comparison logic
- `network_effects.kk` — network access effect type
- `concurrency_effects.kk` — concurrency effect type

---

## 3. Shelter → Mandala Upgrade

### Current State

`@/home/lucas/Desktop/WHITEMAGIC/core/whitemagic/shelter/manager.py` already has:
- 5-tier isolation (thread → namespace → container → microvm → wasm)
- Capability-based access (filesystem_read/write, network, tools_allow, system_allow)
- Dharma checks inside shelters
- Karma logging for shelter executions
- Auto-detection of available tiers with graceful degradation

### What's Missing for True MandalaOS Compartments

| Feature | Priority | Implementation |
|---|---|---|
| Per-shelter Dharma profiles | High | Add `dharma_profile` param to `create()`, load per-shelter rule set |
| Per-shelter Karma scoping | High | Add `shelter_id` to `KarmaEntry`, filter ledger by shelter |
| Per-shelter Harmony Vector | Medium | Per-shelter health metrics in `Shelter` dataclass |
| Shelter templates | Medium | Pre-configured capability sets: "research", "sandbox", "production", "secure" |
| Shelter chaining | Medium | Output of one shelter feeds input of another via `input_data` |
| Content-addressed read layer | Low | SHA-256 content store for shelter inputs |
| Append-only write journal | Low | Journal per shelter work dir |
| `mandala-ctl` CLI | Medium | CLI wrapper in `cli/` for shelter lifecycle |

### Implementation Steps

1. **Add `dharma_profile` to `ShelterManager.create()`**
   - Load named profile (creative, secure, default, custom)
   - Each profile has different Dharma rule sets and sensitivities
   - Profiles stored in `dharma/profiles/`

2. **Add `shelter_id` to `KarmaEntry`**
   - All karma records scoped to shelter
   - `karma.report(shelter_id=...)` filters by shelter
   - Per-shelter debt tracking and forgiveness

3. **Add shelter templates**
   ```python
   SHELTER_TEMPLATES = {
       "research": {"capabilities": ["network_read", "fs_read:/data"], "tier": "container"},
       "sandbox": {"capabilities": [], "tier": "namespace", "limits": {"timeout_s": 60}},
       "production": {"capabilities": ["network_full"], "tier": "container"},
       "secure": {"capabilities": [], "tier": "microvm", "dharma_profile": "secure"},
   }
   ```

4. **Add shelter chaining**
   - `mandala.chain(shelters=[...])` — execute sequence, pipe outputs to inputs
   - Each shelter's `output.json` becomes next shelter's `input_data`

5. **Add `mandala-ctl` CLI**
   - `wm mandala create <name> --template research`
   - `wm mandala exec <name> --code "..."`
   - `wm mandala inspect <name> --artifact output.json`
   - `wm mandala destroy <name>`
   - `wm mandala list`

6. **New MCP tools** (aliases that map to shelter handlers):
   - `mandala.create` → `shelter.create` with template support
   - `mandala.execute` → `shelter.execute` with chaining
   - `mandala.inspect` → `shelter.inspect`
   - `mandala.destroy` → `shelter.destroy`
   - `mandala.list` → `shelter.status`
   - `mandala.templates` → list available templates
   - `mandala.chain` → new chaining handler

---

## 4. Koka Effect Enforcement

### Current State

- `@/home/lucas/Desktop/WHITEMAGIC/core/whitemagic/core/acceleration/koka_native_bridge.py` — Python↔Koka bridge with persistent subprocesses, circuit breakers, connection pooling
- `@/home/lucas/Desktop/WHITEMAGIC/core/whitemagic/core/acceleration/hybrid_dispatcher.py` — Adaptive routing between Python (speed) and Koka (safety) based on operation complexity
- 50 Koka `.kk` files with typed effects already defined
- `KokaCircuitDispatch` — stateful circuit breaker via Koka subprocess

### What's Missing

The Koka effect types exist but aren't **enforced** at dispatch time. The Python bridge sends JSON to Koka and gets JSON back, but doesn't compare declared vs actual effects through Koka's type system.

### Implementation Steps

1. **Create `karmic_dispatch.kk`** — new Koka module that:
   - Receives tool name + params + declared `effect-sig`
   - Dispatches to the appropriate handler
   - Captures actual effects (writes, network calls, state changes)
   - Returns `karmic-result` with mismatch detection and debt calculation

2. **Extend `KokaNativeBridge`** with `dispatch_karmic()` method:
   ```python
   def dispatch_karmic(self, tool: str, params: dict, declared: EffectSignature) -> dict:
       """Dispatch through Koka with effect tracking."""
       return self.dispatch("karmic", "dispatch-with-effects", {
           "tool": tool, "params": params,
           "declared": declared.to_dict()
       })
   ```

3. **Add `OperationProfile` entries** for karmic dispatch:
   ```python
   "karmic_dispatch": OperationProfile("karmic_dispatch", True, True, True, 0.8),
   ```

4. **Wire into PRAT router** — when `HybridDispatcher` mode is `SAFETY` or `ADAPTIVE` with high complexity, route through Koka karmic dispatch

5. **Use existing `effect_visualization.kk`** for trace trees and heat maps
   - `effect.trace` MCP tool — get effect trace for a tool call
   - `effect.visualize` MCP tool — export DOT/Mermaid/JSON visualization

---

## 5. Mandala Dashboard

### Concept

A new page at `/mandala` on the existing Next.js site showing a live view of the MandalaOS software layer.

### Data Sources (all existing MCP tools)

| Dashboard Widget | Data Source |
|---|---|
| Active mandalas (radial diagram) | `shelter.status` |
| Per-mandala Harmony Vector (radar chart) | `harmony.vector` (needs per-shelter scoping) |
| Karma debt per mandala | `karma.report(shelter_id=...)` |
| Effect flow visualization | `effect.trace` / Koka trace trees |
| Tool usage heatmap | `tool_usage_stats` (just built) |
| Dharma alerts | `dharma.alerts` |
| System health | `health_report` |

### Implementation

1. New Next.js page `apps/site/src/app/mandala/page.tsx`
2. WebSocket or SSE connection to WM MCP server for live updates
3. D3.js or React Flow for radial mandala diagram
4. Recharts for Harmony Vector radar chart
5. Effect flow graph from Koka trace data (DOT/Mermaid → React Flow)

---

## 6. Synthesis: Old Plans → Current Reality

### The Windsurf 5-Phase Roadmap (Reimagined)

| Phase | Original Plan | What We Can Do Now | Effort |
|---|---|---|---|
| **Phase 1: Simulation (Maya)** | Tauri desktop app | Next.js `/mandala` dashboard page | 1 day |
| **Phase 2: Monitoring (Lakshmi)** | eBPF probes | Harmony Vector + ToolUsageTracker + GreenScore | **Done** |
| **Phase 3: Ethical Layer (Yama)** | OPA/qrexec | Dharma rules engine + per-shelter profiles | 1 day |
| **Phase 4: Language Spike (SutraCode)** | New compiler | Koka IS SutraCode — extend effect types | 2-3 days |
| **Phase 5: Bindu Core** | seL4 microkernel | Shelter 5-tier isolation (no custom kernel needed) | **Done** |

### The Hybrid Stack Analysis (Reimagined)

| Tech | Guna | Original Purpose | Current Equivalent |
|---|---|---|---|
| Astro | Sattva | Docs, Gnosis Portals | `docs/`, `llms.txt`, gnosis tools |
| Next.js | Rajas | Dashboard, agents | `apps/site/` + new `/mandala` page |
| Tauri | Vayu | Lightweight tools | Not needed (MCP server is lighter) |
| Electron | Prithvi | Heavy desktop | Not needed |

### The Grok Conversations (Key Insights)

**Jan 2026 — Kabbalistic AI Golems**: Mat Moura's OpenClaw golem project maps the Tree of Life as an execution workflow. WhiteMagic's 28 Ganas are the system-level equivalent. The "lightning path" (Kether → Malkuth) maps to the PRAT dispatch pipeline (gana_horn → gana_wall). The "serpent path" (dissolution) maps to the Dream Cycle.

**Mar 2026 — Whitemagic in Mandala OS**: Grok recalled Lucas describing WhiteMagic as "the mind" of MandalaOS, with "Violet" as the autoimmune system. In current architecture:
- **Mind** = PRAT dispatch + Ganas + Gnosis
- **Autoimmune system** = Dharma rules + Karma Ledger + circuit breaker + anomaly detection
- **Body** = Shelter compartments + memory galaxies + GanYingBus

---

## 7. New MCP Tools Summary

Tools that will be added by this strategy:

| Tool | Gana | Purpose |
|---|---|---|
| `mandala.create` | gana_room | Create isolated mandala compartment |
| `mandala.execute` | gana_room | Execute payload in mandala |
| `mandala.inspect` | gana_room | Inspect mandala output/artifacts |
| `mandala.destroy` | gana_room | Destroy mandala |
| `mandala.list` | gana_room | List active mandalas |
| `mandala.templates` | gana_room | List available mandala templates |
| `mandala.chain` | gana_room | Chain multiple mandalas |
| `karmic.effects` | gana_hairy_head | Query effect signatures and mismatches |
| `karmic.debt` | gana_hairy_head | Per-tool/shelter/session debt reports |
| `karmic.verify` | gana_hairy_head | Verify Merkle chain + effect integrity |
| `effect.trace` | gana_ghost | Get effect trace for a tool call |
| `effect.visualize` | gana_ghost | Export effect flow visualization |

All map to the single WM meta-tool via PRAT routing.

---

## 8. Implementation Order for Next Session

1. **Fix the 169 errors + 43 exceptions** from the use-every-tool campaign first
   - This ensures the existing 587 tools are solid before adding new ones
   - Categorize fixes: missing SAFE_DEFAULTS (majority), handler signature bugs (TypeError group), missing Rust attributes (AttributeError group), connection errors (browser tools)

2. **Phase A: Karmic Types** (1-2 days)
   - Define `EffectSignature` dataclass
   - Create effect registry for all 587 tools
   - Expand `KarmaEntry` and `record()` method
   - Add `karmic.effects`, `karmic.debt`, `karmic.verify` MCP tools

3. **Phase B: Shelter → Mandala** (1-2 days)
   - Add `dharma_profile` to shelter creation
   - Add `shelter_id` to KarmaEntry
   - Add shelter templates
   - Add shelter chaining
   - Add `mandala.*` MCP tools (aliases to shelter handlers)

4. **Phase C: Koka Effect Enforcement** (2-3 days)
   - Create `karmic_effects.kk`, `network_effects.kk`, `concurrency_effects.kk`
   - Extend `KokaNativeBridge` with `dispatch_karmic()`
   - Wire into PRAT router via `HybridDispatcher`
   - Add `effect.trace`, `effect.visualize` MCP tools

5. **Phase D: Mandala Dashboard** (1 day)
   - New Next.js `/mandala` page
   - Live data from MCP tools
   - Radial diagram + radar charts + effect flow graph

---

## 9. Exercise Campaign Error Analysis

From the use-every-tool run (587 tools, 63.9% success):

### Error Categories (by count)

| Category | Count | Root Cause | Fix Approach |
|---|---|---|---|
| UNKNOWN | ~97 | Tool returned `{"status": "error"}` without error_code | Add error_code to handler responses |
| ValueError | 17 | Missing required params not in SAFE_DEFAULTS | Add to SAFE_DEFAULTS dict |
| TypeError | 15 | Handler expects `params` positional arg, not kwargs | Fix handler signatures to accept `**kwargs` |
| invalid_params | 15 | Params provided but invalid format | Fix SAFE_DEFAULTS values |
| not_found | 7 | Agent/watcher not found with default args | Add valid default IDs |
| AttributeError | 6 | Rust module missing attributes / Python API mismatch | Fix Rust bindings or add Python fallbacks |
| missing_params | 5 | Required params not provided | Add to SAFE_DEFAULTS |
| ConnectError | 3 | Browser tools need running browser | Add skip or mock for headless env |
| Other | 4 | Various single issues | Individual fixes |

### Priority Fix Order

1. **TypeError group (15 tools)** — handler signature mismatch. These are real bugs. Handlers like `handle_dream_expire()` expect `params` as a positional arg but the dispatch table calls with `**kwargs`. Fix: update handlers to accept `**kwargs` like all other handlers do.

2. **ValueError group (17 tools)** — missing SAFE_DEFAULTS. Easy fix: add entries to `SAFE_DEFAULTS` dict in `exercise_all_tools.py` and/or fix the handlers to have sensible defaults.

3. **AttributeError group (6 tools)** — Rust binding mismatches. `whitemagic_rust` module is missing `read_files_fast`, `audit_directory`, `fast_compress`. Either add these to the Rust extension or add Python fallbacks.

4. **UNKNOWN group (~97 tools)** — handlers return error without error_code. Need to audit each handler and add proper error_code fields. Many may be legitimate errors (e.g., "no data found") that just need better error reporting.

5. **invalid_params group (15 tools)** — need correct default values in SAFE_DEFAULTS.

6. **not_found group (7 tools)** — need valid default IDs for agent/watcher tools.

7. **ConnectError (3 tools)** — browser tools need a running browser. Add `WM_SKIP_BROWSER` guard or mock.

8. **Single issues (4 tools)** — individual fixes:
   - `embedding.daemon_process` — missing `memory_embeddings` table (init issue)
   - `gratitude.benefits` — timeout (slow handler)
   - `vitality` — internal_error (needs investigation)
   - `skill.invoke` / `skill.import` — missing_name/missing_path (need defaults)

---

## 10. Document Sources

All MandalaOS documents studied for this strategy:

| Source | Location | Key Content |
|---|---|---|
| Original MandalaOS text | `CODEX/LIBRARY/---MandalaOS.txt` (1660 lines) | Full OS + SutraCode design |
| Current v0.1 spec | `docs/spec/MANDALA_OS.md` (191 lines) | NixOS-based practical spec |
| Feasibility roadmap | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_mandalaos-feasibility-roadmap.md` | Qubes vs Linux vs App analysis |
| Hybrid stack analysis | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_hybrid-stack-analysis.md` | eBPF + Tauri/Next.js mapping |
| Sprint plan | `WindsurfRips/organized/ai_research/fe5ed4b1_MandalaOS_Hybrid_Prototype_prototype-sprint-plan.md` | 4-week prototype plan |
| Grok: Kabbalistic AI Golems | `CODEX/Grok/imported/2026-01-31_grok_Kabbalistic_AI_Golems_Meet_MandalaOS_43a4ea45.md` | Tree of Life execution workflow |
| Grok: Whitemagic in Mandala OS | `CODEX/Grok/imported/2026-03-09_grok_Whitemagic_Project_in_Mandala_OS_71bea6c3.md` | WM as "mind", Violet as "autoimmune" |
| System mapping | `docs/message_board/MANDALA_OS_MAPPING.md` | Module-by-module code mapping |
