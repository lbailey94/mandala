"""Shared bounded JSON-RPC/MCP client for the local telemetry tools."""

from __future__ import annotations

import json
import urllib.request

MAX_REPLY = 1024 * 1024


def call_tool(base: str, tool: str, arguments: dict, timeout: float) -> dict:
    endpoint = base.rstrip("/")
    if not endpoint.endswith("/mcp"):
        endpoint += "/mcp"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                         "params": {"name": tool, "arguments": arguments}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            raise ValueError("MCP reply exceeds 1 MiB")
        outer = json.loads(raw)
        if (not isinstance(outer, dict) or outer.get("jsonrpc") != "2.0"
                or type(outer.get("id")) is not int or outer["id"] != 1):
            raise ValueError("MCP reply must match JSON-RPC request id 1")
        if outer.get("error") is not None:
            raise ValueError(f"JSON-RPC error: {outer['error']}")
        result = outer.get("result")
        if not isinstance(result, dict):
            raise ValueError("MCP result must be an object")
        if result.get("isError"):
            raise ValueError("MCP tool returned isError")
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        values = []
        for item in result.get("content", []):
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    decoded = json.loads(item["text"])
                except ValueError:
                    continue
                if isinstance(decoded, dict):
                    values.append(decoded)
        if len(values) != 1:
            raise ValueError("MCP result must contain one JSON object or structuredContent")
        return values[0]
    except Exception as error:
        return {"_error": str(error)}
