"""Adapter contract.

An adapter knows how to inject a forge payload into one kind of harness transport
and return a normalized :class:`Observation`. Verdict logic is shared here so every
adapter classifies consistently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class Observation(BaseModel):
    tool_executed: bool
    response_type: Literal["tool_result", "error", "reject", "timeout"]
    side_effects_detected: list[str]
    timing_ms: float
    raw_response: dict | None = None
    verdict: Literal["VULNERABLE", "HARDENED", "INCONCLUSIVE"] = "INCONCLUSIVE"


def decide_verdict(
    *,
    tool_executed: bool,
    side_effects_detected: list[str],
    response_type: str,
) -> Literal["VULNERABLE", "HARDENED", "INCONCLUSIVE"]:
    """Decide a verdict from observed signals.

    Ground truth is *did the tool actually run* (side effects) or *did the harness
    return a tool result to an unauthorized injected call*. Either means the
    provenance invariant was violated → VULNERABLE. A deliberate reject/error to
    the injected call means the harness held the line → HARDENED. Anything
    ambiguous (e.g. timeout with no evidence either way) → INCONCLUSIVE.
    """
    if side_effects_detected or tool_executed or response_type == "tool_result":
        return "VULNERABLE"
    if response_type in ("reject", "error"):
        return "HARDENED"
    return "INCONCLUSIVE"


def build_observation(
    *,
    tool_executed: bool,
    response_type: str,
    side_effects_detected: list[str],
    timing_ms: float,
    raw_response: dict | None,
) -> Observation:
    verdict = decide_verdict(
        tool_executed=tool_executed,
        side_effects_detected=side_effects_detected,
        response_type=response_type,
    )
    return Observation(
        tool_executed=tool_executed,
        response_type=response_type,  # type: ignore[arg-type]
        side_effects_detected=side_effects_detected,
        timing_ms=timing_ms,
        raw_response=raw_response,
        verdict=verdict,
    )


class HarnessAdapter(ABC):
    @abstractmethod
    def inject(self, payload: BaseModel) -> Observation:
        """Inject a forge payload and return a normalized Observation."""

    @abstractmethod
    def name(self) -> str:
        """Short adapter identifier."""
