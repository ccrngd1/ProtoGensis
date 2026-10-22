#!/usr/bin/env python3
"""Full-run cost estimator from measured pilot tokens.

From measured per-item tokens and cost per (model, effort, task set) in the
pilot, estimate: all items in each set x 3 seeds x each arm x each effort
level. Outputs a table by arm AND effort level, per-task-set subtotals, a
grand total, the cost-matching solution (N for A2, panel effort, A1 effort so
arms land within +/-15%), and 2-3 reduced-scope options. Estimates using
UNKNOWN prices are marked. Uncertainty: n=10 pilot -> a range from the
per-item token-count spread (mean +/- the 10-90th percentile band).

Usage: python3 scripts/estimate_full_run.py <pilot_run_id>
"""

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ensemble_reboot.pricing import PricingTable
from ensemble_reboot.records import RecordStore
from ensemble_reboot.roster import load_roster

ROOT = Path(__file__).resolve().parent.parent
SEEDS = 3
MATCH_TOL = 0.15

# Full-set sizes come from the committed manifests (dataset text stays local).
MANIFEST = ROOT / "ensemble_reboot" / "data" / "manifest.json"


def full_set_sizes() -> dict:
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        return {ts: m[ts]["n_items"] for ts in ("gpqa", "math", "code")}
    raise SystemExit("data manifest missing; run scripts/build_manifest.py")


class TokenModel:
    """Measured per-call token stats per (model, effort, task_set)."""

    def __init__(self, records):
        self.cells = defaultdict(list)
        for r in records:
            if r.get("usage") and r["model_id"] != "programmatic-vote":
                self.cells[(r["model_id"], r["effort"], r["task_set"])].append(r)

    def stats(self, model, effort, ts):
        """(mean_in, mean_out, lo_out, hi_out, n, record_ids) or None.
        Falls back to the same model at any effort, scaled by nothing - just
        flagged lower confidence - when the exact effort is missing."""
        rs = self.cells.get((model, effort, ts))
        fallback = False
        if not rs:
            rs = list(itertools.chain.from_iterable(
                v for (m, e, t), v in self.cells.items() if m == model and t == ts
            ))
            fallback = True
        if not rs:
            return None
        ins = sorted(r["input_tokens"] for r in rs)
        outs = sorted(r["output_tokens"] for r in rs)
        n = len(outs)
        lo = outs[max(0, int(0.1 * n) - 1)] if n > 1 else outs[0]
        hi = outs[min(n - 1, int(0.9 * n))]
        return {
            "mean_in": sum(ins) / n, "mean_out": sum(outs) / n,
            "lo_out": lo, "hi_out": hi, "n": n,
            "record_ids": [r["record_id"] for r in rs],
            "fallback_effort": fallback,
        }


def per_item_cost(pricing, model, st) -> dict | None:
    """{mean, lo, hi, unknown} cost per call."""
    if st is None:
        return None
    c_mean = pricing.cost(model, int(st["mean_in"]), int(st["mean_out"]))
    c_lo = pricing.cost(model, int(st["mean_in"]), int(st["lo_out"]))
    c_hi = pricing.cost(model, int(st["mean_in"]), int(st["hi_out"]))
    unknown = c_mean.cost_usd is None
    pick = (lambda c: c.conservative_usd) if unknown else (lambda c: c.cost_usd)
    return {"mean": pick(c_mean), "lo": pick(c_lo), "hi": pick(c_hi),
            "unknown": unknown, "fallback": st["fallback_effort"]}


