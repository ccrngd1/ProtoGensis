"""
Benchmark report: print comparison table for xMemory vs flat top-k retrieval.
"""

from __future__ import annotations

import sys
from typing import List


def print_report(rows) -> None:
    """Print a formatted comparison table to stdout."""
    if not rows:
        print("No benchmark results to report.")
        return

    # Header
    sep = "-" * 100
    print("\n" + sep)
    print("xMemory vs Flat Top-k Retrieval — Benchmark Results")
    print(sep)
    print(
        f"{'Query':<52} {'xMem Tok':>8} {'Flat Tok':>8} "
        f"{'Reduction':>10} {'Level':<10} {'xMem Sems':>9}"
    )
    print(sep)

    for row in rows:
        query_display = row.query[:50] + ".." if len(row.query) > 50 else row.query
        print(
            f"{query_display:<52} {row.xmemory_tokens:>8} {row.flat_tokens:>8} "
            f"{row.token_reduction_pct:>9.1f}% {row.xmemory_level:<10} "
            f"{row.xmemory_semantic_count:>9}"
        )

    print(sep)

    # Aggregate stats
    avg_reduction = sum(r.token_reduction_pct for r in rows) / len(rows)
    avg_xmem = sum(r.xmemory_tokens for r in rows) / len(rows)
    avg_flat = sum(r.flat_tokens for r in rows) / len(rows)

    print(f"{'AVERAGE':<52} {avg_xmem:>8.0f} {avg_flat:>8.0f} {avg_reduction:>9.1f}%")
    print(sep)

    goal_met = avg_reduction >= 40.0
    print(f"\n✅ Token reduction goal (≥40%): {'MET' if goal_met else 'NOT MET'} "
          f"(actual: {avg_reduction:.1f}%)")

    levels = [r.xmemory_level for r in rows]
    from collections import Counter
    level_counts = Counter(levels)
    print(f"Retrieval levels used: {dict(level_counts)}")
    print()


if __name__ == "__main__":
    # Allow piping JSON rows for standalone use
    import json
    from dataclasses import dataclass

    # Minimal shim to re-use print_report from CLI
    data = json.load(sys.stdin)

    @dataclass
    class Row:
        query: str
        xmemory_tokens: int
        flat_tokens: int
        xmemory_level: str
        xmemory_semantic_count: int
        flat_message_count: int
        token_reduction_pct: float

    rows = [Row(**r) for r in data]
    print_report(rows)
