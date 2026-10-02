"""Proposal: what an agent asks the gate to commit.

Carries writes, the context-derived read set (key -> version shown),
commutative draws on owned resources, postconditions for the effect monitor,
and optional model-cited premises that can narrow (never widen) the read set.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Proposal:
    agent: str
    role: str
    writes: dict[str, Any] = field(default_factory=dict)
    read_set: dict[str, int] = field(default_factory=dict)
    draws: dict[str, int] = field(default_factory=dict)
    postconditions: dict[str, Any | Callable[[Any], bool]] = field(default_factory=dict)
    premises: list[str] | None = None

    def validated_read_set(self) -> dict[str, int]:
        """Premise narrowing: read_set ∩ premises. Premises never widen it."""
        if self.premises is None:
            return dict(self.read_set)
        return {k: v for k, v in self.read_set.items() if k in self.premises}

    def unseen_premises(self) -> list[str]:
        """Cited keys that were never shown in context (flagged, ignored for validation)."""
        if self.premises is None:
            return []
        return sorted(k for k in self.premises if k not in self.read_set)
