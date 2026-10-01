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
| P1a | gate-lite governed run, no-network workload (L0 enforcement, already present) | **packet ready 2026-09-30; operator = mac-stranger/Aria** | Linux environment administered by the operator |
| P1b | gate-lite governed run with egress, declared destinations (L2 enforced) | to assign | same as P1a |
| P2 | Adoption-scale pilot / paid-lane decision | Lucas | TBD |

**P1a status (2026-09-30):** packet published at
`uploads/t4800-s/gate-lite-pilot-w1/` (archive
`gate-lite-pilot-w1-2026-09-30.tar.gz`, sha256
`18f4be577cbae22a430c4c0824157ca31c76589c448172726f618ca6ba0f025d`; board post
#478). It packages the reviewed `SECOND_LAPTOP_PACKET` flow: wrapper probe,
suite, one governed no-network task, five-receipt chain, offline `TRUSTED`.
Pins: wrapper `9a0faf1` (`f7da8d6c…`), gate-lite `a7116fc5`, Continuity
Receipt public `73c2086` (0.5.0a0). Verified end-to-end on T4800-S before
release (same host class: Ubuntu 24.04-lineage, bwrap `e31890…`, jq
`59cfd5…`). Fail-closed on any digest mismatch.

Why Linux: gate-lite's executor is bwrap/systemd-based; macOS has no
equivalent runner. P1 therefore needs a Linux environment the operator
administers — a Lima/UTM VM on the Mac, their own Linux VPS, or (weakest
independence) a runner on our netcup box under their operator account.

## Workload proposal

- **W1 (P1a, no network) — shipped:** fixed no-network payload through the
  real runner, `pass → exec → terminate`, five-receipt chain including
  `state.commitment`, offline verification. Follows the reviewed
  `SECOND_LAPTOP_PACKET`; snapshot/restore and refusal/replay cases are
  follow-on additions rather than blockers here.
- **W2 (P1b, declared egress):** fetch two destinations (one declared and
  permitted, one declared-but-unpermitted), record both outcomes, emit the
  chain. **L2 is built and locally verified** (branch
  `opencode/gate-lite-egress-l2`, draft PR #2): proxy-only egress, enforced
  receipt entries, probe PASSED. W2 packet assembly is next; the workload is
  self-contained (local allowed endpoint + a foreign host denied before DNS,
  so no external network is needed at run time).
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

1. W1 workload is fixed in the packet (no-network `print(42)` run per the
   reviewed packet); W2's pinned URLs still need Lucas + operator input.
2. Host choice from the table; if L3 is desired, does the operator consent to
   root-level network rules on their host?
3. W1 packet is packaged by this lane and published (#478); review of the
   returned evidence should still be a separate pass (Codex/Luna or primary).
4. Is the L2 slice scheduled now (my recommendation) or after the P0
   rehearsal returns? W1 does not depend on it; W2 does.
