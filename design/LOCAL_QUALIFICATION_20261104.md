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
