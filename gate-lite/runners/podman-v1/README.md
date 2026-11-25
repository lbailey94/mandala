# Rootless Podman OCI Runner Candidate (`podman-v1`)

OpenComputer-inspired rootless container wrapper (`podman run --rm --network=none --userns=keep-id --read-only --cap-drop=ALL --security-opt=no-new-privileges`).

This runner is staged as a portable OCI candidate awaiting a CPR `0.6+` `oci-rootless` `sandbox_class`; it never masquerades as `bwrap` or `landlock` in CPR `0.5` receipts.
