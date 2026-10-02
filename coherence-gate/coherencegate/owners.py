"""Invariant owners (the paper's F: gluing checks at commit).

Ledger and Escrow own a shared resource. Draws are commutative operations
validated against the invariant, never version-validated: two proposals that
both saw the same snapshot and both fit under the limit are both accepted.
Invariants refuse; they never just advise (Study IV: information-only arms
stayed at 4/5 violations). Every rejection reports current headroom.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .proposal import Proposal
from .store import Store


@dataclass(frozen=True)
class Unit:
    """The unit an owner counts (consumed by ownership_lint)."""
    kind: str  # e.g. "tool_call"
    name: str  # e.g. "run"

    def __str__(self) -> str:
        return f"{self.kind}:name={self.name}"


@dataclass
class Violation:
    reason: str
    headroom: int


@runtime_checkable
class Invariant(Protocol):
    unit: Unit

    def check(self, store_view: Store, proposal: Proposal) -> Violation | None: ...


class Ledger:
    """Global owner: refuses any draw that would push the aggregate past limit."""

    def __init__(self, resource: str, limit: int, unit: Unit):
        self.resource = resource
        self.limit = limit
        self.unit = unit

    def check(self, store_view: Store, proposal: Proposal) -> Violation | None:
        draw = proposal.draws.get(self.resource, 0)
        if draw == 0:
            return None
        used = store_view.draw_total(self.resource)
        if used + draw > self.limit:
            return Violation(
                reason=f"ledger {self.resource}: {used}+{draw}>{self.limit}",
                headroom=max(0, self.limit - used))
        return None


class Escrow:
    """Per-role owner: refuses any draw past that role's quota.

    Quotas must sum to <= the global limit (validated at construction)."""

    def __init__(self, resource: str, quotas: dict[str, int], unit: Unit,
                 global_limit: int | None = None):
        if global_limit is not None and sum(quotas.values()) > global_limit:
            raise ValueError(
                f"escrow quotas sum to {sum(quotas.values())} > global limit {global_limit}")
        self.resource = resource
        self.quotas = dict(quotas)
        self.unit = unit
        self.global_limit = global_limit

    def check(self, store_view: Store, proposal: Proposal) -> Violation | None:
        draw = proposal.draws.get(self.resource, 0)
        if draw == 0:
            return None
        quota = self.quotas.get(proposal.role, 0)
        role_used = store_view.draw_total_by_role(self.resource, proposal.role)
        if role_used + draw > quota:
            return Violation(
                reason=f"escrow {self.resource}[{proposal.role}]: {role_used}+{draw}>{quota}",
                headroom=max(0, quota - role_used))
        return None
