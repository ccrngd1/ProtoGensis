"""Stats (AC #10): exact McNemar, seeded bootstrap, Holm. Stdlib only."""

import math
import random


def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k + 1))


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value on discordant pairs (binomial, p=0.5).

    b = pairs where arm A passed and arm B failed; c = the reverse."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2.0 * _binom_cdf(k, n, 0.5)
    if b == c:
        p -= math.comb(n, k) * 0.5**n  # don't double-count the center term
    return min(1.0, p)


def bootstrap_ci(values, stat=None, n_resamples: int = 10_000, seed: int = 20261009,
                 alpha: float = 0.05):
    """Seeded percentile bootstrap CI for a statistic over `values`.

    `values` is a list of per-unit observations (e.g. paired differences);
    `stat` defaults to the mean. Deterministic for a given seed."""
    if not values:
        return (0.0, 0.0)
    stat = stat or (lambda xs: sum(xs) / len(xs))
    rng = random.Random(seed)
    n = len(values)
    stats = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        stats.append(stat(sample))
    stats.sort()
    lo = stats[int((alpha / 2) * n_resamples)]
    hi = stats[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return (lo, hi)


def holm(p_values: dict, alpha: float = 0.05) -> dict:
    """Holm step-down correction. p_values: id -> p. Returns id ->
    {p, adjusted, reject}."""
    items = sorted(p_values.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(items)
    out = {}
    running_max = 0.0
    rejecting = True
    for i, (hid, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running_max = max(running_max, adj)
        adj = running_max
        if rejecting and adj > alpha:
            rejecting = False
        out[hid] = {"p": p, "adjusted": adj, "reject": rejecting and adj <= alpha}
    # Holm rejects the ordered prefix while adj <= alpha
    return out
