# Next project gates

The next integration target is one external project using the
`gate-lite/INTEGRATION_CONTRACT.md` flow from a clean install, with its own
payload and artifact. Record exact gate-lite, runner, and verifier versions.
Its success criteria are real contained execution, failure and replay refusal,
a recoverable artifact, and an offline-verifiable receipt bundle. Capture
installation friction and the operator help required. This is the next
adoption test after the same-host 0.4 reproduction.

The 2026-09-25 WhiteMagic receipt-probe rehearsal is a same-host adapter test,
not that independent adoption test. It also found that gate-lite labels the
portable Bubblewrap runner `bwrap-landlock` in signed receipts even though the
runner does not invoke Landlock. Resolve the runner-class vocabulary and bind
the reported class to executable evidence before promoting a containment
claim; preserve historical receipts with their original labels.

| Lane | Trigger to start | Evidence required before promotion |
|---|---|---|
| Gate-hard microVM | A project must run genuinely untrusted tenants, with a host offering the required virtualization | tenant threat model, isolation and escape tests, lifecycle/recovery test, independent review; retain the shared-kernel label for gate-lite |
| WhiteMagic store and karma ledger integration | A project needs query or accounting semantics SQLite cannot provide | migration/recovery design, measurable benefit, exact data and receipt invariants; do not migrate solely for scale while indexed SQLite meets the measured workload |
| (Milestone Reached: 2026-09-27) | Native Rust bridge (`crates/wm-gen3-core/src/mandala.rs`) + CLI (`wm3 mandala`) landed. Gate-lite spec 0.4 receipt (`outsider-2026-09-24-04`) committed as Record #403873 in Gen3 LMDB substrate. Replay ledger, offline pass issuance/verification verified. | Verified with zero dependencies under Article 1 CommitCapability. Ready for Phase 3 native Landlock engine expansion. |
| External anchor issuance | A counterparty needs independent time/existence evidence beyond signed offline bundles | issuance and upgrade path, companion proof verification, failure semantics and test vectors on an exact receipt spec |
| Yama enforcement | Observe windows show stable subject identity and acceptable false-positive rates for a specific policy | per-policy promotion report, rollback and kill switch, bounded actuator test, operator approval for that policy |

The publication playbook remains separate: the 72-hour active soak, Sovereign
stranger-install threshold, and repository hygiene gate cannot be satisfied
by a gate-lite clean-export run or a focused unit suite. See
`publication/GATE_EVIDENCE_PLAYBOOK.md` and
`publication/STRANGER_INSTALL_PROTOCOL.md`.
