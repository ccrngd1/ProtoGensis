"""Majority vote at (derived type, predicate, tool) granularity (AC #6).

N runs are aggregated: a (type, predicate, tool) triple kept iff it appears in
> N/2 runs; the vote string ("4/5") is recorded; minority drops are reported.
A run whose polarity disagrees yields a different derived type and is counted
separately.
"""

from collections import defaultdict

from .. import rules


def aggregate(runs, n=None):
    """runs: list of lists of candidate dicts (one list per LLM run).

    Returns {"kept": [candidate...], "minority_drops": [...], "votes": {...}}.
    Each kept candidate's `votes` field is set to "<k>/<N>".
    """
    n = n if n is not None else len(runs)
    # key: (type, predicate, tool); value: {"count": int, "example": candidate}
    tally = defaultdict(lambda: {"count": 0, "runs": set(), "example": None,
                                 "tools": set()})
    for ri, run in enumerate(runs):
        for c in run:
            try:
                typ = rules.derive_type(c.get("polarity"))
            except rules.RuleError:
                continue
            for tool in c.get("tools", []):
                key = (typ, c["predicate"], tool)
                t = tally[key]
                if ri not in t["runs"]:
                    t["count"] += 1
                    t["runs"].add(ri)
                t["example"] = c
    kept_triples = {}
    minority = []
    for key, t in tally.items():
        typ, pred, tool = key
        vote = f"{t['count']}/{n}"
        if t["count"] * 2 > n:
            kept_triples.setdefault((typ, pred), {"example": t["example"],
                                                  "tools": [], "count": t["count"]})
            kept_triples[(typ, pred)]["tools"].append(tool)
            kept_triples[(typ, pred)]["count"] = max(kept_triples[(typ, pred)]["count"], t["count"])
        else:
            minority.append({"type": typ, "predicate": pred, "tool": tool, "votes": vote})
    kept = []
    for (typ, pred), info in sorted(kept_triples.items()):
        c = dict(info["example"])
        c["type"] = typ
        c["tools"] = sorted(set(info["tools"]))
        c["votes"] = f"{info['count']}/{n}"
        kept.append(c)
    return {
        "kept": kept,
        "minority_drops": sorted(minority, key=lambda m: (m["type"], m["predicate"], m["tool"])),
        "n": n,
    }
