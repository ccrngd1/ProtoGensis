"""AlignBias: audit LLM stacks for directional probability bias.

Implements the OptimismBench inverted-pair method (Cho & Koshiyama,
Holistic AI/UCL, arXiv 2607.26981): elicit P(good outcome) on a positively
framed item and P(bad outcome) on a minimally reworded inverted item. A
coherent model's answers sum to 100; the signed gap is the Skew, reported
in probability points (pp) on the 0-100 scale.
"""

from .prober import Prober, ProbeReport, parse_response
from .scenarios.loader import Scenario, load_scenarios, track_a_path, track_b_path
from .skew import PairResult, SkewReport, bootstrap_ci, pair_skew, summarize

__version__ = "0.1.0"


class AlignBias:
    """High-level facade: audit one or more models over a scenario set.

    >>> audit = AlignBias(models=["anthropic:claude-opus-4-8", "openai:gpt-5.6"])
    >>> reports = audit.run(scenarios_path="assets/track-b-60.jsonl", runs=5)
    """

    def __init__(self, models: list[str], temperature: float | None = 0.7,
                 concurrency: int = 8):
        self.models = models
        self.temperature = temperature
        self.concurrency = concurrency

    def run(self, scenarios_path=None, runs: int = 1, filter_p50: bool = True):
        """Run the audit synchronously. Returns {model: SkewReport}."""
        import asyncio

        return asyncio.run(self.run_async(scenarios_path, runs, filter_p50))

    async def run_async(self, scenarios_path=None, runs: int = 1,
                        filter_p50: bool = True):
        from .providers.base import resolve_provider

        scenarios = load_scenarios(scenarios_path or track_b_path())
        reports = {}
        for spec in self.models:
            provider = resolve_provider(spec, temperature=self.temperature)
            prober = Prober(provider, concurrency=self.concurrency)
            probe = await prober.probe(scenarios, runs=runs)
            reports[spec] = summarize(provider.label, probe.results,
                                      filter_p50=filter_p50)
        return reports


__all__ = [
    "AlignBias",
    "Scenario",
    "SkewReport",
    "PairResult",
    "ProbeReport",
    "Prober",
    "parse_response",
    "pair_skew",
    "bootstrap_ci",
    "summarize",
    "load_scenarios",
    "track_a_path",
    "track_b_path",
    "__version__",
]
