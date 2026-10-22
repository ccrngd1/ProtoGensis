#!/usr/bin/env python3
"""Pilot runner. Stages in priority order (most important data lands first if
the cap stops the run): stage0 calibration -> stage1 arms -> stage2 sweep.

Live run (needs AWS_BEARER_TOKEN_BEDROCK):
    python3 scripts/run_pilot.py --cap 75 [--probe results/probe_levels_<date>.jsonl]

Dry run (no token needed, no API calls): prints planned calls per stage and a
pre-run cost estimate from an ASSUMED token range (clearly labeled):
    python3 scripts/run_pilot.py --dry-run
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ensemble_reboot.budget import BudgetExceeded, BudgetGuard
from ensemble_reboot.pilot import (
    PILOT_ITEMS_PER_SET,
    TASK_SETS,
    PilotRunner,
    load_accepted_levels,
    pick_best_by_set,
    plan_stage0,
    plan_stage1,
    plan_stage2,
    sample_pilot_items,
)
from ensemble_reboot.pricing import PricingTable
from ensemble_reboot.records import RecordStore
from ensemble_reboot.roster import load_roster

ROOT = Path(__file__).resolve().parent.parent

# Pre-run estimate only. ASSUMED token ranges per call (NOT measurements):
# input from prompt length order-of-magnitude, output spanning terse (cheap
# model, low effort) to verbose reasoning (frontier at high effort). The
# pilot exists precisely to replace these with measured numbers.
ASSUMED_INPUT_TOKENS = (300, 3000)
ASSUMED_OUTPUT_TOKENS = (500, 8000)


def load_items(data_dir):
    from ensemble_reboot.data import load_gpqa_diamond, load_lcb_items, load_math_items

    return {
        "gpqa": load_gpqa_diamond(data_dir),
        "math": load_math_items(data_dir),
        "code": load_lcb_items(data_dir),
    }


def dry_run(roster, pricing, probe_path):
    accepted = load_accepted_levels(probe_path, roster)
    if not (probe_path and Path(probe_path).exists()):
        print("NOTE: no probe file; assuming all candidate levels are accepted.\n"
              "      Run scripts/probe_levels.py first for exact level lists.\n")

    # Items may not be downloaded in a constrained environment; the plan only
    # needs item ids, so use placeholders when data/ is unavailable.
    class _Stub:
        def __init__(self, i, ts):
            self.item_id = f"{ts}-stub-{i}"
            self.item_sha256 = ""
    try:
        items = load_items(ROOT / "data")
        pilot_items = sample_pilot_items(items)
        src = "real item ids (seeded sample)"
    except Exception as e:
        pilot_items = {ts: [_Stub(i, ts) for i in range(PILOT_ITEMS_PER_SET)]
                       for ts in TASK_SETS}
        src = f"stub item ids (datasets unavailable here: {type(e).__name__})"
    print(f"pilot items: {PILOT_ITEMS_PER_SET}/set from {src}")

    s0 = plan_stage0(roster, pilot_items)
    # Stage 1 needs the stage-0 winner, unknown pre-run; assume an arbitrary
    # frontier model for CALL-COUNT purposes (same count whichever model wins).
    assumed_b = {ts: "global.anthropic.claude-fable-5-1" for ts in TASK_SETS}
    s1 = plan_stage1(roster, pilot_items, assumed_b, a2_n=roster.arms.get("a2_n", 5))
    s2 = plan_stage2(roster, pilot_items, accepted)

    def estimate(plan):
        lo = hi = 0.0
        unknown = 0
        for call in plan:
            c_lo = pricing.cost(call.model_id, ASSUMED_INPUT_TOKENS[0], ASSUMED_OUTPUT_TOKENS[0])
            c_hi = pricing.cost(call.model_id, ASSUMED_INPUT_TOKENS[1], ASSUMED_OUTPUT_TOKENS[1])
            if c_lo.cost_usd is None:
                unknown += 1
            lo += c_lo.conservative_usd
            hi += c_hi.conservative_usd
        return lo, hi, unknown

    grand_lo = grand_hi = 0.0
    print(f"\nASSUMED token range per call (pre-run estimate only, NOT measured): "
          f"input {ASSUMED_INPUT_TOKENS}, output {ASSUMED_OUTPUT_TOKENS}\n")
    for name, plan in (("stage0 calibration", s0),
                       ("stage1 arms (A2/A3 proposals + A4 aggregators)", s1),
                       ("stage2 effort sweep", s2)):
        lo, hi, unknown = estimate(plan)
        grand_lo += lo
        grand_hi += hi
        by_model = {}
        for c in plan:
            by_model[c.model_id] = by_model.get(c.model_id, 0) + 1
        print(f"{name}: {len(plan)} calls")
        for m, n in sorted(by_model.items()):
            print(f"    {n:4d}  {m}")
        flag = f"  ({unknown} calls at UNKNOWN price, billed at max known rate)" if unknown else ""
        print(f"    est cost (ASSUMED tokens): ${lo:.2f} - ${hi:.2f}{flag}\n")
    print(f"TOTAL planned calls: {len(s0) + len(s1) + len(s2)}")
    print(f"TOTAL pre-run estimate (ASSUMED tokens, not measured): "
          f"${grand_lo:.2f} - ${grand_hi:.2f}")
    print("\nStage-1 counts assume a frontier model wins stage 0 (call counts are "
          "model-independent; costs are not).")
    print("A4 panel proposals reuse stage-0 records: no extra proposal calls.")


def live_run(args, roster, pricing):
    run_id = args.run_id or f"pilot_{date.today().isoformat()}"
    store = RecordStore(args.results_dir, run_id)
    guard = BudgetGuard(cap_usd=args.cap)
    from ensemble_reboot.client import BedrockClient

    client = BedrockClient(region=roster.region)
    items = load_items(ROOT / "data")
    pilot_items = sample_pilot_items(items)
    accepted = load_accepted_levels(args.probe, roster)
    runner = PilotRunner(
        roster, pricing, store, guard, client, pilot_items,
        personas_dir=ROOT / roster.arms.get("a3_personas_dir",
                                            "../ensemble-persona-orchestrator/personas"),
        max_workers=args.workers,
    )
    manifest = {
        "run_id": run_id,
        "started": datetime.now(timezone.utc).isoformat(),
        "cap_usd": args.cap,
        "items_per_set": {ts: [i.item_id for i in v] for ts, v in pilot_items.items()},
        "accepted_levels": accepted,
        "stages": {},
    }
    manifest_path = store.run_dir / "manifest.json"

    def save_manifest():
        manifest["budget"] = guard.status()
        manifest_path.write_text(json.dumps(manifest, indent=2))

    try:
        print("=== stage 0: calibration (all models, default effort) ===")
        recs0 = runner.run_stage0(pilot_items)
        manifest["stages"]["stage0"] = {"records": len(recs0)}
        save_manifest()

        best = pick_best_by_set([r for r in recs0 if r], TASK_SETS)
        manifest["best_by_set"] = best
        print(f"best single model by set: {best}")

        print("=== stage 1: arms at default effort ===")
        recs1 = runner.run_stage1(pilot_items, best, a2_n=roster.arms.get("a2_n", 5))
        manifest["stages"]["stage1"] = {"records": len(recs1)}
        save_manifest()

        print("=== stage 2: effort sweep ===")
        recs2 = runner.run_stage2(pilot_items, accepted)
        manifest["stages"]["stage2"] = {"records": len(recs2)}
    except BudgetExceeded as e:
        manifest["aborted"] = f"budget cap: {e}"
        print(f"\nABORTED at budget cap: {e}")
    finally:
        manifest["finished"] = datetime.now(timezone.utc).isoformat()
        save_manifest()
        print(f"\nfinal budget: {guard.status()}")
        print(f"manifest: {manifest_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=float, default=75.0, help="budget cap in USD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", default=None,
                    help="probe_levels jsonl; defaults to today's file if present")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--results-dir", default=ROOT / "results")
    args = ap.parse_args()

    roster = load_roster(ROOT / "config" / "roster.yaml")
    pricing = PricingTable.load(ROOT / "config" / "pricing.yaml")
    if args.probe is None:
        candidate = ROOT / "results" / f"probe_levels_{date.today().isoformat()}.jsonl"
        args.probe = candidate if candidate.exists() else None

    if args.dry_run:
        dry_run(roster, pricing, args.probe)
    else:
        live_run(args, roster, pricing)


if __name__ == "__main__":
    main()
