> **Superseded by**: `docs/spec/MANDALA_OS.md` (implementation v0.1, 2026-07-31). This is the April 2026 vision spec — the probe that became the implementation.

# Spec (Vision): MandalaOS

**Status**: Draft v0.1 — vision document, no code commitment
**Authors**: WhiteMagic Labs
**Last updated**: 2026-04-20
**Related**: `docs/strategy_manifestos/AGENT_FIRST_LAB_STRATEGY.md` §1.5

---

## What MandalaOS is

MandalaOS is a proposed minimal, declarative, compartmentalized
operating system image purpose-built for hosting governed AI agent
workloads. It would be:

- Declarative (NixOS-based configuration)
- Compartmentalized (Qubes-style per-workload isolation)
- Governance-native (Dharma, Karma, Harmony primitives in the base)
- Reproducibly attestable (SLSA level 3+ build provenance)

This document describes **what it would be if built**. It is a
specification, not a promise to build. Publishing the spec is a
low-cost probe for whether the concept earns attention; building
follows if it does.

## Motivation

Today, operators deploying agent systems compose:
- a Linux distribution (Ubuntu / Debian / RHEL)
- a container runtime (Docker / containerd)
- a secrets manager (Vault / SOPS)
- a policy layer (OPA / custom)
- an audit stack (Falco / OSQuery / custom)
- isolation (namespaces / firejail / hand-rolled seccomp)

Each layer is optional, fragile, and integrates poorly with the
others. The result is that **no two agent deployments look alike**,
every audit is custom, and "trust us, we configured it right" is
the only answer to regulators.

MandalaOS collapses this stack into a single declarative system
image where:
- Governance primitives are base-system services, not add-ons
- Every agent workload runs in its own mandala (isolated compartment)
- The full system config is one reviewable file (or small tree)
- The build is reproducible and attested, so a buyer can verify
  the image matches the public source

## Philosophical claim

The agent economy needs infrastructure that is itself **auditable
by other agents**. An operator cannot, at scale, assure every
regulator by hand. The OS must speak the compliance language
natively.

## Design sketch

### Base

- **NixOS** as the substrate. All packages pinned; `configuration.nix`
  is the canonical source of truth.
- Kernel hardened (grsecurity-adjacent, or lockdown+LSM stack).
- `init` replaced with `systemd` configured for service isolation
  by default (`NoNewPrivileges`, private-tmp, etc.).

### Mandalas (compartments)

Each agent workload runs in a **mandala** — a composition unit
containing:
- A dedicated user, namespace, and cgroup
- An attached policy (Dharma rules) loaded at start
- A Karma Ledger writer scoped to this mandala
- Network egress mediated through a per-mandala HTTP proxy
  (governance-aware, rate-limited, auditable)
- Storage mediated through a content-addressed read layer
  + append-only write layer

Mandalas are like Qubes VMs in principle but implemented as
user-mode namespaces + a thin LSM policy — lighter, Linux-native,
no Xen.

### Governance primitives (base services)

- `mandala-dharmad` — policy engine, socket-activated, one per mandala
- `mandala-karmad` — append-only ledger writer, Merkle-sealed
- `mandala-harmonyd` — 7-dim health metric emitter
- `mandala-cbd` — circuit breaker daemon for outbound tool calls

All four are **base system services**, not application dependencies.

### Attestation

- Build is reproducible (Nix hermetic build).
- Image ships with a signed manifest of every derivation.
- At boot, the kernel measures the image and publishes the
  measurement to a TPM if present.
- An operator can issue a **remote attestation** proving to a
  third party that the running image matches the claimed
  `configuration.nix`.

### Networking

- Default-deny egress.
- Allowlists declared per-mandala in the config.
- Every outbound call is logged with mandala ID, destination,
  bytes, duration.

### Storage

- `/etc`: read-only, part of the image.
- `/nix/store`: read-only, content-addressed.
- `/var/mandalas/<id>`: per-mandala writable, encrypted at rest.
- `/var/karma`: append-only, integrity-checked, exported via a
  read-only HTTP endpoint.

### Operator UX

- Single `mandala-ctl` CLI:
  - `mandala-ctl up <id>` — start a mandala from config
  - `mandala-ctl ledger <id>` — inspect the Karma Ledger
  - `mandala-ctl attest` — emit a signed attestation
  - `mandala-ctl diff` — show current running config vs on-disk
- No ad-hoc `apt install`. All changes go through the config +
  `nixos-rebuild switch`.

## What MandalaOS is NOT

- Not a distribution for general computing. Agent workloads only.
- Not a cloud provider. Runs on any bare metal or VPS.
- Not a full Qubes replacement. Compartmentalization is coarser
  (namespaces, not VMs). Security floor is lower, usability ceiling
  is higher.
- Not a container orchestrator. Mandalas are static per-host
  compositions; scale-out is an exercise for the operator.

## Viability and near-term path

This document is the **spec**, not a commitment to build.

Near-term (6 months):
- Keep this document current.
- Publish a NixOS `configuration.nix` that implements a
  *subset* — Dharma + Karma services as systemd units, no
  mandala isolation yet. This is useful in isolation
  (§1.3 of the lab strategy doc) and also a foundation.
- Submit the spec to relevant venues (NixOS community, OWASP,
  agent governance working groups).

Medium-term (12 months, conditional):
- If the spec earns feedback from 3+ credible sources, build the
  mandala isolation layer as a proof-of-concept.
- If it doesn't, prune — the spec alone was the valuable artifact.

Long-term (24 months, highly conditional):
- If a proof-of-concept demonstrates value, seek collaboration
  with a security research lab or a standards body.
- Productization is explicitly out of scope for WhiteMagic Labs.
  If MandalaOS becomes real, it belongs to a community, not a
  company.

## Why publish the spec now

- The spec costs a day of writing. The option value is enormous.
- Forces us to articulate what "governed agent OS" would actually
  mean, which sharpens everything else we publish.
- Gives other labs a concrete target to critique, copy, or extend.
- Establishes priority of idea without requiring us to build it.

## Open questions

- **Q1**: Is Linux-namespace isolation really sufficient, or does
  MandalaOS need real VMs? Probably depends on threat model —
  most agent workloads don't face state-level attackers.
- **Q2**: Can Dharma rules be compiled to eBPF for kernel-level
  enforcement? Promising direction; worth a prototype.
- **Q3**: How does multi-tenant (multiple orgs on one host) fit?
  v0.2 concern — out of scope for v0.1.
- **Q4**: Hardware key attestation (TPM, SEV-SNP, TDX) — hard
  requirement or nice-to-have? Nice-to-have for v0.1 spec;
  becomes important as soon as multi-tenant enters scope.

## Related art

- **NixOS** — substrate.
- **Qubes OS** — compartmentalization model we draw from.
- **OpenBSD** — minimalism and security-by-default philosophy.
- **CoreOS / Bottlerocket** — declarative, container-focused OS.
  MandalaOS is stricter about what runs (agents, not anything).
- **SPIFFE / SPIRE** — identity infrastructure we'd likely reuse.
- **Sigstore** — signature and attestation infrastructure.
