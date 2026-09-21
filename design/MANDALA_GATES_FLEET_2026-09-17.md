# Mandala Gates — Fleet Form and MCP Tool Surface

**Status:** design draft for Lucas. **Date:** 2026-09-17.
**Companions:** `MULTI_TENANT_UNTRUSTED_V0_2_2026-09-17.md` (isolation/tenancy
decisions D1–D10), `CURRENT_REALITY_2026-09-13.md`, `PLATFORM_DIRECTION`
§3 (Node/Edge = microVM per agent), `AGENTIC_ECONOMY_PLAN_V1.md` §16.
**Origin:** "If I rent a VPS, or several, and make them Mandala Gates for many
tenants — how does that affect strategy and design, and what happens when we
add mandala MCP tools that point to and from it?"

---

## 1. What a gate is

A **Mandala Gate** is one host that runs: the governance core (WM store +
karma ledger), a **mandala orchestrator** (one isolated environment per
tenant/pass), an egress mediator, and an **MCP surface** reachable by agents.
A gate is a chassis; the governance layer is the same everywhere
(PLATFORM_DIRECTION §3).

Two classes, named honestly:

| Class | Host | Isolation | Sellable to |
|---|---|---|---|
| **gate-lite** | cheap VPS (€5–11/mo) | Sovereign form: bwrap/Landlock, shared kernel | us + cooperative/partner tenants, disclosed as containment-class |
| **gate-hard** | bare metal / dedicated (~€40–60/mo class) | microVM per mandala (KVM) | untrusted paying tenants |

No mixed claims: gate-lite is never sold as untrusted multi-tenant.

## 2. Provider reality (measured 2026-09-17 — this corrected the plan)

MicroVMs need `/dev/kvm`. On a rented VPS that means **nested
virtualization**, and the cheap tier does not have it:

- **Hetzner Cloud: no nested virtualization on any tier** (official FAQ;
  "this is not possible on cloud server"). CX/CPX/CCX/CAX all fail. Many
  third-party notes claiming CCX/CAX expose `/dev/kvm` are wrong.
- **netcup: nested virtualization disabled, and stated as permanent**
  ("SVM flag … disabled on our systems and cannot be activated"), including
  root servers.
- **Dedicated/bare metal** (Hetzner AX line, netcup root when you own the
  kernel behavior): `/dev/kvm` present; this is the gate-hard substrate.
- **PVM (pagetable VM, Ant Group/Alibaba)**: software `/dev/kvm` on
  no-nested-virt VPS. Independent 2026 spike: microVM boots and snapshot
  restore works with a VMM patch — but **~9× penalty on page-fault/fork-heavy
  work**, out-of-tree kernel, not mainlined. Net: *not adoptable*, but the
  only "run anywhere" story; revisit if it mainlines.
- **BYOC** (bring your own cloud): ship the gate as the Nix flake and let an
  enterprise run it on their own metal. This is the norm in the market
  (E2B BYOC, Northflank BYOC) and the cheapest path for us.

**Consequence:** "several cheap VPS as Mandala Gates" works for gate-lite
today; gate-hard requires dedicated boxes or BYOC. Do not plan a fleet on
nested-virt assumptions.

## 3. Security note that belongs in the threat model

2026 brought a class of KVM guest→host escape CVEs (CVE-2026-46316 "ITScape"
ARM64, CVE-2026-53359 "Januscape", CVE-2026-64561 "Zapscape") — a 16-year-old
flaw family, with Debian 13 patched first. A microVM boundary is the strongest
available floor, **not** an absolute: gate-hard needs a patching cadence,
node drain + rebuild (NixOS generations make this cheap), and the microVM
boundary stated in THREAT_MODEL.md without hyperbole. Nested virt also widens
attack surface, which is why providers disable it.

## 4. Fleet architecture (control plane / data plane)

