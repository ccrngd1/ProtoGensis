"""Authoritative versioned store (the paper's D: history/versions).

Two backends at parity: InMemoryStore and SQLiteStore. Every write bumps the
key's version. ``apply_atomic`` is the only write path for agents; the gate
calls it under the store's lock. Owned-resource totals (draws) are stored
separately from versioned keys so spenders never conflict on a counter's
version (no OCC thrash; see research design decision 2).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, NamedTuple, Protocol


class Versioned(NamedTuple):
    value: Any
    version: int


@dataclass
class ApplyResult:
    ok: bool
    stale: dict[str, Versioned] = field(default_factory=dict)


class Store(Protocol):
    """Protocol both backends implement."""

    def get(self, key: str) -> Versioned: ...
    def snapshot(self, keys: list[str]) -> dict[str, Versioned]: ...
    def apply_atomic(
        self,
        expected: dict[str, int],
        writes: dict[str, Any],
        draws: dict[str, int] | None = None,
        role: str | None = None,
        source: str = "agent",
    ) -> ApplyResult: ...
    def out_of_band(self, key: str, value: Any) -> None: ...
    def subscribe(self, callback: Callable[[dict], None]) -> None: ...
    def draw_total(self, resource: str) -> int: ...
    def draw_total_by_role(self, resource: str, role: str) -> int: ...
    def lock(self): ...


class _BaseStore:
    """Shared lock/subscription machinery."""

    def __init__(self) -> None:
        self._rlock = threading.RLock()
        self._subscribers: list[Callable[[dict], None]] = []

    @contextmanager
    def lock(self):
        with self._rlock:
            yield self

    def subscribe(self, callback: Callable[[dict], None]) -> None:
        self._subscribers.append(callback)

    def _notify(self, event: dict) -> None:
        for cb in self._subscribers:
            cb(event)


class InMemoryStore(_BaseStore):
    def __init__(self, init: dict[str, Any] | None = None):
        super().__init__()
        self._kv: dict[str, Versioned] = {}
        self._draws: dict[tuple[str, str], int] = {}  # (resource, role) -> amount
        for k, v in (init or {}).items():
            self._kv[k] = Versioned(v, 1)

    def get(self, key: str) -> Versioned:
        with self._rlock:
            return self._kv.get(key, Versioned(None, 0))

    def snapshot(self, keys: list[str]) -> dict[str, Versioned]:
        with self._rlock:  # consistent cut
            return {k: self.get(k) for k in keys}

    def apply_atomic(self, expected, writes, draws=None, role=None, source="agent"):
        with self._rlock:
            stale = {}
            for k, ver in (expected or {}).items():
                cur = self.get(k)
                if cur.version != ver:
                    stale[k] = cur
            if stale:
                return ApplyResult(ok=False, stale=stale)
            for k, v in (writes or {}).items():
                cur = self.get(k)
                self._kv[k] = Versioned(v, cur.version + 1)
                self._notify({"kind": "write", "key": k, "value": v,
                              "version": cur.version + 1, "source": source})
            for resource, amount in (draws or {}).items():
                rk = (resource, role or "")
                self._draws[rk] = self._draws.get(rk, 0) + amount
                self._notify({"kind": "draw", "resource": resource, "role": role,
                              "amount": amount, "source": source})
            return ApplyResult(ok=True)

    def out_of_band(self, key: str, value: Any) -> None:
        with self._rlock:
            cur = self.get(key)
            self._kv[key] = Versioned(value, cur.version + 1)
            self._notify({"kind": "env_change", "key": key, "value": value,
                          "version": cur.version + 1, "source": "environment"})

    def draw_total(self, resource: str) -> int:
        with self._rlock:
            return sum(a for (r, _), a in self._draws.items() if r == resource)

    def draw_total_by_role(self, resource: str, role: str) -> int:
        with self._rlock:
            return self._draws.get((resource, role), 0)


class SQLiteStore(_BaseStore):
    """SQLite backend: one file, BEGIN IMMEDIATE for atomic validate+apply."""

    def __init__(self, path: str = ":memory:", init: dict[str, Any] | None = None):
        super().__init__()
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.isolation_level = None  # explicit transactions
        with self._rlock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT, version INTEGER)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS draws (resource TEXT, role TEXT, amount INTEGER)")
            for k, v in (init or {}).items():
                self._conn.execute(
                    "INSERT OR REPLACE INTO kv VALUES (?, ?, 1)", (k, json.dumps(v)))

    def get(self, key: str) -> Versioned:
        with self._rlock:
            row = self._conn.execute(
                "SELECT value, version FROM kv WHERE key = ?", (key,)).fetchone()
            if row is None:
                return Versioned(None, 0)
            return Versioned(json.loads(row[0]), row[1])

    def snapshot(self, keys: list[str]) -> dict[str, Versioned]:
        with self._rlock:
            return {k: self.get(k) for k in keys}

    def apply_atomic(self, expected, writes, draws=None, role=None, source="agent"):
        with self._rlock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                stale = {}
                for k, ver in (expected or {}).items():
                    cur = self.get(k)
                    if cur.version != ver:
                        stale[k] = cur
                if stale:
                    self._conn.execute("ROLLBACK")
                    return ApplyResult(ok=False, stale=stale)
                events = []
                for k, v in (writes or {}).items():
                    cur = self.get(k)
                    self._conn.execute(
                        "INSERT OR REPLACE INTO kv VALUES (?, ?, ?)",
                        (k, json.dumps(v), cur.version + 1))
                    events.append({"kind": "write", "key": k, "value": v,
                                   "version": cur.version + 1, "source": source})
                for resource, amount in (draws or {}).items():
                    self._conn.execute(
                        "INSERT INTO draws VALUES (?, ?, ?)", (resource, role or "", amount))
                    events.append({"kind": "draw", "resource": resource, "role": role,
                                   "amount": amount, "source": source})
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            for ev in events:
                self._notify(ev)
            return ApplyResult(ok=True)

    def out_of_band(self, key: str, value: Any) -> None:
        with self._rlock:
            cur = self.get(key)
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?, ?)",
                               (key, json.dumps(value), cur.version + 1))
            self._conn.execute("COMMIT")
            self._notify({"kind": "env_change", "key": key, "value": value,
                          "version": cur.version + 1, "source": "environment"})

    def draw_total(self, resource: str) -> int:
        with self._rlock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM draws WHERE resource = ?",
                (resource,)).fetchone()
            return row[0]

    def draw_total_by_role(self, resource: str, role: str) -> int:
        with self._rlock:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM draws WHERE resource = ? AND role = ?",
                (resource, role)).fetchone()
            return row[0]

    def close(self) -> None:
        with self._rlock:
            self._conn.close()
