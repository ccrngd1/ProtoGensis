"""Layer 0 — test tampering.

Compares each changed test file against its baseline version with ``ast`` and
flags edits that make a passing suite less meaningful:

* test functions deleted from an existing test file
* assertions removed from a surviving test function
* new ``pytest.mark.skip`` / ``pytest.mark.xfail`` decorators, or new
  ``pytest.skip(...)`` / ``pytest.xfail(...)`` calls, on existing tests
* trivially-true assertions added (``assert True``, ``assert 1``, constant
  tuples/strings — anything statically truthy)

All of the above are blocking. Only the delta matters: a test file that was
already skipping at the baseline does not fail the gate.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from swe_gate.findings import Finding, LayerResult
from swe_gate.gitdiff import Changeset

LAYER = 0


def _is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return path.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


@dataclass
class _TestInfo:
    name: str
    lineno: int
    assertion_count: int = 0
    skip_markers: int = 0  # skip/xfail decorators + pytest.skip()/xfail() calls
    trivial_assert_lines: list[int] = field(default_factory=list)


def _dotted(node: ast.AST) -> str:
    """Render an attribute/name/call target as a dotted string."""
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


_SKIP_SUFFIXES = ("mark.skip", "mark.skipif", "mark.xfail")
_SKIP_CALLS = ("pytest.skip", "pytest.xfail", "pytest.importorskip", "unittest.skip")


def _statically_truthy(test: ast.expr) -> bool:
    """True when an assert condition is a constant that always passes."""
    try:
        value = ast.literal_eval(test)
    except (ValueError, SyntaxError):
        return False
    return bool(value)


def _collect_tests(source: str, path: str) -> dict[str, _TestInfo] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    tests: dict[str, _TestInfo] = {}

    def visit_function(fn: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str) -> None:
        if not fn.name.startswith("test"):
            return
        qualname = f"{prefix}{fn.name}"
        info = _TestInfo(name=qualname, lineno=fn.lineno)
        for deco in fn.decorator_list:
            d = _dotted(deco)
            if d.endswith(_SKIP_SUFFIXES):
                info.skip_markers += 1
        for node in ast.walk(fn):
            if isinstance(node, ast.Assert):
                info.assertion_count += 1
                if _statically_truthy(node.test):
                    info.trivial_assert_lines.append(node.lineno)
            elif isinstance(node, ast.Call):
                callee = _dotted(node)
                if callee in _SKIP_CALLS:
                    info.skip_markers += 1
                elif isinstance(node.func, ast.Attribute) and node.func.attr.startswith(
                    "assert"
                ):
                    # unittest-style self.assertEqual(...) etc.
                    info.assertion_count += 1
        tests[qualname] = info

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visit_function(node, "")
        elif isinstance(node, ast.ClassDef):
            class_skips = sum(
                1 for deco in node.decorator_list if _dotted(deco).endswith(_SKIP_SUFFIXES)
            )
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visit_function(sub, f"{node.name}.")
                    qual = f"{node.name}.{sub.name}"
                    if qual in tests:
                        tests[qual].skip_markers += class_skips
    return tests


def run(changeset: Changeset) -> LayerResult:
    result = LayerResult(layer=LAYER, status="")

    test_files = [f for f in changeset.python_files if _is_test_file(f.path)]
    if not changeset.python_files:
        result.status = "n/a"
        result.detail = "no Python in scope"
        return result
    if not test_files:
        result.status = "pass"
        result.detail = "no test files changed"
        return result

    for cf in test_files:
        new_src = changeset.working_content(cf)
        if new_src is None:
            continue
        new_tests = _collect_tests(new_src, cf.path)
        if new_tests is None:
            result.findings.append(
                Finding(
                    layer=LAYER,
                    rule_id="tamper-unparseable",
                    message="changed test file does not parse; cannot verify assertions",
                    file=cf.path,
                    blocking=True,
                )
            )
            continue

        old_src = changeset.baseline_content(cf)
        old_tests = _collect_tests(old_src, cf.path) if old_src is not None else {}
        if old_tests is None:
            old_tests = {}

        # New trivially-true assertions are flagged even in brand-new files.
        for name, info in sorted(new_tests.items()):
            old = old_tests.get(name)
            old_trivial = len(old.trivial_assert_lines) if old else 0
            if len(info.trivial_assert_lines) > old_trivial:
                result.findings.append(
                    Finding(
                        layer=LAYER,
                        rule_id="tamper-trivial-assert",
                        message=f"trivially-true assertion in {name}",
                        file=cf.path,
                        line=info.trivial_assert_lines[0],
                        blocking=True,
                    )
                )

        if old_src is None:
            continue  # brand-new test file: nothing to weaken

        for name, old in sorted(old_tests.items()):
            new = new_tests.get(name)
            if new is None:
                result.findings.append(
                    Finding(
                        layer=LAYER,
                        rule_id="tamper-test-deleted",
                        message=f"test {name} deleted from existing test file",
                        file=cf.path,
                        line=old.lineno,
                        blocking=True,
                    )
                )
                continue
            if new.assertion_count < old.assertion_count:
                result.findings.append(
                    Finding(
                        layer=LAYER,
                        rule_id="tamper-assert-removed",
                        message=(
                            f"assertions in {name} reduced "
                            f"{old.assertion_count} -> {new.assertion_count}"
                        ),
                        file=cf.path,
                        line=new.lineno,
                        blocking=True,
                    )
                )
            if new.skip_markers > old.skip_markers:
                result.findings.append(
                    Finding(
                        layer=LAYER,
                        rule_id="tamper-skip-added",
                        message=f"skip/xfail added to existing test {name}",
                        file=cf.path,
                        line=new.lineno,
                        blocking=True,
                    )
                )

    result.detail = f"{len(test_files)} changed test file(s) compared against baseline"
    return result.finalize()
