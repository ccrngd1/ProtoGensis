"""EffectMonitor: committed-effect tracking (Study V P-tasks).

On Accept, the gate registers (agent, commit_id, postconditions). check()
runs on store events and at turn boundaries. When an earlier committed
postcondition stops holding (silent revert) it emits exactly one Notice per
(commit, key) breakage no matter how many times check() runs, and re-arms
only after the postcondition holds again. Notices are advisory to the agent
(one notice was enough in Study V); invariants, by contrast, refuse.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Notice:
    agent: str
    commit_id: int
    key: str
    expected: Any
    actual: Any

    def render(self) -> str:
        return (f"NOTICE to {self.agent}: committed effect {self.key}={self.expected!r} "
                f"no longer holds (now {self.actual!r})")


class EffectMonitor:
    def __init__(self, store):
        self.store = store
        self._registrations: list[tuple[str, int, dict[str, Any]]] = []
        self._tripped: set[tuple[int, str]] = set()  # (commit_id, key) already noticed
        self.notices: list[Notice] = []
        self._pending: dict[str, list[Notice]] = {}  # agent -> undelivered notices
        store.subscribe(self._on_event)

    def register(self, agent: str, commit_id: int, postconditions: dict[str, Any]) -> None:
        self._registrations.append((agent, commit_id, dict(postconditions)))

    def _holds(self, key: str, want: Any) -> bool:
        actual = self.store.get(key).value
        if callable(want):
            return bool(want(actual))
        return actual == want

    def _on_event(self, event: dict) -> None:
        if event.get("kind") in ("write", "env_change"):
            self.check()

    def check(self) -> list[Notice]:
        """Re-check all registered postconditions. Returns only NEW notices."""
        new: list[Notice] = []
        for agent, commit_id, posts in self._registrations:
            for key, want in posts.items():
                dedup = (commit_id, key)
                if self._holds(key, want):
                    self._tripped.discard(dedup)  # re-arm once it holds again
                    continue
                if dedup in self._tripped:
                    continue
                self._tripped.add(dedup)
                expected = want if not callable(want) else f"<predicate {getattr(want, '__name__', 'fn')}>"
                notice = Notice(agent=agent, commit_id=commit_id, key=key,
                                expected=expected, actual=self.store.get(key).value)
                new.append(notice)
                self.notices.append(notice)
                self._pending.setdefault(agent, []).append(notice)
        return new

    def pending_for(self, agent: str) -> list[Notice]:
        """Drain undelivered notices for an agent (the adapter injects them
        into the agent's next context)."""
        out = self._pending.pop(agent, [])
        return out
