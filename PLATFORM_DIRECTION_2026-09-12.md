> **Status update 2026-09-13:** §6 decisions 1–3 are resolved (Sovereign
> build-now; real Nix installed; naming unchanged). Verified build state,
> Yama v0 decision, and the supersession map:
> `CURRENT_REALITY_2026-09-13.md`.

# MandalaOS Platform Direction — Reconciliation (2026-09-12)

**Status:** proposal for Lucas review — resolves the conflict between
`implementation/QUBES_PATH_ASSESSMENT_2026-09-10.md` (Qubes product layer for v0)
and `MANDALA_NIXOS_SOVEREIGN_EDITION.md` + `MANDALA_NIXOS_FLAKE_SPEC.md` (NixOS pivot).

---

## 1. Why this doc exists

The two most recent platform docs disagree, and neither is wrong — they describe
different **assurance levels** and cost envelopes as if they were one decision:

- **Sep 10:** MandalaOS Workstation v0 = SecureDrop-style product layer on stock
  Qubes 4.3.1 (hypervisor isolation, 2–4 engineers/quarter). NixOS + microVMs for
  headless Node/Edge.
- **Sep 12:** "Why NixOS beats Qubes" — NixOS + Bubblewrap/Landlock as the
  lightweight sovereign desktop, ARM-friendly, buildable now.

Resolution: keep both, name the trust boundaries honestly, and pick which one is
the **first buildable artifact**.

## 2. The honest threat-model comparison

| Form | Isolation mechanism | What it actually contains | ARM/edge | Build cost |
|---|---|---|---|---|
| Qubes product layer | Xen hypervisor; each qube a VM | Kernel/OS compromise contained per-qube (modulo Xen escapes) | No (x86 only) | Heavy; VT-x/VT-d hardware, per-release rebase |
| NixOS + microVMs | KVM per agent | Same class as Qubes for headless workloads | Yes (KVM) | Medium; headless-centric |
| NixOS + bwrap/Landlock (Sovereign) | **Shared kernel**: namespaces + Landlock LSM + seccomp | Misbehaving tools/agents with declared effects — the same trust class as browser sandboxes and systemd services. Does **not** contain kernel exploits or a hostile local user. | Yes | Light; runs on old laptops and ARM SBCs |

**Correction to the record:** "Qubes-level compartment security with near-zero
overhead" is not achievable in a single kernel. The Sovereign Edition's value is
*containment of tool/agent behavior* — exactly where WM's governance layer already
bites — plus reproducibility and rollback. It is not hypervisor-class isolation.
State it as containment, never as "Qubes-level."

## 3. Reconciled strategy — three forms, one governance layer

1. **MandalaOS Workstation (high-assurance):** Qubes product layer per the Sep 10
   plan; stays gated on the R&D trigger (funding + hardware).
2. **MandalaOS Sovereign Edition (build now):** NixOS flake + bwrap/Landlock + WM
   systemd service. Matches WM's shipped Landlock v0
   (`crates/wm-mcp/src/landlock_sandbox.rs`, `WM_LANDLOCK=1`). Tier A/B/C hardware.
   This is the first buildable MandalaOS artifact.
3. **MandalaOS Node/Edge:** NixOS + one microVM per agent (KVM). Headless fleets.

All three run the same core: `wm-governance` (dharma gate, karma ledger, scope
tokens) + `wm-sangha` transport + `wm-substrate` telemetry. The forms differ in
chassis, not in the governance layer.

## 4. Verified corrections to the record (checked 2026-09-12, WMv9 @ fd673cb)

1. **`pkgs.whitemagic` does not exist.** The flake must package WM from source
   (`rustPlatform.buildRustPackage` over the WMv9 tree; binary `wm`, with
   `serve` and `daemon` subcommands both real).
2. **`landlock-sandbox` is not a nixpkgs package.** Real options: `landrun`
   (nixpkgs; Landlock v5, filesystem + TCP), `landlock-sandboxer` (NUR; kernel
   sample), or plain `bwrap`. WM's Rust path uses the `landlock` crate.
3. **"Landlock ABI v4" is stale.** WM's crate ladder probes ABI V1–V9
   (`landlock_sandbox.rs:249`); the local 7.0 kernel is far newer.
4. **`yama-gatekeeper.nix` is fiction as described** — Nix cannot express
   "declarative syscall interception." Real mechanisms: systemd sandboxing
   (`SystemCallFilter`, `Protect*`), WM's Landlock (`WM_LANDLOCK=1`), AppArmor
   profiles shipped as text, and (for the eBPF+OPA sprint) Tetragon/OPA out of
   band. Re-specify the module around these.
5. **SX1262 LoRa has no mainline kernel driver.** Userspace spidev/out-of-tree is
   the reality; mesh work lives in `~/Desktop/projects/OFFGRID_MESH_TERMINAL`.
   `offline-mesh.nix` = userspace mesh daemon + DT overlay, not "LoRa drivers."
6. **"Vulkan zero-copy page sharing across bicameral models"** is aspirational —
   llama.cpp does not share model pages across processes at that level.
7. **Perf table numbers** (420–580 MB idle, 3.8–5.2 s boot, 4.2 GB store) are
   **targets**, not measurements. Keep them in a targets row; measure post-build.
8. **The two docs list different module sets.** Canonical set:
   `kernel-hardening.nix`, `landlock-isolation.nix`, `whitemagic-service.nix`,
   `zram-swap.nix`, `arm-hardware.nix` (future: `offline-mesh.nix`,
   `local-ai.nix` after userland plans land).

## 5. WM status corrections (README table)

- **Typed karma debt: landed** — F-3 (`a9f25ce`): `KarmaEntry` carries
  `declared_writes`/`actual_writes`/`debt_delta`; deep chain verify default.
- **Engagement tokens: enforced on mesh locks** — F-1 (`fc11ca2`); dispatch-level
  `EffectRow.invokes` authorization remains the open piece.
- **Landlock v0: shipped** — opt-in `WM_LANDLOCK=1`; outcome graded by
  `wm doctor`; not yet enabled fleet-wide.
- **Harmony Vector: correction** — `wm-substrate` ships a **hardware**
  `HarmonyVector` (cpu/mem/swap/thermal/battery/disk + Guna tag). The **7-dim
  OS-level vector** (fairness/responsiveness/throughput/stability/energy/dharma/
  karma_debt) is **spec-only** (`feasibility/harmony-vector-spec.md`), unimplemented.

## 6. Open decisions

1. Confirm Sovereign Edition as the "build now" v0 form, with Qubes staying the
   funded high-assurance track. *(Recommend yes.)*
2. Nix install on the dev machine for eval/build (`nix flake check`, VM build)?
   Without it we can scaffold but not validate. Options: Determinate Systems
   installer, distro package, or `nix-portable`.
3. Naming: keep "Sovereign Edition" as the NixOS form, or fold under
   "MandalaOS v0" with Qubes as "v0-HA"?
