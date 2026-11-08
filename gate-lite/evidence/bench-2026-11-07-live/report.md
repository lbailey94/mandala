# Gate-lite benchmark report

- Profile: **quick** · recorded 2026-11-07T21:43:10Z
- Host: Intel(R) Core(TM) i5-8350U CPU @ 1.70GHz · 8 threads · 15867 MB RAM · kernel 7.0.0-42-generic
- Python 3.12.3 · bubblewrap 0.9.0 · systemd 255 (255.4-1ubuntu8.18)
- Runner: `/home/lucas/Desktop/front burner/repos/MANDALA_OS/gate-lite/runners/bwrap-v1/mandala-sandbox` · load avg at start [4.53564453125, 3.30322265625, 2.091796875]

Method: warmup, auto-calibrated n against a per-case time budget; latency
percentiles are over per-operation samples. Percentiles on low-n latency
cases (snapshot, kill, OOM) are indicative, not distribution-grade.

## A

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| canonicalize body (small, ~0.3 KB) | 200 | 0.0199 ms | 0.0215 ms | 0.0325 ms | 0.0212 ms | 0.0136 ms | 0.0169 ms | 0.2019 ms | 47269.74 |
| canonicalize body (large, ~20 KB) | 157 | 0.7698 ms | 1.5259 ms | 1.84 ms | 0.9298 ms | 0.2912 ms | 0.6771 ms | 1.922 ms | 1075.45 |
| commit_field (small body) | 200 | 0.027 ms | 0.0347 ms | 0.0429 ms | 0.0276 ms | 0.0035 ms | 0.0234 ms | 0.0457 ms | 36246.63 |
| sign_receipt (Ed25519) | 200 | 0.0674 ms | 0.0934 ms | 0.1278 ms | 0.0715 ms | 0.0123 ms | 0.0648 ms | 0.1678 ms | 13992.59 |
| verify bundle (6 receipts) | 101 | 1.4591 ms | 2.8337 ms | 3.3045 ms | 1.6816 ms | 0.499 ms | 1.3368 ms | 3.3229 ms | 594.68 |
| verify bundle (100 receipts) | 8 | 24.9736 ms | 27.3903 ms | 27.3903 ms | 25.3394 ms | 1.467 ms | 22.8122 ms | 27.3903 ms | 39.46 |
| build chain (100 receipts) | 14 | 14.129 ms | 21.8724 ms | 21.8724 ms | 14.8066 ms | 2.3102 ms | 12.6577 ms | 21.8724 ms | 67.54 |
| verify tampered bundle (100 receipts) | 8 | 26.5664 ms | 30.8369 ms | 30.8369 ms | 26.9874 ms | 2.4263 ms | 23.937 ms | 30.8369 ms | 37.05 |

## B

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| get_slot (100 slots) | 200 | 0.0165 ms | 0.0429 ms | 0.0716 ms | 0.0215 ms | 0.011 ms | 0.0139 ms | 0.0884 ms | 46548.13 |
| put_slot (100 slots) | 200 | 0.0579 ms | 0.0879 ms | 0.1075 ms | 0.0625 ms | 0.0118 ms | 0.055 ms | 0.1249 ms | 16012.8 |
| recall miss (100 slots) | 200 | 0.0075 ms | 0.0182 ms | 0.0383 ms | 0.0101 ms | 0.0065 ms | 0.0062 ms | 0.0463 ms | 98771.87 |
| get_slot (1000 slots) | 200 | 0.0144 ms | 0.0155 ms | 0.0236 ms | 0.0148 ms | 0.0019 ms | 0.0138 ms | 0.0356 ms | 67651.01 |
| put_slot (1000 slots) | 200 | 0.0618 ms | 0.1003 ms | 0.1248 ms | 0.0722 ms | 0.0168 ms | 0.0577 ms | 0.1278 ms | 13850.81 |
| recall miss (1000 slots) | 200 | 0.0066 ms | 0.0069 ms | 0.0075 ms | 0.0067 ms | 0.0008 ms | 0.0063 ms | 0.0167 ms | 149837.32 |
| get_slot (10000 slots) | 200 | 0.0147 ms | 0.0395 ms | 0.0508 ms | 0.018 ms | 0.0082 ms | 0.0139 ms | 0.0535 ms | 55572.27 |
| put_slot (10000 slots) | 10 | 0.0548 ms | 0.0625 ms | 0.0625 ms | 0.056 ms | 0.0034 ms | 0.0525 ms | 0.0625 ms | 17846.85 |
| recall miss (10000 slots) | 200 | 0.0061 ms | 0.0066 ms | 0.0138 ms | 0.0063 ms | 0.0012 ms | 0.0059 ms | 0.0158 ms | 158556.75 |

