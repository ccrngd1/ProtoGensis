"""Answer extractors: GPQA letter, math boxed/final-answer, code fences."""

import pytest

from ensemble_reboot.extractors import (
    extract_boxed,
    extract_code,
    extract_letter,
    extract_math_answer,
    is_single_exact_answer,
    math_answers_equal,
    normalize_math_answer,
)

# ---------------------------------------------------------------- GPQA letter


@pytest.mark.parametrize("text,expected", [
    ("Answer: C", "C"),
    ("The final answer is (B).", "B"),
    ("answer: d", "D"),
    ("Long reasoning...\n\nAnswer: A", "A"),
    ("I considered A and B, but Answer: B", "B"),
    ("\\boxed{C}", "C"),
    ("\\boxed{(D)}", "D"),
    ("blah blah\n(C)", "C"),
    ("blah blah\nC.", "C"),
    ("no letter anywhere", None),
    ("", None),
    (None, None),
])
def test_extract_letter(text, expected):
    assert extract_letter(text) == expected


def test_extract_letter_takes_last_marker():
    text = "Answer: A\nWait, reconsidering...\nFinal answer: C"
    assert extract_letter(text) == "C"


# ---------------------------------------------------------------- math answer


@pytest.mark.parametrize("text,expected", [
    ("Thus \\boxed{42}.", "42"),
    ("\\boxed{\\frac{3}{7}}", "\\frac{3}{7}"),
    ("first \\boxed{1} then \\boxed{204}", "204"),
    ("\\boxed{x^{2}+1}", "x^{2}+1"),  # nested braces balanced
    ("Final answer: 117", "117"),
    ("final answer: -5.", "-5"),
    ("Final Answer: $36$", "36"),
    ("no answer here", None),
    ("", None),
])
def test_extract_math_answer(text, expected):
    assert extract_math_answer(text) == expected


def test_boxed_beats_final_answer_line():
    assert extract_math_answer("Final answer: 1\n\\boxed{2}") == "2"


def test_extract_boxed_unterminated():
    assert extract_boxed("\\boxed{42") is None


@pytest.mark.parametrize("raw,norm", [
    ("42", "42"),
    (" 042 ", "42"),
    ("1,000", "1000"),
    ("-17", "-17"),
    ("\\frac{3}{6}", "1/2"),
    ("\\dfrac{10}{5}", "2"),
    ("-\\frac{1}{2}", "-1/2"),
    ("6/8", "3/4"),
    ("0.25", "1/4"),
    ("$100$", "100"),
    ("1/0", None),
    ("", None),
    (None, None),
])
def test_normalize_math_answer(raw, norm):
    assert normalize_math_answer(raw) == norm


@pytest.mark.parametrize("a,b,eq", [
    ("042", "42", True),
    ("\\frac{1}{2}", "0.5", True),
    ("2/4", "1/2", True),
    ("41", "42", False),
    (None, "42", False),
])
def test_math_answers_equal(a, b, eq):
    assert math_answers_equal(a, b) is eq


@pytest.mark.parametrize("ref,keep", [
    ("204", True),
    ("3/7", True),
    ("0.125", True),          # exact fraction 1/8
    ("\\sqrt{2}", False),     # not a single exact rational
    ("x=1 or x=2", False),
])
def test_is_single_exact_answer(ref, keep):
    assert is_single_exact_answer(ref) is keep


# ------------------------------------------------------------------ code fence


def test_extract_code_last_fence():
    text = (
        "First try:\n```python\nprint(1)\n```\n"
        "Actually the final solution:\n```python\nprint(2)\n```"
    )
    assert extract_code(text) == "print(2)"


def test_extract_code_plain_fence_and_py():
    assert extract_code("```\nx = 1\n```") == "x = 1"
    assert extract_code("```py\nx = 2\n```") == "x = 2"


def test_extract_code_bare_code_fallback():
    assert extract_code("import sys\nprint(sys.argv)") == "import sys\nprint(sys.argv)"


def test_extract_code_none_for_prose():
    assert extract_code("I cannot solve this problem.") is None
