"""AC #6 health gate, AC #7 oracle flags, AC #8/#9 scorer + cause codes."""

from memdoc.health import arm_invalid_rates, cell_validity, gate_headline, storyline_flags
from memdoc.scorer import assign_cause, is_visible, score_abstention, score_compliance, score_probe, score_recall


def _cell(arm="a4", **kw):
    base = {"arm": arm, "size": 25000, "seed": 0, "storyline": "c1s0",
            "embedding_calls": 5, "retrieval_hits": 3, "catalog_nonempty": True,
            "transcript_count": 2, "core_loaded": True,
            "tools_registered": ["memory_search", "grep"]}
    base.update(kw)
    return base


def test_dead_embedder_is_invalid_not_fail():
    status, reason = cell_validity(_cell(embedding_calls=0))
    assert status == "INVALID" and "embedding" in reason


def test_empty_index_invalid():
    status, reason = cell_validity(_cell(retrieval_hits=0))
    assert status == "INVALID" and "retrieval" in reason


def test_empty_catalog_invalid():
    status, _ = cell_validity(_cell(arm="a2", catalog_nonempty=False))
    assert status == "INVALID"


def test_a6_needs_transcripts_and_grep():
    assert cell_validity(_cell(arm="a6", transcript_count=0))[0] == "INVALID"
    assert cell_validity(_cell(arm="a6", tools_registered=["read"]))[0] == "INVALID"
    assert cell_validity(_cell(arm="a6"))[0] == "VALID"


def test_invalid_counted_never_failed():
    cells = [_cell(), _cell(embedding_calls=0)]
    rates = arm_invalid_rates(cells)
    assert rates["a4"]["invalid"] == 1 and rates["a4"]["total"] == 2


def test_gate_refuses_over_5pct():
    cells = [_cell() for _ in range(18)] + [_cell(embedding_calls=0), _cell(embedding_calls=0)]
    ok, _ = gate_headline(cells)
    assert not ok  # 2/20 = 10% invalid
    ok2, _ = gate_headline([_cell() for _ in range(100)])
    assert ok2


def test_broken_and_non_separating_flags():
    def probes(arm, story, rate, n=10):
        return [{"arm": arm, "storyline": story, "applied": i < int(rate * n)}
                for i in range(n)]
    # oracle fails -> BROKEN
    ps = probes("astar", "s_broken", 0.5) + probes("a1", "s_broken", 0.4)
    assert storyline_flags(ps)["s_broken"] == "BROKEN"
    # everyone ties the oracle -> NON_SEPARATING
    ps = probes("astar", "s_tie", 1.0) + probes("a1", "s_tie", 1.0) + probes("a4", "s_tie", 1.0)
    assert storyline_flags(ps)["s_tie"] == "NON_SEPARATING"
    # normal separation -> OK
    ps = probes("astar", "s_ok", 1.0) + probes("a1", "s_ok", 0.8) + probes("a4", "s_ok", 0.5)
    assert storyline_flags(ps)["s_ok"] == "OK"


# ----------------------------------------------------------------- scorer

def test_recall_exact_match():
    assert score_recall("19222", "19222")
    assert score_recall("  19222 ", "19222")
    assert not score_recall("19223", "19222")
    assert not score_recall("port 19222", "19222")  # exact, not containment


def test_abstention_pass_and_fail():
    assert score_abstention("ABSTAIN")
    assert not score_abstention("The code is XK-1234")
    assert not score_abstention("ABSTAIN but maybe XK-1234", near_miss_canary="XK-1234")


def test_compliance_rules():
    assert score_compliance("A clean prose paragraph.", "prose_no_bullets")
    assert not score_compliance("- a bullet", "prose_no_bullets")
    assert score_compliance("Due 05-Mar.", "date_format_dd_mon")
    assert not score_compliance("Due 2026-03-05.", "date_format_dd_mon")


def _rec(**kw):
    base = {"gold": "19222", "answer": "19222", "stale": "18111", "kind": "recall",
            "gold_in_store": True, "stale_stored_current": False,
            "fact_in_context": True, "stale_in_context": False,
            "read_policy": "similarity"}
    base.update(kw)
    return base


def test_stale_answer_separate_from_miss():
    s = score_probe(_rec(answer="18111"))
    assert not s["applied"] and s["stale_answer"]
    s2 = score_probe(_rec(answer="ABSTAIN"))
    assert not s2["applied"] and not s2["stale_answer"] and s2["abstained"]


# one hand-built example per cause code (AC #9)

def test_cause_write_miss():
    r = _rec(answer="ABSTAIN", gold_in_store=False, fact_in_context=False)
    assert assign_cause(r) == "write_miss"
    assert is_visible("write_miss")


def test_cause_stale_in_store():
    r = _rec(answer="18111", stale_stored_current=True, fact_in_context=False)
    assert assign_cause(r) == "stale_in_store"
    assert is_visible("stale_in_store")


def test_cause_retrieval_miss():
    r = _rec(answer="ABSTAIN", fact_in_context=False)
    assert assign_cause(r) == "retrieval_miss"
    assert not is_visible("retrieval_miss")


def test_cause_catalog_miss():
    r = _rec(answer="ABSTAIN", fact_in_context=False, read_policy="catalog")
    assert assign_cause(r) == "catalog_miss"
    assert not is_visible("catalog_miss")


def test_cause_rank_stale():
    r = _rec(answer="18111", stale_in_context=True)
    assert assign_cause(r) == "rank_stale"
    assert not is_visible("rank_stale")


def test_cause_applied_wrong():
    r = _rec(answer="55555")
    assert assign_cause(r) == "applied_wrong"
    assert not is_visible("applied_wrong")
