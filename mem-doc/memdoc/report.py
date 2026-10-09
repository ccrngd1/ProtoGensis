"""Report (AC #5, #7, #9, #10): computed only from the run log (+ prereg).

Sections: validity; per arm x category x size success / SR@depth-k / retention /
stale rate / write fidelity / store growth / cause codes / silent-failure share;
cost block (cached + uncached counterfactual side by side, cache hit %); and the
hypotheses block (live logs only; mock logs print "hypotheses not evaluated:
mock run" and exit 0).

Formats: terminal, md, json (sorted keys, fixed float formatting). Mock reports
carry the mechanism banner and label success columns "context delivery
(mechanism)", never accuracy.
"""

import json
from collections import defaultdict

from . import MECHANISM_BANNER
from .cost import aggregate, load_pricing
from .health import arm_invalid_rates, cell_validity, gate_headline, storyline_flags
from .prereg import prereg_hash
from .runlog import read_events
from .scorer import score_probe

EXIT_HEADLINE_REFUSED = 3


def fmt(x, nd=4):
    return f"{x:.{nd}f}"


def build_report(runlog_path, pricing_path=None) -> tuple[dict, int]:
    """Returns (report dict, exit code)."""
    events = read_events(runlog_path)
    header = next((e for e in events if e.get("event") == "run_header"), {})
    mode = header.get("mode", "mock")
    calls = [e for e in events if e.get("event") == "call"]
    probes = [e for e in events if e.get("event") == "probe"]
    cells = [e for e in events if e.get("event") == "cell"]
    fidelity = [e for e in events if e.get("event") == "write_fidelity"]
    prices = load_pricing(pricing_path)

    # ---- score probes on VALID cells only ----
    validity = {}
    for c in cells:
        key = (c["arm"], c["size"], c["seed"], c["storyline"])
        status, reason = cell_validity(c)
        validity[key] = (status, reason)
    scored = []
    for p in probes:
        key = (p["arm"], p["size"], p["seed"], p["storyline"])
        status, _ = validity.get(key, ("VALID", ""))
        rec = dict(p)
        rec.update(score_probe(p))
        rec["cell_status"] = status
        scored.append(rec)
    valid_scored = [p for p in scored if p["cell_status"] == "VALID"]

    headline_ok, invalid_rates = gate_headline(cells)
    flags = storyline_flags([{"arm": p["arm"], "storyline": p["storyline"],
                              "applied": p["applied"]} for p in valid_scored])
    broken = sorted([s for s, f in flags.items() if f == "BROKEN"])
    non_separating = sorted([s for s, f in flags.items() if f == "NON_SEPARATING"])

    # ---- per arm x size blocks ----
    by_cell_calls = defaultdict(list)
    for c in calls:
        by_cell_calls[(c["arm"], c["size"])].append(c)

    def _probe_block(ps):
        n = len(ps)
        if not n:
            return {}
        applied = sum(p["applied"] for p in ps)
        gold_ctx = sum(p["fact_in_context"] for p in ps)
        stale_ctx = sum(p["stale_in_context"] for p in ps)
        stale_first = sum(p.get("stale_first", False) for p in ps)
        stale_ans = sum(p["stale_answer"] for p in ps)
        causes = defaultdict(int)
        silent = visible = 0
        for p in ps:
            if not p["applied"]:
                causes[p["cause"]] += 1
                if p["cause_class"] == "visible":
                    visible += 1
                else:
                    silent += 1
        failed = visible + silent
        depths = defaultdict(lambda: [0, 0])
        for p in ps:
            d = p.get("depth", 1)
            depths[d][0] += p["applied"]
            depths[d][1] += 1
        uu = [p for p in ps if p.get("unknown_unknown")]
        return {
            "probes": n,
            "delivery_rate": fmt(applied / n),
            "gold_in_context_pct": fmt(100 * gold_ctx / n, 1),
            "stale_in_context_pct": fmt(100 * stale_ctx / n, 1),
            "stale_first_pct": fmt(100 * stale_first / n, 1),
            "stale_answer_rate": fmt(stale_ans / n),
            "retention": fmt(sum(1 for p in ps if p["fact_in_context"] and p["applied"]) / n),
            "sr_at_depth": {str(d): fmt(a / t) for d, (a, t) in sorted(depths.items())},
            "cause_codes": dict(sorted(causes.items())),
            "silent_failure_share": fmt(silent / failed) if failed else "n/a",
            "unknown_unknown": {"probes": len(uu),
                                "delivery_rate": fmt(sum(p["applied"] for p in uu) / len(uu))
                                if uu else "n/a"},
        }

    arms = sorted({p["arm"] for p in probes})
    sizes = sorted({p["size"] for p in probes})
    per_arm_size = {}
    for arm in arms:
        for size in sizes:
            ps = [p for p in valid_scored if p["arm"] == arm and p["size"] == size]
            cs = by_cell_calls.get((arm, size), [])
            usages = [{k: c.get(k, 0) for k in ("inputTokens", "cacheReadInputTokens",
                                                "cacheWriteInputTokens", "outputTokens")}
                      for c in cs]
            agg = aggregate(usages, prices)
            cell_list = [c for c in cells if c["arm"] == arm and c["size"] == size]
            n_sessions = max(1, len(cell_list) * 5)
            block = _probe_block(ps)
            block["cost"] = {
                "usd_total": agg["usd"],
                "usd_uncached_counterfactual": agg["usd_uncached_counterfactual"],
                "usd_per_session_cached": fmt(agg["usd"] / n_sessions, 4),
                "usd_per_session_uncached": fmt(agg["usd_uncached_counterfactual"] / n_sessions, 4),
                "cache_hit_pct": agg["cache_hit_pct"],
                "tokens": agg["tokens"],
                "calls": agg["calls"],
            }
            if cell_list:
                block["store_tokens_measured"] = round(
                    sum(c.get("store_tokens", 0) for c in cell_list) / len(cell_list))
                block["memory_tokens_per_call"] = fmt(
                    sum(c.get("memory_tokens_per_call", 0.0) for c in cell_list) / len(cell_list), 1)
            # $ per successful task: storyline-runs whose final probe passed
            final = {}
            for p in ps:
                key = (p["storyline"], p["seed"])
                cur = final.get(key)
                if cur is None or (p["session"], p["probe_id"]) >= cur[0]:
                    final[key] = ((p["session"], p["probe_id"]), p["applied"])
            successes = sum(1 for _, ok in final.values() if ok)
            block["usd_per_successful_task"] = (
                fmt(agg["usd"] / successes, 4) if successes else "n/a")
            per_arm_size[f"{arm}@{size}"] = block

    # write fidelity per arm
    wf = {}
    for arm in arms:
        fs = [f for f in fidelity if f["arm"] == arm]
        if fs:
            wf[arm] = {"present_rate": fmt(sum(f["present"] for f in fs) / len(fs)),
                       "superseded_handled_rate": fmt(
                           sum(f["superseded_handled"] for f in fs) / len(fs))}

    report = {
        "banner": MECHANISM_BANNER if mode == "mock" else None,
        "mode": mode,
        "run_id": header.get("run_id", ""),
        "prereg_hash_log": header.get("prereg_hash", ""),
        "prereg_hash_current": prereg_hash(),
        "token_source": header.get("token_source", ""),
        "label": "context delivery (mechanism)" if mode == "mock" else "accuracy",
        "validity": {"invalid_rates": invalid_rates,
                     "headline_ok": headline_ok,
                     "broken_storylines": broken,
                     "non_separating_storylines": non_separating},
        "per_arm_size": per_arm_size,
        "write_fidelity": wf,
        "pricing": {"as_of": prices.as_of, "label": prices.label},
    }

    if mode == "mock":
        report["hypotheses"] = "hypotheses not evaluated: mock run"
    else:
        if header.get("prereg_hash") != prereg_hash():
            report["hypotheses"] = "REFUSED: run log prereg hash differs from current lock"
            return report, 1
        report["hypotheses"] = evaluate_hypotheses(valid_scored, per_arm_size)

    exit_code = 0 if headline_ok else EXIT_HEADLINE_REFUSED
    return report, exit_code


