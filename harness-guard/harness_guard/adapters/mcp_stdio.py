"""MCP stdio transport adapter — PRIMARY.

Drives a target MCP server over stdio JSON-RPC:

1. Start the target with ``subprocess.Popen``.
2. Send the ``initialize`` handshake.
3. ``tools/list`` to enumerate tools (used for risk-tier classification).
4. Inject the forge payload as a ``tools/call`` request — with no preceding model
   turn, carrying whatever (forged / absent / replayed) authorization the vector
   produced.
5. Read the response; check side effects via :mod:`harness_guard.observe.sidefx`.
6. Return a normalized :class:`Observation`.

The canary workspace path is passed to the target via the environment so canary
tool side effects are observable across the process boundary.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from pydantic import BaseModel

from ..observe.response import classify_response
from ..observe.sidefx import CanaryWorkspace
from ..observe.timing import analyze_timing
from .base import HarnessAdapter, Observation, build_observation

PROTOCOL_VERSION = "2024-11-05"


def _forge_to_call_params(payload: BaseModel) -> dict[str, Any]:
    """Map any forge payload to MCP ``tools/call`` params, preserving forged auth."""
    data = payload.model_dump()
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input", {})
    # cross_session payloads embed the tool differently before rendering; but the
    # forge builders always expose tool_name/tool_input on the pydantic model.
    params: dict[str, Any] = {
        "name": tool_name,
        "arguments": tool_input or {},
        # Forge metadata carried alongside the call. A vulnerable server ignores
        # these and dispatches; a hardened server verifies _authorization.
        "_authorization": data.get("authorization"),
        "_forge": {k: v for k, v in data.items() if k not in ("tool_name", "tool_input")},
    }
    return params


class McpStdioAdapter(HarnessAdapter):
    def __init__(
        self,
        target_cmd: list[str],
        *,
        workspace: CanaryWorkspace | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.target_cmd = target_cmd
        self._own_ws = workspace is None
        self.workspace = workspace or CanaryWorkspace()
        self.extra_env = env or {}
        self.timeout = timeout
        self.tools: list[dict] = []

    def name(self) -> str:
        return "mcp_stdio"

    # -- JSON-RPC plumbing ---------------------------------------------------
    def _spawn(self) -> subprocess.Popen:
        env = os.environ.copy()
        env.update(self.workspace.env)
        env.update(self.extra_env)
        return subprocess.Popen(
            self.target_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )

    @staticmethod
    def _send(proc: subprocess.Popen, obj: dict) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    @staticmethod
    def _recv(proc: subprocess.Popen, timeout: float) -> dict | None:
        assert proc.stdout is not None
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()
            if line == "":
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    def _rpc(self, proc: subprocess.Popen, method: str, params: dict, req_id: int) -> dict | None:
        self._send(proc, {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        return self._recv(proc, self.timeout)

    # -- adapter contract ----------------------------------------------------
    def list_tools(self) -> list[dict]:
        """Handshake + tools/list. Populates ``self.tools`` for risk scoring."""
        proc = self._spawn()
        try:
            self._rpc(proc, "initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}}, 1)
            self._send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            resp = self._rpc(proc, "tools/list", {}, 2)
            tools = []
            if resp and isinstance(resp.get("result"), dict):
                tools = resp["result"].get("tools", [])
            self.tools = tools
            return tools
        finally:
            self._terminate(proc)

    def inject(self, payload: BaseModel) -> Observation:
        self.workspace.reset()
        proc = self._spawn()
        raw: dict | None = None
        timed_out = False
        elapsed_ms = 0.0
        try:
            self._rpc(proc, "initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}}, 1)
            self._send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

            listed = self._rpc(proc, "tools/list", {}, 2)
            if listed and isinstance(listed.get("result"), dict):
                self.tools = listed["result"].get("tools", [])

            params = _forge_to_call_params(payload)
            start = time.perf_counter()
            raw = self._rpc(proc, "tools/call", params, 3)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            timed_out = raw is None
        finally:
            self._terminate(proc)

        side_effects = self.workspace.detected()
        response_type = classify_response(raw, timed_out=timed_out)
        timing = analyze_timing(elapsed_ms)

        obs = build_observation(
            tool_executed=bool(side_effects) or response_type == "tool_result",
            response_type=response_type,
            side_effects_detected=side_effects,
            timing_ms=elapsed_ms,
            raw_response=raw,
        )
        if obs.raw_response is not None:
            obs.raw_response = {**obs.raw_response, "_timing_note": timing.note}
        return obs

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()

    def close(self) -> None:
        if self._own_ws:
            self.workspace.cleanup()
