# Local runner qualification — 4 November 2026

The changed pinned-DNS proxy was exercised on the same Linux operator host
as the reviewed Bubblewrap and jq identities. The first full gate run refused
the new proxy because the profile still pinned its previous bytes. The
follow-up explicitly updates that pin; it does not weaken dependency checks.

| Input | SHA-256 |
|---|---|
| `mandala-sandbox-egress` | `0a0720955e135ec2a6b31a74fcdb1a9c8ecfb372177fb8f6d925d48379b17a43` |
| `mandala-egress-proxy.py` | `63400f0d98fc07ff29f5ef218ae6de4d72bed8e040e12bc21785e9af3dbf9d00` |
| Bubblewrap | `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71` |
| jq | `59cfd58d7e470b103aede0e7589cfea929e45ee27f5471f08aa9676ac7bfc566` |

The isolated environment used `continuity-receipt==0.5.0`, matching this
producer's declared dependency.

Observed controls:

- `tools/egress_l2_probe.py` passes standalone and full gate phases: direct
  loopback network access is blocked in the sandbox, explicitly granted
  loopback HTTP succeeds only through the proxy, an unlisted destination is
  denied, and the emitted bundle verifies as TRUSTED with enforced egress
  entries and the selected runner profile.
- `test_acceptance.py` passes all 12 controls with both real-runner and quota
  opt-ins enabled. This includes the bounded 96 MiB memory-overrun drill,
  wall-time quota termination, operator kill, receipt-emitter refusal,
  workspace roundtrip and snapshot controls. These were scratch workloads,
  not production incidents.
- The 22 focused profile controls pass, including a new shipped-profile
  identity control which detects wrapper/sidecar drift without requiring a
  particular CI host's native executable identities.

The egress receipt's invocation digest commits the actual helper digests.
The retained same-host probe output is under
`gate-lite/evidence/egress-l2-local-2026-11-04/`.

This is one operator and one administered host. It does not qualify another
host, a current NixOS VM boot, arbitrary TLS/application behavior, UDP,
complete workload containment, external witness custody or SCITT registration.
The six default-suite skips remain explicit unless the native acceptance
opt-ins and exact prerequisites are supplied. A profile id names a mechanism;
the executable and invocation digests bind the selected bytes.

## Sanctioned Multi-Host Qualification Process (`MAN-01`)

Because `gate-lite` fail-closes whenever `/usr/bin/bwrap` or `/usr/bin/jq`
differs by a single byte from the reviewed profile (for example, Ubuntu Noble's
`bwrap 0.9.0` hashes to `3e33f825...` rather than `e3189038...`), qualifying a
second host **must never** be done by casually editing pinned hashes in place to
silence a refusal. Instead, follow this four-step reviewed-profile procedure:

1. **Record Host Identity & Binary Digests**:
   Run `sha256sum /usr/bin/bwrap /usr/bin/jq $(realpath gate-lite/runners/bwrap-v1/mandala-sandbox)`
   and `bwrap --version`, `jq --version`, `uname -a`. Verify package integrity
   against the distribution's signed package database (`dpkg --verify bubblewrap jq`
   or `rpm -V bubblewrap jq`).
2. **Verify Wrapper & Sidecar Immutability**:
   The portable wrapper (`mandala-sandbox`, `f7da8d6c...`), egress wrapper
   (`mandala-sandbox-egress`, `0a072095...`), and proxy (`mandala-egress-proxy.py`,
   `63400f0d...`) are repo-controlled scripts and **must match** `PROVENANCE.json`
   byte-for-byte on every host.
3. **Register a Host-Scoped Reviewed Profile Entry**:
   Add a dated host-qualification record (`design/LOCAL_QUALIFICATION_<YYYYMMDD>_<HOST>.md`)
   and register the verified `(bwrap_sha256, jq_sha256, distro_package_version)` tuple
   in `gate-lite/acceptance_policy.py` as an explicitly named host profile rather
   than overwriting the primary reference pin.
4. **Execute the 12-Control Native Acceptance & Egress L2 Battery**:
   As a non-root user on a host that permits unprivileged user namespaces with a
   fresh `--proc /proc` mount and an active systemd user manager, run:
   ```bash
   cd gate-lite
   GATE_LITE_REAL_RUNNER_TESTS=1 GATE_LITE_QUOTA_TESTS=1 \
     WM_GATELITE_RUNNER="$(realpath runners/bwrap-v1/mandala-sandbox)" \
     python3 -m unittest discover -s tests -p test_acceptance.py -v
   python3 tools/egress_l2_probe.py
   ```
   Retain the emitted receipt bundles and raw output under `gate-lite/evidence/`.
