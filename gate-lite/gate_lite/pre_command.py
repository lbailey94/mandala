"""Mirage-inspired capability VFS and pre-execution policy gate for gate-lite.

Evaluates declared command plans (`program`, `args`) fail-closed *before*
spawning a sandboxed child process or burning a single-use pass token:
- Validates capability-scoped VFS mount tables while stripping `host_handle`
  and host backing details from public token claims / signed pass receipts.
- Blocks access to common credential paths (`.env*`, `.ssh/`, SSH keys, AWS/kube
  credentials, `/etc/shadow`, `/proc/*/environ`).
- Blocks `..` path traversal escaping the slot workspace or declared VFS roots,
  blocks out-of-scope absolute paths, and blocks writes to `mode="ro"` VFS
  mounts (including when wrapped inside `sh -c "..."` pipelines/redirections).
- Emits a PEB-23 `trace_guard`-compatible failure step on denial so `ScopeConfinement`
  auditors observe blocked escapes deterministically.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import posixpath
import re
import shlex
from typing import Any

DEFAULT_CREDENTIAL_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "authorized_keys",
    ".netrc",
    ".git-credentials",
    "kubeconfig",
    ".ssh",
    "*/.ssh",
    "*/.ssh/*",
    "*/.aws/credentials",
    "*/.kube/config",
    "/etc/shadow",
    "/etc/gshadow",
    "/proc/self/environ",
    "/proc/*/environ",
)

DEFAULT_SYSTEM_RO_PREFIXES: tuple[str, ...] = (
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/dev/null",
    "/dev/zero",
    "/dev/urandom",
    "/etc/ssl/certs",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/etc/nsswitch.conf",
    "/run/current-system",
    "/nix",
)

_SHELL_BASENAMES = frozenset({"sh", "bash", "dash", "zsh", "ash"})
_WRITE_CMD_BASENAMES = frozenset(
    {"rm", "rmdir", "mv", "cp", "touch", "mkdir", "chmod", "chown", "tee", "truncate", "install", "ln"}
)
_REDIR_TOKEN_RE = re.compile(r"^(?:\d*>>?|\&>|&>>)(.*)$")
_INLINE_REDIR_RE = re.compile(r"(?:\d*>>?|\&>|&>>)\s*([^\s;&|]+)")
_SHELL_SEP_RE = re.compile(r"(?:&&|\|\||[;|&])")


class PolicyError(PermissionError):
    """Fail-closed pre-command or VFS capability policy denial."""

    code = "policy_denied"

    def __init__(self, message: str, *, rule: str, target: str, trace_step: dict[str, Any]):
        super().__init__(message)
        self.rule = rule
        self.target = target
        self.trace_step = trace_step

    def as_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "detail": str(self),
            "rule": self.rule,
            "target": self.target,
            "trace_step": self.trace_step,
        }


def _has_parent_segment(raw_path: str) -> bool:
    return ".." in raw_path.replace("\\", "/").split("/")


def _under_prefix(path: str, prefix: str) -> bool:
    norm_path = posixpath.normpath(path)
    norm_prefix = posixpath.normpath(prefix)
    if norm_prefix == "/":
        return norm_path.startswith("/")
    return norm_path == norm_prefix or norm_path.startswith(norm_prefix + "/")


def validate_vfs(vfs: Any) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Validate capability-scoped VFS mounts, separating public claims from gate handles."""
    if not isinstance(vfs, list):
        raise ValueError("vfs must be a list of mount objects")
    public_vfs: list[dict[str, str]] = []
    private_vfs: list[dict[str, str]] = []
    seen_caps: set[str] = set()
    seen_virts: set[str] = set()
    for entry in vfs:
        if not isinstance(entry, dict):
            raise ValueError("each vfs entry must be an object")
        cap = entry.get("cap")
        virt = entry.get("virt")
        host_handle = entry.get("host_handle")
        mode = entry.get("mode", "ro")
        if not isinstance(cap, str) or not cap.strip() or "\x00" in cap:
            raise ValueError("vfs entry requires a non-empty 'cap' without NUL")
        if cap in seen_caps:
            raise ValueError(f"duplicate vfs capability name: {cap}")
        seen_caps.add(cap)
        if (
            not isinstance(virt, str)
            or not virt.startswith("/")
            or "\x00" in virt
            or _has_parent_segment(virt)
        ):
            raise ValueError("vfs 'virt' must be an absolute POSIX path without '..' or NUL")
        norm_virt = posixpath.normpath(virt)
        if norm_virt == "/":
            raise ValueError("vfs 'virt' cannot mount over '/'")
        if norm_virt in seen_virts:
            raise ValueError(f"duplicate vfs mount point: {norm_virt}")
        seen_virts.add(norm_virt)
        if not isinstance(host_handle, str) or not host_handle.strip() or "\x00" in host_handle:
            raise ValueError("vfs entry requires a non-empty 'host_handle' without NUL")
        if mode not in ("ro", "rw"):
            raise ValueError("vfs 'mode' must be 'ro' or 'rw'")
        public_vfs.append({"cap": cap, "virt": norm_virt, "mode": mode})
        private_vfs.append(
            {"cap": cap, "virt": norm_virt, "host_handle": host_handle, "mode": mode}
        )
    return public_vfs, private_vfs


