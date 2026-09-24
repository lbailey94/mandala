# MANDALA_OS — Project Home (consolidated)

Copies of the MandalaOS corpus, gathered 2026-08-28 (two passes) from CODEX_VAULT, XPRIZE notebooks, the Antigravity brain dir, and WHITEMAGIC archives. **Originals remain in place** — dedupe/removal is a later, user-approved step. See `CONSOLIDATION_LOG.md`.

## What lives here
- `design/` — the v1 vision: the 1,659-line OS spec (Bindu kernel, Ganas, IndraNet, Dharma Engine, SutraCode, Gnosis Portals) + the May 2025 OpenAI "Concept Review" + the cross-conversation concept genealogy + the vaya-vida concept page.
- `feasibility/` — the v2 planning era: phased roadmap (Qubes → eBPF/OPA → Tauri → seL4), hybrid-stack analysis, prototype sprint plan, Antigravity brain working history, and **`harmony-vector-spec.md`** (the OS-level 7-dim vector, v0.1).
- `implementation/` — Phase C/D implementation export (Windsurf) + implementation plan + Windsurf/Claude sessions + **`lakshmi-yama-sprint-plan.md`** (2026 eBPF+OPA prototype) + **`wm-rust-effect-port-plan.md`** (restore Phase A effect types in Rust) + **`yama-v0-bridge-design.md`** (the observation→policy bridge; S1+S2 built 2026-09-14) + **`QUBES_PATH_ASSESSMENT_2026-09-10.md`** + **`MANDALAOS_V0_PLAN_2026-09-10.md`** + **`ADOPTION_IMPLICATIONS_2026-09-10.md`** (platform route decision, Qubes v0 execution plan, adoption/GTM implications).
- `realization/` — WHITEMAGIC-side realization docs (vision spec, v0.1 shelter spec, OS mapping, strategy, Jan 2026 handoffs).
- `narrative/` — Grok conversations (mind/autoimmune framing, Kabbalistic Golems, Mandala Civilization) and other narrative-layer references (XPRIZE "Gentle Singularity" context).

