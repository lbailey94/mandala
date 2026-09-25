# WhiteMagic receipt probe through gate-lite — 2026-09-25

**Disposition: PASS for a bounded same-host project rehearsal; external-project
adoption gate remains OPEN.** The workload was a small Rust executable using
WhiteMagic main's `wm-receipts::verify_bundle` wrapper. Gate-lite launched it
through the pre-existing portable `mandala-sandbox` runner in a slot with no
network. The probe read the captured gate-lite 0.4 bundle from the slot
workspace and wrote `wm-verdict.json`. No WhiteMagic store, model call, or
remote endpoint was used.

| Boundary | Exact evidence |
|---|---|
| Gate-lite source | clean archive of private `mandala-os` `033e5ceb78ba608955c9b8e7986d7958bc4e6792` |
| Python verifier | installed `continuity-receipt==0.4.0` in a fresh venv |
| WhiteMagic source | clean `WMv9` main `251031e39c1d8f9ed6d3250fb76b695ebf5a076f`; Rust `continuity-receipt` 0.4.0 |
| Probe binary | SHA-256 `b8783fdf207aa215dfbb70112c8f106e93f04cac8412519eb2f4dadccbb79654` |
| Input bundle | `outsider-2026-09-24-04/bundle-task.json`, SHA-256 `114283e2ba318322c1f61e0fd500fda8f28bb447800e6b02c64b96795afcbf9c` |
| Portable runner | `/home/lucas/.local/bin/mandala-sandbox`, SHA-256 `de273c62ae22147634164e84cc9b6f6ae83a7f25e05755b50bc7c1257f525641` |
| Slot | `slot-4da66f8af3a6`; task `urn:uuid:01a0d93b-b52f-7f94-9619-5b37abd337ad` |

The probe source parsed the input as `serde_json::Value`, called
`wm_receipts::verify_bundle(&bundle, false)`, printed `to_value()`, and exited
nonzero unless `is_trusted()`. It was built offline from a scratch Cargo
package with a path dependency on the above WhiteMagic source. Gate-lite
installed from the clean archive in an isolated venv. The first attempt with
an invalid token exited 2; the matching token then ran the payload with exit
0; reusing that token before settlement exited 2. The gate recorded an
unsimulated runner and an execution receipt. The Rust probe artifact reports
`TRUSTED` and has SHA-256
`d5f6526bd395b930066699b333621eee7e4aa23ce5f3b59b21d380f644136369`.

Before termination, the slot snapshot was `snap-8cdc918f7dfb`. Its archive
SHA-256 was `02a988e7424b171fb305290c2705e78df5a2efc2d1c9dd44896689507b2a9a94`;
extracting `wm-verdict.json` from it reproduced the artifact hash above. The
slot settled at zero USD minor units and terminated. The seven-record final
[`bundle.json`](bundle.json) (SHA-256
`037029589ce037f5aca6848ac3a03111289a75131278c29379e8902e7823edc8`)
is `TRUSTED` by both gate-lite and the standalone published 0.4.0 verifier;
their saved verdicts are identical. The pass token is absent from this folder.

## Claim boundary and discovered issue

This was a maintainer-host rehearsal with a pre-installed runner and an
adapter built beforehand. It is not an independent other-host install or a
published WhiteMagic release test; WhiteMagic's v9.2.8 tag pinned the older
Rust receipt crate. The snapshot archive remains in temporary local state;
the small result artifact and final receipt bundle are preserved here.

**Runner classification is OPEN.** Gate-lite's receipt and status say
`bwrap-landlock`, but the exact portable runner script above invokes
Bubblewrap and does not invoke Landlock. The Sovereign module documents
Bubblewrap and Landlock as separate runner paths. The signed field therefore
overstates what this exact run demonstrates. `TRUSTED` proves that the signed
bundle satisfies verifier policy, not that this containment label is true.
The current `continuity-receipt/0.4` vocabulary has no Bubblewrap-only value;
changing the field unilaterally would create a nonconforming bundle. A
versioned vocabulary/runner-attestation fix and a fresh exact-candidate run
are required before promoting a containment claim from this evidence.
