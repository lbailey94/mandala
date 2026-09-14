# MandalaOS → WM v7: Landlock v0 as the first kernel-ring realization (2026-08-29)

The 2026-08-28 audit table marked "OS-level (eBPF/Qubes/seL4, SutraCode)" as
deferred-by-design. Update: v7's Landlock v0 (crates/wm-mcp/src/landlock_sandbox.rs,
commit aad623d) delivers the first kernel-enforced ring — write-class FS rights
confined to the store root via the Linux LSM, probe-ladder ABI matching (enforced
at ABI v8), EffectRow.sandbox declared as the per-tool restricted-thread seam
(Koka-enforcement pathway, Phase C's spiritual successor).

Layer mapping after this change:
- Rings (compartments): mandala.rs (sandbox/production/secure) — process layer
- Kernel ring: Landlock v0 — the store root as the innermost ring
- Effect types: EffectRow + sandbox declaration — compile/audit layer
- Harmony/Lakshmi: wm-substrate (7-dim) — resource layer
- Dharma/Karma/Yama: wm-governance — dispatch pipeline layer
- Deferred: eBPF+OPA (lakshmi-yama-sprint-plan), seL4 (more viable now — MCS
  RISC-V verified, AArch64 confidentiality proof Aug 2026), SutraCode.

Inter-device note: mesh-received content should land in a peer-scoped
compartment with mesh provenance + trust assignment (v8.1 groundwork shipped
2026-08-29) — rings federate per-peer, not globally.
