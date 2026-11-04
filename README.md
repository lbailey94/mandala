# Mandala: Governed Agent Execution & Kernel Confinement

Mandala is an open-source systems security framework providing deterministic kernel sandboxing, policy-governed execution envelopes, and offline-verifiable task continuity receipts for autonomous AI agents.

Designed for production agentic workloads, Mandala ensures that autonomous agents operate within strictly bounded operating system capabilities, emit tamper-evident execution receipts, and enforce zero ambient authority.

---

## Architecture Overview

```
                                  +--------------------------------------+
                                  |       Autonomous Agent Process       |
                                  +-------------------+------------------+
                                                      |
                                                      v
                                  +--------------------------------------+
                                  |       Gate-Lite Policy Governor      |
                                  |   (Envelope Authority & Preflight)   |
                                  +-------------------+------------------+
                                                      |
                         +----------------------------+----------------------------+
                         |                                                         |
                         v                                                         v
    +------------------------------------------+              +------------------------------------------+
    |           MANDALAOS_SOVEREIGN            |              |                 LAKSHMI                  |
    |  - Linux Landlock LSM Confinement        |              |  - Actuation Hysteresis Engine           |
    |  - Bubblewrap Unprivileged Namespaces    |              |  - Telemetry Digestor & Health Mon       |
    |  - Tetragon eBPF Kernel Event Auditing   |              |  - Systemd Service Supervision           |
    +--------------------+---------------------+              +--------------------+---------------------+
                         |                                                         |
                         +----------------------------+----------------------------+
                                                      |
                                                      v
                                  +--------------------------------------+
                                  |       Signed Continuity Receipt      |
                                  |    (IETF SCITT & RFC 3339 Bounded)   |
                                  +--------------------------------------+
```

Mandala unifies three foundational subsystems:

### 1. `gate-lite/` — Execution Governor & Continuity Receipts
* **Policy Enforcement**: Validates execution envelopes, capability allowances, and token authority before any workload runner is spawned.
* **Deterministic Provenance**: Emits offline-verifiable [continuity receipts](https://github.com/lbailey94/continuity-receipt) documenting task lifecycle transitions (authority, execution, delivery, settlement, termination).
* **Network & Egress Controls**: Enforces loopback-restricted and proxy-mediated egress semantics.

### 2. `MANDALAOS_SOVEREIGN/` — Kernel Confinement & Telemetry
* **Linux Landlock LSM**: Unprivileged, in-kernel filesystem and network access restrictions. Restricts read/write access to designated workspace directories.
* **Namespace Isolation**: Bubblewrap-based unprivileged sandbox envelope with explicit read-only mounts.
* **eBPF Observation**: Integrated Tetragon sensor policies auditing security-critical kernel events without intrusive tracing overhead.
* **NixOS Flake Substrate**: Reproducible system definitions and VM configurations for sovereign execution.

### 3. `LAKSHMI/` — Actuation Supervision & Metrics
* **Actuation Hysteresis**: Prevents oscillatory or runaway state changes across automated system actuations.
* **Telemetry Digestor**: Aggregates node health, memory pressure, and execution metrics into structured state reports.
* **Systemd Integration**: Provides reliable daemon timers and unit definitions for background monitoring.

---

## Core Security & Confinement Principles

1. **Deterministic Kernel Sandboxing**: Confinement is enforced at the Linux kernel level (Landlock LSM, cgroups, namespaces), avoiding brittle user-space wrappers.
2. **Cryptographic Provenance**: Every task execution produces verifiable, detached signatures linking authority envelopes to final state commitments.
3. **Zero Ambient Authority**: Processes possess only the explicit file descriptors, capabilities, and network endpoints granted in their execution pass.
4. **Offline Verifiability**: All receipt assertions, cryptographic hashes, and lifecycle state proofs can be validated without cloud dependencies.

---

## Directory Structure

* [`gate-lite/`](gate-lite/) — Task orchestrator, execution runner profiles, receipt generator, and test vectors.
* [`MANDALAOS_SOVEREIGN/`](MANDALAOS_SOVEREIGN/) — NixOS flake definitions, Landlock isolation modules, Tetragon policies, and sandbox scripts.
* [`LAKSHMI/`](LAKSHMI/) — Actuation governor, telemetry sampler, bridge reporting, and systemd units.
* [`eval-endpoint/`](eval-endpoint/) — Standalone verification service endpoint and test suite.
* [`design/`](design/) — Formal interface contracts (Actuator Contract, Egress Enforcement, Orchestrator Contract).
* [`publication/`](publication/) — Verification playbooks, review errata, and outsider exercise protocols.

---

## Quickstart

### Running Gate-Lite Tests
```bash
cd gate-lite
python3 -m unittest discover tests/
```

### Qualifying the Sandbox Envelope
```bash
python3 gate-lite/tools/qualify_bwrap_runner.py
```

### Inspecting Sovereign Kernel Isolation
```bash
cd MANDALAOS_SOVEREIGN
pytest tests/test_sandbox_argv.py
```

---

## License

Dual-licensed under either the [Apache License, Version 2.0](LICENSE-APACHE) or the [MIT License](LICENSE-MIT).
