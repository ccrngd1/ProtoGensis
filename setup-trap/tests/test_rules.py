"""Rule regression tests (NFR4).

Guarantees:
  * every starter rule fires on the malicious corpus,
  * no rule fires above INFO on the clean corpus (no false positives),
  * the provenance honesty gate holds (sourced rules cite a source_ref;
    the sourced set is exactly the package-install class).
"""

from __future__ import annotations

import pytest

from setup_trap.model import Provenance, Severity
from setup_trap.scanner.engine import scan_path
from setup_trap.scanner.loader import load_rules

from .conftest import CLEAN, MALICIOUS

ALL_RULES = load_rules()
ALL_RULE_IDS = sorted(r.id for r in ALL_RULES)

# Rule IDs that are legitimately allowed to be SOURCED. Everything else must be
# synthesized or inferred (the honesty gate). TOOL-001..003 detect the paper's
# redirection class as a config directive; COND-004 is the CVE-pin (V5).
SOURCED_YAML_IDS = {"TOOL-001", "TOOL-002", "TOOL-003", "COND-004"}


@pytest.fixture(scope="module")
def malicious_result():
    return scan_path(MALICIOUS)


@pytest.fixture(scope="module")
def clean_result():
    return scan_path(CLEAN)


def test_expected_rule_count():
    assert len(ALL_RULES) == 25, "brief specifies 25 starter rules"


def test_five_categories_five_rules_each():
    from collections import Counter

    counts = Counter(r.category for r in ALL_RULES)
    assert set(counts) == {
        "identity",
        "exfiltration",
        "tool-binding",
        "memory-hooks",
        "conditional",
    }
    assert all(c == 5 for c in counts.values()), counts


@pytest.mark.parametrize("rule_id", ALL_RULE_IDS)
def test_every_rule_fires_on_malicious(malicious_result, rule_id):
    fired = {f.rule_id for f in malicious_result.findings}
    assert rule_id in fired, f"rule {rule_id} did not fire on any malicious fixture"


def test_clean_corpus_has_no_critical_or_warning(clean_result):
    offenders = [
        (f.rule_id, f.file, f.matched_text)
        for f in clean_result.findings
        if f.severity >= Severity.WARNING
    ]
    assert offenders == [], f"false positives on clean corpus: {offenders}"


def test_clean_corpus_pytorch_index_is_info(clean_result):
    # The legit PyTorch --extra-index-url must be recognized (INFO), not Critical.
    pre_src = [f for f in clean_result.findings if f.rule_id == "PRE-SRC"]
    assert pre_src, "expected the PyTorch extra-index-url to be surfaced as INFO"
    assert all(f.severity is Severity.INFO for f in pre_src)


# -- provenance honesty gate ------------------------------------------------


@pytest.mark.parametrize("rule", ALL_RULES, ids=[r.id for r in ALL_RULES])
def test_sourced_rules_cite_a_source(rule):
    if rule.provenance is Provenance.SOURCED:
        assert rule.source_ref, f"{rule.id}: sourced rule must carry a source_ref"
        assert "2607.15143" in rule.source_ref, (
            f"{rule.id}: sourced rule must cite the paper"
        )


def test_only_expected_rules_are_sourced():
    sourced = {r.id for r in ALL_RULES if r.provenance is Provenance.SOURCED}
    assert sourced == SOURCED_YAML_IDS, (
        "the sourced YAML set must be exactly the package-install class; "
        f"got {sorted(sourced)}"
    )


def test_synthesized_rules_do_not_claim_paper_proof():
    # A synthesized rule may REFERENCE the paper's class, but its source_ref must
    # make clear it was not evaluated / is a synthesized framing.
    for r in ALL_RULES:
        if r.provenance is Provenance.SYNTHESIZED and r.source_ref and "2607.15143" in r.source_ref:
            assert (
                "not evaluated" in r.source_ref.lower()
                or "synthesized" in r.source_ref.lower()
            ), f"{r.id}: synthesized rule must not present the paper as proof"
