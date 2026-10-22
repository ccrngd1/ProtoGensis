"""Graders: GPQA/math (incl. truncation = wrong), code grading via sandbox."""

from ensemble_reboot.grading_api import grade_gpqa, grade_math
from grading.code_grader import grade_code


def test_grade_gpqa_correct():
    out = grade_gpqa("Reasoning...\nAnswer: C", "C")
    assert out.correct and out.extracted == "C"


def test_grade_gpqa_wrong():
    out = grade_gpqa("Answer: B", "C")
    assert not out.correct and out.extracted == "B"


def test_truncated_graded_wrong_and_flagged():
    out = grade_gpqa("Answer: C", "C", truncated=True)
    assert not out.correct
    assert out.details["truncated"]
    out = grade_math("\\boxed{42}", "42", truncated=True)
    assert not out.correct
    assert out.details["truncated"]


def test_grade_math_normalized_equality():
    out = grade_math("The answer is \\boxed{\\frac{2}{4}}", "1/2")
    assert out.correct and out.extracted == "1/2"


def test_grade_math_no_answer():
    out = grade_math("I give up.", "42")
    assert not out.correct and out.extracted is None


# ----------------------------------------------------------------- code grading

STDIN_TESTS = [
    {"testtype": "stdin", "input": "2 3\n", "output": "5\n"},
    {"testtype": "stdin", "input": "10 -4\n", "output": "6\n"},
]

GOOD_CODE = "a, b = map(int, input().split())\nprint(a + b)"
BAD_CODE = "a, b = map(int, input().split())\nprint(a - b)"


def test_grade_code_stdin_pass():
    r = grade_code(GOOD_CODE, STDIN_TESTS)
    assert r.passed and r.n_passed == 2


def test_grade_code_stdin_fail_stops_early():
    r = grade_code(BAD_CODE, STDIN_TESTS)
    assert not r.passed
    assert r.n_tests == 1  # stopped at first failure
    assert r.first_failure["test_index"] == 0


def test_grade_code_signature_covers_all_tests_when_not_stopping():
    r_all = grade_code(BAD_CODE, STDIN_TESTS, stop_at_first_failure=False)
    assert r_all.n_tests == 2
    # same wrong code -> same signature (stable for majority tie-breaking)
    r_again = grade_code(BAD_CODE, STDIN_TESTS, stop_at_first_failure=False)
    assert r_all.output_signature() == r_again.output_signature()
    # different behavior -> different signature
    r_good = grade_code(GOOD_CODE, STDIN_TESTS, stop_at_first_failure=False)
    assert r_good.output_signature() != r_all.output_signature()


def test_grade_code_functional():
    # LCB convention: one JSON-encoded argument per input line
    tests = [{"testtype": "functional", "input": "2\n3", "output": "5"}]
    code = "class Solution:\n    def add(self, a, b):\n        return a + b"
    r = grade_code(code, tests, metadata={"func_name": "add"})
    assert r.passed


def test_grade_code_no_code():
    r = grade_code(None, STDIN_TESTS)
    assert not r.passed and r.n_tests == 0
