"""Parser tests: strict JSON path plus the tolerant fallbacks."""

import asyncio

import pytest

from alignbias.prober import Prober, parse_response

from conftest import MockProvider, make_scenario


# --- strict JSON ----------------------------------------------------------

def test_strict_json():
    assert parse_response('{"probability": 72}') == 72.0


def test_strict_json_float():
    assert parse_response('{"probability": 33.3}') == 33.3


def test_json_with_whitespace():
    assert parse_response('  {"probability": 20}\n') == 20.0


# --- tolerant fallbacks ---------------------------------------------------

def test_json_in_markdown_fence():
    assert parse_response('```json\n{"probability": 65}\n```') == 65.0


def test_json_embedded_in_prose():
    text = 'Based on the scenario, {"probability": 40} seems right.'
    assert parse_response(text) == 40.0


def test_json_string_value():
    assert parse_response('{"probability": "55"}') == 55.0


def test_percent_in_prose():
    assert parse_response("I'd estimate about 70% chance of success.") == 70.0


def test_pp_units():
    assert parse_response("Roughly 65 pp") == 65.0


def test_labelled_number():
    assert parse_response("The probability is approximately 35") == 35.0


def test_bare_number():
    assert parse_response("72") == 72.0


def test_bare_number_with_period():
    assert parse_response("72.") == 72.0


def test_bare_float():
    assert parse_response("33.3") == 33.3


# --- boundaries and rejections ---------------------------------------------

def test_zero_and_hundred_are_valid():
    assert parse_response('{"probability": 0}') == 0.0
    assert parse_response('{"probability": 100}') == 100.0


def test_out_of_range_rejected():
    assert parse_response('{"probability": 150}') is None
    assert parse_response('{"probability": -5}') is None


def test_empty_reply():
    assert parse_response("") is None
    assert parse_response("   \n") is None


def test_refusal_prose_without_number():
    assert parse_response("I'm sorry, I can't estimate probabilities for medical outcomes.") is None


def test_prose_without_any_number():
    assert parse_response("It depends on many unknown factors.") is None


def test_refusal_with_embedded_estimate_still_parses():
    # Explicit percentage outranks the refusal marker.
    text = "I can't be certain, but I'd put it around 60%."
    assert parse_response(text) == 60.0


# --- prober end-to-end with mock providers ---------------------------------

def test_prober_records_raw_and_parsed(scenario):
    provider = MockProvider(
        answers={
            "POSITIVE_FRAME": '{"probability": 72}',
            "NEGATIVE_FRAME": '{"probability": 20}',
        }
    )
    result = asyncio.run(Prober(provider).probe_pair(scenario))
    assert result.p_positive == 72.0
    assert result.p_negative == 20.0
    assert result.raw_positive == '{"probability": 72}'
    assert not result.refused


def test_prober_marks_unparseable_as_refused(scenario):
    provider = MockProvider(
        answers={
            "POSITIVE_FRAME": "I cannot answer that.",
            "NEGATIVE_FRAME": '{"probability": 20}',
        }
    )
    result = asyncio.run(Prober(provider).probe_pair(scenario))
    assert result.p_positive is None
    assert result.refused


def test_prober_survives_provider_errors(scenario):
    from alignbias.providers.base import Provider, ProviderError

    class ExplodingProvider(Provider):
        name = "mock"

        def __init__(self):
            super().__init__(model="boom", temperature=None)

        async def complete(self, system, user, max_tokens=300):
            raise ProviderError("simulated outage")

    result = asyncio.run(Prober(ExplodingProvider()).probe_pair(scenario))
    assert result.refused
    assert "provider error" in result.raw_positive


def test_prober_runs_multiplier(scenarios_six_domains):
    from conftest import SkewedMockProvider

    provider = SkewedMockProvider(72, 20)
    report = asyncio.run(Prober(provider).probe(scenarios_six_domains, runs=3))
    assert len(report.results) == 18  # 6 scenarios x 3 runs
    assert all(r.skew == -8.0 for r in report.results)


def test_prober_asks_both_frames_independently(scenario):
    provider = MockProvider(default='{"probability": 50}')
    asyncio.run(Prober(provider).probe_pair(scenario))
    assert len(provider.calls) == 2
    joined = " ".join(provider.calls)
    assert "POSITIVE_FRAME" in joined and "NEGATIVE_FRAME" in joined
