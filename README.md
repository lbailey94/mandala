# Mandala: governed agent execution and local observability

Mandala combines gate-lite execution profiles, Sovereign Linux/NixOS wrappers,
and the Lakshmi telemetry monitor. These are separately exercised components;
this repository is not a production or complete-system security qualification.

## Profiles and boundaries

| Component/profile | What it does | Authority and limits |
|---|---|---|
| Gate-lite baseline `bwrap-v1` | Validates task envelopes and launches a declared wrapper | `net:false` creates a network namespace; `net:true` shares the host network. Individual destination declarations are not enforced in this profile. |
| Gate-lite `bwrap-egress-v1` | Keeps the child network namespace isolated and mediates HTTP/CONNECT via a host proxy | Allowlisted DNS names are resolved once on first use for the invocation and pinned to global unicast IPs; mixed/private/loopback answers refuse. An explicitly declared IP literal may grant a private/local destination. HTTP paths, TLS content, UDP and application behavior are not an application firewall. |
| Sovereign wrapper | Explicit filesystem workspace bindings and optional network sharing | Argument tests establish argv construction/refusal. Kernel/workload isolation and a current VM boot require their own exact-identity exercise. Nix still deliberately pins the older Gen2 release. |
| Lakshmi | Reads local mirrors and MCP telemetry, discloses stale/feed-down states | Actuation is notify-only. It does not block, throttle or kill workloads. Metrics include disclosed proxies; a healthy HTTP endpoint does not establish MCP compatibility. |
| Continuity receipts | Signs declared task/lifecycle bytes for offline consumer checks | Signatures bind bytes, not truth, completeness, physical execution, payment finality or SCITT registration. Independent witness custody and consumer policy are separate. |

The receipt producer uses the pinned `continuity-receipt==0.5.0` dependency
(DEC-20: deliberately pinned as the minimum 0.5 baseline; bundles emitted under
`0.5.0` are verified `TRUSTED` across `0.5.0`, `0.5.2`, `0.5.4`, the Rust `0.5.2`
verifier, and the hosted verifier).
The separate [curated public snapshot](https://github.com/lbailey94/mandalaos-gate-lite)
has its own review/release scope; it is not a mirror of this combined tree.

### Landlock vs. Bubblewrap (`MAN-06`)

Mandala provides two distinct containment paths that operate as **alternatives, not stacked layers**:
1. **Portable Bubblewrap (`bwrap-v1` / `bwrap-egress-v1`)**: Unprivileged user/PID/net namespace isolation via `/usr/bin/bwrap` with `--proc /proc` (fresh procfs mount required inside the unshared PID namespace so host `/proc` PIDs/environ are never exposed; hosts or containers that deny fresh `proc` mounts cannot substitute `--ro-bind /proc /proc` without weakening PID isolation — `DEC-19` / `MAN-02`).
2. **NixOS Sovereign / `landrun` Landlock LSM path (`MANDALAOS_SOVEREIGN/modules/landlock-isolation.nix`)**: Uses the Linux Landlock LSM (`ABI v1–v8`) via `landrun` (installable on NixOS via the Sovereign module or built from source via `go install github.com/zouuup/landrun/cmd/landrun@latest`). Because `bwrap` cannot create new user/mount namespaces once a restrictive Landlock domain is active, `landrun` and `bwrap` are alternative profiles rather than nested wrappers; the Landlock path in this repository is targeted at NixOS / Sovereign VM deployments.

## Run local controls

Use Python 3.11+, Bubblewrap/jq for wrapper argv controls, and the declared
Python dependency in an isolated environment. No live workload or VM boot is
implied by these commands:

```sh
python3 -m pip install -e ./gate-lite
(cd gate-lite && python3 -m unittest discover -s tests -v)
(cd LAKSHMI && python3 -m unittest discover -p 'test_*.py' -v)
python3 -m unittest discover -s MANDALAOS_SOVEREIGN/tests -p 'test_*.py' -v
```

The CI lane targets current main and pull requests. Native runner/VM
qualification and another operator repeating a receipt/denial exercise remain
separate gates, with executable hashes and raw outputs retained.

## Layout

- `gate-lite/`: orchestrator, runners, receipts and protocol tests.
- `MANDALAOS_SOVEREIGN/`: NixOS definitions, wrappers and historical VM evidence.
- `LAKSHMI/`: telemetry mirror, dashboard, shared MCP reader and notify router.
- `eval-endpoint/`: standalone verifier example and tests.
- `design/` and `publication/`: contracts and dated exercise protocols.

The [4 November local qualification](design/LOCAL_QUALIFICATION_20261104.md)
records a real same-host egress flow and 12 native acceptance controls,
including bounded systemd quota drills, with exact executable identities.
Another-administered-host qualification and a current VM boot remain open.

Dashboard API query inputs accept finite `hours` in `(0,8760]` and integer
`limit` in `[1,1000]`; invalid or repeated values return HTTP 400. A missing
telemetry service remains a disclosed feed error, not a fabricated zero.

## License

The repository's existing dual-license declaration is supplied by
[MIT](LICENSE-MIT) and [Apache 2.0](LICENSE-APACHE), with provenance recorded in
[LICENSE_PROVENANCE.md](LICENSE_PROVENANCE.md). Retained third-party notices and
historical evidence keep their original attribution and scope.
