"""Calibration: derive correction offsets from a Skew report.

Produces a JSON offsets file with *separate* success-side and failure-side
coefficients, because a tilt is rarely symmetric: a model can be accurate on
failure questions while deflating success estimates (delta+ < 0, delta- ~ 0).
Correcting both sides with one scalar would over- or under-correct one side.

Offsets are in probability points (pp) on the 0-100 scale and are additive
corrections to apply to the model's raw estimate:

    corrected P(success) = clamp(raw + offset_success, 0, 100)
    corrected P(failure) = clamp(raw + offset_failure, 0, 100)

The offset is a starting correction measured on this scenario distribution,
not a universal fix.
"""

from __future__ import annotations

import json
from pathlib import Path


def derive_offsets(model_summaries: list[dict]) -> dict:
    """Build per-model additive offsets from skew.json model summaries.

    delta+ = mean(P+) - 50 is the good-side push; delta- = mean(P-) - 50 the
    bad-side push. The correction is the negation of each push component.
    """
    offsets = {}
    for summary in model_summaries:
        model = summary.get("model", "?")
        delta_plus = summary.get("delta_plus")
        delta_minus = summary.get("delta_minus")
        skew = summary.get("skew_mean")
        if delta_plus is None or delta_minus is None:
            offsets[model] = {
                "offset_success_pp": None,
                "offset_failure_pp": None,
                "skew_mean_pp": skew,
                "note": "insufficient data",
            }
            continue
        offsets[model] = {
            # Each side is corrected by its own measured push, so the two
            # coefficients are independent: a good-side-only pessimist
            # (delta+ < 0, delta- ~ 0) gets a success-side boost and an
            # untouched failure side. Note offset_success + offset_failure
            # = -Skew, i.e. the pair jointly restores complementarity.
            "offset_success_pp": round(-delta_plus, 2),
            "offset_failure_pp": round(-delta_minus, 2),
            "delta_plus_pp": delta_plus,
            "delta_minus_pp": delta_minus,
            "skew_mean_pp": skew,
        }
    return offsets


def apply_offset(raw_probability: float, offset_pp: float) -> float:
    """Apply an additive pp offset, clamped to [0, 100]."""
    return max(0.0, min(100.0, raw_probability + offset_pp))


def write_offsets(offsets: dict, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "units": "probability points (pp), 0-100 scale, additive",
        "usage": "corrected = clamp(raw + offset, 0, 100); apply offset_success_pp "
        "to P(success)-style estimates and offset_failure_pp to "
        "P(failure)-style estimates",
        "caveat": "starting correction measured on the audit scenario "
        "distribution — not a universal fix",
        "offsets": offsets,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path
