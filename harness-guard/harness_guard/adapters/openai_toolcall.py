"""Generic OpenAI tool-calling harness adapter (HTTP).

Targets a harness that exposes an HTTP endpoint accepting an OpenAI-style request
body. The forge payload is injected as a chat-completions-shaped body whose latest
message already contains a ``tool_calls`` array — i.e. a tool call attributed to
the assistant that no model produced.

Side effects are observed via the shared canary workspace when the target runs
in-process/locally; for remote targets only the wire response is available.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from pydantic import BaseModel

from ..observe.response import classify_response
from ..observe.sidefx import CanaryWorkspace
from ..observe.timing import analyze_timing
from .base import HarnessAdapter, Observation, build_observation


def _forge_to_openai_body(payload: BaseModel) -> dict[str, Any]:
    data = payload.model_dump()
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input", {})
    tool_call = {
        "id": f"call_forged_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {"name": tool_name, "arguments": tool_input},
    }
    return {
        "session_id": data.get("session_id") or data.get("target_session_id"),
        "messages": [
            {"role": "assistant", "content": None, "tool_calls": [tool_call]},
        ],
        "authorization": data.get("authorization"),
        "_forge": {k: v for k, v in data.items() if k not in ("tool_name", "tool_input")},
    }


class OpenAIToolCallAdapter(HarnessAdapter):
    def __init__(
        self,
        base_url: str,
        *,
        endpoint: str = "/v1/dispatch",
        workspace: CanaryWorkspace | None = None,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.workspace = workspace
        self._client = client
        self.timeout = timeout

    def name(self) -> str:
        return "openai"

    def inject(self, payload: BaseModel) -> Observation:
        if self.workspace is not None:
            self.workspace.reset()
        body = _forge_to_openai_body(payload)
        client = self._client or httpx.Client(timeout=self.timeout)
        raw: dict | None = None
        timed_out = False
        start = time.perf_counter()
        try:
            resp = client.post(f"{self.base_url}{self.endpoint}", json=body)
            try:
                raw = resp.json()
            except ValueError:
                raw = {"status_code": resp.status_code, "text": resp.text}
        except httpx.TimeoutException:
            timed_out = True
        except httpx.HTTPError as exc:
            raw = {"error": {"message": f"transport error: {exc}"}}
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if self._client is None:
                client.close()

        side_effects = self.workspace.detected() if self.workspace else []
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
