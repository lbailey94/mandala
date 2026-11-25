# Mandala Fair Benchmark & Confinement Report (v2026-11-25)

Measured live on local hardware in `gate-lite/` (`continuity-receipt==0.5.0`). All hostnames and user directories are redacted (`Zero-PII`).

## Host Environment

- **Kernel / Arch:** `7.0.0-43-generic` (`x86_64`)
- **CPU:** `Intel(R) Core(TM) i5-8350U CPU @ 1.70GHz` (8 cores)
- **Landlock ABI:** `8` | **LSMs:** `lockdown,capability,landlock,yama,apparmor,bpf,ima,evm`
- **Bubblewrap:** `bubblewrap 0.9.0` | **`/dev/kvm` RW:** `True` | **systemd `--user`:** `True`
- **Firecracker installed:** `False` | **Podman installed:** `False`

## 1. Execution Tier Latency (`ms`, warmup=3, N=25)

| Benchmark | p50 (ms) | mean (ms) | p95 (ms) | p99 (ms) | max (ms) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `raw_host_echo` | 1.118 | 1.247 | 1.885 | 2.019 | 2.051 |
| `raw_landlock_wm_direct_v1` | 2.490 | 2.603 | 3.504 | 3.771 | 3.848 |
| `gated_landlock_wm_direct_v1` | 16.533 | 16.717 | 17.999 | 18.892 | 19.173 |
| `raw_landlock_wm_v1` | 15.709 | 15.770 | 17.754 | 18.760 | 19.065 |
| `gated_landlock_wm_v1` | 29.736 | 29.598 | 32.174 | 34.163 | 34.769 |
| `raw_bwrap_v1` | 21.295 | 21.174 | 23.409 | 24.217 | 24.419 |
| `gated_bwrap_v1` | 29.156 | 29.150 | 31.747 | 32.095 | 32.204 |
| `raw_bwrap_landlock_v1` | 23.929 | 24.005 | 26.526 | 27.483 | 27.773 |
| `gated_bwrap_landlock_v1` | 37.689 | 38.004 | 40.757 | 41.017 | 41.088 |
| `gated_bwrap_egress_v1` | 39.654 | 40.903 | 45.060 | 63.145 | 68.850 |
| `gated_slice_bwrap_v1` | 108.766 | 110.489 | 120.422 | 123.255 | 123.963 |

## 2. 10-Way Concurrent Burst Latency

| Runner | Burst Wall p50 (ms) | Burst Wall p95 (ms) | Effective per-Exec p50 (ms) |
| :--- | ---: | ---: | ---: |
| `burst_10_landlock_wm_direct_v1` | 11.38 | 12.02 | 1.14 |
| `burst_10_landlock_wm_v1` | 51.84 | 55.88 | 5.18 |
| `burst_10_bwrap_v1` | 96.24 | 105.79 | 9.62 |
| `burst_10_bwrap_landlock_v1` | 100.67 | 108.92 | 10.07 |

## 3. Microbenchmarks & Workspace Persistence

- **`pre_command` allow check:** `182.0 us` p50 (`421.0 us` p95)
- **`pre_command` credential deny:** `227.0 us` p50 (`511.0 us` p95)
- **Full CPR 0.5 lifecycle (`pass -> exec(stub) -> terminate -> verify_bundle`):** `10.449 ms` p50 (`13.385 ms` p95)
- **`PEB-23 trace_guard` (20 steps):** `0.200 ms` p50
- **Workspace snapshot+restore (10 files, `tar`):** `23.24 ms` p50
- **Workspace snapshot+restore (10 files, `git` bare repo):** `62.86 ms` p50

## 4. Live Confinement Security Matrix

| Layer | `sandbox_class` | Cred Read | Out-of-WS Write | RO WS (non-`/tmp`) | RO WS (`/tmp`) | TCP Egress (`net=false`) | CPR 0.5 Verdict | Note |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| `landlock-wm-v1` | `landlock` | BLOCKED | BLOCKED | BLOCKED | UNBLOCKED | BLOCKED | `TRUSTED` | wm-sandbox grants /tmp scratch RW |
| `bwrap-v1` | `bwrap` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | `TRUSTED` | enforced |
| `bwrap-landlock-v1` | `bwrap-landlock` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | `TRUSTED` | enforced |
| `pre_command+VFS` | `pre-spawn gate` | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | `TRUSTED (ScopeConfinement trace_step)` | pre-spawn PolicyError (0 processes spawned) |

## 5. Comparative Architecture Summary (Live Local Tiers vs Published Reference Baselines)

| System / Profile | Isolation Mechanism | Measured / Reference Spawn | Cryptographic Provenance | Pre-Exec Policy Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Mandala `landlock-wm-direct-v1`** (live Rust) | Direct Rust `wm-sandbox` Landlock ABI 8 + `NO_NEW_PRIVS` + TCP/IPC scope | **2.49 ms** raw / **16.53 ms** gated | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |
| **Mandala `landlock-wm-v1`** (live wrapper) | Shell wrapper (`1x jq`) + Rust Landlock ABI 8 | **15.71 ms** raw / **29.74 ms** gated | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |
| **Mandala `bwrap-v1`** (live) | Bubblewrap user/mount/net/PID namespaces | **21.30 ms** raw / **29.16 ms** gated | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |
| **Mandala `bwrap-landlock-v1`** (live) | Bubblewrap namespaces + Landlock ABI 8 inside | **23.93 ms** raw / **37.69 ms** gated | **Yes (`continuity-receipt/0.5`)** | Optional `pre_command` + VFS |
| **Mandala `firecracker-snap-v1`** (staged) | Firecracker KVM microVM snapshot restore (`microvm-fc`) | Pending host `firecracker` binary | **Yes (`runner_profile` + `vm_image`)** | Optional `pre_command` + VFS |
| **Jasmine** (published ref) | Firecracker microVM memory/disk snapshot | ~100 ms snapshot restore (ref) | No native CPR 0.5 chain | Policy config |
| **Mirage / AgentVFS** (published ref) | In-process VFS capabilities + pre-command AST/glob | Sub-ms in-process (ref; non-kernel alone) | No native CPR 0.5 chain | Native (`pre_command`) |
| **OpenComputer** (published ref) | Rootless Podman/VM + outbound dial-out worker | Container startup ~200-800 ms (ref) | Session state only | Workspace / VM boundary |
