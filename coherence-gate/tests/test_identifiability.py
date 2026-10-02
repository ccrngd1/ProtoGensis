"""Identifiability audit tests (AC #6). The byte-equality test is first:
R2 says the generator leaking the answer is the main risk."""
import pytest

from coherencegate.audit.identifiability import (
    audit, evaluate_all_truths, generate_family, prompt_sha256, render_prompt,
)


@pytest.fixture(scope="module")
def family():
    return generate_family(n_tasks=40, seed=0)


def test_aliased_prompts_byte_identical_across_truths(family):
    """R2 guard: for every task, the aliased prompt has equal sha256 for all
    3 truths (aliasing is exact by construction)."""
    for task in family:
        hashes = {prompt_sha256(task, truth, "aliased") for truth in (0, 1, 2)}
        assert len(hashes) == 1, f"task {task.task_id} leaks the truth"


def test_identifiable_prompts_differ_across_truths(family):
    for task in family:
        hashes = {prompt_sha256(task, truth, "identifiable") for truth in (0, 1, 2)}
        assert len(hashes) == 3


def test_every_mock_arm_exactly_40_of_120_on_aliased(family):
    """All-truths evaluation (40 tasks x 3 truths): every deterministic arm
    on the aliased variant scores exactly 40/120 (the 1/k bound, exact)."""
    for arm in ("competent", "planner_verifier", "majority5", "blind_tool"):
        result = evaluate_all_truths(family, "aliased", arm)
        assert (result["correct"], result["total"]) == (40, 120), result


def test_fact_and_reading_tool_restore_full_score(family):
    assert evaluate_all_truths(family, "fact", "competent")["correct"] == 120
    assert evaluate_all_truths(family, "aliased", "reading_tool")["correct"] == 120
    assert evaluate_all_truths(family, "identifiable", "competent")["correct"] == 120


def test_audit_reports_k3_bound_one_third_on_aliased(family):
    result = audit(family, "aliased")
    assert result.identifiable is False
    assert result.max_k == 3
    assert result.worst_bound == pytest.approx(1 / 3)
    assert result.aliased_fibers == 40
    assert all(f.k == 3 and f.intersection_empty for f in result.fibers)


def test_audit_identifiable_on_fact_and_identifiable_variants(family):
    for variant in ("identifiable", "fact"):
        result = audit(family, variant)
        assert result.identifiable is True
        assert result.max_k == 1
        assert result.worst_bound == 1.0


def test_generator_deterministic():
    a = generate_family(n_tasks=5, seed=0)
    b = generate_family(n_tasks=5, seed=0)
    for ta, tb in zip(a, b):
        assert ta.events == tb.events
        assert ta.final_events == tb.final_events
        assert ta.heads == tb.heads


def test_prompt_has_60_events(family):
    text = render_prompt(family[0], 0, "identifiable")
    assert sum(1 for line in text.splitlines() if line[:1] == "e" and ":" in line[:5]) == 60
