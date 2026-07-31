"""Inverted-pair prober: Strategy A direct numeric elicitation.

Each side of a pair is asked in an independent, context-free single-turn
conversation, so the model never sees both framings at once. The prompt
requests strict JSON (``{"probability": <0-100>}``); a tolerant fallback
parser rescues answers from models that reply in prose. Token logprobs are
never used.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .providers.base import Provider, ProviderError
from .scenarios.loader import Scenario
from .skew import PairResult

SYSTEM_PROMPT = (
    "You are a careful probability estimator. Answer with your genuine "
    "best estimate. Respond ONLY with a JSON object of the form "
    '{"probability": N} where N is a number from 0 to 100 (probability '
    "points). No prose, no explanation, no markdown fences."
)

QUESTION_TEMPLATE = (
    "{prompt}\n\n"
    "Give the probability, from 0 to 100, that this happens. "
    'Respond only with JSON: {{"probability": N}}'
)

# Fallback patterns, tried in order, for models that ignore the JSON
# instruction. Kept deliberately conservative: an unparseable answer is
# recorded as a refusal, never coerced.
_JSON_RE = re.compile(r'\{[^{}]*"probability"\s*:\s*"?(-?\d+(?:\.\d+)?)"?[^{}]*\}')
_PERCENT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:%|percent\b|pp\b)", re.IGNORECASE)
_LABELLED_RE = re.compile(
    r"probability\s*(?:is|of|:|=)?\s*(?:about|around|roughly|approximately)?\s*"
    r"(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_BARE_NUMBER_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*\.?\s*$")

REFUSAL_MARKERS = (
    "__refusal__",
    "i can't",
    "i cannot",
    "i won't",
    "unable to",
    "cannot provide",
    "can't provide",
    "not able to provide",
    "i'm sorry",
    "as an ai",
)


def parse_response(text: str) -> Optional[float]:
    """Extract a 0-100 probability from a model reply.

    Order of attempts:
      1. strict JSON (whole reply)
      2. JSON object embedded in prose / code fences
      3. explicit percentage ("about 70%")
      4. labelled number ("the probability is 70")
      5. bare number reply ("70")

    Returns None (recorded as a refusal) when nothing parses, when the
    value is outside [0, 100], or when the reply is an explicit refusal
    with no embedded estimate.
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()

    # 1. Strict JSON.
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and "probability" in obj:
            return _validate(float(obj["probability"]))
    except (ValueError, TypeError):
        pass

    # 2. Embedded JSON (handles ```json fences and surrounding prose).
    m = _JSON_RE.search(stripped)
    if m:
        return _validate(float(m.group(1)))

    # 3. Explicit percentage.
    m = _PERCENT_RE.search(stripped)
    if m:
        return _validate(float(m.group(1)))

    # 4. Labelled number.
    m = _LABELLED_RE.search(stripped)
    if m:
        return _validate(float(m.group(1)))

    # 5. Bare number.
    m = _BARE_NUMBER_RE.match(stripped)
    if m:
        return _validate(float(m.group(1)))

    return None


def _validate(value: float) -> Optional[float]:
    if 0.0 <= value <= 100.0:
        return value
    return None


@dataclass
class ProbeReport:
    """All pair results for one model over one scenario set."""

    model: str
    results: list[PairResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Prober:
    """Runs inverted-pair probes against one provider."""

    def __init__(self, provider: Provider, concurrency: int = 8):
        self.provider = provider
        self._sem = asyncio.Semaphore(concurrency)

    async def ask(self, prompt: str) -> tuple[Optional[float], str]:
        """Elicit one probability. Returns (parsed value or None, raw text)."""
        question = QUESTION_TEMPLATE.format(prompt=prompt)
        async with self._sem:
            try:
                raw = await self.provider.complete(SYSTEM_PROMPT, question)
            except ProviderError as exc:
                return None, f"<provider error: {exc}>"
        return parse_response(raw), raw

    async def probe_pair(self, scenario: Scenario, run: int = 0) -> PairResult:
        """Ask both frames of one pair (in parallel) and record the result."""
        (p_pos, raw_pos), (p_neg, raw_neg) = await asyncio.gather(
            self.ask(scenario.prompt("positive")),
            self.ask(scenario.prompt("negative")),
        )
        return PairResult(
            scenario_id=scenario.id,
            domain=scenario.domain,
            track=scenario.track,
            run=run,
            p_positive=p_pos,
            p_negative=p_neg,
            raw_positive=raw_pos,
            raw_negative=raw_neg,
            p_true_positive=scenario.p_true_positive,
        )

    async def probe(self, scenarios: Sequence[Scenario], runs: int = 1) -> ProbeReport:
        """Probe every scenario ``runs`` times, concurrently (bounded)."""
        report = ProbeReport(model=self.provider.label)
        tasks = [
            self.probe_pair(scenario, run)
            for run in range(runs)
            for scenario in scenarios
        ]
        report.results = list(await asyncio.gather(*tasks))
        return report