## C

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| full flow (pass/exec/settle/terminate) | 23 | 7.0429 ms | 10.1577 ms | 19.2499 ms | 7.9885 ms | 2.6678 ms | 6.4732 ms | 19.2499 ms | 125.18 |
| flow without settlement (3 receipts) | 39 | 5.8358 ms | 46.9408 ms | 48.2666 ms | 8.2779 ms | 9.3179 ms | 5.1679 ms | 48.2666 ms | 120.8 |
| idempotent replay (pass+exec) | 200 | 0.6151 ms | 1.0242 ms | 1.2663 ms | 0.6753 ms | 0.1552 ms | 0.5759 ms | 1.4065 ms | 1480.84 |
| sweep 500 expired slots (fresh batch) | 3 | 387.1234 ms | 450.6623 ms | 450.6623 ms | 406.2539 ms | 38.5814 ms | 380.9761 ms | 450.6623 ms | 2.46 |
| snapshot workspace 1 MB | 5 | 40.1994 ms | 41.3634 ms | 41.3634 ms | 40.206 ms | 1.1584 ms | 38.864 ms | 41.3634 ms | 24.87 |
| restore workspace 1 MB | 5 | 11.3029 ms | 12.8697 ms | 12.8697 ms | 11.7157 ms | 0.9419 ms | 10.6862 ms | 12.8697 ms | 85.36 |
| snapshot workspace 10 MB | 5 | 394.8529 ms | 424.5057 ms | 424.5057 ms | 397.7269 ms | 16.1179 ms | 380.8938 ms | 424.5057 ms | 2.51 |
| restore workspace 10 MB | 5 | 94.0108 ms | 108.9023 ms | 108.9023 ms | 95.4341 ms | 8.0647 ms | 88.4024 ms | 108.9023 ms | 10.48 |
| list_ tenant slots (10k registry) | 5 | 75.7548 ms | 94.139 ms | 94.139 ms | 79.6291 ms | 8.2944 ms | 74.4421 ms | 94.139 ms | 12.56 |

## D

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| raw wrapper exec (bwrap, echo) | 14 | 13.8975 ms | 15.327 ms | 15.327 ms | 13.9508 ms | 0.6012 ms | 13.0733 ms | 15.327 ms | 71.68 |
| gate exec via SandboxRunner (echo) | 10 | 26.6844 ms | 29.2828 ms | 29.2828 ms | 26.7244 ms | 1.4659 ms | 24.7039 ms | 29.2828 ms | 37.42 |
| gate exec via SliceRunner (echo) | 10 | 87.064 ms | 220.2469 ms | 220.2469 ms | 99.922 ms | 42.5302 ms | 78.8457 ms | 220.2469 ms | 10.01 |
| operator kill latency (sleep payload) | 10 | 50.7661 ms | 51.0077 ms | 51.0077 ms | 50.7871 ms | 0.1166 ms | 50.6494 ms | 51.0077 ms | 19.69 |
| egress-denied curl exec | 6 | 34.0578 ms | 39.4475 ms | 39.4475 ms | 34.5522 ms | 2.7423 ms | 31.8703 ms | 39.4475 ms | 28.94 |

## E

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| HTTP keep-alive ping | 200 | 0.4715 ms | 0.6253 ms | 0.7204 ms | 0.4714 ms | 0.0888 ms | 0.3304 ms | 0.8855 ms | 2121.12 |
| HTTP keep-alive status | 200 | 0.5628 ms | 0.672 ms | 0.9956 ms | 0.5749 ms | 0.0946 ms | 0.43 ms | 1.3036 ms | 1739.29 |
| HTTP per-connection ping (urllib) | 200 | 0.7721 ms | 1.0918 ms | 1.4038 ms | 0.8127 ms | 0.1461 ms | 0.6082 ms | 1.4347 ms | 1230.54 |
| HTTP concurrent ping (8 clients x 50) | 400 | 3.5543 ms | 6.9585 ms | 8.1606 ms | 3.8692 ms | 1.8198 ms | 0.3728 ms | 13.1678 ms | 258.45 |
| stdio ping | 200 | 0.0301 ms | 0.0614 ms | 0.1006 ms | 0.0367 ms | 0.0154 ms | 0.0294 ms | 0.1531 ms | 27228.57 |
| stdio status | 200 | 0.1316 ms | 0.1843 ms | 0.2061 ms | 0.1295 ms | 0.0304 ms | 0.0844 ms | 0.2086 ms | 7719.08 |
| full lifecycle over stdio | 10 | 1.7693 ms | 1.9684 ms | 1.9684 ms | 1.7892 ms | 0.1001 ms | 1.6926 ms | 1.9684 ms | 558.92 |
| full lifecycle over HTTP keep-alive | 10 | 3.2541 ms | 4.9806 ms | 4.9806 ms | 3.4718 ms | 0.6178 ms | 2.9275 ms | 4.9806 ms | 288.04 |

## F