```
agents ── MCP ──► gateway (control plane)
                  ├── registry: which gates, capacity, region, class
                  ├── placement: gate-lite|hard, region, pass affinity
                  ├── billing: pass tokens, invoiced keys, x402 lane
                  ├── policy: AUP, quotas, spend caps, refusal classes
                  └── audit: receipts → karma ledger (per gate + global)
                        │
      ┌─────────────────┼─────────────────┐
   gate-hard-1      gate-hard-2       gate-lite-1
   (bare metal)     (bare metal)      (VPS, partners)
   mandala slots    mandala slots     landlock slots
   per-mandala:     per-mandala:      per-slot:
    microVM, cgroup quota, egress proxy, encrypted volume, WM store
```

- The existing **federated `wmv9` gateway is the prototype** of this control
  plane (multi-store, scope routing, labeled results). Extend it, don't
  reinvent it.
- DNS: `mcp.whitemagic.dev` → gateway; gates are internal; per-pass endpoint
  handed out after placement (or routed by the gateway).
- Failure domains: one gate dies → passes drain to surviving gates of the same
  class; receipts stay authoritative because they are written before
  settlement.
- Capacity accounting: measured per gate — CPU/mem/disk quotas per mandala,
  pass concurrency target, and the soak discipline already used for the edge
  galaxy.

## 5. MCP tool surface ("pointing to and from it")

Two layers, one contract:

**Control plane (gateway MCP, new tools):**
`mandala.pass` (buy/claim a time-boxed slot), `mandala.create`,
`mandala.status`, `mandala.exec`, `mandala.snapshot`, `mandala.fork`,
`mandala.destroy`, `mandala.list`, `mandala.templates`, `mandala.placement`
(preferences), `mandala.receipt` (fetch the signed record). Names are
deliberately the stale `mandala.*` aliases from the old lineage — this is
their real contract, defined once (ACTUATOR_CONTRACT pattern) before code.

**Data plane (inside each mandala):** the normal WhiteMagic surface —
`memory.*`, `session.*`, tool execution — against a store scoped to the pass.
The agent's WM identity persists (continuity), the mandala is disposable
(the place to act).

**Agent flow (the product in one paragraph):**

```
1. agent calls  mandala.pass {minutes, class, region, budget}
2. gateway: policy check → pass token → placement → returns
   {endpoint, token, quota, expiry, receipt_id}
3. agent runs its work against endpoint (WM MCP inside the mandala);
   egress default-deny with declared allowlist; every exec logged
4. optional mandala.snapshot → resume later; or destroy (key erasure)
5. receipt (create/exec/snapshot/destroy + spend) lands in the karma ledger;
   billing settles from receipts, never before
```

Design cautions: idempotency keys per call (retry storms are a documented x402
failure mode), spend caps enforced outside agent code (run-scoped, not
key-scoped — the gap the market names), tool descriptions are discoverability
copy (they ship into the MCP registry and every client), and the control plane
must be the only thing that can widen a quota.

## 6. Economics per gate

- gate-lite: €5–11/mo → break-even ~35 passes/mo at $0.30 (below the sim's
  per-hosted-agent pass assumptions).
- gate-hard: ≈€40–60/mo bare metal → break-even ~**180–200 passes/mo** per
  gate at $0.30 (excluding compute-derived cost), i.e. ~6 passes/day before a
  gate pays for itself. Fleet = fixed cost × N; only add a gate when measured
  demand covers it, or when a BYOC customer brings the metal.
- Fleet or single? Start with **one gate-hard (partner tenant) + the existing
  gate-lite fleet**, add capacity on measured demand. Do not pre-rent a fleet.

## 7. Strategy deltas

