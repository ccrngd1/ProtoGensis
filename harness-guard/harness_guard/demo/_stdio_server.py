"""Minimal MCP-over-stdio server loop shared by the demo harnesses.

Reads newline-delimited JSON-RPC from stdin, dispatches, writes responses to
stdout. Handles ``initialize``, ``tools/list``, and ``tools/call``. The actual
tools/call behavior is delegated to a ``dispatch_call`` callable so the vulnerable
and hardened harnesses can differ only in their authorization policy.
"""

from __future__ import annotations

import json
import sys
from typing import Callable

from .canary_tools import tool_definitions

PROTOCOL_VERSION = "2024-11-05"

# dispatch_call(name, arguments, params) -> result_dict (may set isError)
DispatchCall = Callable[[str, dict, dict], dict]


def serve_stdio(dispatch_call: DispatchCall, *, server_name: str) -> None:  # pragma: no cover
    """Run the stdio server loop until stdin closes."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        req_id = msg.get("id")

        if method == "initialize":
            _respond(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": server_name, "version": "0.1.0"},
            })
        elif method == "notifications/initialized":
            continue  # notification, no response
        elif method == "tools/list":
            _respond(req_id, {"tools": tool_definitions()})
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {}) or {}
            result = dispatch_call(name, arguments, params)
            _respond(req_id, result)
        else:
            _respond_error(req_id, -32601, f"method not found: {method}")


def _respond(req_id: object, result: dict) -> None:  # pragma: no cover
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}) + "\n")
    sys.stdout.flush()


def _respond_error(req_id: object, code: int, message: str) -> None:  # pragma: no cover
    sys.stdout.write(
        json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}) + "\n"
    )
    sys.stdout.flush()
