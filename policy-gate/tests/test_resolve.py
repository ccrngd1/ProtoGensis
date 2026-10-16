"""RESOLVE tests: one firing + one passing fixture per class a-h (AC #7)."""

import json
from pathlib import Path

import pytest

from policygate import resolve

CASES = json.loads((Path(__file__).parent.parent / "fixtures" / "resolve" / "cases.json").read_text())["classes"]


def _as_list(x):
    return x if isinstance(x, list) else [x]


def _outcomes(cands):
    _, report = resolve.resolve(cands)
    return report


@pytest.mark.parametrize("cls", list(CASES))
def test_firing_fixture(cls):
    firing = _as_list(CASES[cls]["firing"])
    report = _outcomes(firing)
    classes_fired = {r["class"] for r in report}
    assert cls in classes_fired, f"class {cls} did not fire: {report}"


@pytest.mark.parametrize("cls", [c for c in CASES if c not in ("contradiction", "subject-scope", "shadowing")])
def test_passing_fixture_clean(cls):
    passing = _as_list(CASES[cls]["passing"])
    report = _outcomes(passing)
    assert cls not in {r["class"] for r in report}, f"passing fixture for {cls} wrongly fired: {report}"


def test_contradiction_passing_no_conflict():
    report = _outcomes(_as_list(CASES["contradiction"]["passing"]))
    assert not any(r["outcome"] == "CONFLICT" for r in report)


def test_subject_scope_passing_decided():
    report = _outcomes(_as_list(CASES["subject-scope"]["passing"]))
    assert not any(r["outcome"] == "SUBJECT_UNDECIDED" for r in report)


def test_shadowing_passing_single_rule():
    report = _outcomes(_as_list(CASES["shadowing"]["passing"]))
    assert not any(r["class"] == "shadowing" for r in report)


def test_read_gate_predicate_not_write_scoped():
    # channel_shared is a read-gate: write-scope repair must leave it alone (AC #7a)
    cand = [{"id": "RG", "polarity": "block_until_true", "predicate": "channel_shared",
             "params": {}, "tools": ["file.read", "file.edit"], "subjects": ["agent:x"],
             "src": {"file": "x.md"}}]
    report = _outcomes(cand)
    assert not any(r["class"] == "write-scope" for r in report)


def test_call_field_reads_not_argument_signature_unbound():
    # quiet_hours_utc reads the call timestamp, not a vtool argument: it is
    # signature-compatible with every vtool and must survive RESOLVE (b)
    cand = [{"id": "QH", "polarity": "block_when_true", "predicate": "quiet_hours_utc",
             "params": {"start": 0, "end": 8},
             "tools": ["gateway.restart", "cron.edit", "config.set"],
             "subjects": ["agent:x"], "src": {"file": "x.md"}}]
    kept, report = resolve.resolve(cand)
    assert not any(r["class"] in ("argument-signature", "no-operable-tool")
                   for r in report)
    assert kept and sorted(kept[0]["tools"]) == ["config.set", "cron.edit",
                                                 "gateway.restart"]


def test_explicit_type_rejected():
    cand = [{"id": "T", "type": "FORBIDDEN", "polarity": "block_when_true",
             "predicate": "weakens_policy", "params": {}, "tools": ["file.edit"],
             "subjects": ["agent:x"]}]
    report = _outcomes(cand)
    assert any(r["outcome"] == "REJECT" and r["class"] == "type-not-derivable" for r in report)


def test_spike2_resolve_block():
    """demo feb19 reproduces spike 2's RESOLVE block (AC #7)."""
    from policygate import demos
    out = demos.feb19_data()
    triples = [[r["id"], r["outcome"], r["class"]] for r in out["resolve"]]
    assert triples == [
        ["TWR-PRE-01", "REPAIR", "write-scope"],
        ["TWR-FBD-02", "REPAIR", "argument-signature"],
        ["TWR-PRE-04", "REJECT", "unscoped-wildcard"],
    ]