## Relationship to other projects
- **WM (WHITEMAGIC/)**: the shipped realization of the Dharma/Karma/bicameral/compartment layer (crates `wm-governance`, `wm-bicameral`, `wm-memory/src/mandala.rs`, `wm-substrate`). Principles fold in; the OS-level project does not.
- **LAKSHMI/** (in this folder): telemetry digestor + dashboard + step-0 observe policies.
- **MANDALAOS_SOVEREIGN/** (in this folder): the NixOS flake/VM build-now artifact.
- **VIOLET/**: the security/autoimmune layer concept.
- **DEVICE_SYNC/**: the IndraNet-inspired transport.
- Full cross-project synthesis (2026-09-10): `WHITEMAGIC/planning/FAMILY_SYNTHESIS_VIOLET_MANDALA_DEVICE_2026-09-10.md`.
- North star: WM runs *on* MandalaOS someday — keep that as one paragraph, not a dependency.

### WM implementation status (re-verified 2026-09-12, WMv9 @ fd673cb v9.1.3)
| MandalaOS layer | WM v9 (Rust) status |
|---|---|
| Effect system (Phase A) | **Shipped** — `wm-core/src/effects.rs` (Koka-inspired `EffectRow`), CI-gated by `wm-mcp/src/effect_audit.rs` |
| Karma ledger typed debt accounting | **Shipped** — `KarmaEntry.debt_delta` + declared/actual writes (F-3 `a9f25ce`); deep chain verify default. The old gap plan is archived in place: `implementation/wm-rust-effect-port-plan.md` |
| Dharma gate / Karma ledger chain | Shipped (`wm-governance`); `wm doctor` §9 grades chain depth |
| Harmony Vector / Lakshmi | **Hardware vector shipped** (`wm-substrate`: cpu/mem/swap/thermal/battery/disk + Guna). The **7-dim OS vector is spec-only** — `feasibility/harmony-vector-spec.md` |
| Ganas / Mandala compartments (Phase B) | Shipped (`wm-core/gana.rs`, `wm-memory/src/mandala.rs`) |
| Bicameral engine | Shipped (`wm-bicameral`) |
| Violet fold-in (scope tokens / model signing) | **Enforced on mesh locks 2026-09-12** (F-1 `fc11ca2`); dispatch-level `EffectRow.invokes` authorization still open |
| Koka enforcement (Phase C) | Stubbed by design |
| Dashboard (Phase D) | Site backups only |
| OS-level (eBPF/Qubes/seL4, SutraCode) | Landlock v0 **shipped** (`wm-mcp/src/landlock_sandbox.rs`, `WM_LANDLOCK=1`); eBPF/Qubes/seL4/SutraCode research-gated |

## Status

**Current status (2026-09-24).** Component table with the evidence date behind
each claim; older narrative below is kept as a dated record.

| Component | Repo / artifact | Version | Evidence date | State |
|---|---|---|---|---|
| gate-lite | `mandala-os` (private); public snapshot `mandalaos-gate-lite` | spec 0.3 via `continuity-receipt` 0.3.3 | 2026-09-24 (86 tests green) | built + locally tested; stub-safety guard + authorization contract + idempotency scoping added; public snapshot is the 2026-09-18 curation (refresh pending) |
| Continuity Receipt | `continuity-receipt` (public) | 0.3.3 (PyPI + crates.io) | 2026-09-23 | spec published; 0.4 hardening in flight (board #192) |
| Eval endpoint | live at `api.whitemagic.dev/eval` | — | 2026-09-24 (24 tests green; `/eval/health` ok) | hosted (evaluation infrastructure, not a product surface) |
| Sovereign | `mandalaos-sovereign` (private) | WM pin v9.2.7 | VM dogfood 2026-09-15 | built + VM tested; pin bump needs a fresh VM re-verify |
| Lakshmi | `lakshmi` (private) | — | 2026-09-24 (94 tests green) | built + locally tested; S3 live |
| WM substrate | `whitemagic` (public) | v9.2.7 | 2026-09-23 | released (all channels) |

**2026-09-14/15 record (history, kept as written).** The Sovereign VM boots and is
dogfooded (NixOS 26.05, in-guest sandbox matrix green); WM is at v9.1.5 with
typed telemetry live (1-min windows → telemetry galaxy), the Lakshmi dashboard
shipped, and step-0 observe policies writing decision records. Yama v0 is
**observe-only** with the enforcement seam (runner/bwrap/Landlock) proven.
The Yama bridge is now built through evaluation: S1 (sandbox drift →
`sandbox_observation` bus events) is **merged to main (`3384dfb`) and pushed**
(worktree removed after merge); S2 (Tetragon collector,
`MANDALAOS_SOVEREIGN/scripts/yama-collector.py`) and S3 (Lakshmi policy inputs)
landed 2026-09-14, with S3 **live in production** (sampler restarted; window
records carry the `bridge` counts block). S4 (in-guest eBPF capture) is
**executed and proven 2026-09-15**: rebuilt VM, Tetragon v1.7.1
`observe-etc-shadow` (monitor_only), collector streamed 67 events → 3 records
into the live store, and the fleet sampler transitioned `shadow.access.v1` to
`observing` (value 5, mirror-first feed); evidence in
`session-notes/2026-09-15_s4-tetragon-observe.md`.

Canonical status and supersession map: `CURRENT_REALITY_2026-09-13.md` (wins
over plans). Latest handoffs: `SESSION_HANDOFF_2026-09-13.md` (software) and
`SESSION_HANDOFF_2026-09-14.md` (website/release truth pass). Bridge design:
`implementation/yama-v0-bridge-design.md`.

Publication gates in flight: edge-galaxy **≥72 h of accumulated active soak
time** (gate redefined 2026-09-15, public: host suspend excluded and disclosed,
every other interruption resets the run; soak run at 13.9/72 h — see
`publication/GATE_EVIDENCE_PLAYBOOK.md`), Sovereign VM stranger install (≥4/5
unassisted; protocol at `publication/STRANGER_INSTALL_PROTOCOL.md`, last
dry-run 2026-09-15 — re-verification pending with the WM v9.2.7 pin; note this
protocol covers the Sovereign VM, not gate-lite), gate-lite outsider exercise
(separate protocol pending; run against a pinned candidate + real runner after
the authorization fixes), repo hygiene (sovereign pinned to v9.2.7 as of
2026-09-24). **Signing-key custody:** Option 1
register live in `security/KEY_CUSTODY_REGISTER.md` (all four copies verified
across the two cards: A1+B1 on FA99, B2+C1 on FEEC; B's identity and signature
chain proven; rotation runbook drafted; pre-release gate
`security/custody_gate.sh`; hardware-token and Shamir hardening tracked for
near-future releases).

**Latest handoff: `SESSION_HANDOFF_2026-09-13.md`** — VM dogfooding infra, WM
B1/B3 (daemon Landlock + dharma counters), Lakshmi dims 6/7, the telemetry
"edge galaxy" design, and all open workstreams with acceptance notes.

**Next-session handoff: `session-notes/2026-09-15_handoff_post-s4.md`** —
bridge read-path fix, S4 executed, Y1 actuator contract, and the open board
(publication gates, Y1.0, custody owner actions). S4 evidence:
`session-notes/2026-09-15_s4-tetragon-observe.md`.

**Active lane — gate-lite / evidence (`gate-lite/HANDOFF_2026-09-18.md`):**
receipt spec **published** (`continuity-receipt/0.1` + `0.2`, public repo),
**registry scaling fixed** (SQLite; bench-2026-09-18-sqlite evidence), anchor
policy decided (OpenTimestamps default, `ANCHORING.md`), sweep cadence
unblocked — plus the **adoption/interop lane** (W3C AI Agent Memory
Interoperability CG alignment; CG intro + mapping drafts await Lucas review;
strategy: `WHITEMAGIC/planning/ADOPTION_DEFAULT_THESIS_2026-09-18.md`).
Focused sessions on receipts/evidence should read the gate-lite handoff
first.

**Update 2026-09-24:** gate-lite emits spec **0.3** via the published PyPI
implementation (vendored copy dropped, `77821a7`); S2b pass binding
(`c310b22`), the stub-safety guard, the **authorization contract** (tenant
agent list at issuance; required single-use token at exec; durable replay),
and the idempotency-scoping fix (board #203/#204) landed. Next: a gate-lite
outsider exercise against a pinned candidate + real runner (new protocol;
`STRANGER_INSTALL_PROTOCOL.md` is the Sovereign VM gate), then public-snapshot
curation. CR spec 0.4 hardening is in flight (board #192).

### 2026-08-28 research pass (key external findings)
- **seL4 path is viable:** MCS verified on RISC-V (2026), confidentiality proof on AArch64 completed Aug 2026; `rust-sel4` 5.0 + Microkit 2.3 are mature scaffolding.
- **Direct competitors exist:** agentOS (seL4, bootable agent OS) and OctantOS (Rust kernel, capability manifests) are building the Bindu vision now — both early-stage.
- **The Yama layer is being commoditized:** AWS AgentCore Policy (Cedar, GA Mar 2026) + Dogwood (temporal policies, Aug 2026); OPA/Falco/Tetragon/Tracee are the mature open-source substrate.
- **SutraCode's bet remains unproven:** Koka still explicitly research-grade (v3.2.3); production effects = OCaml 5 eio + Rust's effect-generics initiative.
