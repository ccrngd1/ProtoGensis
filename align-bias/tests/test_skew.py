"""Skew math tests, including the paper's GPT-5.4 worked-example fixture."""

import pytest

from alignbias.prober import Prober
from alignbias.skew import PairResult, bootstrap_ci, pair_skew, summarize

from conftest import SkewedMockProvider, make_scenario


# --- GPT-5.4 worked example from the paper -------------------------------

@pytest.fixture
def gpt54_worked_example():
    """Paper worked example: s+ = 72, s- = 20 -> Skew = 72 - (100-20) = -8."""
    return {"s_plus": 72.0, "s_minus": 20.0, "expected_skew": -8.0}


def test_gpt54_worked_example_pair_skew(gpt54_worked_example):
    ex = gpt54_worked_example
    assert pair_skew(ex["s_plus"], ex["s_minus"]) == ex["expected_skew"]
    # spelled out: Skew = s+ - (100 - s-) = 72 - 80 = -8
    assert pair_skew(72, 20) == 72 - (100 - 20) == -8


def test_gpt54_worked_example_through_prober(gpt54_worked_example):
    """End-to-end: mock provider returns s+=72 / s-=20, Skew must be -8 pp."""
    import asyncio

    ex = gpt54_worked_example
    provider = SkewedMockProvider(ex["s_plus"], ex["s_minus"])
    prober = Prober(provider)
    result = asyncio.run(prober.probe_pair(make_scenario()))
    assert result.p_positive == 72.0
    assert result.p_negative == 20.0
    assert result.skew == -8.0

    report = summarize(provider.label, [result])
    assert report.skew_mean == -8.0
    assert report.verdict in ("pessimistic tilt", "no significant tilt (CI spans 0)")


# --- Skew identities ------------------------------------------------------

def test_coherent_model_has_zero_skew():
    assert pair_skew(70, 30) == 0.0
    assert pair_skew(15, 85) == 0.0


def test_optimistic_positive_skew():
    # Both frames rosy: success inflated AND failure deflated.
    assert pair_skew(80, 30) == 10.0


def test_skew_equals_delta_plus_plus_delta_minus():
    """Skew = delta+ + delta- where delta+/- = mean(P+/-) - 50."""
    results = [
        PairResult("a", "d", p_positive=72.0, p_negative=20.0),
        PairResult("b", "d", p_positive=60.0, p_negative=45.0),
        PairResult("c", "d", p_positive=30.0, p_negative=65.0),
    ]
    report = summarize("m", results, filter_p50=False)
    assert report.delta_plus == pytest.approx((72 + 60 + 30) / 3 - 50)
    assert report.delta_minus == pytest.approx((20 + 45 + 65) / 3 - 50)
    assert report.skew_mean == pytest.approx(report.delta_plus + report.delta_minus)


def test_skew_mean_is_mean_of_pair_skews():
    results = [
        PairResult("a", "d", p_positive=72.0, p_negative=20.0),  # -8
        PairResult("b", "d", p_positive=60.0, p_negative=48.0),  # +8
    ]
    report = summarize("m", results, filter_p50=False)
    assert report.skew_mean == pytest.approx(0.0)


# --- refusal filtering ----------------------------------------------------

def test_refused_pairs_excluded_but_counted():
    results = [
        PairResult("a", "d", p_positive=72.0, p_negative=20.0),
        PairResult("b", "d", p_positive=None, p_negative=20.0),   # refused
        PairResult("c", "d", p_positive=70.0, p_negative=None),   # refused
    ]
    report = summarize("m", results)
    assert report.n_pairs == 3
    assert report.n_refused == 2
    assert report.n_scored == 1
    assert report.skew_mean == -8.0


def test_all_refused_yields_no_data():
    results = [PairResult("a", "d")]
    report = summarize("m", results)
    assert report.n_scored == 0
    assert report.skew_mean is None
    assert report.verdict == "insufficient data"


# --- P=50 filter ----------------------------------------------------------

def test_p50_hedges_filtered_by_default():
    results = [
        PairResult("a", "d", p_positive=72.0, p_negative=20.0),  # -8
        PairResult("b", "d", p_positive=50.0, p_negative=50.0),  # hedge
        PairResult("c", "d", p_positive=50.0, p_negative=30.0),  # hedge (one side)
    ]
    report = summarize("m", results)
    assert report.n_hedged_50 == 2
    assert report.n_scored == 1
    assert report.skew_mean == -8.0


def test_p50_filter_can_be_disabled():
    results = [
        PairResult("a", "d", p_positive=50.0, p_negative=50.0),  # skew 0
        PairResult("b", "d", p_positive=72.0, p_negative=20.0),  # skew -8
    ]
    report = summarize("m", results, filter_p50=False)
    assert report.n_scored == 2
    assert report.skew_mean == pytest.approx(-4.0)


# --- bootstrap CI ---------------------------------------------------------

def test_bootstrap_ci_brackets_mean():
    values = [-8.0, -6.0, -10.0, -7.0, -9.0, -8.5, -7.5]
    lo, hi = bootstrap_ci(values, n_resamples=1000, seed=42)
    assert lo <= sum(values) / len(values) <= hi
    assert lo < hi


def test_bootstrap_ci_deterministic_with_seed():
    values = [1.0, 2.0, 3.0, 4.0]
    assert bootstrap_ci(values, seed=7) == bootstrap_ci(values, seed=7)


def test_bootstrap_ci_single_value():
    assert bootstrap_ci([5.0]) == (5.0, 5.0)


def test_bootstrap_ci_empty_raises():
    with pytest.raises(ValueError):
        bootstrap_ci([])


# --- verdicts and per-domain ----------------------------------------------

def test_pessimistic_verdict_when_ci_below_zero():
    results = [
        PairResult(f"s{i}", "d", p_positive=72.0, p_negative=20.0 + (i % 3))
        for i in range(20)
    ]
    report = summarize("m", results)
    assert report.ci_high < 0
    assert report.verdict == "pessimistic tilt"


def test_per_domain_breakdown():
    results = [
        PairResult("a", "business", p_positive=80.0, p_negative=30.0),   # +10
        PairResult("b", "medical", p_positive=60.0, p_negative=30.0),    # -10
    ]
    report = summarize("m", results)
    assert report.per_domain["business"] == pytest.approx(10.0)
    assert report.per_domain["medical"] == pytest.approx(-10.0)


# --- Track A control ------------------------------------------------------

def test_track_a_control_near_zero_for_calibrated_mock():
    """A well-calibrated model answering complementary values -> Skew ~ 0."""
    import asyncio

    provider = SkewedMockProvider(s_plus=33.3, s_minus=66.7)
    prober = Prober(provider)
    scenarios = [make_scenario(f"A{i}", track="A", p_true=33.3) for i in range(15)]
    probe = asyncio.run(prober.probe(scenarios))
    report = summarize(provider.label, probe.results)
    assert report.n_scored == 15
    assert abs(report.skew_mean) < 0.5  # near 0 within float wiggle
