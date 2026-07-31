"""CLI tests — all offline (mock data or bundled assets, no API calls)."""

import json

import pytest
import yaml
from click.testing import CliRunner

from alignbias.cli import main
from alignbias.report import write_json
from alignbias.skew import PairResult, summarize


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def skew_json(tmp_path):
    """A realistic skew.json produced through the real report writer."""
    results = {
        "anthropic:claude-opus-4-8": [
            PairResult("a", "business", p_positive=72.0, p_negative=20.0),
            PairResult("b", "medical", p_positive=60.0, p_negative=45.0),
        ],
        "openai:gpt-5.6": [
            PairResult("a", "business", p_positive=80.0, p_negative=28.0),
            PairResult("b", "medical", p_positive=75.0, p_negative=35.0),
        ],
    }
    reports = [summarize(model, rs, filter_p50=False) for model, rs in results.items()]
    path = tmp_path / "skew.json"
    write_json(reports, path, results)
    return path


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for command in ("audit", "control", "routing-advisor", "calibrate", "demo"):
        assert command in result.output


def test_version(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0


def test_list_scenarios_track_b(runner):
    result = runner.invoke(main, ["list-scenarios", "--track", "B"])
    assert result.exit_code == 0
    assert len(result.output.strip().splitlines()) == 60


def test_list_scenarios_track_a(runner):
    result = runner.invoke(main, ["list-scenarios", "--track", "A"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert len(lines) == 15
    assert "stated P+" in result.output  # base rates are surfaced


def test_audit_requires_models(runner):
    result = runner.invoke(main, ["audit"])
    assert result.exit_code != 0
    assert "--models" in result.output


def test_audit_with_unresolvable_model_fails_cleanly(runner, tmp_path):
    # "mystery-model" has no provider prefix -> resolve fails, no API calls.
    result = runner.invoke(
        main, ["audit", "--models", "mystery-model", "--out", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "no models could be audited" in result.output


def test_routing_advisor(runner, skew_json, tmp_path):
    config = tmp_path / "routing.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "tasks": {
                    "risk-assessment": {"preferred_tilt": "pessimistic"},
                    "forecasting": {"preferred_tilt": "neutral", "max_abs_skew": 5},
                }
            }
        )
    )
    result = runner.invoke(
        main,
        ["routing-advisor", "--config", str(config), "--report", str(skew_json)],
    )
    assert result.exit_code == 0, result.output
    assert "risk-assessment" in result.output
    assert "forecasting" in result.output
    assert "pp" in result.output


def test_calibrate(runner, skew_json, tmp_path):
    out = tmp_path / "offsets.json"
    result = runner.invoke(
        main, ["calibrate", "--report", str(skew_json), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    offsets = payload["offsets"]
    assert set(offsets) == {"anthropic:claude-opus-4-8", "openai:gpt-5.6"}
    for entry in offsets.values():
        # separate success/failure coefficients, both present
        assert entry["offset_success_pp"] is not None
        assert entry["offset_failure_pp"] is not None
        # correction restores complementarity: offsets sum to -Skew
        assert entry["offset_success_pp"] + entry["offset_failure_pp"] == pytest.approx(
            -entry["skew_mean_pp"], abs=0.02
        )
    assert "starting correction" in result.output


def test_calibrate_output_units_are_pp(runner, skew_json, tmp_path):
    out = tmp_path / "offsets.json"
    runner.invoke(main, ["calibrate", "--report", str(skew_json), "--out", str(out)])
    payload = json.loads(out.read_text())
    assert "probability points" in payload["units"]


def test_bundled_assets_are_valid():
    from alignbias.scenarios.loader import load_scenarios, track_a_path, track_b_path

    track_b = load_scenarios(track_b_path())
    assert len(track_b) == 60
    domains = {}
    for s in track_b:
        domains[s.domain] = domains.get(s.domain, 0) + 1
    assert len(domains) == 6
    assert all(count == 10 for count in domains.values())

    track_a = load_scenarios(track_a_path())
    assert len(track_a) == 15
    assert all(s.p_true_positive is not None for s in track_a)
    # Paper construction rule: stated base rates within a usable band.
    assert all(0 < s.p_true_positive < 100 for s in track_a)
