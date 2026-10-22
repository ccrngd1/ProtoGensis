"""Rule-4 checks (incl. the A4b exemption label), majority vote, code
selection, arm cost chaining with UNKNOWN propagation."""

import pytest

from ensemble_reboot.arms import (
    Proposal,
    arm_cost_usd,
    build_aggregator_prompt,
    majority_vote,
    select_code_response,
)
from ensemble_reboot.rules import Rule4FamilyViolation, check_rule4

PANEL = [
    ("global.openai.gpt-6.1-sol", "openai"),
    ("global.xai.grok-4.7", "xai"),
    ("global.moonshotai.kimi-k3", "moonshot"),
]


# ---------------------------------------------------------------------- rule 4


def test_rule4a_family_on_panel_is_hard_error():
    with pytest.raises(Rule4FamilyViolation):
        check_rule4("global.openai.gpt-6-astra", "openai", PANEL)


def test_rule4b_pass():
    acc = {
        "global.anthropic.claude-fable-5-1": (0.9, 0.80, 0.95),
        "global.openai.gpt-6.1-sol": (0.8, 0.70, 0.88),
        "global.xai.grok-4.7": (0.7, 0.60, 0.80),
        "global.moonshotai.kimi-k3": (0.75, 0.65, 0.83),
    }
    res = check_rule4("global.anthropic.claude-fable-5-1", "anthropic", PANEL,
                      accuracies=acc, task_set="gpqa")
    assert res.ok
    assert not res.exempt_from_b
    assert res.label == "rule-4 checked"
    # overlapping CIs are noted, not fatal
    assert any("overlaps" in n for n in res.ci_overlap_notes)


def test_rule4b_fail_when_aggregator_below_panel_member():
    acc = {
        "global.anthropic.claude-fable-5-1": (0.6, 0.5, 0.7),
        "global.openai.gpt-6.1-sol": (0.8, 0.7, 0.88),
        "global.xai.grok-4.7": (0.5, 0.4, 0.6),
        "global.moonshotai.kimi-k3": (0.5, 0.4, 0.6),
    }
    res = check_rule4("global.anthropic.claude-fable-5-1", "anthropic", PANEL,
                      accuracies=acc, task_set="gpqa")
    assert not res.ok


def test_rule4_a4b_exemption_is_labeled():
    acc = {
        "global.anthropic.claude-haiku-5-5": (0.4, 0.3, 0.5),
        "global.openai.gpt-6.1-sol": (0.8, 0.7, 0.88),
        "global.xai.grok-4.7": (0.7, 0.6, 0.8),
        "global.moonshotai.kimi-k3": (0.75, 0.65, 0.83),
    }
    res = check_rule4("global.anthropic.claude-haiku-5-5", "anthropic", PANEL,
                      accuracies=acc, task_set="gpqa", exempt_from_b=True)
    # weaker than every panel member, yet ok BY DESIGN - and labeled
    assert res.ok
    assert res.exempt_from_b
    assert "WEAK-BY-DESIGN" in res.label
    assert "exempt from rule-4(b)" in res.label


def test_rule4a_still_enforced_for_a4b():
    with pytest.raises(Rule4FamilyViolation):
        check_rule4("global.xai.grok-4.7", "xai", PANEL, exempt_from_b=True)


# -------------------------------------------------------------- majority vote


def P(rid, ans, **kw):
    return Proposal(record_id=rid, model_id=f"m{rid}", extracted_answer=ans, **kw)


def test_majority_vote_simple():
    winner, d = majority_vote([P("1", "A"), P("2", "B"), P("3", "A")])
    assert winner == "A"
    assert d["votes"] == {"A": 2, "B": 1}
    assert not d["tie"]


def test_majority_vote_tie_breaks_to_earliest():
    winner, d = majority_vote([P("1", "B"), P("2", "A"), P("3", "B"), P("4", "A")])
    assert winner == "B"
    assert d["tie"]


def test_majority_vote_nones_do_not_vote():
    winner, d = majority_vote([P("1", None), P("2", "C"), P("3", None)])
    assert winner == "C"
    assert d["n_voted"] == 1


def test_majority_vote_all_none():
    winner, d = majority_vote([P("1", None), P("2", None)])
    assert winner is None


# ------------------------------------------------------------- code selection


def CP(rid, code, public_pass, sig):
    return Proposal(record_id=rid, model_id=f"m{rid}", extracted_answer=code,
                    public_pass=public_pass, output_signature=sig)


def test_code_first_passing_selected():
    sel, d = select_code_response([
        CP("1", "bad", False, "sigX"),
        CP("2", "good", True, "sigA"),
        CP("3", "also", True, "sigB"),
    ])
    assert sel.record_id == "2"
    assert d["n_passers"] == 2


def test_code_signature_majority_tie_break():
    sel, d = select_code_response([
        CP("1", "v1", True, "sigB"),
        CP("2", "v2", True, "sigA"),
        CP("3", "v3", True, "sigA"),
    ])
    assert sel.record_id == "2"  # first proposal carrying the majority signature
    assert d["strategy"] == "signature-majority"


def test_code_no_passers_falls_back():
    sel, d = select_code_response([
        CP("1", "v1", False, "s1"),
        CP("2", "v2", False, "s1"),
        CP("3", "v3", False, "s2"),
    ])
    assert sel.record_id == "1"
    assert d["n_passers"] == 0


def test_code_nothing_extractable():
    sel, d = select_code_response([
        Proposal(record_id="1", model_id="m", extracted_answer=None),
    ])
    assert sel is None


# ----------------------------------------------------------------- arm cost


def test_arm_cost_sums_parents_plus_aggregator():
    assert arm_cost_usd([0.10, 0.20, 0.05], 0.15) == pytest.approx(0.50)


def test_arm_cost_unknown_parent_propagates():
    assert arm_cost_usd([0.10, None, 0.05], 0.15) is None


def test_arm_cost_unknown_aggregator_propagates():
    assert arm_cost_usd([0.10, 0.20], None) is None


def test_arm_cost_programmatic_vote_is_free():
    assert arm_cost_usd([0.10, 0.20]) == pytest.approx(0.30)


# ------------------------------------------------------- aggregator prompting


def test_aggregator_prompt_contains_problem_and_responses():
    props = [
        Proposal(record_id="1", model_id="a", extracted_answer="A",
                 response_text="I think A because..."),
        Proposal(record_id="2", model_id="b", extracted_answer="B",
                 response_text="Clearly B."),
    ]
    prompt = build_aggregator_prompt("gpqa", "Which is heavier?", props)
    assert "Which is heavier?" in prompt
    assert "I think A because..." in prompt
    assert "Clearly B." in prompt
    assert 'Answer: X' in prompt  # required output format


def test_aggregator_prompt_math_format():
    prompt = build_aggregator_prompt("math", "1+1?", [])
    assert "\\boxed{}" in prompt
