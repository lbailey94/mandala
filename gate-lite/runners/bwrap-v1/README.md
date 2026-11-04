# Qualified portable Bubblewrap wrapper — local candidate

`mandala-sandbox` is byte-identical to private Sovereign commit
`9a0faf19fbebfd6a4c803822ed23e8ba6cf055b6:scripts/mandala-sandbox`.
`PROVENANCE.json` records its SHA-256 and the exact Bubblewrap/jq profile.

This local copy removes the need to fetch a private upstream or trust the
preinstalled host wrapper. The public license declaration and curation sign-off
are pending. Do not describe the wrapper as publicly shipped yet.

The executable bytes must remain unchanged: adding a license header changes the
qualified digest. Place any applicable license/attribution in adjacent files.
The argv tests adapt the Bubblewrap subset of upstream tests/test_sandbox_argv.py
from the same commit (local path changes, Landrun cases excluded, and the fake
partial-output jq shim repaired to emit bytes before failing). Tests use a
capture shim, not real containment; the separate fixed mechanism probe tests
runtime namespace and filesystem properties.

From gate-lite:

```bash
bash -n runners/bwrap-v1/mandala-sandbox
python3 runners/bwrap-v1/test_sandbox_argv.py -v
```

A different host/tool build requires reviewed new profile evidence. This is
shared-kernel Bubblewrap containment for cooperative workloads, not Landlock,
virtualization, or hostile-tenant isolation.
