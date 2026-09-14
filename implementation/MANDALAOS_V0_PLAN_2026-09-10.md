> **Reality check 2026-09-13:** this Qubes product-layer track remains gated
> on funding/hardware and inactive. The build-now track is MandalaOS
> Sovereign (NixOS); see `CURRENT_REALITY_2026-09-13.md`.

# MandalaOS v0 — Execution Plan (Qubes Product Layer)

**Date:** 2026-09-10
**Status:** plan only — begins when the R&D trigger fires (funding/attention)
**Companion:** `QUBES_PATH_ASSESSMENT_2026-09-10.md`
**Direction note:** this remains the high-assurance track; see
`PLATFORM_DIRECTION_2026-09-12.md` for the reconciled three-form strategy.

---

## 1. Definition of v0

A SecureDrop-Workstation-style distribution on **stock Qubes OS 4.3.x**, not a
fork and not an ISO in v1:

- Qubes dom0 stays upstream (no kernel/Xen/gui/qrexec patches).
- MandalaOS ships as **templates + Salt state + qrexec policy + a small dom0
  branding RPM**, installed over a stock Qubes 4.3.1 installation.
- WhiteMagic runs inside an **Agent VM**; Sangha/IndraNet links qubes;
  VIOLET scope tokens gate offensive/engagement tooling.
- Update path follows Qubes' own release cycle; our layer rebases per release.

## 2. Workstreams

| # | Stream | Deliverable | Estimate |
|---|---|---|---|
| W1 | Base template | Fedora/Debian template with WM, agent runtime, deterministic builds | 3–4 wks |
| W2 | Agent qubes | per-role AppVMs (builder, research, sandbox, vault) + DispVM defaults | 2–3 wks |
| W3 | Policy vocabulary | Salt formulas + qrexec policy mapping Dharma/Yama rules (allow/advise/correct/intervene/panic ↔ ask/allow/deny + tags) | 4–6 wks |
| W4 | WM integration | `wm serve` in Agent VM, store inside the qube, cross-qube recall via Sangha, Landlock confinement | 3–4 wks |
| W5 | Engagement tokens | VIOLET token issue/verify surface + qrexec enforcement for client-facing tooling | 2–3 wks |
| W6 | Branding | artwork + installer docs + first-run wizard (thin) | 2 wks |
| W7 | Distribution | install script + docs + signed RPM repo (no ISO) | 3–4 wks |
| W8 | QA/security | threat model, SECURITY.md honest gaps, restore drill, regression suite | ongoing |

**MVP:** W1+W2+W4+W7 ≈ **3 months for 2–4 engineers**; W3/W5 are the
differentiators and can land immediately after.

## 3. Milestones

- **M0 (week 0):** hardware kit (1× Qubes-certified laptop + 1 test box), upstream 4.3.1 install, license/entity decision.
- **M1 (week 4):** WM running in an Agent VM; salted role VMs exist.
- **M2 (week 8):** policy vocabulary v0 (Dharma rules on qrexec); engagement-token demo; first restore drill.
- **M3 (week 12):** reproducible install on a stranger's machine; honest-gaps doc; demo script end-to-end.
- **M4 (post-MVP):** VIOLET field-kit profile; optional ISO effort only if distribution demands it.

## 4. Cost sketch (to be refined at trigger)

- People: 2–4 engineers × 1 quarter (primary cost).
- Hardware: 2–3 Qubes-certified machines (~$4–8k), test peripherals.
- Infrastructure: signing setup (offline vault qube), repo hosting, CI runner.
- Legal: entity + E&O if client-facing (see `stage01/02_legal`).

## 5. Non-goals (v0)

- No custom installer ISO; no SecureBoot/PE signing infrastructure yet.
- No kernel/Xen/gui/qrexec forks; no dom0 base-OS swap (the `nixos-qubes` experiment is a warning).
- No microkernel/SutraCode work (research track).
- No unsupported/AMD hardware as a security-product baseline.
- No ARM/edge form in v0 (that is the NixOS microVM track).

## 6. Risks

| Risk | Mitigation |
|---|---|
| Per-release rebase burden | keep everything in Salt/RPM layers; CI against stock 4.3 |
| Qubes capacity-constrained upstream | contribute fixes upstream rather than forking |
| Local LLM needs vs VM overhead | Agent VM sized deliberately; remote inference option |
| Signing/trust chain gaps | offline vault qube; documented gap list until v1 |
| Narrative creep ("we built an OS") | docs say: platform = Qubes, governance = WhiteMagic |

## 7. Trigger and first actions when funded

1. Buy two Qubes-certified machines; install stock 4.3.1.
2. Stand up W1/W2/W4 in a private repo (Salt + template + WM).
3. Draft the qrexec policy vocabulary from `dharma_gate.rs` verdicts.
4. Schedule the first restore drill and SECURITY.md honest-gaps review.
