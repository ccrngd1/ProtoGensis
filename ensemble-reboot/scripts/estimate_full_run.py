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
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ensemble_reboot.pricing import PricingTable
from ensemble_reboot.records import RecordStore, is_billed
from ensemble_reboot.roster import load_roster, short_id

ROOT = Path(__file__).resolve().parent.parent
SEEDS = 3
MATCH_TOL = 0.15

# Full-set sizes come from the committed manifests (dataset text stays local).
MANIFEST = ROOT / "ensemble_reboot" / "data" / "manifest.json"

# Call role per recorded arm. Roles have very different input sizes for the
# SAME (model, effort, task set): aggregator calls read the problem plus all
# panel responses (~2,000 input tokens vs ~300 for a plain call in the pilot)
# and persona calls carry a system prompt (~2x the plain input). Pooling them
# would skew per-call cost, so TokenModel keys stats by role.
ROLE_BY_ARM = {"a4a": "aggregator", "a4b": "aggregator", "a3": "persona"}


def full_set_sizes() -> dict:
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        return {ts: m[ts]["n_items"] for ts in ("gpqa", "math", "code")}
    raise SystemExit("data manifest missing; run scripts/build_manifest.py")


class TokenModel:
    """Measured per-call token stats per (model, effort, task_set, role)."""

    def __init__(self, records):
        self.cells = defaultdict(list)
        for r in records:
            if r.get("usage") and is_billed(r):
                role = ROLE_BY_ARM.get(r.get("arm"), "proposal")
                self.cells[(r["model_id"], r["effort"], r["task_set"], role)].append(r)

    def stats(self, model, effort, ts, role="proposal"):
        """(mean_in, mean_out, lo_out, hi_out, n, record_ids) or None.
        Falls back to the same model/role at any effort (flagged
        fallback_effort), then - for non-proposal roles with no measured calls
        at all - to the proposal-call stats (flagged fallback_role)."""
        rs = self.cells.get((model, effort, ts, role))
        fallback = False
        if not rs:
            rs = list(itertools.chain.from_iterable(
                v for (m, e, t, ro), v in self.cells.items()
                if m == model and t == ts and ro == role
            ))
            fallback = True
        if not rs:
            if role != "proposal":
                st = self.stats(model, effort, ts, "proposal")
                if st:
                    st["fallback_role"] = True
                return st
            return None
        ins = sorted(r["input_tokens"] for r in rs)
        outs = sorted(r["output_tokens"] for r in rs)
        n = len(outs)
        # nearest-rank 10th/90th percentiles (same convention as analysis.stats)
        lo = outs[max(0, math.ceil(0.1 * n) - 1)]
        hi = outs[max(0, math.ceil(0.9 * n) - 1)]
        return {
            "mean_in": sum(ins) / n, "mean_out": sum(outs) / n,
            "lo_out": lo, "hi_out": hi, "n": n,
            "record_ids": [r["record_id"] for r in rs],
            "fallback_effort": fallback,
            "fallback_role": False,
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
            "unknown": unknown, "fallback": st["fallback_effort"],
            "fallback_role": st.get("fallback_role", False)}


