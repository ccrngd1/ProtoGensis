#!/usr/bin/env python3
"""Summarize a run: accuracy with 95% CI (Wilson), cost per correct, p50/p95
latency, co-failure matrix, accuracy-vs-cost curves. Outputs
results/<run_id>/summary.md + summary.json.

Every number carries the record_ids it came from (inline list when short,
otherwise a reference to a group file written next to the summary).

Usage: python3 scripts/summarize.py <run_id>
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.stats import (
    co_failure_matrix,
    group_correct_by_model,
    percentiles,
    wilson_ci,
)
from ensemble_reboot.records import RecordStore

ROOT = Path(__file__).resolve().parent.parent
INLINE_IDS_MAX = 12


def _ids_ref(rec_ids, groups, key):
    if len(rec_ids) <= INLINE_IDS_MAX:
        return ",".join(rec_ids)
    groups[key] = rec_ids
    return f"see record_groups.json#{key} (n={len(rec_ids)})"


def summarize(run_id, results_dir):
    store = RecordStore(results_dir, run_id)
    records = store.load_all()  # refuses is_mock
    if not records:
        print(f"no records for run {run_id}")
        sys.exit(1)

    groups = {}
    summary = {"run_id": run_id, "n_records": len(records)}
    lines = [f"# Summary: {run_id}", "",
             f"{len(records)} records. All numbers trace to record_ids "
             "(inline or in record_groups.json).", ""]

    # ---------------- accuracy / cost / latency per (arm?, model, effort, set)
    cells = defaultdict(list)
    for r in records:
        if r.get("correct") is None:
            continue
        cells[(r["arm"], r["model_id"], r["effort"], r["task_set"])].append(r)

    table = []
    for (arm, model, effort, ts), rs in sorted(cells.items()):
        n = len(rs)
        succ = sum(1 for r in rs if r["correct"])
        p, lo, hi = wilson_ci(succ, n)
        costs = [r["cost_usd"] for r in rs]
        unknown = sum(1 for c in costs if c is None)
        known_cost = sum(c for c in costs if c is not None)
        trunc = sum(1 for r in rs if r.get("truncated"))
        lat = percentiles([r["latency_s"] for r in rs if r["latency_s"]])
        cpc = (known_cost / succ) if succ and not unknown else None
        rec_ids = [r["record_id"] for r in rs]
        key = f"{arm}_{model}_{effort}_{ts}".replace("/", "_").replace(":", "_")
        row = {
            "arm": arm, "model": model, "effort": effort, "task_set": ts,
            "n": n, "correct": succ, "accuracy": round(p, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "truncated": trunc,
            "cost_usd_known": round(known_cost, 4),
            "unknown_price_calls": unknown,
            "cost_per_correct": round(cpc, 4) if cpc is not None else None,
            "latency": lat,
            "record_ids": _ids_ref(rec_ids, groups, key),
        }
        table.append(row)
    summary["cells"] = table

    lines.append("## Accuracy / cost / latency\n")
    lines.append("| arm | model | effort | set | acc (95% CI) | n | trunc | "
                 "cost$ | $/correct | p50/p95 lat (s) | records |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in table:
        ci = row["ci95"]
        lat = row["latency"]
        lat_s = f"{lat.get('p50', '-')}/{lat.get('p95', '-')}" if lat else "-"
        unk = " +UNKNOWN!" if row["unknown_price_calls"] else ""
        cpc = row["cost_per_correct"]
        lines.append(
            f"| {row['arm']} | {row['model'].split('.')[-1]} | {row['effort']} "
            f"| {row['task_set']} | {row['accuracy']:.2f} [{ci[0]:.2f},{ci[1]:.2f}] "
            f"| {row['n']} | {row['truncated']} | {row['cost_usd_known']:.3f}{unk} "
            f"| {cpc if cpc is not None else 'UNKNOWN'} | {lat_s} | {row['record_ids']} |"
        )
    lines.append("")

    # --------------------------------------------------------- co-failure
    stage0 = [r for r in records if r["stage"] == "stage0"]
    co_lines = []
    co_data = []
    if stage0:
        for ts in sorted({r["task_set"] for r in stage0}):
            sub = [r for r in stage0 if r["task_set"] == ts]
            per_model, fams = group_correct_by_model(sub)
            pairs = co_failure_matrix(per_model, fams)
            for pr in pairs:
                d = asdict(pr)
                key = f"cofail_{ts}_{pr.model_a.split('.')[-1]}_{pr.model_b.split('.')[-1]}"
                d["task_set"] = ts
                d["item_ids"] = _ids_ref(pr.item_ids, groups, key)
                co_data.append(d)
                ratio = f"{pr.ratio:.2f}" if pr.ratio is not None else "n/a"
                co_lines.append(
                    f"| {ts} | {pr.model_a.split('.')[-1]} | {pr.model_b.split('.')[-1]} "
                    f"| {pr.grouping} | {pr.p_both_wrong:.2f} | "
                    f"{pr.expected_independent:.2f} | {ratio} | {pr.n} |"
                )
    summary["co_failure"] = co_data
    if co_lines:
        lines.append("## Co-failure matrix (stage-0, per pair)\n")
        lines.append("| set | A | B | grouping | P(both wrong) | P(A w)*P(B w) | ratio | n |")
        lines.append("|---|---|---|---|---|---|---|---|")
        lines += co_lines
        lines.append("")
        lines.append("Item ids per pair: record_groups.json (cofail_* keys).")
        lines.append("")

    # ------------------------------------------------- accuracy-vs-cost curves
    curves = defaultdict(list)
    for row in table:
        if row["arm"] in ("a1", "sweep"):
            curves[(row["model"], row["task_set"])].append(row)
    curve_rows = []
    for (model, ts), rows in sorted(curves.items()):
        for row in sorted(rows, key=lambda r: r["cost_usd_known"]):
            curve_rows.append({
                "model": model, "task_set": ts, "effort": row["effort"],
                "cost_usd": row["cost_usd_known"], "accuracy": row["accuracy"],
                "unknown_price_calls": row["unknown_price_calls"],
                "record_ids": row["record_ids"],
            })
    summary["acc_vs_cost_points"] = curve_rows
    csv_path = store.run_dir / "acc_vs_cost.csv"
    with open(csv_path, "w") as f:
        f.write("model,task_set,effort,cost_usd,accuracy,unknown_price_calls\n")
        for c in curve_rows:
            f.write(f"{c['model']},{c['task_set']},{c['effort']},"
                    f"{c['cost_usd']},{c['accuracy']},{c['unknown_price_calls']}\n")
    plot_note = plot_curves(curve_rows, store.run_dir)
    lines.append(f"## Accuracy vs cost\n\nPoints: acc_vs_cost.csv. {plot_note}\n")

    # ------------------------------------------------------------- outputs
    if groups:
        (store.run_dir / "record_groups.json").write_text(json.dumps(groups, indent=2))
    (store.run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (store.run_dir / "summary.md").write_text("\n".join(lines))
    print(f"wrote {store.run_dir}/summary.md and summary.json")


def plot_curves(curve_rows, run_dir) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib not installed: CSV only."
    if not curve_rows:
        return "No curve points."
    by_set = defaultdict(lambda: defaultdict(list))
    for c in curve_rows:
        by_set[c["task_set"]][c["model"]].append(c)
    fig, axes = plt.subplots(1, len(by_set), figsize=(6 * len(by_set), 5), squeeze=False)
    for ax, (ts, models) in zip(axes[0], sorted(by_set.items())):
        for model, pts in sorted(models.items()):
            pts = sorted(pts, key=lambda p: p["cost_usd"])
            ax.plot([p["cost_usd"] for p in pts], [p["accuracy"] for p in pts],
                    marker="o", label=model.split(".")[-1])
        ax.set_title(ts)
        ax.set_xlabel("cost (USD, known prices)")
        ax.set_ylabel("accuracy")
        ax.legend(fontsize=7)
    out = Path(run_dir) / "acc_vs_cost.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return f"Plot: {out.name}."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--results-dir", default=ROOT / "results")
    args = ap.parse_args()
    summarize(args.run_id, args.results_dir)


if __name__ == "__main__":
    main()
