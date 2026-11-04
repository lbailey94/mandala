# Local Bubblewrap runner probe — 2026-09-25

**Disposition: probe PASS; runner classification OPEN; independent adoption OPEN.**

The fixed probe in `gate-lite/tools/qualify_bwrap_runner.py` was run on the
maintainer host with the portable `mandala-sandbox` wrapper. Its complete
machine-readable output is `probe.json` (SHA-256
`2e4c4474f2c69922cd89399bd933be002ec3f3b46bc15f7b3c6d067e95ddb91a`).

Command from `gate-lite/`:

```sh
python3 tools/qualify_bwrap_runner.py \
  --expected-bwrap-sha256 sha256:e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71 \
  > evidence/bwrap-probe-2026-09-25/probe.json
```

The wrapper resolved to `/home/lucas/.local/bin/mandala-sandbox`, SHA-256
`de273c62ae22147634164e84cc9b6f6ae83a7f25e05755b50bc7c1257f525641`.
Bubblewrap resolved to `/usr/bin/bwrap`, SHA-256
`e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71`,
version 0.9.0. The Bubblewrap digest was first observed locally and then
provided as the expected value; it has not been independently sourced.

The captured invocation requested `--unshare-all`, a read-only bind for the
temporary workspace, tmpfs at `/tmp`, and `--die-with-parent`. The fixed
in-sandbox probe observed different network and mount namespace identifiers
from the caller, a read-only `/workspace` mount with a denied write, and a
writable tmpfs `/tmp`. Wrapper and Bubblewrap hashes remained stable across
the run. No arbitrary task payload was executed.

This is one same-host, fixed-payload behavior check. It does not test outbound
egress to destinations, attest the provenance of either executable, bind the
runner to a signed Continuity Receipt, or qualify gate-lite for real execution.
The wrapper's line-oriented `mapfile` argument parsing splits arguments with
embedded newlines; the probe uses a one-line encoded Python payload and does
not qualify multiline arguments. An independently administered host still
needs to install the exact candidate and reproduce positive and negative
mechanism cases before the adoption gate can be reviewed.
