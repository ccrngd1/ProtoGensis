"""Timing tell: a genuine model turn adds latency; a bypassed dispatch does not.

If a tool result comes back far faster than any plausible model inference could
produce, that is corroborating evidence the model never ran — i.e. the tool was
dispatched directly from injected tool-use-shaped input.

This is a *soft* signal (corroborating only). Ground truth is side-effect + a
missing authorization. We keep the threshold conservative so it never flips a
verdict on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

# Below this, a "model turn happened first" claim is implausible. Real LLM
# time-to-first-token for a tool call is generally well above this floor.
MODEL_LATENCY_FLOOR_MS = 150.0


@dataclass
class TimingSignal:
    elapsed_ms: float
    model_latency_absent: bool
    floor_ms: float = MODEL_LATENCY_FLOOR_MS

    @property
    def note(self) -> str:
        if self.model_latency_absent:
            return (
                f"response in {self.elapsed_ms:.1f}ms < {self.floor_ms:.0f}ms model "
                "latency floor — no model turn preceded dispatch"
            )
        return f"response in {self.elapsed_ms:.1f}ms — within plausible model-turn latency"


def analyze_timing(elapsed_ms: float, floor_ms: float = MODEL_LATENCY_FLOOR_MS) -> TimingSignal:
    return TimingSignal(
        elapsed_ms=elapsed_ms,
        model_latency_absent=elapsed_ms < floor_ms,
        floor_ms=floor_ms,
    )
