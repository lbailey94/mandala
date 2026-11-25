# Bubblewrap + Landlock ABI 8 Defense-in-Depth Profile (`bwrap-landlock-v1`)

`mandala-sandbox-bwrap-landlock` layers unprivileged `bubblewrap` user/mount/network/PID namespaces (`--unshare-all`, private `--tmpfs /tmp`, read-only or writable `/workspace`) around the compiled Rust `wm-sandbox` Landlock ABI 8 binary inside the container.

- `sandbox_class`: `bwrap-landlock`
- `profile_id`: `urn:mandala:runner-profile:bwrap-landlock-v1`

Verify syntax and argv parsing:

```bash
bash -n runners/bwrap-landlock-v1/mandala-sandbox-bwrap-landlock
python3 runners/bwrap-landlock-v1/test_bwrap_landlock_argv.py -v
```