def arm_cost_per_item(arm, model, effort, ts, tm, pricing, roster, a2_n):
    """Estimated cost per item for an arm at a given effort. Returns
    {mean, lo, hi, unknown, components} or None if unmeasurable."""
    def cc(m, e, role="proposal"):
        return per_item_cost(pricing, m, tm.stats(m, e, ts, role))

    def scaled(c, factor, components):
        return {"mean": c["mean"] * factor, "lo": c["lo"] * factor,
                "hi": c["hi"] * factor, "unknown": c["unknown"],
                "fallback": c["fallback"],
                "fallback_role": c.get("fallback_role", False),
                "components": components}

    if arm == "a1":
        c = cc(model, effort)
        return c and scaled(c, 1, f"1x {model}@{effort}")
    if arm == "a2":
        c = cc(model, effort)
        return c and scaled(c, a2_n,
                            f"{a2_n}x {model}@{effort} (programmatic vote)")
    if arm == "a3":
        # Persona calls carry a system prompt (~2x the plain input tokens);
        # use the measured persona-call records, not the a1 stats.
        c = cc(model, effort, role="persona")
        return c and scaled(c, 7,
                            f"7 personas x {model}@{effort} (programmatic vote)")
    if arm in ("a4a", "a4b"):
        panel = roster.arms["a4_panel"]
        agg = roster.arms["a4a_aggregator" if arm == "a4a" else "a4b_aggregator"]
        total = {"mean": 0.0, "lo": 0.0, "hi": 0.0,
                 "unknown": False, "fallback": False, "fallback_role": False}
        parts = []
        for pid in panel:
            # effort "default" = each panel member at its own default level
            # (the combination stage 0/1 actually measured).
            lvl = roster.by_id(pid).default_level if effort == "default" else effort
            c = cc(pid, lvl)
            if not c:
                return None
            for k in ("mean", "lo", "hi"):
                total[k] += c[k]
            total["unknown"] |= c["unknown"]
            total["fallback"] |= c["fallback"]
            parts.append(f"{short_id(pid)}@{lvl}")
        # Aggregator reads the problem + all panel responses: use its measured
        # aggregator-call tokens (stage1 a4a/a4b records); only when none exist
        # does it fall back to the model's plain-call stats (flagged).
        agg_spec = roster.by_id(agg)
        ca = cc(agg, agg_spec.default_level, role="aggregator")
        if not ca:
            return None
        for k in ("mean", "lo", "hi"):
            total[k] += ca[k]
        total["unknown"] |= ca["unknown"]
        total["fallback"] |= ca["fallback"]
        total["fallback_role"] |= ca.get("fallback_role", False)
        parts.append(f"agg {short_id(agg)}@{agg_spec.default_level}"
                     + (" (ROLE FALLBACK: no aggregator-call tokens)"
                        if ca.get("fallback_role") else ""))
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
            # effort axis: panel/B efforts actually accepted for the models involved.
            # For a4, "default" = each panel member at its own default level
            # (the only combination the pilot actually measured).
            levels = b_levels if arm in ("a1", "a2", "a3") else ["default"] + sorted(
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
                is_default = (effort == "default" if arm in ("a4a", "a4b")
                              else effort == roster.by_id(b).default_level)
                row = {
                    "task_set": ts, "arm": arm, "effort": effort,
                    "is_default_effort": is_default,
                    "n_items": n_items, "seeds": args.seeds,
                    "per_item_usd": round(c["mean"], 4),
                    "total_mean_usd": round(c["mean"] * scale, 2),
                    "total_range_usd": [round(c["lo"] * scale, 2),
                                        round(c["hi"] * scale, 2)],
                    "unknown_price": c["unknown"],
                    "effort_fallback": c.get("fallback", False),
                    "role_fallback": c.get("fallback_role", False),
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
        if r.get("role_fallback"):
            flags.append("role-fallback")
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
        fallback_used = set()

        def cpc(m, e, role="proposal"):  # cost per call
            c = per_item_cost(pricing, m, tm.stats(m, e, ts, role))
            if c and c["fallback"]:
                fallback_used.add(f"{short_id(m)}@{e}")
            return c["mean"] if c else None
        a3_cost = cpc(b, b_spec.default_level, role="persona")
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
                        ca = cpc(agg_a, roster.by_id(agg_a).default_level,
                                 role="aggregator")
                        cb = cpc(agg_b, roster.by_id(agg_b).default_level,
                                 role="aggregator")
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
                                "residual_pct_by_arm": {
                                    k: round(100 * (v - center) / center, 1)
                                    for k, v in arms.items()},
                                "max_deviation": round(dev, 3),
                                "within_15pct": dev <= MATCH_TOL,
                            }
        if best and fallback_used:
            best["effort_fallbacks"] = sorted(fallback_used)
            best["note"] = ("some (model, effort) cells lack stage-2 pilot "
                            "data; their costs fall back to default-effort "
                            "tokens, so effort choices among them are not "
                            "meaningful")
        results[ts] = best or {"status": "NO PILOT DATA"}
    return results


def reduced_options(rows):
    def total(pred):
        t = sum(r["total_mean_usd"] for r in rows if "total_mean_usd" in r and pred(r))
        return round(t, 2)

    full = total(lambda r: True)
    return [
        {"option": "default-effort only (no sweep)",
         "est_usd": total(lambda r: r["is_default_effort"])},
        {"option": "2 seeds instead of 3",
         "est_usd": round(full * 2 / 3, 2)},
        {"option": "GPQA + math only (drop code)",
         "est_usd": total(lambda r: r["task_set"] != "code")},
    ]


if __name__ == "__main__":
    main()