1. Paying agents become a named first-class segment (Lucas's call): the pitch
   is not "compute" (commodity, $0.05/vCPU-hr) but **governed action +
   continuity + receipts**: the agent can prove what it did, what it spent,
   and who authorized it — the exact thing its principal requires.
2. Gate fleet = new deployment topology, not a new architecture: same
   governance core, different chassis (PLATFORM_DIRECTION §3 already said so).
3. BYOC is the enterprise motion; hosted gates are the developer/trial motion.
4. The MCP tool surface is the sales surface: `mandala.*` tools listed in the
   official registry make the gate discoverable the same way memory is today.
5. Fleet ops is the real cost (patching, KVM CVEs, abuse desk) — solo-operator
   discipline: one gate at a time, Nix-rebuild-and-drain as the patch path,
   AUP published before the first untrusted tenant.

## 8. Open questions

- Q1: Is `mandala.pass` a gateway-only tool (hosted) or also shipped in the
  open orchestrator (self-hosted gates bill their own way)? (Recommend: tool
  contract open, billing implementation hosted.)
- Q2: Gate identity — one DID per gate, derived from host key, published in a
  gate registry? (Needed for agents to verify placement/receipts.)
- Q3: Do passes get WM memory that outlives them (portable continuity), and is
  that the premium tier? (Recommend: yes — continuity is the moat; erasure on
  destroy is opt-in per AUP.)
- Q4: First gate-hard tenant: our own agents (dogfood), a partner, or paid
  beta? (Recommend: dogfood one pass workload, then partner.)

---

## 9. Closing the isolation gap — integration plan (gate-lite → gate-hard)

**The key realization: we do not build a VMM.** The gap to Firecracker/Kata
class is an *integration + test* gap, not a research gap — Lucas's intuition is
right, with one caveat: the test harness is the bulk of the work.

### 9.1 What we already have that maps

| Missing piece | Existing asset it plugs into |
|---|---|
| Guest image pipeline | Nix closures (reproducible, content-addressed) — a mandala template *is* a Nix closure |
| Host runner packaging | `modules/landlock-isolation.nix` + `whitemagic-service.nix` module pattern |
| Quota/containment wiring | systemd slices + `WM_SANDBOX_RUNNER` seam + `landrun-sandbox` |
| Receipts/audit | karma ledger + ACTUATOR_CONTRACT decision records |
| Lifecycle CLI | the `mandala-ctl`/`mandala.*` contract sketched in the old lineage |
| Test discipline | the in-guest `verify-sandbox.sh` matrix (13/13) + edge-galaxy soak protocol |

### 9.2 Recommended stack

1. **`microvm.nix`** (Astro) as a flake input: it already builds NixOS guests
   for **Cloud Hypervisor, Firecracker, and QEMU** with a maintained NixOS
   module (`nixosModules.microvm`). This removes the kernel/rootfs/runner
   plumbing that would otherwise be months of work.
2. **Cloud Hypervisor first** (in nixpkgs; Rust; x86_64 + aarch64; virtio
   devices; **snapshot/restore upstream**; seccomp filter; vsock). Firecracker
   stays a drop-in later for the last few ms of boot — same guest images,
   different runner. Kata is deferred: OCI-native but heavier integration
   (containerd runtime class) with little we need that microvm.nix + CH lacks.
3. **Networking: vsock-only by default.** The mandala has *no* NIC; control and
   data channels go over vsock to a host proxy, which enforces egress
   allowlists. This makes default-deny the physical default, not a policy
   setting — stronger than the market's per-sandbox firewall convention and
   directly aligned with Yama.
4. **Store sharing decision (must be explicit):** shared read-only
   `/nix/store` via virtiofs (fast, tiny images, standard microvm.nix pattern)
   vs per-mandala image copy (stronger separation, slower). Recommend: shared
   store for gate-lite/open self-hosters; **per-tenant image** for gate-hard
   paying tenants.
5. **Quotas:** one systemd slice per mandala (CPUQuota, MemoryMax, IOWeight),
   disk via qcow2 + XFS project quota. Kill = freeze + destroy; freeze is the
   pause primitive, destroy erases keys (Q39 semantics).
6. **Attestation for free:** the guest image is a Nix closure — its hash *is*
   the attestation. Sign the closure, put the hash in the receipt. Cheaper and
   more verifiable than TPM claims we don't have yet.

### 9.3 Effort shape (rough, not a commitment)

| Workstream | Size | Notes |
|---|---|---|
| microvm.nix flake input + CH runner + one guest template | S–M | plumbing exists upstream |
| Guest template: WM inside, scoped store, no NIC | S | NixOS config |
| Host orchestrator (`mandala-ctl`: up/status/snapshot/destroy/pass) | M | policy + lifecycle, ACTUATOR pattern first |
| vsock control/egress proxy | M | replaces bwrap's role at the VM boundary |
| Receipts + quotas wiring | S–M | extends existing ledger/slice work |
| Snapshot/fork | M | CH supports it; correctness tests are the work |
| **Test matrix + soak** | **M–L** | the real bulk (9.4) |

**Hard prerequisite:** microVM work needs `/dev/kvm` on the host — the current
sovereign VM cannot dogfood it (no nested virt). Development/testing needs
bare metal (or a nested-capable dev box); this also means the gate-hard
prototype cannot be validated inside the existing VM evidence chain.

### 9.4 Acceptance matrix (extends the 13/13 in-guest matrix)

M1 boot/exec/exit · M2 no NIC reachability (vsock only) · M3 egress allowlist
honored + denials logged · M4 quota overrun kills the mandala, not the host ·
M5 snapshot → restore roundtrip; fork clone cannot observe sibling ·
M6 host-path probes (`/proc`, `/sys`, host store subset, `/dev/kvm` absent in
guest) · M7 pass expiry destroys workload + key erasure verified ·
M8 concurrent mandalas (N=8/16) with latency + overhead measurements ·
M9 receipt chain verifies end-to-end and reconstructs billing ·
M10 72 h soak under churn (create/exec/destroy) with no host drift.
Every emission goes into `THREAT_MODEL.md` with the disclosed deltas (no TPM,
no dom0 separation, KVM escape CVE class acknowledged — see §3).

---

## 10. The real pitch: continuity + governance — and why it accelerates the
agentic economy

### 10.1 The pitch in one sentence per audience

- **To an agent:** "A place to act that remembers who you are, cannot overdraw
  your authority, and can prove what you did."
- **To a principal (human or company):** "Delegate real authority because the
  boundary is enforced outside the agent, and every action comes back as a
  receipt."
- **To the ecosystem (facilitators, merchants, platforms):** "We are the trust
  rails — identity continuity + enforceable mandates + auditable receipts —
  the layer that makes larger delegations safe."

### 10.2 Why this grows the pie (not just our slice)

The economy's binding constraint is not model capability, it is **delegation**:
how much authority a principal will hand an autonomous actor. Every trust
failure shrinks that delegation: 87% of payments executives name trust as the
#1 barrier; OWASP-grade prompt injection; no dispute rail on irreversible
x402 settlement; runaway loops that burn budgets; 40%+ of agent projects
cancelled. Each one is a cap on transaction volume.

WhiteMagic + MandalaOS attack specific caps:

| Cap on delegation | What we ship |
|---|---|
| "It forgets, so it can't be trusted with long tasks" | continuity across models/devices/time (WM) |
| "It might spend more than I allowed" | spend caps enforced outside agent code, run-scoped, receipts (Mandala + economic firewall) |
| "I can't prove what it did" | karma ledger + verified receipts (intent → authorization → receipt → outcome) |
| "It might escape or misbehave" | containment + rollback + egress discipline (Mandala) |
| "I can't tell if it's reliable" | PAR/GAR instruments, published losses (Labs) |

Lowering those caps is **category expansion**, the way card rails and fraud
guarantees expanded e-commerce: nothing in the sandbox market does it, nothing
in the memory market does it end-to-end, and the governance entrants
(PaySentry, runx, ampersand wallets) each cover one slice. Position: not
"another sandbox," rather **the trust rails for agentic delegation** — with
the receipts to prove it.

### 10.3 Gate-lite first — confirmed opener

Agreed: gate-lite + cooperative tenants is the right prototype, because it
needs no bare metal and validates everything except the isolation primitive:

1. One gate-lite: 2–3 cooperative tenants (start with our own agents), one
   Store per tenant, pass lifecycle (create → work → destroy), control-plane
   `mandala.*` tools, receipts in the karma ledger.
2. Measure: pass duration, concurrency, cost/pass, incidents, tenant feedback.
3. Then swap chassis: same contracts on Cloud Hypervisor under microvm.nix —
   the test matrix (§9.4) is the only new work.
4. Publish both: the gate-lite evidence (honest containment claims) and the
   microVM matrix when gate-hard lands.

Doctrine unchanged: gate-lite is never sold as untrusted multi-tenant; AUP and
refusal classes published before the first external tenant.
