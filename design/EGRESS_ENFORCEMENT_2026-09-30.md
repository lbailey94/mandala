# Egress enforcement — current truth and the destination-allowlist path

**Status:** this note first recorded the 2026-09-30 vocabulary correction.
Private PR #2 adds an L2 candidate with a Unix-socket proxy, host-and-port
checks, raw-network isolation, and receipt evidence. The candidate is local
qualification work pending adversarial review; a green CI or local probe does
not establish independent-host adoption. Gate-lite receipts retain the
per-entry `"enforced"` flag and the older whole-network profile remains
distinct from the L2 candidate.

## Baseline whole-network profile

- Default deny: without `net: true` and declared destinations, the wrapper
  runs `bwrap --unshare-all` (no network); the denial is recorded in
  `task.execution.egress` with `"enforced": true`.
- Granted egress: `net: true` plus a declared list grants the **whole
  network** (`bwrap --share-net` plus resolver/CA binds). The declared
  destinations are recorded intent — they are an audit list, not an
  allowlist — and now carry `"enforced": false` so no reader can mistake the
  entry for destination-level enforcement.
- The wrapper envelope (`wm-sandbox-exec-v1`) carries the declared list for
  L2, but the baseline wrapper uses only `net` and does not mediate individual
  destinations.

## Why this matters

The governed-workspace promise is "state exactly what it may do." For
strangers running arbitrary code on a shared kernel, granting whole-network
access is the largest remaining capability gap after filesystem containment:
exfiltration, proxying, and scanning are all reachable once any host can be
contacted. A `TRUSTED` receipt must not imply otherwise; hence the correction
above is a truth fix independent of when enforcement lands.

## Options for destination-level enforcement

| # | Approach | Strengths | Costs / risks |
|---|---|---|---|
| A | Per-slot netns + veth + nftables allowlist with DNS pinning (root/systemd) | Kernel-level, works for any protocol | Domain→IP pinning breaks CDNs/rotation; needs root; DNS complexity |
| B | Per-slot netns + nft REDIRECT into a filtering proxy; allowlist by SNI/Host (CONNECT) | No MITM needed for host allowlisting; TLS passthrough; testable | HTTP(S)-only; every flow must be forced through the proxy; proxy failure must fail closed |
| C | microVM / gVisor tier with host-side egress policy | Real isolation boundary; clean policy point | Separate tier; not the current bwrap profile |
| D | Keep whole-network grants, record `"enforced": false`, require explicit operator opt-in per pass | Zero new mechanism; honest | Not suitable for untrusted tenants |

## Recommendation

1. **Now:** option D with the vocabulary correction that landed 2026-09-30.
   Any granted-egress pass remains an operator decision, and receipts say
   exactly what was enforced.
2. **Next qualified profile:** option B on the bwrap lane — a per-slot
   filtering proxy with fail-closed behavior — because it is implementable
   unprivileged with `--unshare-all` plus a Unix-socket bind, and its
   enforcement can be proven from the outside. Option A is a fallback for
   fixed endpoints; option C belongs to the microVM track.
3. A profile may only claim `"enforced": true` with an enforcer id when the
   acceptance suite below passes on the host where it runs.

## L2 candidate boundary

The proxy checks the destination host and port in an HTTP `CONNECT` request,
then relays the tunnel bytes. It does not inspect HTTP paths, methods, TLS
content, or application behavior. It also does not pin or restrict the IP
addresses returned for an allowed hostname. The L2 candidate therefore makes
a destination claim only; it is not an application policy or DNS-to-IP
firewall. Each allowed connection must have a matching start and terminal log
record; an absent, malformed, or incomplete log forces a non-success runner
result and an explicit incomplete slot hold.

## Acceptance criteria for a future qualified egress profile

1. Allowed host reachable; an unlisted host fails, with the denial recorded.
2. A broader DNS-to-IP-qualified profile must prevent unlisted resolved
   destinations, including rebinding/pinning attempts. This L2 host-and-port
   candidate does not close that requirement.
3. Proxy/runtime failure denies egress rather than falling back to an open
   network, and the failure is recorded.
4. The receipt records the enforcement mode truthfully (`"enforced": true`
   plus an enforcer identifier) and the qualified runner profile digest.
5. The G3 denial cases still pass unchanged; the baseline remains the
   default profile unless the exact L2 wrapper is selected.
