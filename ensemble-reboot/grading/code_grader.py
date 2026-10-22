"""Grade LLM code against LiveCodeBench tests via the sandbox.

Two test types:
  stdin      - run the program with the test input on stdin, compare stdout.
  functional - LeetCode-style: the test input is "arg-lines" consumed by a
               harness that calls Solution().<method>(...) per LCB metadata
               (metadata["func_name"]).

Public tests are for best-of-N selection ONLY; grading uses private tests.
"""

import json
from dataclasses import dataclass, field

from .code_sandbox import run_untrusted

MAX_TESTS_PER_ITEM = 25  # cap grading cost per item; recorded in details


@dataclass
class CodeGradeResult:
    passed: bool
    n_tests: int
    n_passed: int
    first_failure: dict | None = None
    details: dict = field(default_factory=dict)

    def output_signature(self) -> str:
        """Stable signature of per-test outputs, for majority tie-breaking."""
        return self.details.get("output_signature", "")


def _norm_out(s: str) -> str:
    lines = [ln.rstrip() for ln in s.strip().splitlines()]
    return "\n".join(lines)


FUNCTIONAL_HARNESS = """
import json, sys
{code}

_args = json.loads(sys.stdin.readline())
_res = Solution().{func}(*_args)
print(json.dumps(_res))
"""


def _run_one(code: str, test: dict, func_name: str | None, timeout_s: float):
    if test.get("testtype") == "functional":
        if not func_name:
            return None, "no func_name in metadata"
        args = [json.loads(ln) for ln in test["input"].strip().splitlines()]
        prog = FUNCTIONAL_HARNESS.format(code=code, func=func_name)
        res = run_untrusted(prog, stdin_data=json.dumps(args) + "\n",
                            wall_timeout_s=timeout_s)
        if res.timed_out:
            return None, "timeout"
        if res.returncode != 0:
            return None, f"error: {res.stderr[-400:]}"
        got = res.stdout.strip()
        try:
            expected = json.loads(test["output"])
            ok = json.loads(got) == expected
        except (json.JSONDecodeError, ValueError):
            ok = _norm_out(got) == _norm_out(test["output"])
        return (got, None) if ok else (got, "wrong answer")
    # stdin type
    res = run_untrusted(code, stdin_data=test["input"], wall_timeout_s=timeout_s)
    if res.timed_out:
        return None, "timeout"
    if res.returncode != 0:
        return None, f"error: {res.stderr[-400:]}"
    got = res.stdout
    ok = _norm_out(got) == _norm_out(test["output"])
    return (got, None) if ok else (got, "wrong answer")


def grade_code(
    code: str | None,
    tests: list,
    metadata: dict | None = None,
    timeout_s: float = 40,
    max_tests: int = MAX_TESTS_PER_ITEM,
    stop_at_first_failure: bool = True,
) -> CodeGradeResult:
    """stop_at_first_failure=True for grading (pass requires all tests).
    Use False when computing output signatures over public tests, so the
    signature covers every test regardless of where failures land."""
    if not code:
        return CodeGradeResult(False, 0, 0, details={"reason": "no code extracted"})
    func_name = (metadata or {}).get("func_name")
    used = tests[:max_tests]
    outputs = []
    n_passed = 0
    first_failure = None
    for i, t in enumerate(used):
        got, err = _run_one(code, t, func_name, timeout_s)
        outputs.append(got if got is not None else f"<{err}>")
        if err is None:
            n_passed += 1
        else:
            if first_failure is None:
                first_failure = {"test_index": i, "error": err}
            if stop_at_first_failure:
                break
    import hashlib
    sig = hashlib.sha256("\x00".join(outputs).encode()).hexdigest()[:16]
    # passed requires ALL planned tests to pass; n_tests = tests actually run
    # (fewer than planned when stopping at the first failure).
    return CodeGradeResult(
        passed=(n_passed == len(used) and len(used) > 0),
        n_tests=len(outputs),
        n_passed=n_passed,
        first_failure=first_failure,
        details={
            "tests_capped": len(tests) > max_tests,
            "n_total_tests": len(tests),
            "output_signature": sig,
        },
    )
