# Mandala: adapt or retire — decision memo

**Status:** decision memo for Lucas, 2026-09-30. This turns the 2026-09-28
strategy thread into options and a recommendation. It commits to nothing;
no website, naming, or code change follows from this file alone.

## Where things actually stand (verified 2026-09-30)

- **gate-lite 0.4 lane is real and green**: 102 tests passed in a clean venv
  against the published `continuity-receipt==0.4.0` pin (the workspace venv
  had drifted to a local dev checkout and was corrected today). It issues a
  receipt chain per task and verifies offline.
- **Sovereign v9.2.9 is maintainer-VM qualified** (13/13 containment checks,
  loopback-only MCP, Landlock enforced ABI v8, healthy `wm doctor`;
  `MANDALAOS_SOVEREIGN/docs/VM_REVERIFY_V929_2026-09-28.md`).
- **The 0.5 profile candidate is open** (PR #1, exact local bwrap profile).
- **Egress truth was corrected today**: granted network is whole-network;
  receipts no longer imply per-destination enforcement
  (`design/EGRESS_ENFORCEMENT_2026-09-30.md`).
- **The competitive field is crowded where Mandala was originally pointed**:
  Boxd (persistent/forkable KVM), e2b (Firecracker pause/resume), and
  x402-paid box services already sell "machine for an agent." The payment
  challenge is the easy part; provisioning, metering, lifecycle, abuse
  handling, and isolation are the hard parts, and incumbents have scale.

## The strategic question

Do we (a) retire Mandala as a product and keep it as a documented early
exploration, (b) adapt it to the one thing the field is not selling —
**bounded, receipted authority over an ephemeral workspace** — or (c) fold
gate-lite into WhiteMagic/Continuity Receipt as a reference runner and let
the Mandala name rest?

## Options

| Option | What it means | Cost | Risk |
|---|---|---|---|
| A. Retire | Archive code as-is; site footnote with early notes dates | Low | Abandons working, qualified artifacts; the receipts lane loses its reference executor |
| B. Adapt narrow (recommended) | Product = governed task execution: authority + lifecycle + offline-verifiable receipts, with bwrap/slice containment and honest class labels; target vetted agents/operators first, no hostile-tenant claims | Medium; already 80% built | Requires demand proof before any paid lane |
| C. Fold in | gate-lite becomes a WhiteMagic/CR reference runner; Mandala name retired | Low-medium | Loses a possible standalone identity; little practical gain over B for now |

## Recommendation: B, with hard non-goals

Position: **"an ephemeral workspace with a contract and a receipt."** The
differentiator is not speed, forking, or price — it is that a task states
what it may do, runs inside a disclosed containment class, and produces a
chain a third party can verify offline. That is exactly what gate-lite
already does.

Explicit non-goals unless the field changes:

- no competing on machine performance, persistence, or fork (Boxd/e2b do it
  better; integrate rather than rebuild a VM control plane);
- no generic "pay USDC, get a Linux box" offer;
- no hostile-tenant or VM-level isolation claims on the shared-kernel
  bwrap/Landlock class;
- no x402 paid lane before the prerequisites below.

## Demand validation (the gate that decides everything)

From the prior adoption lessons: one real workload, on another host, with a
clean install, failure/replay/recovery evidence, and offline verification —
not fixtures, not same-host demos. Concretely:

1. Recruit 1–2 external agent/operator workloads (the mac second-host
   channel is already in motion for Continuity Receipt; it can carry a
   gate-lite pilot too).
2. Measure installation friction, runner setup, receipt readability, and
   refusal behavior; keep every failure in the report.
3. Decision point after those results: invest in B's paid lane, or fold
   (C), or retire (A).

## If the paid x402 lane is ever built, prerequisites

1. Destination-level egress enforcement or an explicit whole-network
   disclosure per pass (`design/EGRESS_ENFORCEMENT_2026-09-30.md`).
2. A tenant-boundary statement per offer: cooperative tenants only on the
   current class; hostile tenants need the microVM/gVisor track.
3. Settlement records already exist in the chain; pricing, metering, caps,
   and abuse policy do not — those are product work, not protocol work.
4. VPS capacity/virtualization reality check before promising anything
   (netcup nesting support is unverified for microVM options).

## Decision requested

1. Pick A, B (recommended), or C.
2. If B: approve the demand-validation plan as the next milestone, and
   whether destination-level egress enforcement is worth building before
   the first external pilot or after it.
3. If A or C: say so explicitly so effort stops flowing to the product
   surface and the site copy gets updated accordingly.

## Decision update — 2026-09-30 (same session, after review)

- **Direction: pilot milestone; brand deferred.** B vs C naming is parked
  until pilot results land; the engineering for both is identical.
- **First pilot channel: mac-stranger / Aria (the CR rehearsal channel).**
  The CR packet (claim #456) stays Codex-owned and unchanged; the gate-lite
  run is a complementary Linux-side follow-on — see
  `notes/PILOT_ONE_PAGER_2026-09-30.md`.
- **Egress enforcement comes before the pilot (Lucas).** Applied to the
  workload: a no-network workload (W1) is already enforced today (L0); the
  declared-egress workload (W2) waits for the L2 Unix-socket proxy slice and
  its acceptance evidence. Receipts may not claim `"enforced": true` before
  that qualification runs on the pilot host.
- **Sequencing:** W1 on an operator-administered Linux VM/VPS first, then W2
  after L2; L3 (rootful nftables) only if the operator consents and a broader
  toolset is required.
