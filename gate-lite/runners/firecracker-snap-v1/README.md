# Firecracker Snapshot MicroVM Profile (`firecracker-snap-v1`)

Jasmine-inspired pre-warmed microVM snapshot wrapper (`sandbox_class="microvm-fc"`, `profile_id="urn:mandala:runner-profile:firecracker-snap-v1"`).

Requires a reviewed `firecracker` binary and four pinned snapshot artifacts (`kernel.bin`, `rootfs.ext4`, `mem.snap`, `vmstate.snap`) in `MANDALA_FC_SNAPSHOT_DIR`. `FirecrackerSnapRunner` hashes all four image digests plus invocation argv into `runner_profile.invocation_digest` while keeping the strict 3-key CPR 0.5 `runner_profile` shape and recording `vm_image` as a sibling `task.execution` body field.