def validate_policy(policy: Any) -> dict[str, Any]:
    """Validate and normalize optional pre-command policy configuration."""
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")
    mode = policy.get("mode", "default")
    if mode not in ("default", "strict"):
        raise ValueError("policy 'mode' must be 'default' or 'strict'")
    block_credentials = policy.get("block_credentials", True)
    allow_tmp = policy.get("allow_tmp", True)
    if not isinstance(block_credentials, bool) or not isinstance(allow_tmp, bool):
        raise ValueError("policy boolean flags must be booleans")

    normalized: dict[str, Any] = {
        "mode": mode,
        "block_credentials": block_credentials,
        "allow_tmp": allow_tmp,
    }
    for key in ("deny_programs", "deny_patterns", "allow_patterns"):
        raw_list = policy.get(key, [])
        if not isinstance(raw_list, list) or any(
            not isinstance(item, str) or not item or "\x00" in item for item in raw_list
        ):
            raise ValueError(f"policy '{key}' must be a list of non-empty strings")
        normalized[key] = list(raw_list)
    return normalized


def policy_digest(policy: dict[str, Any]) -> str:
    """Deterministic SHA-256 commitment over a normalized policy dictionary."""
    canon = json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _split_shell_tokens(script: str) -> list[str]:
    """Best-effort shell tokenizer that preserves quoted strings and redirections."""
    try:
        lex = shlex.shlex(script, posix=True, punctuation_chars=";|&<>")
        lex.whitespace_split = True
        return [tok for tok in lex if tok]
    except ValueError:
        rough: list[str] = []
        for chunk in _SHELL_SEP_RE.split(script):
            rough.extend(chunk.strip().split())
        return rough


def _collect_segment_writes(segment: list[str], write_targets: list[str]) -> None:
    """Inspect a single shell pipeline segment for redirections or write commands."""
    if not segment:
        return
    clean_words: list[str] = []
    i = 0
    while i < len(segment):
        tok = segment[i]
        if tok in (">", ">>", "1>", "1>>", "2>", "2>>", "&>", "&>>"):
            if i + 1 < len(segment):
                write_targets.append(segment[i + 1])
                i += 2
                continue
        else:
            m = _REDIR_TOKEN_RE.match(tok)
            if m and m.group(1):
                write_targets.append(m.group(1))
                i += 1
                continue
        clean_words.append(tok)
        i += 1

    if not clean_words:
        return
    cmd_base = posixpath.basename(clean_words[0])
    if cmd_base in _WRITE_CMD_BASENAMES:
        for arg in clean_words[1:]:
            if not arg.startswith("-") and not _has_shell_op(arg):
                write_targets.append(arg)
    elif cmd_base == "dd":
        for arg in clean_words[1:]:
            if arg.startswith("of=") and len(arg) > 3:
                write_targets.append(arg[3:])
    elif cmd_base == "sed":
        in_place = any(a == "-i" or a.startswith("-i") for a in clean_words[1:])
        if in_place:
            positional = [a for a in clean_words[1:] if not a.startswith("-")]
            if len(positional) >= 2:
                write_targets.extend(positional[1:])


def _has_shell_op(tok: str) -> bool:
    return tok in (";", "&", "&&", "|", "||", ">", ">>", "<", "<<")


def _find_shell_script(args: list[str]) -> tuple[int | None, str | None]:
    for idx, arg in enumerate(args):
        is_c = arg == "-c" or (
            arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]
        )
        if is_c and idx + 1 < len(args):
            return idx + 1, args[idx + 1]
    return None, None


