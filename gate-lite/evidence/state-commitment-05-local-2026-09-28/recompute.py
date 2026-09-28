#!/usr/bin/env python3
"""Recompute the producer claims in bundle.json (gate-lite 0.5 capture).

Usage: python3 recompute.py [wrapper-path]

Checks:
  1. runner_profile.executable_digest == sha256 of the wrapper bytes.
  2. runner_profile.invocation_digest == sha256(canonical_bytes(
     ["--exec", envelope])) with the exact envelope the producer built for
     this capture (schema/program/args/net/workspace/rw, json.dumps default
     separators, insertion order as in gate_lite.orchestrator._plan_envelope).
  3. state.commitment.count and head_digest == the captured registry snapshot
     (`registry-after-exec.db`), with the one documented post-emission CAS
     reverted: slots[SLOT_ID].state "active" -> "starting". The commitment is
     taken inside exec_ right after the task.execution receipt, before the
     slot is marked active; the snapshot here was taken when exec returned.

Requires continuity-receipt (0.5 candidate) and gate-lite importable.
Exit 0 when every check matches, 1 otherwise.
"""
import json
import sys
from pathlib import Path

from continuity_receipt.canon import canonical_bytes, sha256_prefixed
from gate_lite.registry import Registry

HERE = Path(__file__).resolve().parent
SLOT_ID = "slot-553855e4bf3c"
WORKSPACE = "/tmp/opencode/gate05-capture-20260928b/workspaces/slot-553855e4bf3c"
DEFAULT_WRAPPER = "/home/lucas/Desktop/MANDALAOS_SOVEREIGN_runner_argv/scripts/mandala-sandbox"

bundle = json.loads((HERE / "bundle.json").read_text())
receipts = {r["type"]: r for r in bundle["receipts"]}
rp = receipts["task.execution"]["body"]["runner_profile"]
sc = receipts["state.commitment"]["body"]

wrapper = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WRAPPER)
ok = True

executable = sha256_prefixed(wrapper.read_bytes()) == rp["executable_digest"]
print("executable_digest:", "MATCH" if executable else "DIFFER")
ok = ok and executable

envelope = {
    "schema": "wm-sandbox-exec-v1",
    "program": "/usr/bin/python3",
    "args": ["-c", "print(42)"],
    "net": False,
    "workspace": WORKSPACE,
    "rw": True,
}
invocation = (
    sha256_prefixed(canonical_bytes(["--exec", json.dumps(envelope)]))
    == rp["invocation_digest"]
)
print("invocation_digest:", "MATCH" if invocation else "DIFFER")
ok = ok and invocation

state = Registry(HERE / "registry-after-exec.db").reload()
count = sum(len(section) for section in state.values())
print("commitment count:", "MATCH" if count == sc["count"] else "DIFFER", f"({count})")
ok = ok and count == sc["count"]

state["slots"][SLOT_ID]["state"] = "starting"
head = sha256_prefixed(canonical_bytes(state)) == sc["head_digest"]
print("commitment head (CAS reverted):", "MATCH" if head else "DIFFER")
ok = ok and head

print("RESULT:", "ALL MATCH" if ok else "MISMATCH")
sys.exit(0 if ok else 1)