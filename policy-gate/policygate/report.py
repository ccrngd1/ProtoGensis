"""Reports from a run directory alone (AC #17). DETERMINISTIC.

Renders: violations per rule x reading; (rule, vtool) firing rates with the
0.9/min_support flag; policy self-edits; retroactive section; obligations
placeholder; the principal-provenance line.
"""

import json
import os

from . import readings as readings_mod

MIN_SUPPORT = 5
FLAG_RATE = 0.9


def firing_rates(by_rule_tool, min_support=MIN_SUPPORT):
    """by_rule_tool: {(rule, vtool): {"n": int, "fired": int}} -> list sorted."""
    out = []
    for (rule, vtool), c in sorted(by_rule_tool.items()):
        n, fired = c["n"], c["fired"]
        rate = round(fired / n, 4) if n else 0.0
        out.append({"rule": rule, "vtool": vtool, "n": n, "fired": fired,
                    "rate": rate, "flag": rate >= FLAG_RATE and n >= min_support})
    return out


def render_run(run_dir, fmt):
    with open(os.path.join(run_dir, "aggregates.json"), encoding="utf-8") as f:
        agg = json.load(f)
    obligations = agg.get("obligations")
    data = {
        "profile": agg["profile"],
        "provenance_source": agg["provenance_source"],
        "readings_sha256": agg["readings_sha256"],
        "violations_per_reading": {r: agg["readings"][r]["blocked"] for r in readings_mod.READINGS},
        "firing_rates": agg.get("firing_rates", []),
        "retroactive": agg.get("retroactive_rules", {}),
        "obligations": obligations if obligations is not None
        else "obligations: not evaluated in v1",
        "verdict_classes": agg.get("verdict_classes", {}),
    }
    if "counterfactual" in agg:
        data["counterfactual"] = agg["counterfactual"]
    if agg.get("per_version_rules"):
        data["per_version_rules"] = agg["per_version_rules"]
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [
        f"profile: {data['profile']}",
        f"principal provenance: {data['provenance_source']} (legacy JSONL has no typed provenance)",
        f"readings sha256: {data['readings_sha256'][:16]}",
        "",
        "violations per reading:",
    ]
    for r in readings_mod.READINGS:
        lines.append(f"  {r}: {data['violations_per_reading'][r]}")
    if isinstance(data["obligations"], dict):
        lines.append("obligations (report section, not gates):")
        for rid, n in data["obligations"].items():
            lines.append(f"  {rid}: {n}")
    else:
        lines.append(data["obligations"])
    if data.get("retroactive"):
        lines.append("retroactive (never counted as violations):")
        for rid, row in data["retroactive"].items():
            lines.append(f"  {rid}: flagged {row['flagged']} ({row['class']})")
    cf = data.get("counterfactual")
    if cf:
        lines.append(cf["label"])
        for r in readings_mod.READINGS:
            t = cf["readings"][r]
            lines.append(f"  {r}: {t['blocked']}/{t['total']}")
    return "\n".join(lines)
