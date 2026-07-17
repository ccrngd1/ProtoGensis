"""Reporter and CLI integration tests (FR7)."""

from __future__ import annotations

import json

from setup_trap.cli import main
from setup_trap.reporter import render_cli, render_html, render_json
from setup_trap.reporter.json_reporter import result_to_dict
from setup_trap.scanner.engine import scan_path
from setup_trap.simulator import is_available
from setup_trap.simulator.agent_sim import SimulationResult, _parse_behaviors

from .conftest import CLEAN, MALICIOUS


def test_json_reporter_shape():
    result = scan_path(MALICIOUS)
    payload = json.loads(render_json(result, path=str(MALICIOUS)))
    assert payload["tool"] == "setup-trap"
    assert payload["summary"]["total"] == len(result.findings)
    assert payload["findings"]
    for f in payload["findings"]:
        assert f["provenance"] in {"sourced", "synthesized", "inferred"}


def test_cli_reporter_shows_provenance_legend():
    result = scan_path(MALICIOUS)
    text = render_cli(result, path=str(MALICIOUS))
    assert "sourced" in text and "synthesized" in text
    assert "arXiv:2607.15143" in text


def test_html_reporter_is_selfcontained():
    result = scan_path(MALICIOUS)
    html = render_html(result, path=str(MALICIOUS))
    assert html.startswith("<!DOCTYPE html>")
    assert "Provenance" in html
    assert "<script" not in html  # no external/embedded JS


def test_result_to_dict_counts():
    result = scan_path(CLEAN)
    d = result_to_dict(result)
    assert d["summary"]["critical"] == 0
    assert d["summary"]["warning"] == 0


def test_cli_scan_exit_code_clean(capsys):
    rc = main(["scan", str(CLEAN)])
    assert rc == 0


def test_cli_scan_exit_code_malicious(capsys):
    rc = main(["scan", str(MALICIOUS)])
    assert rc == 1


def test_cli_scan_json_output(capsys):
    rc = main(["scan", str(MALICIOUS), "--format", "json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["summary"]["total"] > 0
    assert rc == 1


def test_cli_surface_json(capsys):
    rc = main(["surface", "--runtime", "openclaw", "--format", "json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["runtime"] == "openclaw"
    assert rc == 0


def test_cli_surface_unknown_runtime(capsys):
    rc = main(["surface", "--runtime", "nope"])
    assert rc == 2


def test_cli_audit_runs(capsys):
    rc = main(["audit", str(MALICIOUS), "--runtime", "openclaw"])
    assert rc == 1


def test_cli_fail_on_warning(capsys):
    # Clean corpus (INFO only) must pass even with --fail-on warning.
    rc = main(["scan", str(CLEAN), "--fail-on", "warning"])
    assert rc == 0


# -- simulator (no creds path) ---------------------------------------------


def test_simulator_degrades_without_boto3():
    if is_available():
        return  # environment has boto3; graceful-degradation path not exercised
    sim_res = SimulationResult(file="x", available=False, error="no boto3")
    assert not sim_res.available
    assert sim_res.to_dict()["advisory"] is True


def test_simulation_behavior_parsing():
    text = (
        'Here is the analysis:\n'
        '[{"behavior":"rewrites identity","rating":"MALICIOUS","reason":"x"},'
        '{"behavior":"reads build cmd","rating":"benign","reason":"y"}]'
    )
    behaviors = _parse_behaviors(text)
    assert len(behaviors) == 2
    assert behaviors[0].rating == "MALICIOUS"
    assert behaviors[1].rating == "BENIGN"  # normalized upper


def test_simulation_parsing_tolerates_garbage():
    assert _parse_behaviors("no json here") == []