def evaluate_hypotheses(valid_scored, per_arm_size):
    """Live-only hypothesis block. Arms not present make comparisons NOT_TESTED."""
    from .prereg import HYPOTHESES
    from .stats import holm, mcnemar_exact

    present_arms = {p["arm"] for p in valid_scored}
    results = {}
    p_values = {}
    for h in HYPOTHESES:
        missing = [a for a in h.arms if a not in present_arms]
        if missing:
            results[h.id] = {"verdict": "NOT_TESTED",
                             "reason": f"arms not built/run: {', '.join(missing)}"}
            continue
        # paired by storyline x seed on the hypothesis's categories/sizes
        pairs = defaultdict(dict)
        for p in valid_scored:
            if p["category"] in h.categories and p["size"] in h.sizes:
                pairs[(p["storyline"], p["seed"], p["probe_id"])][p["arm"]] = p["applied"]
        a_arm, b_arm = h.arms[0], h.arms[-1]
        b = c = 0
        for d in pairs.values():
            if a_arm in d and b_arm in d:
                if d[a_arm] and not d[b_arm]:
                    b += 1
                elif d[b_arm] and not d[a_arm]:
                    c += 1
        p_val = mcnemar_exact(b, c)
        p_values[h.id] = p_val
        results[h.id] = {"verdict": "SUPPORTED" if (b > c and p_val < 0.05) else "NOT_SUPPORTED",
                         "mcnemar_p": fmt(p_val), "discordant": [b, c]}
    if p_values:
        adj = holm(p_values)
        for hid, info in adj.items():
            results[hid]["holm_adjusted_p"] = fmt(info["adjusted"])
            if results[hid]["verdict"] == "SUPPORTED" and not info["reject"]:
                results[hid]["verdict"] = "NOT_SUPPORTED"
                results[hid]["reason"] = "did not survive Holm correction"
    return results


