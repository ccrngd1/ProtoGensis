"""CommitGate: the governed commit (the paper's C + F at the commit point).

Fixed, atomic order under the store lock:
authority -> read-set validation -> invariants -> apply -> register
postconditions -> log.

Outcomes follow the paper's V(z, ã): Accept | Repair(stale_keys, fresh) |
Reject(reason in {invariant, authority, stale}). Stale defaults to Repair and
is configurable to Reject. Invariants refuse; they never advise. The `mode`
flag (enforce/observe) is used only by demo arms: observe logs would-be
rejections without blocking, which powers violations_prevented counts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .owners import Invariant
from .proposal import Proposal
from .store import Store, Versioned
from .topology import Topology


@dataclass
class Accept:
    commit_id: int
    kind: str = "accept"


@dataclass
class Repair:
    stale_keys: list[str]
    fresh: dict[str, tuple[Any, int]]
    kind: str = "repair"


@dataclass
class Reject:
    reason: str  # invariant | authority | stale
    detail: str = ""
    headroom: int | None = None
    kind: str = "reject"


@dataclass
class _Registration:
    agent: str
    commit_id: int
    postconditions: dict[str, Any]


class CommitGate:
    def __init__(self, store: Store, topology: Topology | None = None,
                 invariants: list[Invariant] | None = None,
                 stale_policy: str = "repair", mode: str = "enforce",
                 runlog=None, monitor=None):
        if stale_policy not in ("repair", "reject"):
            raise ValueError(f"stale_policy must be repair|reject, got {stale_policy!r}")
        if mode not in ("enforce", "observe"):
            raise ValueError(f"mode must be enforce|observe, got {mode!r}")
        self.store = store
        self.topology = topology
        self.invariants = list(invariants or [])
        self.stale_policy = stale_policy
        self.mode = mode
        self.runlog = runlog
        self.monitor = monitor
        self._next_commit_id = 1
        self.would_be_rejections: list[dict] = []

    def _log(self, kind: str, agent: str, **payload) -> None:
        if self.runlog is not None:
            self.runlog.emit(kind, agent=agent, **payload)

    def commit(self, p: Proposal) -> Accept | Repair | Reject:
        with self.store.lock():
            self._log("propose", p.agent, role=p.role,
                      writes=sorted(p.writes), draws=dict(sorted(p.draws.items())),
                      read_set=dict(sorted(p.read_set.items())),
                      unseen_premises=p.unseen_premises())

            # 1. authority: writes outside the role's registered write set
            if self.topology is not None:
                for key in p.writes:
                    if not self.topology.can_write(p.role, key):
                        self._log("reject", p.agent, reason="authority", key=key)
                        return Reject(reason="authority",
                                      detail=f"role {p.role!r} may not write {key!r}")

            # 2. read-set validation (cross-key: every key the context showed)
            validated = p.validated_read_set()
            stale: dict[str, Versioned] = {}
            for key, ver in validated.items():
                cur = self.store.get(key)
                if cur.version != ver:
                    stale[key] = cur
            if stale and self.mode == "enforce":
                stale_keys = sorted(stale)
                if self.stale_policy == "repair":
                    fresh = {k: (v.value, v.version) for k, v in stale.items()}
                    self._log("repair", p.agent, stale_keys=stale_keys)
                    return Repair(stale_keys=stale_keys, fresh=fresh)
                self._log("reject", p.agent, reason="stale", stale_keys=stale_keys)
                return Reject(reason="stale", detail=f"stale keys: {stale_keys}")

            # 3. invariants: refuse, never advise
            for inv in self.invariants:
                violation = inv.check(self.store, p)
                if violation is not None:
                    if self.mode == "observe":
                        self.would_be_rejections.append(
                            {"agent": p.agent, "reason": "invariant",
                             "detail": violation.reason})
                        self._log("reject", p.agent, reason="invariant",
                                  detail=violation.reason,
                                  headroom=violation.headroom, observed_only=True)
                        break
                    self._log("reject", p.agent, reason="invariant",
                              detail=violation.reason, headroom=violation.headroom)
                    return Reject(reason="invariant", detail=violation.reason,
                                  headroom=violation.headroom)

            # 4. apply (atomic; versions re-checked inside apply_atomic)
            result = self.store.apply_atomic(
                expected=validated if self.mode == "enforce" else {},
                writes=p.writes, draws=p.draws, role=p.role)
            if not result.ok:
                stale_keys = sorted(result.stale)
                fresh = {k: (v.value, v.version) for k, v in result.stale.items()}
                self._log("repair", p.agent, stale_keys=stale_keys)
                return Repair(stale_keys=stale_keys, fresh=fresh)

            commit_id = self._next_commit_id
            self._next_commit_id += 1

            # 5. register postconditions
            if p.postconditions and self.monitor is not None:
                self.monitor.register(p.agent, commit_id, p.postconditions)

            # 6. log
            for resource, amount in sorted(p.draws.items()):
                self._log("draw", p.agent, resource=resource, amount=amount)
            self._log("accept", p.agent, commit_id=commit_id,
                      writes=sorted(p.writes))
            return Accept(commit_id=commit_id)
