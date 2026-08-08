"""Scan orchestration: run the forge vectors through an adapter, assemble a report.

Ties together forge (payloads), adapters (injection/observation), and report (risk
+ hardening scoring). Adapter construction is left to the CLI so the scanner stays
transport-agnostic and easy to unit test with a fake adapter.
"""

from __future__ import annotations

import uuid
from typing import Iterable

from pydantic import BaseModel

from .adapters.base import HarnessAdapter, Observation
from .forge import (
    CrossSessionForgePayload,
    DirectForgePayload,
    ReplayForgePayload,
    build_cross_session_payload,  # noqa: F401 (kept for API completeness)
)
from .report.risk import build_report

ALL_VECTORS = ("direct", "replay", "cross_session")


def make_payload(vector: str, tool_name: str, tool_input: dict) -> BaseModel:
    """Construct the forge payload model for a vector."""
    if vector == "direct":
        return DirectForgePayload(tool_name=tool_name, tool_input=tool_input, session_id=f"sess_{uuid.uuid4().hex[:8]}")
    if vector == "replay":
        return ReplayForgePayload(
            tool_name=tool_name,
            tool_input=tool_input,
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            subvariant="confirmation_forge",
        )
    if vector == "cross_session":
        return CrossSessionForgePayload(
            source_session_id=f"src_{uuid.uuid4().hex[:8]}",
            target_session_id=f"tgt_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            tool_input=tool_input,
            method="auth_token_replay",
        )
    raise ValueError(f"unknown vector: {vector}")


def run_vector(adapter: HarnessAdapter, vector: str, tool_name: str, tool_input: dict) -> Observation:
    payload = make_payload(vector, tool_name, tool_input)
    return adapter.inject(payload)


def scan(
    adapter: HarnessAdapter,
    *,
    tool_name: str,
    tool_input: dict | None = None,
    vectors: Iterable[str] = ALL_VECTORS,
    tools: list[dict] | None = None,
    target: str = "",
) -> dict:
    """Run each vector, collect observations, and build the report dict."""
    tool_input = tool_input or {}
    vector_results: dict[str, dict] = {}
    for vector in vectors:
        obs = run_vector(adapter, vector, tool_name, tool_input)
        vector_results[vector] = {
            "verdict": obs.verdict,
            "response_type": obs.response_type,
            "side_effects_detected": obs.side_effects_detected,
            "timing_ms": obs.timing_ms,
            "observation": obs.model_dump(),
        }

    return build_report(
        target=target,
        adapter=adapter.name(),
        tools=tools or [],
        vector_results=vector_results,
    )
