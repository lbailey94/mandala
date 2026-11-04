# MandalaOS Sovereign Edition — threat model and honest gaps

**One page, 2026-09-14. Every claim here is meant to survive an adversarial
reader; none of it is marketing. Contradicting this document with a verifiable
observation is the intended way to correct it.**

## What this is

A NixOS machine that runs the WhiteMagic cognitive substrate (WMv9) as a
hardened system service, with a declared containment layer for the tools and
agents the substrate dispatches. Containment is **shared-kernel**: Linux
namespaces (bubblewrap) and the Landlock LSM, wired through WM's runner
contract (`wm-sandbox-exec-v1`), plus systemd unit hardening. Landlock
rulesets stack, so a store that already holds a Landlock domain (the daemon)
stacks a pure-Landlock runner on top of it.

## What it contains (the threat class it is for)

- **Misbehaving or buggy tools/agents:** writes outside their store,
  undeclared subprocesses, accidental egress.
- **Prompt-injected agents:** every external spawn is a declared effect;
  tools that spawn without declaring are counted (`unconfined_spawns`) and
  the disclosure is part of the tool response.
- **Supply-chain execution:** spawned commands run under the active runner
  (bwrap, or pure-Landlock where a Landlock domain is active). When no
  runner resolves, WM **loud-degrades** — a warning plus a counter, never a
  false confinement claim.
- **Store integrity:** writes are confined to the store root (Landlock v0 for
  the daemon), stores can be sealed, releases are signed with a manifest, and
  nightly trust manifests + monthly receipts are produced.

This is the same trust class as browser sandboxes or systemd services: it
contains *behavior*, not a compromised kernel.

## What it does NOT contain (stated plainly)

- **Kernel exploits.** A local privilege-escalation bug defeats namespaces,
  Landlock, and systemd sandboxing alike. Out of scope.
- **A hostile local user with root.** The model is a trusted single-user
  machine; root owns the host.
- **Hypervisor-class compartmentalization.** This is not Qubes. There is no
  per-agent VM boundary and no IOMMU/VT-d device isolation. The Qubes product
  layer remains the separate, funded high-assurance track — never describe
  this build as "Qubes-level."
- **Hardware attacks** (DMA, cold boot, firmware implants), **side channels**,
  and **an adversary who already controls the network or the package
  mirrors**.
- **Availability.** A contained tool can still consume what it is allowed;
  the dharma gate vetoes destructive actions under stress, but that is
  policy, not a scheduler guarantee.

## Known gaps and deltas (disclosed, not hidden)

| Gap | Status |
|---|---|
| In-guest Landlock reports `partial` on the VM kernel (6.18); the host kernel (7.0) reports `enforced` | Disclosed by design; no enforcement claim is made from the guest |
| The pure-Landlock runner trades namespaces for path confinement: no private `/tmp`, no `/proc`, no PID/network namespaces | Documented in the runner header; tools needing procfs fail loudly |
| bwrap cannot run inside an active Landlock domain (mount topology is denied). Stores choose one mechanism; Landlock stores use the pure-Landlock runner | Resolved 2026-09-14; containment matrix 13/13 in-guest |
| Yama v0 is observe-only — no blocking without a zero-false-positive observation window | Policy, not a mechanism limit; thresholds + dwell/cooldown are versioned and disclosed |
| Telemetry is producer-supplied (Lakshmi); policy thresholds are declared, not kernel-enforced | Design choice; see `ACTUATION_HYSTERESIS_2026-09-13.md` |
| There is no authentication story for exposing an MCP surface beyond loopback | The fleet binds loopback; the VM forwards one read-only port. Do not expose to a network you do not control |
| Host fleet stores run the bwrap runner, not Landlock (v9.1.4 binaries predate the daemon-Landlock wiring) | Fleet upgrade rides the next release |

## Claim discipline (the rule we hold ourselves to)

1. Say **containment**, never isolation-class terms (Qubes, VM boundary).
2. No kernel-exploit resistance claims — not in docs, not on the site.
3. Every containment claim names the mechanism and its verification:
   `/etc/mandala/verify-sandbox.sh`, `wm doctor`, `wm selftest --json`, the
   signed release manifest.
4. Loud-degrade over silent fallback: a store with no runner says so in the
   tool response, `/status`, and the logs.
5. The gaps above are part of the product surface, not footnotes.

## Verification you can run

- `wm selftest --json` — five-second substrate invariants on a throwaway store.
- `/etc/mandala/verify-sandbox.sh` — 13-check containment matrix (8 bwrap +
  5 pure-Landlock, including "bwrap blocked under Landlock").
- `wm doctor` — Landlock/runner/sandbox disclosure for the live store.
- `release-health.json` on each GitHub Release — registry health plus install
  certification (`npm`/`Docker` artifacts run their own selftest).
