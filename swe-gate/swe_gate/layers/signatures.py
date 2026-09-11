"""Layer 2 — signature mismatch.

Runs ``pyright --outputjson`` scoped to the changed Python files and keeps
only diagnostics that

* belong to the signature-mismatch family (wrong argument count, unknown
  attribute/member, bad argument type, wrong return usage), and
* land on a line actually changed vs the baseline.

Those are blocking: the tests passed, so a signature error on a changed line
means the changed code path is not covered by the suite.

Graceful degradation (never exit 2 for a missing optional tool):

* pyright not installed → status "skipped", non-blocking, clearly labeled
* diagnostics that depend on missing type stubs (reportMissingModuleSource /
  reportMissingTypeStubs and friends) → status "unverifiable", non-blocking
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from swe_gate.findings import Finding, LayerResult
from swe_gate.gitdiff import Changeset

LAYER = 2

PYRIGHT_TIMEOUT = 600  # first run may download a node runtime via nodeenv

# Diagnostic rules in the signature/attribute/return family. Everything else
# pyright reports (unused vars, style, general type opinions) is ignored.
SIGNATURE_RULES = {
    "reportCallIssue",
    "reportAttributeAccessIssue",
    "reportArgumentType",
    "reportReturnType",
    "reportRedeclaration",
    "reportInvalidTypeArguments",
    "reportOptionalCall",
    "reportOptionalMemberAccess",
}

STUB_RULES = {
    "reportMissingImports",  # handled by Layer 1, not double-reported here
    "reportMissingModuleSource",
    "reportMissingTypeStubs",
}


def pyright_available() -> bool:
    return shutil.which("pyright") is not None


def run(changeset: Changeset) -> LayerResult:
    result = LayerResult(layer=LAYER, status="")
    py_files = changeset.python_files
    if not py_files:
        result.status = "n/a"
        result.detail = "no Python in scope"
        return result

    if not pyright_available():
        result.status = "skipped"
        result.detail = "pyright not installed — signature layer skipped (non-blocking)"
        return result

    paths = [str(changeset.repo / f.path) for f in py_files if (changeset.repo / f.path).is_file()]
    if not paths:
        result.status = "n/a"
        result.detail = "changed Python files not present in working tree"
        return result

    try:
        proc = subprocess.run(
            ["pyright", "--outputjson", *paths],
            capture_output=True,
            text=True,
            timeout=PYRIGHT_TIMEOUT,
            cwd=changeset.repo,
        )
        report = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        result.status = "error"
        result.detail = f"pyright failed: {exc}"
        return result

    changed_lines = {
        str((changeset.repo / f.path).resolve()): f.changed_lines for f in py_files
    }
    stub_gaps = 0

    for diag in report.get("generalDiagnostics", []):
        rule = diag.get("rule", "")
        severity = diag.get("severity", "")
        file = str(Path(diag.get("file", diag.get("uri", ""))).resolve())
        line = diag.get("range", {}).get("start", {}).get("line", -1) + 1  # 0-based
        message = diag.get("message", "").split("\n")[0]

        if rule in STUB_RULES:
            stub_gaps += 1
            continue
        if severity != "error" or rule not in SIGNATURE_RULES:
            continue
        lines_for_file = changed_lines.get(file)
        if lines_for_file is None or line not in lines_for_file:
            continue  # pre-existing debt or outside the delta: never gates

        rel = Path(file)
        try:
            rel = rel.relative_to(changeset.repo.resolve())
        except ValueError:
            pass
        result.findings.append(
            Finding(
                layer=LAYER,
                rule_id=f"signature-{rule}",
                message=message,
                file=str(rel),
                line=line,
                blocking=True,
                tool="pyright",
            )
        )

    result.finalize()
    if result.status == "pass" and stub_gaps:
        result.status = "unverifiable"
        result.detail = (
            f"{stub_gaps} import(s) lack type stubs — signatures against those "
            "modules could not be verified (non-blocking)"
        )
    else:
        result.detail = result.detail or f"pyright checked {len(paths)} changed file(s)"
    return result
