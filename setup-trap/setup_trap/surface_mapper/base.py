"""Surface-inventory data model and runtime registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from setup_trap.model import Provenance


@dataclass
class SurfaceEntry:
    """One init-time file an attacker could weaponize.

    ``provenance`` here means: is this runtime read-behavior *documented* by the
    vendor (SOURCED), or an *inferred* deduction (INFERRED)? We do not assert
    unverified read-order as fact.
    """

    path: str
    when_read: str
    scope: str  # user-global | project | directory-chain | skill | session
    risk: str  # attacker-can-write-this -> can-do-that
    provenance: Provenance
    note: str = ""


@dataclass
class SurfaceInventory:
    runtime: str
    display_name: str
    summary: str
    entries: list = field(default_factory=list)  # list[SurfaceEntry]

    def to_dict(self) -> dict:
        return {
            "runtime": self.runtime,
            "display_name": self.display_name,
            "summary": self.summary,
            "entries": [
                {
                    "path": e.path,
                    "when_read": e.when_read,
                    "scope": e.scope,
                    "risk": e.risk,
                    "provenance": e.provenance.value,
                    "note": e.note,
                }
                for e in self.entries
            ],
        }


# runtime key -> loader function; populated at import time.
RUNTIMES: dict = {}


def register(key: str):
    def deco(fn):
        RUNTIMES[key] = fn
        return fn

    return deco


def _ensure_registered() -> None:
    # Import runtime modules so their @register decorators populate RUNTIMES.
    from setup_trap.surface_mapper.runtimes import (  # noqa: F401
        claude_code,
        copilot,
        cursor,
        openclaw,
    )


def list_runtimes() -> list:
    _ensure_registered()
    return sorted(RUNTIMES.keys())


def get_inventory(runtime: str) -> SurfaceInventory:
    _ensure_registered()
    if runtime not in RUNTIMES:
        raise KeyError(
            f"unknown runtime {runtime!r}; known: {list_runtimes()}"
        )
    return RUNTIMES[runtime]()
