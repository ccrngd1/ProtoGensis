"""Routing advisor tests."""

import json

import pytest
import yaml

from alignbias.routing import (
    TaskPolicy,
    advise,
    format_recommendations,
    load_routing_config,
    load_skew_report,
)

SUMMARIES = [
    {"model": "anthropic:opt", "skew_mean": 8.0, "delta_plus": 5.0, "delta_minus": 3.0},
    {"model": "openai:pess", "skew_mean": -7.7, "delta_plus": -4.0, "delta_minus": -3.7},
    {"model": "gemini:neutral", "skew_mean": 0.5, "delta_plus": 0.3, "delta_minus": 0.2},
    {"model": "mock:nodata", "skew_mean": None, "delta_plus": None, "delta_minus": None},
]


def test_neutral_task_prefers_smallest_abs_skew():
    policy = TaskPolicy(name="forecasting", preferred_tilt="neutral")
    [rec] = advise([policy], SUMMARIES)
    assert rec.ranked_models[0]["model"] == "gemini:neutral"


def test_pessimistic_task_prefers_negative_skew():
    policy = TaskPolicy(name="risk", preferred_tilt="pessimistic")
    [rec] = advise([policy], SUMMARIES)
    assert rec.ranked_models[0]["model"] == "openai:pess"


def test_optimistic_task_prefers_positive_skew():
    policy = TaskPolicy(name="brainstorm", preferred_tilt="optimistic")
    [rec] = advise([policy], SUMMARIES)
    assert rec.ranked_models[0]["model"] == "anthropic:opt"


def test_max_abs_skew_excludes():
    policy = TaskPolicy(name="strict", preferred_tilt="neutral", max_abs_skew=5.0)
    [rec] = advise([policy], SUMMARIES)
    ranked = {e["model"] for e in rec.ranked_models}
    excluded = {e["model"] for e in rec.excluded}
    assert ranked == {"gemini:neutral"}
    assert "anthropic:opt" in excluded and "openai:pess" in excluded


def test_no_data_models_always_excluded():
    policy = TaskPolicy(name="any", preferred_tilt="neutral")
    [rec] = advise([policy], SUMMARIES)
    assert any(e["model"] == "mock:nodata" for e in rec.excluded)


def test_invalid_tilt_rejected():
    with pytest.raises(ValueError):
        TaskPolicy(name="bad", preferred_tilt="rosy")


def test_load_routing_config_yaml(tmp_path):
    config = {
        "tasks": {
            "risk-assessment": {"preferred_tilt": "pessimistic", "max_abs_skew": 15},
            "brainstorming": {"preferred_tilt": "optimistic"},
            "default": None,  # bare key -> neutral defaults
        }
    }
    path = tmp_path / "routing.yaml"
    path.write_text(yaml.safe_dump(config))
    policies = load_routing_config(path)
    by_name = {p.name: p for p in policies}
    assert by_name["risk-assessment"].preferred_tilt == "pessimistic"
    assert by_name["risk-assessment"].max_abs_skew == 15
    assert by_name["default"].preferred_tilt == "neutral"


def test_load_routing_config_rejects_missing_tasks(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text("nothing: here\n")
    with pytest.raises(ValueError):
        load_routing_config(path)


def test_load_skew_report(tmp_path):
    path = tmp_path / "skew.json"
    path.write_text(json.dumps({"models": SUMMARIES}))
    assert load_skew_report(path) == SUMMARIES


def test_load_skew_report_rejects_empty(tmp_path):
    path = tmp_path / "skew.json"
    path.write_text(json.dumps({"models": []}))
    with pytest.raises(ValueError):
        load_skew_report(path)


def test_format_recommendations_mentions_pp_units():
    policy = TaskPolicy(name="forecasting", preferred_tilt="neutral")
    recs = advise([policy], SUMMARIES)
    text = format_recommendations(recs)
    assert "forecasting" in text
    assert "pp" in text  # Skew always rendered in probability points
    assert "-7.7 pp" in text or "-7.7" in text
