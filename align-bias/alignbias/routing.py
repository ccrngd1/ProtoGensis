"""Routing advisor: map measured Skew to per-task-type model recommendations.

A YAML routing config declares task types and the directional tilt each one
tolerates (or prefers). Combined with a skew.json report, the advisor ranks
audited models per task type.

Example routing.yaml:

    tasks:
      risk-assessment:
        preferred_tilt: pessimistic     # under-promising is safer
        max_abs_skew: 15
      brainstorming:
        preferred_tilt: optimistic
      forecasting:
        preferred_tilt: neutral         # closest-to-0 wins
        max_abs_skew: 5
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

VALID_TILTS = ("neutral", "optimistic", "pessimistic")


@dataclass
class TaskPolicy:
    name: str
    preferred_tilt: str = "neutral"
    max_abs_skew: Optional[float] = None  # pp; None = no cap

    def __post_init__(self):
        if self.preferred_tilt not in VALID_TILTS:
            raise ValueError(
                f"task {self.name!r}: preferred_tilt must be one of {VALID_TILTS}, "
                f"got {self.preferred_tilt!r}"
            )


@dataclass
class Recommendation:
    task: str
    ranked_models: list[dict] = field(default_factory=list)  # best first
    excluded: list[dict] = field(default_factory=list)


def load_routing_config(path: str | Path) -> list[TaskPolicy]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "tasks" not in data:
        raise ValueError(f"{path}: expected a top-level 'tasks' mapping")
    policies = []
    for name, spec in data["tasks"].items():
        spec = spec or {}
        policies.append(
            TaskPolicy(
                name=name,
                preferred_tilt=spec.get("preferred_tilt", "neutral"),
                max_abs_skew=spec.get("max_abs_skew"),
            )
        )
    if not policies:
        raise ValueError(f"{path}: no tasks defined")
    return policies


def load_skew_report(path: str | Path) -> list[dict]:
    """Read model summaries out of a skew.json produced by `alignbias audit`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    models = data.get("models", [])
    if not models:
        raise ValueError(f"{path}: no model summaries found")
    return models


def _tilt_score(skew: float, preferred: str) -> float:
    """Lower is better. Neutral wants |skew| small; directional tilts want
    the sign to match and modest magnitude."""
    if preferred == "neutral":
        return abs(skew)
    if preferred == "optimistic":
        # Right-sign skew scores by distance from a mild +5 pp target;
        # wrong-sign skew is penalized by its full magnitude plus offset.
        return abs(skew - 5.0) if skew >= 0 else 5.0 + abs(skew)
    # pessimistic
    return abs(skew + 5.0) if skew <= 0 else 5.0 + abs(skew)


def advise(policies: list[TaskPolicy], model_summaries: list[dict]) -> list[Recommendation]:
    recommendations = []
    for policy in policies:
        ranked, excluded = [], []
        for summary in model_summaries:
            skew = summary.get("skew_mean")
            entry = {
                "model": summary.get("model", "?"),
                "skew_mean_pp": skew,
                "delta_plus_pp": summary.get("delta_plus"),
                "delta_minus_pp": summary.get("delta_minus"),
            }
            if skew is None:
                entry["reason"] = "no scored pairs"
                excluded.append(entry)
                continue
            if policy.max_abs_skew is not None and abs(skew) > policy.max_abs_skew:
                entry["reason"] = (
                    f"|Skew| {abs(skew):.1f} pp exceeds cap {policy.max_abs_skew:.1f} pp"
                )
                excluded.append(entry)
                continue
            entry["score"] = _tilt_score(skew, policy.preferred_tilt)
            ranked.append(entry)
        ranked.sort(key=lambda e: e["score"])
        recommendations.append(
            Recommendation(task=policy.name, ranked_models=ranked, excluded=excluded)
        )
    return recommendations


def format_recommendations(recommendations: list[Recommendation]) -> str:
    lines = []
    for rec in recommendations:
        lines.append(f"task: {rec.task}")
        if rec.ranked_models:
            for i, entry in enumerate(rec.ranked_models, 1):
                lines.append(
                    f"  {i}. {entry['model']}  "
                    f"Skew {entry['skew_mean_pp']:+.1f} pp"
                )
        else:
            lines.append("  (no eligible models)")
        for entry in rec.excluded:
            lines.append(f"  x  {entry['model']} — {entry['reason']}")
        lines.append("")
    return "\n".join(lines).rstrip()
