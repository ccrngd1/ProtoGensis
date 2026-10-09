"""Per-call cost from the four usage fields x a dated pricing table (AC #5).

Never computed from per-task token totals, and never from any third-party
tokenizer: usage fields are the source of truth.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PRICING_PATH = Path(__file__).resolve().parent.parent / "config" / "pricing.toml"


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_write_5m_mult: float
    cache_write_1h_mult: float
    cache_read_mult: float
    as_of: str
    source: str
    label: str
    min_cache_tokens: int
    max_cache_points: int
    ttl_seconds: float


def load_pricing(path=None) -> Pricing:
    p = Path(path) if path else DEFAULT_PRICING_PATH
    with open(p, "rb") as f:
        data = tomllib.load(f)
    cache = data.get("cache", {})
    return Pricing(
        input_per_mtok=float(data["input_per_mtok"]),
        output_per_mtok=float(data["output_per_mtok"]),
        cache_write_5m_mult=float(data["cache_write_5m_mult"]),
        cache_write_1h_mult=float(data["cache_write_1h_mult"]),
        cache_read_mult=float(data["cache_read_mult"]),
        as_of=str(data.get("as_of", "")),
        source=str(data.get("source", "")),
        label=str(data.get("label", "")),
        min_cache_tokens=int(cache.get("min_cache_tokens", 1024)),
        max_cache_points=int(cache.get("max_cache_points", 4)),
        ttl_seconds=float(cache.get("ttl_seconds", 300)),
    )


def call_cost(usage: dict, prices: Pricing, cache_ttl: str = "5m") -> float:
    """$ for one call from its usage fields.

    cost = (uncached*P_in + cacheWrite*P_in*w + cacheRead*P_in*r + out*P_out) / 1e6
    """
    w = prices.cache_write_5m_mult if cache_ttl == "5m" else prices.cache_write_1h_mult
    return (
        usage.get("inputTokens", 0) * prices.input_per_mtok
        + usage.get("cacheWriteInputTokens", 0) * prices.input_per_mtok * w
        + usage.get("cacheReadInputTokens", 0) * prices.input_per_mtok * prices.cache_read_mult
        + usage.get("outputTokens", 0) * prices.output_per_mtok
    ) / 1e6


def uncached_counterfactual(usage: dict, prices: Pricing) -> float:
    """$ for the same call if every input token had been billed at 1x."""
    total_in = (
        usage.get("inputTokens", 0)
        + usage.get("cacheWriteInputTokens", 0)
        + usage.get("cacheReadInputTokens", 0)
    )
    return (total_in * prices.input_per_mtok + usage.get("outputTokens", 0) * prices.output_per_mtok) / 1e6


def aggregate(usages, prices: Pricing) -> dict:
    """Sum usage dicts into token/$ splits plus cache hit %."""
    usages = list(usages)
    tot = {"inputTokens": 0, "cacheReadInputTokens": 0, "cacheWriteInputTokens": 0, "outputTokens": 0}
    cost_sum = 0.0
    counterfactual_sum = 0.0
    for u in usages:
        for k in tot:
            tot[k] += u.get(k, 0)
        cost_sum += call_cost(u, prices)
        counterfactual_sum += uncached_counterfactual(u, prices)
    denom = tot["cacheReadInputTokens"] + tot["cacheWriteInputTokens"] + tot["inputTokens"]
    hit = (tot["cacheReadInputTokens"] / denom) if denom else 0.0
    return {
        "tokens": tot,
        "usd": round(cost_sum, 6),
        "usd_uncached_counterfactual": round(counterfactual_sum, 6),
        "cache_hit_pct": round(100.0 * hit, 2),
        "calls": len(usages),
    }
