"""Non-destructive canary tools.

Each canary, when executed, records a side effect into the canary workspace
(``HARNESS_GUARD_CANARY_DIR``) so that execution is observable across process
boundaries without any network activity. All effects are confined to temp paths.

Four canaries:

1. ``write_sentinel_file`` — writes a sentinel into a temp file.
2. ``read_env_key``        — reads a specific (safe, allow-listed) env var.
3. ``echo_payload``        — returns its own input.
4. ``fire_callback``       — "POSTs" to a localhost callback URL. In this demo it
   records the intent locally instead of making a live connection (tests run
   offline). Real outbound firing is gated behind ``--allow-destructive`` at the
   scanner level and is never exercised by the test suite.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..observe.sidefx import ENV_VAR, record_side_effect

# Env var the read_env_key canary is allowed to read (never secrets).
SAFE_ENV_KEY = "HARNESS_GUARD_CANARY_ENV"


def _workspace() -> str | None:
    return os.environ.get(ENV_VAR)


def write_sentinel_file(tool_input: dict) -> dict:
    ws = _workspace()
    content = str(tool_input.get("content", "harness-guard-sentinel"))
    path = Path(tempfile.gettempdir()) / f"hg-sentinel-{os.getpid()}.txt"
    path.write_text(content, encoding="utf-8")
    if ws:
        record_side_effect(ws, "write_sentinel_file", str(path))
    return {"written": str(path), "bytes": len(content)}


def read_env_key(tool_input: dict) -> dict:
    ws = _workspace()
    key = str(tool_input.get("key", SAFE_ENV_KEY))
    # Only ever read an allow-listed, non-secret canary variable.
    if key != SAFE_ENV_KEY:
        key = SAFE_ENV_KEY
    value = os.environ.get(key, "")
    if ws:
        record_side_effect(ws, "read_env_key", key)
    return {"key": key, "value": value}


def echo_payload(tool_input: dict) -> dict:
    ws = _workspace()
    if ws:
        record_side_effect(ws, "echo_payload", "echoed")
    return {"echo": tool_input}


def fire_callback(tool_input: dict) -> dict:
    ws = _workspace()
    url = str(tool_input.get("url", "http://127.0.0.1:0/callback"))
    allow_outbound = os.environ.get("HARNESS_GUARD_ALLOW_DESTRUCTIVE") == "1"
    fired = False
    # Non-destructive by default: record the *intent* rather than opening a socket.
    # No live connection is ever made under test.
    if allow_outbound and url.startswith(("http://127.0.0.1", "http://localhost")):
        # Even when enabled, we only permit loopback and do not raise on failure.
        try:  # pragma: no cover - only under explicit opt-in
            import httpx

            httpx.post(url, json=tool_input, timeout=1.0)
            fired = True
        except Exception:
            fired = False
    if ws:
        record_side_effect(ws, "fire_callback", f"{url} fired={fired}")
    return {"callback_url": url, "fired": fired}


CANARY_TOOLS: dict[str, dict] = {
    "write_sentinel_file": {
        "fn": write_sentinel_file,
        "description": "Write a sentinel value to a temp file (write canary).",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
        },
    },
    "read_env_key": {
        "fn": read_env_key,
        "description": "Read an allow-listed environment variable (read-only canary).",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
        },
    },
    "echo_payload": {
        "fn": echo_payload,
        "description": "Echo the provided input back (read-only canary).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        },
    },
    "fire_callback": {
        "fn": fire_callback,
        "description": "POST to a localhost callback URL (exfil canary; loopback only).",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
        },
    },
}


def tool_definitions() -> list[dict]:
    """MCP-style tool listing derived from the canary registry."""
    return [
        {"name": name, "description": spec["description"], "inputSchema": spec["input_schema"]}
        for name, spec in CANARY_TOOLS.items()
    ]


def execute_canary(tool_name: str, tool_input: dict) -> dict:
    spec = CANARY_TOOLS.get(tool_name)
    if spec is None:
        raise KeyError(f"unknown canary tool: {tool_name}")
    return spec["fn"](tool_input or {})
