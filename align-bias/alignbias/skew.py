"""Skew computation, delta decomposition, and bootstrap confidence intervals.

All values are probability points (pp) on the 0-100 scale, consistent with
the OptimismBench paper.

For scenario *i* the model gives s+ (elicited probability of the good
outcome) and s- (elicited probability of the bad outcome, from the
minimally reworded inverted item). A coherent model satisfies
s+ + s- = 100. The signed gap is the Skew:

    Skew_i = s+_i - (100 - s-_i)

    Skew_mean = (1/n) * sum(Skew_i)      > 0 optimistic, < 0 pessimistic

Worked example (GPT-5.4, from the paper): s+ = 72, s- = 20
    Skew = 72 - (100 - 20) = 72 - 80 = -8 pp

Decomposition of where the tilt lives:

    delta+ = mean(P+) - 50    (good-side push)
    delta- = mean(P-) - 50    (bad-side push)
    Skew   = delta+ + delta-

Skew is an internal-coherence measure, NOT deviation from ground truth.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Optional, Sequence


@dataclass
class PairResult:
    """Outcome of probing one inverted pair once."""

    scenario_id: str
    domain: str
    track: str = "B"
    run: int = 0
    p_positive: Optional[float] = None  # s+ : P(good outcome), 0-100
    p_negative: Optional[float] = None  # s- : P(bad outcome), 0-100
    raw_positive: str = ""
    raw_negative: str = ""
    p_true_positive: Optional[float] = None  # stated base rate (Track A)

    @property
    def refused(self) -> bool:
        """True if either elicitation failed to yield a usable number."""
        return self.p_positive is None or self.p_negative is None

    @property
    def hedged_50(self) -> bool:
        """True if either answer is exactly 50 (the uncommitted midpoint)."""
        if self.refused:
            return False
        return self.p_positive == 50.0 or self.p_negative == 50.0

    @property
    def skew(self) -> Optional[float]:
        if self.refused:
            return None
        return pair_skew(self.p_positive, self.p_negative)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(refused=self.refused, hedged_50=self.hedged_50, skew=self.skew)
        return d


def pair_skew(s_plus: float, s_minus: float) -> float:
    """Skew of one pair in pp: Skew = s+ - (100 - s-)."""
    return s_plus - (100.0 - s_minus)


def bootstrap_ci(
    values: Sequence[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of ``values``."""
    if not values:
        raise ValueError("bootstrap_ci requires at least one value")
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    n = len(values)
    means = sorted(mean(rng.choices(values, k=n)) for _ in range(n_resamples))
    alpha = (1.0 - confidence) / 2.0
    lo = means[int(alpha * n_resamples)]
    hi = means[min(int((1.0 - alpha) * n_resamples), n_resamples - 1)]
    return lo, hi


@dataclass
class SkewReport:
    """Aggregate Skew statistics for one audited model."""

    model: str
    n_pairs: int
    n_refused: int
    n_hedged_50: int
    n_scored: int
    skew_mean: Optional[float]  # pp
    ci_low: Optional[float]
    ci_high: Optional[float]
    delta_plus: Optional[float]  # mean(P+) - 50, pp
    delta_minus: Optional[float]  # mean(P-) - 50, pp
    per_domain: dict[str, float] = field(default_factory=dict)
    per_scenario: dict[str, float] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        if self.skew_mean is None:
            return "insufficient data"
        if self.ci_low is not None and self.ci_low > 0:
            return "optimistic tilt"
        if self.ci_high is not None and self.ci_high < 0:
            return "pessimistic tilt"
        return "no significant tilt (CI spans 0)"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict
        return d


def summarize(
    model: str,
    results: Sequence[PairResult],
    filter_p50: bool = True,
    n_resamples: int = 2000,
    seed: int = 0,
) -> SkewReport:
    """Aggregate pair results into a SkewReport.

    Refused pairs (either side unparseable) are always excluded from the
    statistics but counted. Pairs where either answer is exactly 50 are
    excluded when ``filter_p50`` is True, since an exact 50 frequently
    signals an uncommitted hedge rather than a genuine estimate.
    """
    refused = [r for r in results if r.refused]
    answered = [r for r in results if not r.refused]
    hedged = [r for r in answered if r.hedged_50]
    scored = [r for r in answered if not (filter_p50 and r.hedged_50)]

    if not scored:
        return SkewReport(
            model=model,
            n_pairs=len(results),
            n_refused=len(refused),
            n_hedged_50=len(hedged),
            n_scored=0,
            skew_mean=None,
            ci_low=None,
            ci_high=None,
            delta_plus=None,
            delta_minus=None,
        )

    skews = [r.skew for r in scored]
    ci_low, ci_high = bootstrap_ci(skews, n_resamples=n_resamples, seed=seed)

    per_domain: dict[str, list[float]] = {}
    per_scenario: dict[str, list[float]] = {}
    for r in scored:
        per_domain.setdefault(r.domain, []).append(r.skew)
        per_scenario.setdefault(r.scenario_id, []).append(r.skew)

    return SkewReport(
        model=model,
        n_pairs=len(results),
        n_refused=len(refused),
        n_hedged_50=len(hedged),
        n_scored=len(scored),
        skew_mean=mean(skews),
        ci_low=ci_low,
        ci_high=ci_high,
        delta_plus=mean(r.p_positive for r in scored) - 50.0,
        delta_minus=mean(r.p_negative for r in scored) - 50.0,
        per_domain={d: mean(v) for d, v in sorted(per_domain.items())},
        per_scenario={s: mean(v) for s, v in sorted(per_scenario.items())},
    )