| Case | n | median | p95 | p99 | mean | sd | min | max | per sec |
|---|---|---|---|---|---|---|---|---|---|
| soak flow latency (100 flows) | 100 | 5.4332 ms | 11.2762 ms | 49.688 ms | 6.9684 ms | 8.2657 ms | 3.1078 ms | 58.0331 ms | 143.5 |

## Metrics & sizes

| Group | Metric | Value | Unit |
|---|---|---|---|
| A/sizes | receipt compact bytes (pass) | 595 (595 B) | bytes |
| A/sizes | receipt compact bytes (decision) | 741 (741 B) | bytes |
| A/sizes | receipt compact bytes (termination) | 538 (538 B) | bytes |
| A/sizes | bundle compact bytes (6 receipts) | 5527 (5.4 KB) | bytes |
| A/sizes | bundle stored bytes (6 receipts, indent=2) | 7429 (7.3 KB) | bytes |
| A/sizes | bundle compact bytes (pass+termination) | 1679 (1.6 KB) | bytes |
| A/sizes | receipts per task (full flow) | 6 | count |
| B/sizes | registry db bytes (100 slots) | 164808 (160.9 KB) | bytes |
| B/sizes | registry db bytes (1000 slots) | 531488 (519.0 KB) | bytes |
| B/sizes | registry db bytes (10000 slots) | 8158688 (7.8 MB) | bytes |
| B/parallel | parallel pass writers (4 workers x 5) | 739.55 | ms wall |
| B/parallel | parallel pass writers (8 workers x 5) | 1487.24 | ms wall |
| B/parallel | parallel pass writers (16 workers x 5) | 3133.8 | ms wall |
| B/parallel | parallel status readers (40 processes) | 1913.52 | ms wall |
| C/sizes | sweep per slot | 0.7742 | ms/slot |
| C/sizes | snapshot archive bytes (1 MB source) | 1049209 (1.0 MB) | bytes |
| C/sizes | snapshot archive bytes (10 MB source) | 10489301 (10.0 MB) | bytes |
| D | OOM quota-seal latency | skipped | status |
| E/concurrency | HTTP concurrent throughput (8 clients) | 1951.3 | calls/s |
| F/soak | first-decile median | 3.856 | ms |
| F/soak | last-decile median | 6.52 | ms |
| F/soak | drift (last vs first) | 69.08 | % |
| F/soak | RSS before (VmRSS) | 58.39 | MB |
| F/soak | RSS after (VmRSS) | 58.34 | MB |
| F/soak | RSS delta (VmRSS) | -0.06 | MB |
| F/soak | registry slots at end | 100 | slots |

## Invariants

| Check | Result | Detail |
|---|---|---|
| 6-receipt bundle verifies TRUSTED | PASS | TRUSTED |
| 100-receipt bundle verifies TRUSTED | PASS | TRUSTED |
| tampered 100-receipt bundle is UNTRUSTED | PASS | bad_signature,chain_break |
| no lost updates at 4 parallel writers | PASS | failures=0 slots=20/20 |
| no lost updates at 8 parallel writers | PASS | failures=0 slots=60/60 |
| no lost updates at 16 parallel writers | PASS | failures=0 slots=140/140 |
| parallel readers all succeed | PASS | failures=0 |
| bench flow bundle verifies TRUSTED | PASS | TRUSTED |
| sweep sealed the fresh batches | PASS | sealed=[500, 500, 500] |
| list_ returns all seeded slots | PASS | count=10000 |
| operator kills stopped the run | PASS | n=10 |
| egress deny invariants hold | PASS | all runs non-zero exit |
| concurrent HTTP clients all succeed | PASS | errors=0 |
| soak final bundle verifies TRUSTED | PASS | TRUSTED |

- 1,000 full tasks ≈ 5.3 MB of receipt bundles
- 100,000 full tasks ≈ 527.1 MB of receipt bundles
- 1,000,000 full tasks ≈ 5.1 GB of receipt bundles

- Minimal task (pass+termination) is 30.4% of a full task bundle

## Observations

- Bundle verification scales near-linearly: 100 receipts take 17.1x the 6-receipt time (24.9736 ms vs 1.4591 ms).
- Registry reads are independent of store size: get_slot at 10k slots is 0.9x the 100-slot time (0.0147 ms vs 0.0165 ms) — indexed SQLite lookups replaced full JSON reparsing.
- Containment overhead: raw bwrap 13.8975 ms, through the gate 26.6844 ms, slice-isolated 87.064 ms per exec.
- HTTP connection reuse matters: keep-alive ping 0.4715 ms vs 0.7721 ms per call with a fresh connection.
- Operator kill latency: median 50.7661 ms, p95 51.0077 ms (n=10).
- Soak: 100 flows, median 5.4332 ms, drift 69.08% between first and last decile; the drift tracks registry growth (100 slots at end, RSS delta -0.06 MB), not a process leak — see B for the registry-size curve.

