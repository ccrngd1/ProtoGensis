"""Attack-surface mapper (FR5).

For each supported runtime, enumerate the files read at init time and the
"attacker can write THIS -> can do THAT" mapping. Every entry is provenance
tagged (documented vs inferred) so the report never asserts unverified
read-order as fact (FR5.3).
"""

from setup_trap.surface_mapper.base import (
    RUNTIMES,
    SurfaceEntry,
    SurfaceInventory,
    get_inventory,
    list_runtimes,
)

__all__ = [
    "RUNTIMES",
    "SurfaceEntry",
    "SurfaceInventory",
    "get_inventory",
    "list_runtimes",
]
