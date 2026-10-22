"""Unified programmatic grading per task set.

Truncated responses (stopReason == max_tokens) are graded WRONG and counted
separately in summaries.
"""

from dataclasses import dataclass, field

from .extractors import (
    extract_code,
    extract_letter,
    extract_math_answer,
    math_answers_equal,
    normalize_math_answer,
)


@dataclass
class GradeOutcome:
    extracted: str | None
    correct: bool
    details: dict = field(default_factory=dict)


def grade_gpqa(response_text: str, correct_letter: str, truncated: bool = False) -> GradeOutcome:
    letter = extract_letter(response_text)
    correct = (letter == correct_letter) and not truncated
    return GradeOutcome(letter, correct, {
        "correct_letter": correct_letter,
        "truncated": truncated,
    })


def grade_math(response_text: str, reference: str, truncated: bool = False) -> GradeOutcome:
    ans = extract_math_answer(response_text)
    correct = math_answers_equal(ans, reference) and not truncated
    return GradeOutcome(
        normalize_math_answer(ans) if ans is not None else None,
        correct,
        {"reference": normalize_math_answer(str(reference)), "truncated": truncated},
    )


def grade_code_response(response_text: str, item, truncated: bool = False,
                        timeout_s: float = 40) -> GradeOutcome:
    """Grade on PRIVATE tests only. Also runs public tests (selection signal)
    and reports both."""
    from grading.code_grader import grade_code

    code = extract_code(response_text)
    if truncated or code is None:
        return GradeOutcome(None, False, {
            "truncated": truncated,
            "reason": "truncated" if truncated else "no code extracted",
        })
    public = grade_code(code, item.public_tests, item.metadata,
                        timeout_s=timeout_s, stop_at_first_failure=False)
    private = grade_code(code, item.private_tests, item.metadata, timeout_s=timeout_s)
    return GradeOutcome(code, private.passed, {
        "public_pass": public.passed,
        "public_signature": public.output_signature(),
        "private_n_tests": private.n_tests,
        "private_n_passed": private.n_passed,
        "first_failure": private.first_failure,
        "truncated": truncated,
    })