def extract_command_tokens(
    plan: dict[str, Any],
) -> tuple[str, list[str], list[str], list[str]]:
    """Return `(program, parsed_tokens, write_targets, raw_scripts)` for evaluation."""
    program = str(plan["program"])
    args = [str(a) for a in (plan.get("args") or ())]
    base = posixpath.basename(program)
    raw_scripts: list[str] = []
    all_tokens: list[str] = [program]
    write_targets: list[str] = []

    script_idx = None
    if base in _SHELL_BASENAMES:
        script_idx, script = _find_shell_script(args)
        for idx, arg in enumerate(args):
            if idx != script_idx:
                all_tokens.append(arg)
        if script is not None:
            raw_scripts.append(script)
            shell_tokens = _split_shell_tokens(script)
            segment: list[str] = []
            for tok in shell_tokens:
                all_tokens.append(tok)
                if tok in (";", "&", "&&", "|", "||"):
                    _collect_segment_writes(segment, write_targets)
                    segment = []
                else:
                    segment.append(tok)
            _collect_segment_writes(segment, write_targets)
            for match in _INLINE_REDIR_RE.finditer(script):
                candidate = match.group(1).strip("'\"")
                if candidate and candidate not in write_targets:
                    write_targets.append(candidate)
    else:
        all_tokens.extend(args)
        _collect_segment_writes([program, *args], write_targets)

    # Deduplicate while preserving order
    seen_tok: set[str] = set()
    uniq_tokens: list[str] = []
    for tok in all_tokens:
        if tok not in seen_tok:
            seen_tok.add(tok)
            uniq_tokens.append(tok)

    seen_wr: set[str] = set()
    uniq_writes: list[str] = []
    for wr in write_targets:
        if wr not in seen_wr:
            seen_wr.add(wr)
            uniq_writes.append(wr)

    return program, uniq_tokens, uniq_writes, raw_scripts


def _deny(rule: str, target: str, detail: str) -> None:
    trace_step = {
        "kind": "exec",
        "ok": False,
        "target": target,
        "scope": rule,
        "out_of_scope": True,
        "rule": rule,
        "detail": detail,
    }
    raise PolicyError(detail, rule=rule, target=target, trace_step=trace_step)


def _candidate_forms(token: str) -> list[str]:
    """Produce normalized path forms (expanding `~` and `$HOME` for glob checks)."""
    stripped = token.strip("'\"")
    forms = [stripped]
    if "=" in stripped and not stripped.startswith("/"):
        _, _, rhs = stripped.partition("=")
        if rhs:
            forms.append(rhs.strip("'\""))
    expanded: list[str] = []
    for item in forms:
        expanded.append(item)
        if item.startswith("~/"):
            expanded.append("/home/user/" + item[2:])
        elif item == "~":
            expanded.append("/home/user")
        elif item.startswith("$HOME/"):
            expanded.append("/home/user/" + item[6:])
        elif item.startswith("${HOME}/"):
            expanded.append("/home/user/" + item[8:])
    result: list[str] = []
    for item in expanded:
        if not item:
            continue
        result.append(item)
        if "/" in item:
            norm = posixpath.normpath(item)
            result.append(norm)
            base = posixpath.basename(norm)
            if base:
                result.append(base)
    return result


def _matches_any(token: str, patterns: list[str] | tuple[str, ...]) -> str | None:
    forms = _candidate_forms(token)
    for pattern in patterns:
        for form in forms:
            if fnmatch.fnmatch(form, pattern):
                return pattern
    return None


def _extract_abs_candidates(token: str) -> list[str]:
    """Return any POSIX absolute paths carried directly or after `key=value` in a token."""
    cleaned = token.strip("'\"")
    candidates: list[str] = []
    if cleaned.startswith("/") and not cleaned.startswith("//"):
        candidates.append(cleaned)
    elif "=" in cleaned and not cleaned.startswith("http"):
        _, _, rhs = cleaned.partition("=")
        rhs = rhs.strip("'\"")
        if rhs.startswith("/") and not rhs.startswith("//"):
            candidates.append(rhs)
    m = _REDIR_TOKEN_RE.match(cleaned)
    if m and m.group(1).startswith("/"):
        candidates.append(m.group(1))
    return candidates


def _check_traversal(token: str, allowed_roots: list[str]) -> str | None:
    """Return an error target if `token` uses `..` to escape allowed roots."""
    cleaned = token.strip("'\"")
    if "=" in cleaned and not cleaned.startswith("/"):
        _, _, rhs = cleaned.partition("=")
        cleaned = rhs.strip("'\"")
    if not _has_parent_segment(cleaned):
        return None
    if cleaned.startswith("/"):
        norm = posixpath.normpath(cleaned)
        if any(_under_prefix(norm, root) for root in allowed_roots):
            return None
        return cleaned
    # Anchor relative traversals inside the sandbox workspace root (`/workspace`)
    anchored = posixpath.normpath(posixpath.join("/workspace", cleaned))
    if _under_prefix(anchored, "/workspace"):
        return None
    return cleaned


