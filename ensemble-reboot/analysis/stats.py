"""Statistics: Wilson CI for proportions, bootstrap over items for arm
differences, latency percentiles, co-failure matrix.

Every summary number must trace to record_ids; functions here therefore take
and return the record ids they aggregated.
"""

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

Z95 = 1.959963984540054


def wilson_ci(successes: int, n: int, z: float = Z95) -> tuple:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, max(0.0, center - half), min(1.0, center + half))


def bootstrap_diff_ci(
    correct_a: dict, correct_b: dict, n_boot: int = 10000, seed: int = 0, z: float = 0.95
) -> dict:
    """Bootstrap over ITEMS for the accuracy difference of two arms.

    correct_a/correct_b: item_id -> bool, on the same item set (missing items
    are dropped pairwise).
    """
    items = sorted(set(correct_a) & set(correct_b))
    if not items:
        return {"diff": None, "ci": (None, None), "n_items": 0}
    rng = random.Random(seed)
    a = [1 if correct_a[i] else 0 for i in items]
    b = [1 if correct_b[i] else 0 for i in items]
    n = len(items)
    observed = (sum(a) - sum(b)) / n
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(a[i] - b[i] for i in idx) / n)
    diffs.sort()
    lo_q = (1 - z) / 2
    lo = diffs[int(lo_q * n_boot)]
    hi = diffs[min(n_boot - 1, int((1 - lo_q) * n_boot))]
    return {"diff": observed, "ci": (lo, hi), "n_items": n, "n_boot": n_boot}


def percentiles(values: list, ps=(50, 95)) -> dict:
    """Nearest-rank percentiles; {} when empty."""
    if not values:
        return {}
    xs = sorted(values)
    out = {}
    for p in ps:
        k = max(0, math.ceil(p / 100 * len(xs)) - 1)
        out[f"p{p}"] = xs[k]
    return out


@dataclass
class PairCoFailure:
    model_a: str
    model_b: str
    n: int
    p_both_wrong: float
    p_a_wrong: float
    p_b_wrong: float
    expected_independent: float   # P(A wrong) * P(B wrong)
    ratio: float | None           # observed / expected (None when expected == 0)
    grouping: str                 # "within-lab" | "cross-lab"
    item_ids: list = field(default_factory=list)


def co_failure_matrix(
    per_model_correct: dict,       # model_id -> {item_id -> bool}
    families: dict,                # model_id -> family
) -> list:
    """For every model pair: observed P(both wrong) vs P(A wrong)*P(B wrong),
    on the intersection of graded items."""
    models = sorted(per_model_correct)
    out = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            common = sorted(set(per_model_correct[a]) & set(per_model_correct[b]))
            n = len(common)
            if n == 0:
                continue
            aw = sum(1 for it in common if not per_model_correct[a][it])
            bw = sum(1 for it in common if not per_model_correct[b][it])
            both = sum(
                1 for it in common
                if not per_model_correct[a][it] and not per_model_correct[b][it]
            )
            p_a, p_b, p_both = aw / n, bw / n, both / n
            expected = p_a * p_b
            out.append(PairCoFailure(
                model_a=a, model_b=b, n=n,
                p_both_wrong=p_both, p_a_wrong=p_a, p_b_wrong=p_b,
                expected_independent=expected,
                ratio=(p_both / expected) if expected > 0 else None,
                grouping="within-lab" if families.get(a) == families.get(b) else "cross-lab",
                item_ids=common,
            ))
    return out


def group_correct_by_model(records: list) -> tuple:
    """From raw record dicts -> (model_id -> {item_id -> bool}, model_id -> family).
    Uses only records with a grader verdict (correct is not None). When a
    model answered an item multiple times (seeds), an item counts correct only
    if the FIRST seed was correct (seed 0 = the deterministic choice)."""
    per_model = defaultdict(dict)
    fams = {}
    best_seed = {}
    for r in records:
        if r.get("correct") is None:
            continue
        key = (r["model_id"], r["item_id"])
        seed = r.get("seed", 0)
        if key in best_seed and best_seed[key] <= seed:
            continue
        best_seed[key] = seed
        per_model[r["model_id"]][r["item_id"]] = bool(r["correct"])
        fams[r["model_id"]] = r.get("family", "")
    return dict(per_model), fams
