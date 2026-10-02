"""ContextAssembler: the only path by which authoritative facts enter a prompt.

Every injected fact is rendered with a ``[key@vN]`` tag and the key -> version
read set is recorded as a side effect of rendering (Prop 4.1's "hard
condition", made cheap by construction). Owned-resource headroom is rendered
display-only: it appears in the text but never enters the read set, so
spenders don't version-conflict on a shared counter (AC #4).
"""
from __future__ import annotations

import json
import re
from typing import Any

from .store import Store

_TAG_RE = re.compile(r"\[([^\[\]@]+)@v(\d+)\]")


class AgentContext:
    def __init__(self, store: Store, agent: str, role: str):
        self._store = store
        self.agent = agent
        self.role = role
        self.read_set: dict[str, int] = {}
        self.displayed_owned: dict[str, int] = {}
        self._lines: list[str] = []
        self._frozen = False

    def show(self, key: str) -> Any:
        """Render ``[key@vN] = <json value>`` and record the read."""
        if self._frozen:
            raise RuntimeError("context is frozen; it already went to the model")
        v = self._store.get(key)
        self.read_set[key] = v.version
        self._lines.append(f"[{key}@v{v.version}] = {json.dumps(v.value, sort_keys=True)}")
        return v.value

    def show_owned(self, resource: str, limit: int | None = None) -> int:
        """Display-only owned-resource headroom; recorded as displayed_owned,
        never in the read set."""
        if self._frozen:
            raise RuntimeError("context is frozen; it already went to the model")
        used = self._store.draw_total(resource)
        self.displayed_owned[resource] = used
        suffix = f"/{limit}" if limit is not None else ""
        self._lines.append(f"(owned) {resource} used = {used}{suffix}")
        return used

    def note(self, text: str) -> None:
        """Free-text line (instructions, notices). Not a read."""
        if self._frozen:
            raise RuntimeError("context is frozen; it already went to the model")
        self._lines.append(text)

    def render(self) -> str:
        """Byte-deterministic render. Freezes the read set."""
        self._frozen = True
        return "\n".join(self._lines)


class ContextAssembler:
    def __init__(self, store: Store):
        self._store = store

    def for_agent(self, agent: str, role: str) -> AgentContext:
        return AgentContext(self._store, agent, role)


def tags_in(text: str) -> dict[str, int]:
    """Parse all [key@vN] tags out of rendered text (for parity tests)."""
    return {m.group(1): int(m.group(2)) for m in _TAG_RE.finditer(text)}
