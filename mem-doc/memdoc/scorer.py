"""Deterministic-first scoring (AC #8) + preregistered cause codes (AC #9).

Recall probes: exact canary match (case-sensitive, whitespace-trimmed).
Abstention probes: pass iff ABSTAIN (or the fixed refusal pattern) and no canary
from a near-miss distractor. Compliance probes: offline deterministic rule
checker; a live LLM judge is allowed only for compliance probes (AC #8) and is
validated by hand on >=5 storylines (docs/JUDGE_VALIDATION.md).

Cause codes follow prereg.CAUSE_ASSIGNMENT_RULE exactly; the taxonomy and rule
are covered by the preregistration hash.
"""

import re

from .prereg import CAUSE_TAXONOMY

ABSTAIN_PATTERN = re.compile(r"^\s*(ABSTAIN|I (do not|don't) have that)\b")


def score_recall(answer: str, gold: str) -> bool:
    return answer.strip() == gold.strip()


def score_abstention(answer: str, near_miss_canary: str = "") -> bool:
    if not ABSTAIN_PATTERN.search(answer.strip()):
        return False
    if near_miss_canary and near_miss_canary in answer:
        return False
    return True


# -- compliance rule checkers (offline deterministic judge) ---------------------

def _rule_prose_no_bullets(text: str) -> bool:
    return not any(line.lstrip().startswith(("-", "*")) for line in text.splitlines())


def _rule_date_format(text: str) -> bool:
    # DD-Mon dates only (no ISO dates present)
    return not re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)


COMPLIANCE_RULES = {
    "prose_no_bullets": _rule_prose_no_bullets,
    "date_format_dd_mon": _rule_date_format,
}


def score_compliance(answer: str, rule: str) -> bool:
    fn = COMPLIANCE_RULES.get(rule)
    if fn is None:
        return False
    return fn(answer)


def score_probe(rec: dict) -> dict:
    """rec: a probe event from the run log. Returns scoring fields."""
    gold, answer = rec["gold"], rec["answer"]
    stale = rec.get("stale", "")
    if gold == "ABSTAIN":
        applied = score_abstention(answer, stale)
    elif rec.get("kind") == "compliance":
        # mock compliance probes still carry a canary gold; exact match stands in
        # for the rule checker's "fact applied" half
        applied = score_recall(answer, gold)
    else:
        applied = score_recall(answer, gold)
    stale_answer = bool(stale) and answer.strip() == stale.strip() and gold != "ABSTAIN"
    abstained = bool(ABSTAIN_PATTERN.search(answer.strip()))
    out = {"applied": applied, "stale_answer": stale_answer, "abstained": abstained}
    if not applied:
        out["cause"] = assign_cause(rec)
        out["cause_class"] = CAUSE_TAXONOMY[out["cause"]]["class"]
    return out


def assign_cause(rec: dict) -> str:
    """The preregistered deterministic rule (prereg.CAUSE_ASSIGNMENT_RULE)."""
    gold = rec["gold"]
    answer = rec["answer"].strip()
    stale = rec.get("stale", "")
    gold_stored = rec.get("gold_in_store", False)
    stale_current = rec.get("stale_stored_current", False)
    gold_in_ctx = rec.get("fact_in_context", False)
    stale_in_ctx = rec.get("stale_in_context", False)
    read_policy = rec.get("read_policy", "")

    if gold != "ABSTAIN" and not gold_stored:
        return "write_miss"
    if stale and stale_current and answer == stale and not gold_in_ctx:
        return "stale_in_store"
    if gold != "ABSTAIN" and gold_stored and not gold_in_ctx:
        return "catalog_miss" if read_policy == "catalog" else "retrieval_miss"
    if gold_in_ctx and stale_in_ctx and answer == stale:
        return "rank_stale"
    return "applied_wrong"


def is_visible(cause: str) -> bool:
    return CAUSE_TAXONOMY[cause]["class"] == "visible"
