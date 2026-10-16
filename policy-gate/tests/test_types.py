"""derive_type table + type-not-derivable rejection (AC #5)."""

import pytest

from policygate import rules


def test_derive_type_table():
    assert rules.derive_type("block_when_true") == "FORBIDDEN"
    assert rules.derive_type("block_until_true") == "PRECONDITION"


def test_unknown_polarity():
    with pytest.raises(rules.RuleError):
        rules.derive_type("maybe")


def test_explicit_type_rejected():
    with pytest.raises(rules.RuleError):
        rules.candidate_to_rule({"id": "x", "type": "FORBIDDEN", "polarity": "block_when_true",
                                 "predicate": "weakens_policy", "tools": ["file.edit"]})


def test_candidate_to_rule_ok():
    r = rules.candidate_to_rule({"id": "x", "polarity": "block_until_true",
                                 "predicate": "cc_authorized", "tools": ["cron.disable"]})
    assert r["type"] == "PRECONDITION"
    assert r["origin"] == "builder"
