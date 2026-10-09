"""Health gate against silent fallback (AC #6, gbrain lesson) + oracle flags (AC #7).

A cell is INVALID (excluded, counted, never scored as a failure) unless:
- RAG/hybrid arms (a3, a4, a5, a5bg): >=1 successful embedding call AND >=1
  retrieval returning >=1 hit in that cell;
- a2: a non-empty catalog was injected;
- a6: >=1 transcript file on disk AND the grep tool registered;
- a1/a5/a5bg: the core/workspace was loaded.

The report refuses headline comparisons (exit 3) if any arm exceeds 5% invalid
cells. Oracle flags (AC #7): BROKEN if A* < 90% on a storyline; NON_SEPARATING
if every arm is within 3 pts of A*.
"""

INVALID_THRESHOLD = 0.05
RAG_ARMS = {"a3", "a4", "a5", "a5bg"}


def cell_validity(cell: dict) -> tuple[str, str]:
    """cell: a `cell` event. Returns (status, reason): VALID | INVALID(reason)."""
    arm = cell["arm"]
    if arm in RAG_ARMS:
        if cell.get("embedding_calls", 0) < 1:
            return "INVALID", "no successful embedding call"
        if cell.get("retrieval_hits", 0) < 1:
            return "INVALID", "no retrieval returned a hit"
    if arm == "a2" and not cell.get("catalog_nonempty", False):
        return "INVALID", "empty catalog injected"
    if arm == "a6":
        if cell.get("transcript_count", 0) < 1:
            return "INVALID", "no transcript files"
        if "grep" not in cell.get("tools_registered", []):
            return "INVALID", "grep tool not registered"
    if arm in ("a1", "a5", "a5bg") and not cell.get("core_loaded", True):
        return "INVALID", "core/workspace not loaded"
    return "VALID", ""


def arm_invalid_rates(cells: list[dict]) -> dict:
    """arm -> (invalid_count, total, rate)."""
    out = {}
    for c in cells:
        status, _ = cell_validity(c)
        arm = c["arm"]
        inv, tot = out.get(arm, (0, 0))
        out[arm] = (inv + (status == "INVALID"), tot + 1)
    return {arm: {"invalid": inv, "total": tot,
                  "rate": round(inv / tot, 4) if tot else 0.0}
            for arm, (inv, tot) in sorted(out.items())}


def gate_headline(cells: list[dict]) -> tuple[bool, dict]:
    """False = refuse headline comparisons (any arm > 5% invalid cells)."""
    rates = arm_invalid_rates(cells)
    ok = all(v["rate"] <= INVALID_THRESHOLD for v in rates.values())
    return ok, rates


def storyline_flags(probe_scores: list[dict]) -> dict:
    """storyline -> OK | BROKEN | NON_SEPARATING from scored probes (AC #7).

    probe_scores: dicts with arm, storyline, applied. Flags computed on the
    pooled per-storyline success rates."""
    by_story: dict[str, dict[str, list[bool]]] = {}
    for p in probe_scores:
        by_story.setdefault(p["storyline"], {}).setdefault(p["arm"], []).append(p["applied"])
    flags = {}
    for story, arms in sorted(by_story.items()):
        rates = {a: (sum(v) / len(v)) for a, v in arms.items() if v}
        oracle = rates.get("astar")
        if oracle is None:
            flags[story] = "OK"
            continue
        if oracle < 0.90:
            flags[story] = "BROKEN"
            continue
        others = [r for a, r in rates.items() if a not in ("astar",)]
        if others and all(abs(oracle - r) <= 0.03 for r in others):
            flags[story] = "NON_SEPARATING"
        else:
            flags[story] = "OK"
    return flags
