"""Shared test fixtures: mock providers with canned responses.

No real API calls happen anywhere in this suite.
"""

from __future__ import annotations

import json

import pytest

from alignbias.providers.base import Provider
from alignbias.scenarios.loader import Scenario


class MockProvider(Provider):
    """Returns predetermined s+ / s- values keyed by scenario text.

    ``answers`` maps a substring of the prompt (usually the question text)
    to the raw reply the model should give. Falls back to ``default``.
    """

    name = "mock"

    def __init__(self, answers: dict[str, str] | None = None,
                 default: str = '{"probability": 50}'):
        super().__init__(model="canned", temperature=None)
        self.answers = answers or {}
        self.default = default
        self.calls: list[str] = []

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        self.calls.append(user)
        for needle, reply in self.answers.items():
            if needle in user:
                return reply
        return self.default


class SkewedMockProvider(Provider):
    """Answers every positive frame with s+ and every negative frame with s-.

    The frame is detected from the question phrasing supplied via the
    scenario fixtures below (questions contain 'POSITIVE_FRAME' /
    'NEGATIVE_FRAME' sentinels).
    """

    name = "mock"

    def __init__(self, s_plus: float, s_minus: float):
        super().__init__(model=f"skew({s_plus},{s_minus})", temperature=None)
        self.s_plus = s_plus
        self.s_minus = s_minus

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        if "POSITIVE_FRAME" in user:
            return json.dumps({"probability": self.s_plus})
        if "NEGATIVE_FRAME" in user:
            return json.dumps({"probability": self.s_minus})
        raise AssertionError(f"frame sentinel missing from prompt: {user!r}")


def make_scenario(sid: str = "S1", domain: str = "business",
                  track: str = "B", p_true: float | None = None) -> Scenario:
    return Scenario(
        id=sid,
        track=track,
        domain=domain,
        scenario="A startup ships a new product.",
        question_positive=f"POSITIVE_FRAME What is the probability it succeeds? ({sid})",
        question_negative=f"NEGATIVE_FRAME What is the probability it fails? ({sid})",
        p_true_positive=p_true,
    )


@pytest.fixture
def scenario():
    return make_scenario()


@pytest.fixture
def scenarios_six_domains():
    domains = ["business", "medical", "sports", "relationships", "technology",
               "environment"]
    return [make_scenario(f"S{i}", domain=d) for i, d in enumerate(domains)]
