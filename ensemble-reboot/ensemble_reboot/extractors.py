"""Answer extractors for programmatic grading.

- GPQA: exact letter extraction (A-D).
- Math: \\boxed{...} first, then an explicit "Final answer:" line; normalize to
  an exact string (integer or exactly-normalizable rational/radical left as-is).
- Code: last fenced python block (``` or ```python).
"""

import re
from fractions import Fraction

# ---------------------------------------------------------------- GPQA letter

_LETTER_PATTERNS = [
    # "Answer: C", "Final answer: (C)", "The correct answer is C."
    re.compile(r"(?:final\s+answer|answer)\s*(?:is)?\s*[:\-]?\s*\(?([A-D])\)?(?:\W|$)", re.I),
    re.compile(r"\\boxed\{\(?([A-D])\)?\}"),
]


def extract_letter(text: str) -> str | None:
    """Extract a multiple-choice letter A-D. Prefers explicit 'answer' markers
    scanning from the end; falls back to a lone trailing letter."""
    if not text:
        return None
    for pat in _LETTER_PATTERNS:
        matches = pat.findall(text)
        if matches:
            return matches[-1].upper()
    # Lone letter on the last non-empty line, e.g. "C" or "(C)"
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        m = re.fullmatch(r"\(?([A-D])\)?[.)]?", line)
        if m:
            return m.group(1).upper()
        break
    return None


# ---------------------------------------------------------------- math answer

_BOXED = re.compile(r"\\boxed\s*\{")
_FINAL_LINE = re.compile(r"final\s+answer\s*[:\-]?\s*(.+)", re.I)


def _balanced_braces(text: str, start: int) -> str | None:
    """text[start] must be '{'; return the contents of the balanced group."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return None


def extract_boxed(text: str) -> str | None:
    """Contents of the LAST \\boxed{...}, handling nested braces."""
    last = None
    for m in _BOXED.finditer(text):
        inner = _balanced_braces(text, m.end() - 1)
        if inner is not None:
            last = inner
    return last


def extract_math_answer(text: str) -> str | None:
    """\\boxed{} first; otherwise the last explicit 'Final answer:' line."""
    if not text:
        return None
    boxed = extract_boxed(text)
    if boxed is not None:
        return boxed.strip()
    finals = _FINAL_LINE.findall(text)
    if finals:
        ans = finals[-1].strip()
        # Strip trailing sentence punctuation but keep math like 2^10 or -1/21
        ans = ans.rstrip(". ").strip("$ ")
        return ans or None
    return None


def normalize_math_answer(ans: str) -> str | None:
    """Normalize to a canonical exact string, or None if not exactly
    normalizable. Integers -> canonical int; p/q and \\frac{p}{q} -> reduced
    fraction (integers when q divides p); everything else -> cleaned string
    (compared verbatim), or None when empty."""
    if ans is None:
        return None
    s = ans.strip().strip("$").strip()
    s = s.replace("\\left", "").replace("\\right", "").replace(" ", "")
    s = s.replace(",", "")  # 1,000 -> 1000
    if not s:
        return None
    # \frac{p}{q} / \dfrac / \tfrac
    m = re.fullmatch(r"-?\\[dt]?frac\{(-?\d+)\}\{(-?\d+)\}", s)
    if m:
        p, q = int(m.group(1)), int(m.group(2))
        if s.startswith("-"):
            p = -p
        return _frac_str(p, q)
    m = re.fullmatch(r"(-?\d+)/(-?\d+)", s)
    if m:
        return _frac_str(int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"-?\d+", s)
    if m:
        return str(int(s))
    m = re.fullmatch(r"(-?\d+)\.(\d+)", s)
    if m:
        f = Fraction(s)
        return _frac_str(f.numerator, f.denominator)
    # Not an exact-normalizable number; return cleaned LaTeX-ish string.
    return s


def _frac_str(p: int, q: int) -> str | None:
    if q == 0:
        return None
    f = Fraction(p, q)
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


def math_answers_equal(extracted: str | None, reference: str) -> bool:
    if extracted is None:
        return False
    a = normalize_math_answer(extracted)
    b = normalize_math_answer(str(reference))
    return a is not None and b is not None and a == b


def is_single_exact_answer(reference) -> bool:
    """Keep only items whose reference normalizes to a single exact value
    (integer or exact fraction)."""
    n = normalize_math_answer(str(reference))
    if n is None:
        return False
    return re.fullmatch(r"-?\d+(/\d+)?", n) is not None


# ------------------------------------------------------------------ code fence

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str | None:
    """The LAST fenced code block (models often restate the final solution
    last); falls back to the whole text when it looks like bare code."""
    if not text:
        return None
    blocks = _FENCE.findall(text)
    if blocks:
        return blocks[-1].strip()
    if re.search(r"^\s*(def |class |import |from )", text, re.M):
        return text.strip()
    return None