# ------------------------------------------------------------------ rendering

def render(report: dict, fmt_name: str = "terminal") -> str:
    if fmt_name == "json":
        return json.dumps(report, sort_keys=True, indent=1)
    lines = []
    if report.get("banner"):
        lines.append(report["banner"])
    lines.append(f"mode: {report['mode']}   run: {report['run_id']}")
    lines.append(f"label: {report['label']}   tokens: {report['token_source']}")
    v = report["validity"]
    lines.append("")
    lines.append("## Validity")
    for arm, r in v["invalid_rates"].items():
        lines.append(f"  {arm}: {r['invalid']}/{r['total']} invalid ({100*r['rate']:.1f}%)")
    if v["broken_storylines"]:
        lines.append("  BROKEN storylines: " + ", ".join(v["broken_storylines"]))
    if v["non_separating_storylines"]:
        lines.append("  NON_SEPARATING storylines: " + ", ".join(v["non_separating_storylines"]))
    if not v["headline_ok"]:
        lines.append("  HEADLINE COMPARISONS REFUSED: an arm exceeds 5% invalid cells")
    lines.append("")
    sep = "|" if fmt_name == "md" else " "
    hdr = ["arm@size", "probes", "delivery", "gold-in-ctx%", "stale-in-ctx%",
           "stale-ans", "silent-share", "$/sess cached", "$/sess uncached", "hit%"]
    if fmt_name == "md":
        lines.append("| " + " | ".join(hdr) + " |")
        lines.append("|" + "---|" * len(hdr))
    else:
        lines.append("  ".join(hdr))
    for key, b in sorted(report["per_arm_size"].items()):
        if not b:
            continue
        cost = b.get("cost", {})
        row = [key, str(b.get("probes", 0)), b.get("delivery_rate", "n/a"),
               b.get("gold_in_context_pct", "n/a"), b.get("stale_in_context_pct", "n/a"),
               b.get("stale_answer_rate", "n/a"), str(b.get("silent_failure_share", "n/a")),
               str(cost.get("usd_per_session_cached", "n/a")),
               str(cost.get("usd_per_session_uncached", "n/a")),
               str(cost.get("cache_hit_pct", "n/a"))]
        if fmt_name == "md":
            lines.append("| " + " | ".join(row) + " |")
        else:
            lines.append("  ".join(row))
    lines.append("")
    lines.append("## Write fidelity")
    for arm, x in report["write_fidelity"].items():
        lines.append(f"  {arm}: present {x['present_rate']}, superseded handled "
                     f"{x['superseded_handled_rate']}")
    lines.append("")
    hyp = report["hypotheses"]
    if isinstance(hyp, str):
        lines.append(hyp)
    else:
        lines.append("## Hypotheses (live)")
        for hid, r in sorted(hyp.items()):
            lines.append(f"  {hid}: {r['verdict']}" +
                         (f" ({r.get('reason','')})" if r.get("reason") else ""))
    return "\n".join(lines)
