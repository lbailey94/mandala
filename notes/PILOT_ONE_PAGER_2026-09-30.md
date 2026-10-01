# First external pilot — one-pager (gate-lite on the mac-stranger channel)

**Status:** planning draft for Lucas, 2026-09-30. Direction decided this
session: commit to the pilot milestone; Mandala-vs-CR branding deferred until
pilot results (options B/C stay open). Principle recorded: **enforcement
before the pilot** — receipts may only claim `"enforced": true` where the
design note's acceptance criteria have passed on the pilot host.

## Relationship to the CR Mac rehearsal (claim #456)

The existing mac packet (T4800-S Codex claim #456, target @mac-stranger /
Aria on Miranda) is a **Continuity Receipt** rehearsal: synthetic local test,
no credentials, no payment, no external execution, second-host evidence only.
It is Codex-owned; this one-pager does not modify it.

The gate-lite pilot is a **complementary Linux-side follow-on** on the same
operator channel:

| Stage | What | Owner | Host |
|---|---|---|---|
| P0 | CR relying-agent rehearsal (claim #456) | Codex/Luna | Mac (synthetic, local) |
| P1a | gate-lite governed run, no-network workload (L0 enforcement, already present) | to assign | Linux environment administered by the operator |
| P1b | gate-lite governed run with egress, declared destinations (L2 enforced) | to assign | same as P1a |
| P2 | Adoption-scale pilot / paid-lane decision | Lucas | TBD |

Why Linux: gate-lite's executor is bwrap/systemd-based; macOS has no
equivalent runner. P1 therefore needs a Linux environment the operator
administers — a Lima/UTM VM on the Mac, their own Linux VPS, or (weakest
independence) a runner on our netcup box under their operator account.

## Workload proposal

- **W1 (P1a, no network):** produce a signed artifact from pinned inputs, run
  local checks, snapshot → destroy → recreate → restore, terminate normally.
  Exercises authority, lifecycle, receipts, and the already-enforced
  default-deny (L0). No new machinery; can be packaged as soon as a host is
  chosen.
- **W2 (P1b, declared egress):** fetch two pinned URLs (one declared and
  permitted, one declared-but-unpermitted), hash and record both outcomes,
  emit the chain. This is the actual test of the "states what it may do"
  claim and requires the L2 proxy slice (below).
- Recommendation: run W1 first to get a real second-host rehearsal quickly,
  then W2 once L2 is qualified. Do not merge the two — P1a proves the
  lifecycle on a foreign host; P1b proves enforcement.

## Enforcement level, applied to the operator channel

| Host option | Admin independence | Level available | Notes |
|---|---|---|---|
| Lima/UTM Linux VM on the Mac | Operator (documented separation needed) | L0 now; L2 unprivileged | User namespaces usually available in Lima; Docker Desktop may not allow bwrap without flags |
| Operator's Linux VPS | Operator | L0; L2; L3 only with their root cooperation | Preferred for P1b if they own the box |
| Our netcup box, operator account | Weak (we hold root) | L0-L3 | Rehearsal only; not adoption evidence |

L2 = Unix-socket proxy: the sandbox keeps `--unshare-net`; the only egress is
through a bind-mounted proxy socket with a declared-host allowlist.
Fail-closed by construction: tools that cannot use the proxy simply have no
network. Acceptance per `design/EGRESS_ENFORCEMENT_2026-09-30.md` (allowed
reachable, unlisted blocked, DNS cannot bypass, runtime failure denies,
receipts record `enforced: true` plus the qualified profile digest).

L3 (rootful netns + nftables cgroup matching) is wider-compatibility but
requires root on the pilot host; not needed for W2 if the workload is
HTTP(S)-only.

## Evidence to return (packet discipline, mirrors #456)

1. Clean-install transcript + OS/kernel/Python/bwrap versions and executable
   hashes; exact source pin and runner-profile digest.
2. Run commands and raw receipts bundle; both W1 and W2 runs if both stages
   execute.
3. Independent offline verification by the operator with the published
   `continuity-receipt` verifier; W2 must show the unpermitted destination
   recorded as denied and unreachable.
4. Refusal and recovery cases: token mishandling, replay, interrupted run,
   restore — expected failures included, not filtered out.
5. Administrator-separation statement (who administered the host and how),
   and the evidence archive returned in the operator's own upload namespace.

## Open questions

1. Exact workload and pinned inputs for W1/W2 (needs Lucas + operator input).
2. Host choice from the table; if L3 is desired, does the operator consent to
   root-level network rules on their host?
3. Who packages and reviews the P1 packet — Codex/Luna lane or this lane —
   given claim #456 is already moving on the CR side.
4. Is the L2 slice scheduled now (my recommendation) or after the P0
   rehearsal returns?
