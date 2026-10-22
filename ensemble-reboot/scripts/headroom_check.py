#!/usr/bin/env python3
"""Headroom check: after the pilot, confirm the best single model is <80% on
each task set. If a set is above 80%, say so explicitly and suggest a harder
slice (HMMT-only for math, LCB hard-only / newer window for code, etc.).

Usage: python3 scripts/headroom_check.py <run_id> [--threshold 0.8]
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.stats import wilson_ci
from ensemble_reboot.records import RecordStore

ROOT = Path(__file__).resolve().parent.parent

HARDER_SLICES = {
    "gpqa": "no obvious harder official slice; consider requiring consensus-wrong "
            "items only, or move to GPQA-Extended hard subdomains",
    "math": "HMMT-only (drop AIME), or restrict to problems 20+ of each contest",
    "code": "LCB hard-only is already in use; restrict further to the newest "
            "contest window or platform=codeforces",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--results-dir", default=ROOT / "results")
    args = ap.parse_args()

    store = RecordStore(args.results_dir, args.run_id)
    records = store.load_all()  # refuses is_mock records
    stage0 = [r for r in records if r["stage"] == "stage0" and r.get("correct") is not None]
    if not stage0:
        print("no stage-0 records found; run the pilot first")
        sys.exit(1)

    by = defaultdict(lambda: defaultdict(lambda: [0, 0, []]))
    for r in stage0:
        cell = by[r["task_set"]][r["model_id"]]
        cell[0] += 1 if r["correct"] else 0
        cell[1] += 1
        cell[2].append(r["record_id"])

    ok = True
    for ts in sorted(by):
        best_model, (succ, n, rec_ids) = max(
            by[ts].items(), key=lambda kv: kv[1][0] / kv[1][1]
        )
        p, lo, hi = wilson_ci(succ, n)
        line = (f"{ts}: best single model {best_model} = {succ}/{n} "
                f"({p:.0%}, 95% CI [{lo:.0%},{hi:.0%}]) "
                f"[records: {','.join(rec_ids)}]")
        if p >= args.threshold:
            ok = False
            print(f"HEADROOM FAIL  {line}")
            print(f"  -> above {args.threshold:.0%}; suggest harder slice: {HARDER_SLICES[ts]}")
        else:
            print(f"headroom ok    {line}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
