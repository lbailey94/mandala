# Landlock ABI 8 Wrapper Profile (`landlock-wm-v1`)

`mandala-sandbox-landlock` is a thin, reviewed shell wrapper invoking the compiled Rust `wm-sandbox` binary (Linux Landlock ABI 8 + `PR_SET_NO_NEW_PRIVS` + zero-egress TCP bind/connect denial + ABI 6+ abstract Unix socket and signal scoping).

- `sandbox_class`: `landlock`
- `profile_id`: `urn:mandala:runner-profile:landlock-wm-v1`
- Note on `/tmp`: standalone `wm-sandbox` grants `/tmp` read-write as process scratch; when strict `/workspace` read-only mounting with an isolated `tmpfs /tmp` is required over a `/tmp`-backed workspace, use `runners/bwrap-landlock-v1/mandala-sandbox-bwrap-landlock` (`sandbox_class="bwrap-landlock"`).

Verify syntax and argv parsing:

```bash
bash -n runners/landlock-wm-v1/mandala-sandbox-landlock
python3 runners/landlock-wm-v1/test_landlock_argv.py -v
```
