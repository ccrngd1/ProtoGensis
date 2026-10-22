#!/usr/bin/env python3
"""Effort-level probe: for each roster model, try every candidate level on a
trivial prompt. Writes results/probe_levels_<date>.jsonl recording which
levels return 200, which return 400 (with error text), and tokens.

The pilot runner reads this file and uses only levels that were accepted.
Cheap: ~70 tiny calls. Requires AWS_BEARER_TOKEN_BEDROCK.

Usage: python3 scripts/probe_levels.py [--out results/probe_levels_YYYY-MM-DD.jsonl]
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ensemble_reboot.client import BedrockClient
from ensemble_reboot.roster import ALL_LEVELS, load_roster

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", default=ROOT / "config" / "roster.yaml")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    roster = load_roster(args.roster)
    out_path = Path(args.out) if args.out else (
        ROOT / "results" / f"probe_levels_{date.today().isoformat()}.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = BedrockClient(region=roster.region, timeout_s=300)

    with open(out_path, "w") as f:
        for spec in roster.models:
            for level in ALL_LEVELS:
                res = client.probe(spec, level)
                row = {
                    "model": spec.profile_id,
                    "level": level,
                    "in_candidates": level in spec.candidate_levels,
                    "status": res.status_code,
                    "latency_s": round(res.latency_s, 2),
                }
                if res.status_code == 200:
                    row["stop_reason"] = res.stop_reason
                    row["usage"] = res.usage
                    row["answer_head"] = res.text[:40]
                else:
                    row["error"] = (res.error_text or "")[:500]
                f.write(json.dumps(row) + "\n")
                f.flush()
                print(json.dumps({k: row[k] for k in ("model", "level", "status")}))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
