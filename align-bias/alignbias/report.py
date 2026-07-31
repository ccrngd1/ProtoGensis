"""Reporting: Skew cards, comparison matrix, and matplotlib/seaborn charts.

All Skew values are rendered in probability points (pp) on the 0-100 scale,
e.g. "-7.7 pp".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

from .skew import PairResult, SkewReport


def fmt_pp(value: Optional[float]) -> str:
    """Format a value in probability points, e.g. '-7.7 pp'."""
    if value is None:
        return "n/a"
    return f"{value:+.1f} pp"


def skew_card(report: SkewReport) -> str:
    """One model's Skew summary as a plain-text card."""
    lines = [
        f"┌─ Skew card ── {report.model} " + "─" * max(0, 40 - len(report.model)),
        f"│ pairs scored     : {report.n_scored}/{report.n_pairs}"
        f"  (refused: {report.n_refused}, exact-50 hedges: {report.n_hedged_50})",
        f"│ Skew (mean)      : {fmt_pp(report.skew_mean)}",
    ]
    if report.ci_low is not None:
        lines.append(
            f"│ 95% bootstrap CI : [{report.ci_low:+.1f}, {report.ci_high:+.1f}] pp"
        )
    lines += [
        f"│ delta+ (good-side push, mean(P+)-50) : {fmt_pp(report.delta_plus)}",
        f"│ delta- (bad-side push,  mean(P-)-50) : {fmt_pp(report.delta_minus)}",
        f"│ verdict          : {report.verdict}",
    ]
    if report.per_domain:
        lines.append("│ per-domain Skew  :")
        for domain, skew in report.per_domain.items():
            lines.append(f"│   {domain:<16} {fmt_pp(skew)}")
    lines.append("└" + "─" * 56)
    return "\n".join(lines)


def comparison_matrix(reports: Sequence[SkewReport]) -> str:
    """Cross-model comparison table (plain text)."""
    headers = ["model", "Skew", "95% CI", "delta+", "delta-", "scored", "verdict"]
    rows = []
    for r in reports:
        ci = (
            f"[{r.ci_low:+.1f}, {r.ci_high:+.1f}]"
            if r.ci_low is not None
            else "n/a"
        )
        rows.append(
            [
                r.model,
                fmt_pp(r.skew_mean),
                ci,
                fmt_pp(r.delta_plus),
                fmt_pp(r.delta_minus),
                f"{r.n_scored}/{r.n_pairs}",
                r.verdict,
            ]
        )
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    fmt_row = lambda row: "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
    out = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    out += [fmt_row(row) for row in rows]
    return "\n".join(out)


def write_json(
    reports: Sequence[SkewReport],
    out_path: str | Path,
    results_by_model: Optional[dict[str, Sequence[PairResult]]] = None,
) -> Path:
    """Persist reports (and optionally raw pair results) as skew.json."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "units": "probability points (pp), 0-100 scale",
        "models": [r.to_dict() for r in reports],
    }
    if results_by_model:
        payload["raw_results"] = {
            model: [pr.to_dict() for pr in results]
            for model, results in results_by_model.items()
        }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def plot_skew_histogram(
    results_by_model: dict[str, Sequence[PairResult]],
    out_path: str | Path,
) -> Path:
    """Per-pair Skew distribution histogram, one overlay per model."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5))
    for model, results in results_by_model.items():
        skews = [r.skew for r in results if r.skew is not None]
        if skews:
            sns.histplot(skews, kde=True, stat="count", element="step",
                         label=model, alpha=0.4, ax=ax)
    ax.axvline(0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("per-pair Skew (pp)")
    ax.set_ylabel("count")
    ax.set_title("Skew distribution — 0 = coherent, >0 optimistic, <0 pessimistic")
    ax.legend()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_domain_heatmap(
    reports: Sequence[SkewReport],
    out_path: str | Path,
) -> Path:
    """Model x domain mean-Skew heatmap."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns

    domains = sorted({d for r in reports for d in r.per_domain})
    if not domains:
        raise ValueError("no per-domain data to plot")
    matrix = np.array(
        [[r.per_domain.get(d, np.nan) for d in domains] for r in reports]
    )
    sns.set_theme(style="white")
    fig, ax = plt.subplots(
        figsize=(1.6 * len(domains) + 3, 0.8 * len(reports) + 2)
    )
    sns.heatmap(
        matrix,
        annot=True,
        fmt="+.1f",
        cmap="RdBu_r",
        center=0,
        xticklabels=domains,
        yticklabels=[r.model for r in reports],
        cbar_kws={"label": "mean Skew (pp)"},
        ax=ax,
    )
    ax.set_title("Mean Skew by model and domain (pp)")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
