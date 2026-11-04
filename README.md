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

The receipt producer uses the pinned `continuity-receipt==0.5.0` dependency.
The separate [curated public snapshot](https://github.com/lbailey94/mandalaos-gate-lite)
has its own review/release scope; it is not a mirror of this combined tree.

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

Dashboard API query inputs accept finite `hours` in `(0,8760]` and integer
`limit` in `[1,1000]`; invalid or repeated values return HTTP 400. A missing
telemetry service remains a disclosed feed error, not a fabricated zero.

## License

The repository's existing dual-license declaration is supplied by
[MIT](LICENSE-MIT) and [Apache 2.0](LICENSE-APACHE), with provenance recorded in
[LICENSE_PROVENANCE.md](LICENSE_PROVENANCE.md). Retained third-party notices and
historical evidence keep their original attribution and scope.
