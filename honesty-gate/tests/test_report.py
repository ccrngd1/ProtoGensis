"""Report card layout rules: per-file table leads, coverage separate from
verdict, one verdict per run, blind-spot disclosure present."""

import json

from conftest import FILES, make_transcript

from honesty_gate.classify import classify_run
from honesty_gate.parse import claims as claims_mod
from honesty_gate.report import render, BLIND_SPOT_NOTE


def _run():
    cr = claims_mod.parse("I reviewed all 5 files. No issues.", FILES)
    return classify_run(FILES, FILES[:4], cr)


def test_table_is_lead_element_terminal():
    text = render(_run(), "terminal")
    lines = text.splitlines()
    # the per-file table header appears before coverage and verdict lines
    header_idx = next(i for i, l in enumerate(lines) if "class" in l and "claim" in l)
    coverage_idx = next(i for i, l in enumerate(lines) if l.startswith("Coverage:"))
    verdict_idx = next(i for i, l in enumerate(lines) if l.startswith("Honesty verdict:"))
    assert header_idx < coverage_idx < verdict_idx


def test_one_verdict_per_run_all_formats():
    run = _run()
    term = render(run, "terminal")
    assert term.count("Honesty verdict:") == 1
    md = render(run, "md")
    assert md.count("**Honesty verdict:**") == 1
    data = json.loads(render(run, "json"))
    assert data["honesty_verdict"] in ("PASS", "FAIL")


def test_coverage_and_verdict_are_separate_fields():
    data = json.loads(render(_run(), "json"))
    assert "coverage_pct" in data and "honesty_verdict" in data
    # coverage is a number, verdict a categorical — never merged
    assert isinstance(data["coverage_pct"], float)
    assert isinstance(data["honesty_verdict"], str)


def test_blind_spot_disclosed_in_every_format():
    run = _run()
    for fmt in ("terminal", "md"):
        assert "bash" in render(run, fmt).lower()
    data = json.loads(render(run, "json"))
    assert data["blind_spot"] == BLIND_SPOT_NOTE
    assert "strace" in BLIND_SPOT_NOTE


def test_json_evidence_spans_present():
    data = json.loads(render(_run(), "json"))
    false_claims = [f for f in data["files"] if f["honesty_class"] == "FALSE_CLAIM"]
    assert false_claims and all(f["claim_evidence"] for f in false_claims)


def test_unknown_format_raises():
    import pytest
    with pytest.raises(ValueError):
        render(_run(), "xml")
