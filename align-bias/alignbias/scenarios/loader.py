"""Scenario loading for AlignBias.

Scenarios are inverted pairs: one shared third-person vignette plus two
minimal-wording question phrasings — one asking P(good outcome), one asking
P(bad outcome). Bundled assets derive from OptimismBench (Cho & Koshiyama,
Holistic AI/UCL, arXiv 2607.26981, CC BY 4.0); see assets/ATTRIBUTION.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


@dataclass(frozen=True)
class Scenario:
    """One inverted pair: shared vignette, positive + negative phrasings."""

    id: str
    track: str  # "A" (controlled calibration) or "B" (naturalistic)
    domain: str
    scenario: str
    question_positive: str
    question_negative: str
    p_true_positive: float | None = None  # stated base rate (Track A only)
    source: str = ""
    metadata: dict = field(default_factory=dict)

    def prompt(self, valence: str) -> str:
        """Full elicitation text for one side of the pair."""
        question = self.question_positive if valence == "positive" else self.question_negative
        return f"{self.scenario}\n\n{question}"


def track_a_path() -> Path:
    return ASSETS_DIR / "track-a-calibration-15.jsonl"


def track_b_path() -> Path:
    return ASSETS_DIR / "track-b-60.jsonl"


def load_scenarios(path: str | Path) -> list[Scenario]:
    """Load scenarios from a JSONL file of inverted-pair records."""
    path = Path(path)
    scenarios: list[Scenario] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            for key in ("id", "scenario", "question_positive", "question_negative"):
                if key not in rec:
                    raise ValueError(f"{path}:{lineno}: missing required field {key!r}")
            scenarios.append(
                Scenario(
                    id=rec["id"],
                    track=rec.get("track", "B"),
                    domain=rec.get("domain", "unknown"),
                    scenario=rec["scenario"],
                    question_positive=rec["question_positive"],
                    question_negative=rec["question_negative"],
                    p_true_positive=rec.get("p_true_positive"),
                    source=rec.get("source", ""),
                    metadata=rec.get("metadata", {}),
                )
            )
    if not scenarios:
        raise ValueError(f"{path}: no scenarios found")
    return scenarios
