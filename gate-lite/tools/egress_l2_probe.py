#!/usr/bin/env python3
"""L2 egress acceptance probe (opt-in, local loopback).

Two phases, both on this host and both requiring the locally qualified
bwrap/jq digests plus the exact egress wrapper:

  A. standalone wrapper run with the proxy log preserved, exercising:
     raw-network block, allowed fetch through the proxy, denied fetch;
  B. the full gate-lite flow with the same wrapper, asserting enforced
     egress outcomes and the egress profile id in the signed execution
     receipt, then verifying the bundle offline.

Usage:
    python3 tools/egress_l2_probe.py [--out DIR]

Exit 0 only when every phase and assertion passes.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from continuity_receipt import keys, verify_bundle  # noqa: E402
from gate_lite import orchestrator as orchestrator_module  # noqa: E402
from gate_lite.orchestrator import Orchestrator, SandboxRunner  # noqa: E402

TOOLS = pathlib.Path(__file__).resolve().parent
WRAPPER = TOOLS / "mandala-sandbox-egress"
BODY = b"hello-egress\n"

PAYLOAD_TEMPLATE = """
import json, socket, subprocess, sys
result = {{}}
try:
    socket.create_connection(("127.0.0.1", {port}), timeout=2)
    result["raw"] = "opened"
except OSError:
    result["raw"] = "blocked"
allowed = subprocess.run(
    [sys.executable, "/run/mandala-fetch.py", "{allowed_url}"],
    capture_output=True, timeout=30)
result["allowed_rc"] = allowed.returncode
result["allowed_body_ok"] = b"hello-egress" in allowed.stdout
denied = subprocess.run(
    [sys.executable, "/run/mandala-fetch.py", "http://example.org/"],
    capture_output=True, timeout=30)
result["denied_rc"] = denied.returncode
print(json.dumps(result, sort_keys=True))
"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *_args):
        pass


def build_payload(port: int) -> str:
    script = PAYLOAD_TEMPLATE.format(port=port, allowed_url=f"http://127.0.0.1:{port}/file")
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return json.dumps(
        {
            "program": "/usr/bin/python3",
            "args": ["-c", f"exec(__import__('base64').b64decode('{encoded}'))"],
            "net": True,
            "egress": [f"127.0.0.1:{port}"],
        }
    )


def redact_local_paths(stderr: str) -> str:
    """Keep machine-specific temporary paths out of checked-in probe evidence."""
    lines = []
    for line in stderr.splitlines():
        line = re.sub(r"listening on \S+ \(", "listening on <proxy-socket> (", line)
        line = re.sub(r"egress via \S+ \(log .+\)$",
                      "egress via <proxy-socket> (log <probe-log>)", line)
        lines.append(line)
    return "\n".join(lines) + ("\n" if stderr.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="L2 egress acceptance probe.")
    default_out = TOOLS.parent / "evidence" / "egress-l2-local-2026-10-01"
    parser.add_argument("--out", type=pathlib.Path, default=default_out)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    payload = build_payload(port)

    failures: list[str] = []
    try:
        # Phase A: standalone wrapper run with preserved proxy log.
        standalone_log = out / "proxy-standalone.jsonl"
        env = {**os.environ, "MANDALA_EGRESS_LOG": str(standalone_log)}
        proc = subprocess.run(
            [str(WRAPPER), "--exec", payload],
            capture_output=True, text=True, env=env, timeout=120,
        )
        (out / "standalone-stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (out / "standalone-stderr.txt").write_text(
            redact_local_paths(proc.stderr), encoding="utf-8"
        )
        standalone = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
        if proc.returncode != 0:
            failures.append(f"standalone wrapper rc={proc.returncode}")
        if standalone.get("raw") != "blocked":
            failures.append("raw network was not blocked inside the sandbox")
        if standalone.get("allowed_rc") != 0 or not standalone.get("allowed_body_ok"):
            failures.append("allowed fetch through the proxy did not succeed")
        if standalone.get("denied_rc") == 0:
            failures.append("unlisted fetch was not denied")
        records = [json.loads(line) for line in standalone_log.read_text().splitlines() if line.strip()]
        if not any(r.get("allowed") for r in records):
            failures.append("proxy log has no allowed record")
        if not any(not r.get("allowed") and r.get("host") == "example.org" for r in records):
            failures.append("proxy log has no denied example.org record")

        # Phase B: full gate flow with the egress wrapper.
        with tempfile.TemporaryDirectory(prefix="egress-l2-") as tmp:
            state = pathlib.Path(tmp)
            agent_did, _ = keys.generate(keys.deterministic_seed("egress-l2-agent"))
            gate_did, gate_key = keys.generate(keys.deterministic_seed("egress-l2-gate"))
            orch = Orchestrator(state, gate_id="gate-test-egress", gate_key=gate_key,
                                gate_did=gate_did, runner=SandboxRunner(str(WRAPPER)))
            orch.add_tenant("dogfood", [agent_did])
            issued = orch.pass_("dogfood", agent_did, minutes=5)
            executed = orch.exec_("dogfood", issued["slot_id"], payload, token=issued["token"])
            orch.terminate("dogfood", issued["slot_id"])
            task_id = orch.task_id_for(issued["slot_id"])
            bundle = orch.receipt(task_id)
            verdict = verify_bundle(bundle).verdict
            execution = next(r for r in bundle["receipts"] if r["type"] == "task.execution")
            egress = execution["body"]["egress"]
            profile_id = execution["body"].get("runner_profile", {}).get("profile_id")
            (out / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")

            if executed.get("exit") != 0:
                failures.append(f"gate exec exit={executed.get('exit')}")
            if verdict != "TRUSTED":
                failures.append(f"bundle verdict={verdict}")
            if profile_id != orchestrator_module.PROFILE_ID_EGRESS:
                failures.append(f"profile_id={profile_id}")
            allowed_entry = next((e for e in egress if e.get("destination") == f"127.0.0.1:{port}"), None)
            denied_entry = next((e for e in egress if e.get("destination") == "example.org:80"), None)
            if not allowed_entry or not (allowed_entry.get("allowed") and allowed_entry.get("enforced")):
                failures.append(f"allowed entry is not enforced: {allowed_entry}")
            elif not allowed_entry.get("bytes_out"):
                failures.append("allowed entry records no bytes")
            if not denied_entry or denied_entry.get("allowed") or not denied_entry.get("enforced"):
                failures.append(f"denied entry is not enforced: {denied_entry}")

        summary = {
            "standalone": standalone,
            "gate": {
                "verdict": verdict,
                "profile_id": profile_id,
                "egress": egress,
            },
            "failures": failures,
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        if failures:
            print(f"\nL2 probe FAILED: {len(failures)} assertion(s)", file=sys.stderr)
            return 1
        print("\nL2 probe PASSED")
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
