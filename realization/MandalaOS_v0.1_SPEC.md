> **Reality check 2026-09-13:** speculative pre-Rust spec; component
> statuses are stale. Current canonical state:
> `CURRENT_REALITY_2026-09-13.md`.

# MandalaOS v0.1 — Specification

**Version:** 0.1.0 | **Date:** 2026-05-15 | **Status:** Draft | **Tag:** [Speculative]

## 1. Executive Summary

MandalaOS is a "philosophical operating system" — a set of computational primitives for civilizational-scale governance, resource coordination, and ethical deliberation. This specification maps existing WhiteMagic primitives to MandalaOS modules and identifies gaps requiring new development.

## 2. Kernel Concepts — WhiteMagic → MandalaOS Mapping

| Concept | WhiteMagic Primitive | MandalaOS Role | Gap |
|---------|---------------------|---------------|-----|
| Dharma Engine | `core/whitemagic/dharma/` | Runtime ethical evaluation | Multi-agent consensus |
| PRAT Dispatch | `dispatch_table.py` | Action framework (479 tools) | Cross-system auth |
| Karma Ledger | `karma_ledger.py` | Immutable audit log (Merkle) | Multi-party aggregation |
| Harmony Vector | `harmony/vector.py` | System health scoring (7-dim) | Cross-system homeostasis |
| Gana Council | 28 Gana meta-tools | Multi-perspective deliberation | Voting/veto protocol |
| Corpus Callosum | `corpus_callosum.py` | Bicameral reasoning bridge | Multi-hemisphere scaling |
| Galactic Memory | 5D holographic memory | Persistent experience store | Federation protocol |
| Dream Artifacts | `dream_artifacts.py` | Creative consolidation | Multi-agent dreaming |

## 3. Module Boundaries

```
MandalaOS
├── ethics/         (Dharma Engine, Karma Ledger, Voice Audit)
├── action/         (PRAT dispatch, Tool registry, Cross-system auth)
├── deliberation/   (Gana council, Voting, Corpus Callosum)
├── health/         (Harmony Vector, Homeostasis, Neurotransmitters)
├── memory/         (Experience buffer, Galactic map, Dreams)
└── coordination/   (Resource ledger, Merge evaluator, Convergence tracker)
```

## 4. API Contracts (Summary)

- `POST /dharma/evaluate` — Evaluate proposed action against ethical rules
- `POST /prat/dispatch` — Invoke a tool through the 8-stage pipeline
- `POST /gana/council` — Convene a multi-Gana deliberation
- `GET /harmony/vector` — Current system health state
- `POST /memory/store` — Store an experience in galactic memory
- `POST /resource/allocate` — Allocate resources between agents

## 5. Executable Prototype

```python
# Minimal MandalaOS kernel — bridges WhiteMagic to MandalaOS concepts
from whitemagic.dharma.karma_ledger import get_karma_ledger
from whitemagic.tools.unified_api import call_tool
from whitemagic.core.bridge.gana import gana_invoke

class MandalaKernel:
    def evaluate_action(self, tool, declared, params):
        ledger = get_karma_ledger()
        debt_before = ledger.get_debt()
        result = call_tool(tool, params)
        ledger.record(tool=tool, declared_safety=declared,
                      actual_writes=len(result.get("data", {}).get("writes", [])),
                      success=result["status"] == "success")
        return {"result": result, "debt_before": debt_before, "debt_after": ledger.get_debt()}

    def deliberate(self, proposal, ganas=None):
        if ganas is None: ganas = ["dharma", "wisdom", "courage", "love"]
        responses = {g: gana_invoke(f"{g}.counsel", {"proposal": proposal}) for g in ganas}
        return {"proposal": proposal, "gana_responses": responses}
```

## 6. Gaps Requiring New Development

| Gap | Priority | Effort |
|-----|----------|--------|
| Multi-agent voting protocol | P1 | 2-4 weeks |
| Cross-system authorization | P1 | 2-3 weeks |
| Resource ledger | P2 | 2-3 weeks |
| Merge evaluator | P2 | 3-4 weeks |
| Convergence tracker | P3 | 1-2 weeks |

## 7. Relationship to WhiteMagic

MandalaOS is the **north star** — the long-horizon vision. WhiteMagic is the **first implementation** — a single-system prototype of every kernel concept. The mapping is 1:1: Dharma→Ethics, PRAT→Action, Gana→Deliberation, Harmony→Health, Galactic Memory→Memory.
