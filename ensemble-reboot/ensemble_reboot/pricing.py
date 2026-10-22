"""Pricing table loading and cost computation.

An UNKNOWN price never becomes $0: cost_usd is None and price_status is
"UNKNOWN", and the conservative estimate bills unknown-priced tokens at the
highest known roster rate, flagged so summaries can surface it.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Price:
    input: float | None
    output: float | None
    cache_read: float | None
    status: str  # "OK" or "UNKNOWN"
    source: str = ""

    @property
    def known(self) -> bool:
        return self.status == "OK" and self.input is not None and self.output is not None


@dataclass
class CostResult:
    cost_usd: float | None
    price_status: str            # "OK" | "UNKNOWN"
    conservative_usd: float      # UNKNOWN priced at the highest known rate
    conservative_is_estimate: bool


class PricingTable:
    def __init__(self, profiles: dict[str, Price]):
        self.profiles = profiles
        known = [p for p in profiles.values() if p.known]
        if known:
            self._max_input = max(p.input for p in known)
            self._max_output = max(p.output for p in known)
            self._max_cache = max((p.cache_read or 0.0) for p in known)
        else:
            self._max_input = self._max_output = self._max_cache = None

    @classmethod
    def load(cls, path) -> "PricingTable":
        raw = yaml.safe_load(Path(path).read_text())
        profiles = {}
        for pid, e in raw["profiles"].items():
            profiles[pid] = Price(
                input=e.get("input"),
                output=e.get("output"),
                cache_read=e.get("cache_read"),
                status=e.get("status", "UNKNOWN"),
                source=e.get("source", ""),
            )
        return cls(profiles)

    def cost(
        self,
        profile_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
    ) -> CostResult:
        p = self.profiles.get(profile_id)
        if p is not None and p.known:
            cache_rate = p.cache_read if p.cache_read is not None else p.input
            usd = (
                input_tokens * p.input
                + output_tokens * p.output
                + cache_read_tokens * cache_rate
            ) / 1_000_000
            return CostResult(usd, "OK", usd, False)
        # UNKNOWN: never pretend it is free.
        if self._max_input is None:
            raise ValueError(
                f"no known prices at all; cannot even bound cost for {profile_id}"
            )
        conservative = (
            input_tokens * self._max_input
            + output_tokens * self._max_output
            + cache_read_tokens * self._max_cache
        ) / 1_000_000
        return CostResult(None, "UNKNOWN", conservative, True)