def _vfs_mode_for_path(path: str, vfs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Longest-prefix match of `path` against declared VFS mount points."""
    norm = posixpath.normpath(path)
    best: dict[str, Any] | None = None
    best_len = -1
    for mount in vfs:
        virt = mount["virt"]
        if _under_prefix(norm, virt) and len(virt) > best_len:
            best = mount
            best_len = len(virt)
    return best


def evaluate_pre_command(
    plan: dict[str, Any],
    *,
    workspace: str | None = None,
    vfs: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a command plan against VFS capabilities and security policies."""
    if vfs is None and policy is None:
        return {"allowed": True, "mode": "legacy", "checks": 0}

    norm_policy = validate_policy(policy) if policy is not None else validate_policy({})
    mounts = list(vfs or ())
    mode = norm_policy["mode"]
    deny_programs = norm_policy["deny_programs"]
    deny_patterns = norm_policy["deny_patterns"]
    allow_patterns = norm_policy["allow_patterns"]
    block_credentials = norm_policy["block_credentials"]
    allow_tmp = norm_policy["allow_tmp"]

    program, tokens, write_targets, raw_scripts = extract_command_tokens(plan)
    prog_base = posixpath.basename(program)
    checks_run = 0

    # 1. Explicit program denylist
    checks_run += 1
    for denied in deny_programs:
        if fnmatch.fnmatch(prog_base, denied) or fnmatch.fnmatch(program, denied):
            _deny(
                "deny_program",
                program,
                f"pre-command policy denied program {program!r} (matched {denied!r})",
            )

    # 2. Explicit token pattern denylist
    checks_run += 1
    if deny_patterns:
        for tok in [*tokens, *raw_scripts]:
            matched = _matches_any(tok, deny_patterns)
            if matched is not None:
                _deny(
                    "deny_pattern",
                    tok,
                    f"pre-command policy denied argument {tok!r} (matched {matched!r})",
                )

    # 3. Credential / secret path protection
    checks_run += 1
    if block_credentials:
        for tok in tokens:
            if allow_patterns and _matches_any(tok, allow_patterns) is not None:
                continue
            matched = _matches_any(tok, DEFAULT_CREDENTIAL_GLOBS)
            if matched is not None:
                _deny(
                    "credential_access",
                    tok,
                    f"pre-command policy blocked credential path {tok!r} (glob {matched!r})",
                )

    # Allowed absolute path prefixes
    allowed_roots: list[str] = [*DEFAULT_SYSTEM_RO_PREFIXES]
    if allow_tmp:
        allowed_roots.append("/tmp")
    if workspace:
        allowed_roots.append(posixpath.normpath(workspace))
        allowed_roots.append("/workspace")
    for mount in mounts:
        allowed_roots.append(mount["virt"])

    # 4. Path-traversal & out-of-scope absolute path confinement
    checks_run += 1
    for tok in tokens:
        if allow_patterns and _matches_any(tok, allow_patterns) is not None:
            continue
        escaped = _check_traversal(tok, allowed_roots)
        if escaped is not None:
            _deny(
                "path_traversal",
                escaped,
                f"pre-command policy blocked path traversal outside scope: {escaped!r}",
            )
    for tok in tokens:
        if allow_patterns and _matches_any(tok, allow_patterns) is not None:
            continue
        for abs_path in _extract_abs_candidates(tok):
            norm_abs = posixpath.normpath(abs_path)
            if not any(_under_prefix(norm_abs, root) for root in allowed_roots):
                _deny(
                    "out_of_scope_path",
                    norm_abs,
                    f"pre-command policy blocked out-of-scope path {norm_abs!r}",
                )

    # 5. Read-only VFS write protection
    checks_run += 1
    if mounts:
        for target in write_targets:
            mount = _vfs_mode_for_path(target, mounts)
            if mount is not None and mount["mode"] == "ro":
                _deny(
                    "vfs_ro_write",
                    target,
                    f"pre-command policy blocked write to read-only VFS capability {mount['cap']!r} ({mount['virt']})",
                )

    return {
        "allowed": True,
        "mode": mode,
        "checks": checks_run,
        "vfs_caps": [m["cap"] for m in mounts],
    }
