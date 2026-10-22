"""Stats: Wilson CI, bootstrap, percentiles, and co-failure math checked
against a HAND-COMPUTED example."""

import pytest

from analysis.stats import (
    bootstrap_diff_ci,
    co_failure_matrix,
    group_correct_by_model,
    percentiles,
    wilson_ci,
)


def test_wilson_ci_known_value():
    # 8/10: Wilson 95% interval is approximately [0.49, 0.94]
    p, lo, hi = wilson_ci(8, 10)
    assert p == pytest.approx(0.8)
    assert lo == pytest.approx(0.4902, abs=0.005)
    assert hi == pytest.approx(0.9433, abs=0.005)


def test_wilson_ci_edges():
    p, lo, hi = wilson_ci(0, 10)
    assert p == 0.0 and lo == 0.0 and hi > 0.0
    p, lo, hi = wilson_ci(10, 10)
    assert p == 1.0 and hi == pytest.approx(1.0) and lo < 1.0
    assert wilson_ci(0, 0) == (0.0, 0.0, 1.0)


def test_percentiles_nearest_rank():
    vals = list(range(1, 11))  # 1..10
    out = percentiles(vals)
    assert out["p50"] == 5
    assert out["p95"] == 10
    assert percentiles([]) == {}
    assert percentiles([7.5]) == {"p50": 7.5, "p95": 7.5}


def test_bootstrap_diff_direction_and_determinism():
    a = {f"i{k}": k < 8 for k in range(10)}   # 80%
    b = {f"i{k}": k < 4 for k in range(10)}   # 40%
    r1 = bootstrap_diff_ci(a, b, n_boot=2000, seed=7)
    r2 = bootstrap_diff_ci(a, b, n_boot=2000, seed=7)
    assert r1 == r2  # deterministic given seed
    assert r1["diff"] == pytest.approx(0.4)
    lo, hi = r1["ci"]
    assert lo <= 0.4 <= hi


def test_bootstrap_no_common_items():
    r = bootstrap_diff_ci({"a": True}, {"b": False})
    assert r["diff"] is None and r["n_items"] == 0


def test_co_failure_hand_computed_example():
    """Hand-computed: 10 items. A wrong on {1,2,3,4} -> P(A w)=0.4.
    B wrong on {3,4,5} -> P(B w)=0.3. Both wrong on {3,4} -> P(both)=0.2.
    Independent expectation 0.4*0.3=0.12; ratio 0.2/0.12 = 5/3 ~ 1.667."""
    items = [f"i{k}" for k in range(1, 11)]
    a = {it: it not in {"i1", "i2", "i3", "i4"} for it in items}
    b = {it: it not in {"i3", "i4", "i5"} for it in items}
    pairs = co_failure_matrix(
        {"modelA": a, "modelB": b},
        {"modelA": "anthropic", "modelB": "openai"},
    )
    assert len(pairs) == 1
    pr = pairs[0]
    assert pr.n == 10
    assert pr.p_a_wrong == pytest.approx(0.4)
    assert pr.p_b_wrong == pytest.approx(0.3)
    assert pr.p_both_wrong == pytest.approx(0.2)
    assert pr.expected_independent == pytest.approx(0.12)
    assert pr.ratio == pytest.approx(5 / 3)
    assert pr.grouping == "cross-lab"
    assert set(pr.item_ids) == set(items)


def test_co_failure_within_lab_grouping():
    a = {"i1": True, "i2": False}
    b = {"i1": False, "i2": False}
    pairs = co_failure_matrix(
        {"x": a, "y": b}, {"x": "anthropic", "y": "anthropic"})
    assert pairs[0].grouping == "within-lab"


def test_co_failure_ratio_none_when_either_perfect():
    a = {"i1": True, "i2": True}       # never wrong -> expected = 0
    b = {"i1": False, "i2": True}
    pairs = co_failure_matrix({"a": a, "b": b}, {"a": "x", "b": "y"})
    assert pairs[0].ratio is None


def test_group_correct_by_model_uses_lowest_seed():
    records = [
        {"model_id": "m", "item_id": "i1", "seed": 1, "correct": True, "family": "f"},
        {"model_id": "m", "item_id": "i1", "seed": 0, "correct": False, "family": "f"},
        {"model_id": "m", "item_id": "i2", "seed": 0, "correct": True, "family": "f"},
        {"model_id": "m", "item_id": "i3", "seed": 0, "correct": None, "family": "f"},
    ]
    per_model, fams = group_correct_by_model(records)
    assert per_model["m"] == {"i1": False, "i2": True}  # seed 0 wins; ungraded dropped
    assert fams["m"] == "f"
