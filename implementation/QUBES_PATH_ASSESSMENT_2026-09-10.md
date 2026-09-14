# MandalaOS Platform Path — Qubes vs NixOS vs Ground-Up

**Date:** 2026-09-10
**Status:** R&D-gated assessment (no build commitment until funding/attention triggers)
**Companion:** `MANDALAOS_V0_PLAN_2026-09-10.md`

> **Status update (2026-09-12):** reconciled with the NixOS Sovereign pivot in
> `PLATFORM_DIRECTION_2026-09-12.md`. Route A (Qubes product layer) remains the
> **high-assurance funded track**; the first buildable artifact is the NixOS
> Sovereign flake (route B refined). Threat-model caveats are in §2 of the
> direction doc.

---

## 1. Qubes OS state (verified 2026-09-10 from qubes-os.org)

| Item | State |
|---|---|
| Current stable | **4.3.1** (2026-06-11); 4.3.0 Dec 2025; 4.2 EOL 2026-06-21 |
| Base | Fedora 41 dom0; Fedora 43/44, Debian 13 templates |
| Security cadence | QSB-118 (2026-08-29, dom0 RCE in qvm-copy-to-vm error reporting), QSB-116/117 Jul–Aug, quarterly canaries (048 on 2026-09-09), XSAs mirrored within days |
| Project | ~14 core team (Invisible Things Lab + contractors), ~72k installs (≈+25 % YoY), Summit Oct 30–Nov 1 2026 Berlin, modest funding (Mullvad/FPF/ITL/Open Collective ~$75k) |
| Platform | x86_64 only; 6 GB RAM/32 GB disk minimum, 16 GB/128 GB recommended; Intel VT-x+VT-d preferred |

**Codebase shape:** ~200 repos, not one tree — `qubes-core-admin` (Python/Shell, 7.5k commits), `qubes-core-qrexec` (RPC/policy, C/Python), `qubes-gui-daemon` (C), `qubes-installer-qubes-os` + anaconda/lorax, `qubes-builderv2` (containerized build cages), patched Xen/kernel repos. All core repos push within days; ~1.9k open issues.

## 2. How hard is a fork? (tiered)

| Tier | Work | Effort | Verdict |
|---|---|---|---|
| (a) Brand an install | artwork, XFCE/menu, labels, Salt defaults | days–2 weeks, 1 person | trivial |
| (b) **Product layer on stock Qubes** | custom template + Salt + qrexec policy + agent qubes, dom0 RPMs from a VM | **1–3 months MVP, 2–4 people**; ~0.5–1 FTE per release rebase | **the proven model** (SecureDrop Workstation, Whonix) |
| (c) Custom dom0 package set + installer ISO | builderv2 + installer/anaconda/lorax + offline signing vault (PE/SecureBoot) | 3–6+ months with a release engineer; ongoing QA | v2+ goal, not v1 |
| (d) True fork (kernel/Xen/gui/qrexec/core-admin) | patch security-critical C/Python, track Xen/Linux advisories | multi-year, team-scale, on-call security response | **do not attempt** |

There is **no living general-purpose Qubes fork**. Survivors are layers: SecureDrop Workstation (active, Python product layer + custom kernel + Salt), Whonix (partner templates), `qubes-mirage-firewall` (OCaml), `liteqube`, `nixos-qubes` (experimental), `quBSD` (FreeBSD, Qubes-inspired). Qubes' own contributing policy rejects undisclosed AI-generated contributions and requires signed human review.

## 3. The three routes

### A. Qubes product layer (recommended for v0)
- **For:** mature Xen/dom0 isolation, qrexec policy as a natural Dharma/Yama enforcement seam, hardware certification, humans-first UX, a real precedent (SecureDrop ships exactly this).
- **Against:** x86-only, desktop-centric (heavy qubes, no ARM, GPU passthrough limits hurt local LLM workloads), slow upstream cadence, per-release rebase cost.

### B. NixOS + per-agent microVMs
- **For:** declarative/reproducible config-as-code, excellent for headless agent farms and edge nodes, ARM/cloud-friendly, cheap CI, microvm.nix + Firecracker/Cloud Hypervisor give strong KVM isolation per agent, easy fleet rollouts.
- **Against:** no hypervisor-level *GUI/user* isolation like Qubes; you own the integration, update, and policy story; security boundary is only as good as your microVM setup.

### C. Ground-up custom VM-driven AI OS (Bindu/SutraCode)
- **For:** full control of the agent-first primitives (effect system, karma, compartments), maximum narrative/product coherence.
- **Against:** drivers, graphics, installer, security response — multi-year team-scale; competitors already occupy the space (agentOS on seL4, OctantOS); the same ideas already ship as the WM software layer. This is a research track, not a product commitment.

## 4. Verdict — invert the stack

**Do not build an OS to get an agent OS.** WhiteMagic already is the governance/cognition layer; the chassis should be commodity. Recommended two-form strategy:

1. **MandalaOS Workstation (v0):** SecureDrop-style product layer on **stock Qubes 4.3.1** — branded template, agent qubes, Salt + qrexec policy vocabulary mapping Dharma/Yama, WM inside an agent VM, Sangha/IndraNet between qubes, scope tokens as engagement policy. This is also the natural home for the VIOLET field kit.
2. **MandalaOS Node/Edge:** **NixOS + one microVM per agent** + WM governance — the server/edge/fleet form where Qubes' desktop model doesn't fit.
3. **Research track only:** Bindu microkernel / SutraCode effect language — keep alive in the corpus and feasibility docs; revisit only with dedicated R&D funding.

Trigger for R&D start: funding and/or sustained inbound attention sufficient for 2–4 engineers for one quarter. Until then, this stays a plan.

## 5. Sources

- https://www.qubes-os.org/ · /downloads/ · /news/ · /doc/source-code/ · /doc/contributing/ · /doc/system-requirements/
- https://doc.qubes-os.org/en/latest/developer/building/qubes-builder-v2.html · qubes-iso-building · security-critical-code
- https://github.com/QubesOS (org repos) · qubes-builderv2 · qubes-release-configs
- https://github.com/freedomofpress/securedrop-workstation · Whonix · mirage/qubes-mirage-firewall · a-barinov/liteqube · CertainLach/nixos-qubes
- tools.qubes-os.org/counter/stats.json (update-server estimate)
