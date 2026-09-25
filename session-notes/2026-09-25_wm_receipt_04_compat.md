# WhiteMagic main reads the gate-lite 0.4 bundle — 2026-09-25

**Disposition: bounded verifier interoperability PASS.** This is a local
read-only check of WhiteMagic's `wm-receipts` Rust wrapper against the captured
gate-lite bundle. It is not a release qualification, a bidirectional exchange,
or the external-project gate-lite integration exercise.

| Input | Exact value |
|---|---|
| WhiteMagic source | clean `WMv9` main `251031e39c1d8f9ed6d3250fb76b695ebf5a076f` |
| Rust dependency | `continuity-receipt` 0.4.0, registry checksum `d25c3a3d0f7730ecae9af09b09d374486ccbbcfd05d872801cc368e416feac11` |
| Gate bundle | `gate-lite/evidence/outsider-2026-09-24-04/bundle-task.json`, SHA-256 `114283e2ba318322c1f61e0fd500fda8f28bb447800e6b02c64b96795afcbf9c` |
| Local test | `cargo test -p wm-receipts --locked`: 19 unit tests and 4 Python parity tests passed |

The scratch probe used a Cargo package with a path dependency on the above
`wm-receipts` crate and `serde_json = "1"`. Its main function parsed the bundle
as `serde_json::Value`, called `wm_receipts::verify_bundle(&bundle, false)`,
printed `to_value()`, and exited nonzero unless `is_trusted()`. Its Cargo.lock
SHA-256 was `83a0593abc0b7d853ac430a07b01f39f1fd22788363ff8cfce21d9d96aaaf127`.
The probe returned `TRUSTED`, zero errors, six receipts, settled and terminated.

A copy with the first receipt's `body.tenant` changed to `tampered-tenant`
returned `UNTRUSTED` (exit 1), with `bad_signature` and `chain_break` errors.
The source bundle was not modified. The scratch probe was run offline; it was
not committed as a product adapter.

**Limits:** WhiteMagic's installed `wm` command was 9.2.7; the existing
`target/debug/wm` reported 9.2.8 but did not provide a source provenance
binding for this check. The published v9.2.8 tag pins Rust
`continuity-receipt 0.3.1`; this result applies only to the clean WhiteMagic
main source pin above. The `wm receipt verify` CLI requires a local store even
for a file target, so this check used the library wrapper. No WhiteMagic bundle
was emitted for gate-lite to consume, and no workload was executed through
gate-lite here.
