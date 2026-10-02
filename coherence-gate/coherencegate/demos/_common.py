"""Shared demo plumbing: the citation header, the reproduction banner, and
deterministic table rendering. Every demo header prints both (AC #8/#11)."""
from __future__ import annotations

import json

CITATION = ("Paper: arXiv 2610.02036, Heng (2026), \"Global Coherence: When Every "
            "Agent Is Right and the Team Is Still Wrong\"")
BANNER = "reproduction-style, not a replication of paper numbers"


def header(title: str) -> list[str]:
    return [
        f"=== CoherenceGate demo: {title} ===",
        CITATION,
        BANNER,
        "Scripted mock agents show the mechanism; they are not evidence.",
        "",
    ]


def paper_block(label: str, lines: list[str]) -> list[str]:
    """A separately labeled paper-reference block: the paper's numbers, never ours."""
    out = ["", f"--- paper reference ({label}; not our numbers) ---"]
    out.extend(f"  {line}" for line in lines)
    out.append("  Paper limits: single author, one model family (gpt-6-sol), "
               "5 seeds per cell, synthetic probes / injected failures.")
    return out


def table(rows: list[dict], columns: list[str]) -> list[str]:
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    fmt = "  ".join(f"{{:<{widths[c]}}}" for c in columns)
    lines = [fmt.format(*columns), fmt.format(*("-" * widths[c] for c in columns))]
    lines.extend(fmt.format(*(str(r.get(c, "")) for c in columns)) for r in rows)
    return lines


def to_json(payload: dict) -> str:
    """Stable, byte-deterministic JSON (sorted keys, no timestamps/paths/PIDs)."""
    return json.dumps(payload, sort_keys=True, indent=2)