def arm_cost_per_item(arm, model, effort, ts, tm, pricing, roster, a2_n):
    """Estimated cost per item for an arm at a given effort. Returns
    {mean, lo, hi, unknown, components} or None if unmeasurable."""
    def cc(m, e):
        return per_item_cost(pricing, m, tm.stats(m, e, ts))

    if arm == "a1":
        c = cc(model, effort)
        return c and {**c, "components": f"1x {model}@{effort}"}
    if arm == "a2":
        c = cc(model, effort)
        if not c:
            return None
        return {k: (v * a2_n if isinstance(v, (int, float)) else v)
                for k, v in c.items() if k != "components"} | {
            "components": f"{a2_n}x {model}@{effort} (programmatic vote)"}
    if arm == "a3":
        c = cc(model, effort)
        if not c:
            return None
        return {k: (v * 7 if isinstance(v, (int, float)) else v)
                for k, v in c.items() if k != "components"} | {
            "components": f"7 personas x {model}@{effort} (programmatic vote)"}
    if arm in ("a4a", "a4b"):
        panel = roster.arms["a4_panel"]
        agg = roster.arms["a4a_aggregator" if arm == "a4a" else "a4b_aggregator"]
        total = {"mean": 0.0, "lo": 0.0, "hi": 0.0, "unknown": False}
        parts = []
        for pid in panel:
            c = cc(pid, effort)
            if not c:
                return None
            for k in ("mean", "lo", "hi"):
                total[k] += c[k]
            total["unknown"] |= c["unknown"]
            parts.append(f"{pid.split('.')[-1]}@{effort}")
        # Aggregator reads the problem + all panel responses: use its measured
        # aggregator-call tokens if present (stage1 a4 records), else its a1 stats.
        agg_spec = roster.by_id(agg)
        ca = cc(agg, agg_spec.default_level)
        if not ca:
            return None
        for k in ("mean", "lo", "hi"):
            total[k] += ca[k]
        total["unknown"] |= ca["unknown"]
        parts.append(f"agg {agg.split('.')[-1]}@{agg_spec.default_level}")
        return {**total, "components": " + ".join(parts)}
    raise ValueError(arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pilot_run_id")
    ap.add_argument("--results-dir", default=ROOT / "results")
    ap.add_argument("--seeds", type=int, default=SEEDS)
    args = ap.parse_args()

    roster = load_roster(ROOT / "config" / "roster.yaml")
    pricing = PricingTable.load(ROOT / "config" / "pricing.yaml")
    store = RecordStore(args.results_dir, args.pilot_run_id)
    records = store.load_all()  # refuses is_mock
    if not records:
        raise SystemExit(f"no records for {args.pilot_run_id}")
    tm = TokenModel(records)
    sizes = full_set_sizes()

    manifest = json.loads((store.run_dir / "manifest.json").read_text()) \
        if (store.run_dir / "manifest.json").exists() else {}
    best_by_set = manifest.get("best_by_set") or {}
    a2_n = roster.arms.get("a2_n", 5)
    accepted = manifest.get("accepted_levels") or {
        m.profile_id: m.candidate_levels for m in roster.models}

    arms = ["a1", "a2", "a3", "a4a", "a4b"]
    rows = []
    grand = {"mean": 0.0, "lo": 0.0, "hi": 0.0}
    any_unknown = False
    subtotals = defaultdict(lambda: {"mean": 0.0, "lo": 0.0, "hi": 0.0})
    for ts, n_items in sizes.items():
        b = best_by_set.get(ts) or "global.anthropic.claude-fable-5-1"
        b_levels = accepted.get(b, [])
        for arm in arms:
            # effort axis: panel/B efforts actually accepted for the models involved
            levels = b_levels if arm in ("a1", "a2", "a3") else sorted(
                set.intersection(*(set(accepted.get(pid, []))
                                   for pid in roster.arms["a4_panel"])) or {"medium"}
            )
            for effort in levels:
                c = arm_cost_per_item(arm, b, effort, ts, tm, pricing, roster, a2_n)
                if c is None:
                    rows.append({"task_set": ts, "arm": arm, "effort": effort,
                                 "status": "NO PILOT DATA"})
                    continue
                scale = n_items * args.seeds
                row = {
                    "task_set": ts, "arm": arm, "effort": effort,
                    "n_items": n_items, "seeds": args.seeds,
                    "per_item_usd": round(c["mean"], 4),
                    "total_mean_usd": round(c["mean"] * scale, 2),
                    "total_range_usd": [round(c["lo"] * scale, 2),
                                        round(c["hi"] * scale, 2)],
                    "unknown_price": c["unknown"],
                    "effort_fallback": c.get("fallback", False),
                    "components": c["components"],
                }
                rows.append(row)
                grand["mean"] += c["mean"] * scale
                grand["lo"] += c["lo"] * scale
                grand["hi"] += c["hi"] * scale
                st = subtotals[ts]
                st["mean"] += c["mean"] * scale
                st["lo"] += c["lo"] * scale
                st["hi"] += c["hi"] * scale
                any_unknown |= c["unknown"]

    # ------------------------------------------------ cost matching (+/-15%)
    match = cost_match(sizes, best_by_set, accepted, tm, pricing, roster)

    # ------------------------------------------------ reduced-scope options
    reduced = reduced_options(rows)

    out = {
        "pilot_run_id": args.pilot_run_id,
        "note": ("Estimates from n=10 pilot measurements; ranges span the "
                 "10th-90th percentile of measured output tokens. Rows with "
                 "unknown_price=true use the max known rate (marked). "
                 "'NO PILOT DATA' rows need stage-2 coverage before estimating."),
        "rows": rows,
        "subtotals_by_task_set": {k: {kk: round(vv, 2) for kk, vv in v.items()}
                                  for k, v in subtotals.items()},
        "grand_total_usd": {k: round(v, 2) for k, v in grand.items()},
        "contains_unknown_prices": any_unknown,
        "cost_matching": match,
        "reduced_scope_options": reduced,
    }
    out_path = store.run_dir / "full_run_estimate.json"
    out_path.write_text(json.dumps(out, indent=2))

    # Console table
    print(f"Full-run estimate from pilot {args.pilot_run_id} "
          f"(all items x {args.seeds} seeds x arm x effort)\n")
    print(f"{'set':5} {'arm':4} {'effort':7} {'$/item':>8} {'total$':>9} "
          f"{'range':>17}  flags")
    for r in rows:
        if r.get("status"):
            print(f"{r['task_set']:5} {r['arm']:4} {r['effort']:7} {r['status']}")
            continue
        flags = []
        if r["unknown_price"]:
            flags.append("UNKNOWN-PRICE")
        if r["effort_fallback"]:
            flags.append("effort-fallback")
        print(f"{r['task_set']:5} {r['arm']:4} {r['effort']:7} "
              f"{r['per_item_usd']:8.3f} {r['total_mean_usd']:9.2f} "
              f"[{r['total_range_usd'][0]:7.2f},{r['total_range_usd'][1]:7.2f}]  "
              f"{' '.join(flags)}")
    print("\nsubtotals by set:",
          {k: round(v['mean'], 2) for k, v in subtotals.items()})
    print(f"GRAND TOTAL: ${grand['mean']:.2f} "
          f"(range ${grand['lo']:.2f}-${grand['hi']:.2f})"
          + ("  ** includes UNKNOWN prices at max known rate **" if any_unknown else ""))
    print("\ncost matching:", json.dumps(match, indent=2))
    print("\nreduced-scope options:", json.dumps(reduced, indent=2))
    print(f"\nwrote {out_path}")


def cost_match(sizes, best_by_set, accepted, tm, pricing, roster):
    """Choose N for A2, panel effort, and A1's effort so A1/A2/A3/A4a/A4b land
    within +/-15% of each other; report the residual mismatch.

    Strategy: A3 (7x B at default) is the least adjustable arm, so it anchors
    the target; search A1 effort (highest cost <= window or closest), A2 (N,
    effort), and panel effort to minimize max deviation from the geometric
    center of the five arms."""
    results = {}
    for ts in sizes:
        b = best_by_set.get(ts) or "global.anthropic.claude-fable-5-1"
        b_spec = roster.by_id(b)
        def cpc(m, e):  # cost per call
            c = per_item_cost(pricing, m, tm.stats(m, e, ts))
            return c["mean"] if c else None
        a3_cost = cpc(b, b_spec.default_level)
        if a3_cost is None:
            results[ts] = {"status": "NO PILOT DATA for anchor"}
            continue
        a3_cost *= 7
        best = None
        panel = roster.arms["a4_panel"]
        panel_levels = sorted(set.intersection(
            *(set(accepted.get(p, [])) for p in panel)) or {"medium"})
        agg_a = roster.arms["a4a_aggregator"]
        agg_b = roster.arms["a4b_aggregator"]
        for a1_e in accepted.get(b, [b_spec.default_level]):
            a1 = cpc(b, a1_e)
            if a1 is None:
                continue
            for n in range(3, 10):
                for a2_e in accepted.get(b, [b_spec.default_level]):
                    base = cpc(b, a2_e)
                    if base is None:
                        continue
                    a2 = base * n
                    for p_e in panel_levels:
                        panel_cost = 0.0
                        ok = True
                        for pid in panel:
                            c = cpc(pid, p_e)
                            if c is None:
                                ok = False
                                break
                            panel_cost += c
                        if not ok:
                            continue
                        ca = cpc(agg_a, roster.by_id(agg_a).default_level)
                        cb = cpc(agg_b, roster.by_id(agg_b).default_level)
                        if ca is None or cb is None:
                            continue
                        a4a, a4b = panel_cost + ca, panel_cost + cb
                        arms = {"a1": a1, "a2": a2, "a3": a3_cost,
                                "a4a": a4a, "a4b": a4b}
                        center = (min(arms.values()) * max(arms.values())) ** 0.5
                        dev = max(abs(v - center) / center for v in arms.values())
                        if best is None or dev < best["max_deviation"]:
                            best = {
                                "a1_effort": a1_e, "a2_n": n, "a2_effort": a2_e,
                                "panel_effort": p_e,
                                "per_item_costs": {k: round(v, 4) for k, v in arms.items()},
                                "max_deviation": round(dev, 3),
                                "within_15pct": dev <= MATCH_TOL,
                            }
        results[ts] = best or {"status": "NO PILOT DATA"}
    return results


def reduced_options(rows):
    def total(pred):
        t = sum(r["total_mean_usd"] for r in rows if "total_mean_usd" in r and pred(r))
        return round(t, 2)

    full = total(lambda r: True)
    return [
        {"option": "default-effort only (no sweep)",
         "est_usd": total(lambda r: r["effort"] in ("medium", "high", "max"))},
        {"option": "2 seeds instead of 3",
         "est_usd": round(full * 2 / 3, 2)},
        {"option": "GPQA + math only (drop code)",
         "est_usd": total(lambda r: r["task_set"] != "code")},
    ]


if __name__ == "__main__":
    main()
