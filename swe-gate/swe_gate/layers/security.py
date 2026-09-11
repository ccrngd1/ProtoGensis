"""Layer 3 — security patterns.

Runs two scanners over the changed Python files:

* **bandit** (JSON output) — general Python security checks
* **semgrep** with the curated in-repo rule pack ``rules/ai-patterns.yml`` —
  patterns over-represented in LLM-generated code (f-string SQL,
  shell=True interpolation, verify=False, pickle.loads, hardcoded secrets)

Delta principle: a finding gates only if it is *new*, i.e. it sits on a line
changed vs the baseline. New HIGH severity findings block; MEDIUM/LOW are
advisory. Missing scanners degrade to a labeled "skipped", never exit 2.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib.resources import files as pkg_files
from pathlib import Path

from swe_gate.findings import Finding, LayerResult
from swe_gate.gitdiff import Changeset

LAYER = 3

SCAN_TIMEOUT = 300

_BANDIT_SEVERITY = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW"}
_SEMGREP_SEVERITY = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}


def rules_path() -> Path:
    return Path(str(pkg_files("swe_gate") / "rules" / "ai-patterns.yml"))


def _run_bandit(paths: list[str], repo: Path) -> list[dict] | None:
    if shutil.which("bandit") is None:
        return None
    proc = subprocess.run(
        ["bandit", "-f", "json", "-q", *paths],
        capture_output=True,
        text=True,
        timeout=SCAN_TIMEOUT,
        cwd=repo,
    )
    try:
        return json.loads(proc.stdout).get("results", [])
    except json.JSONDecodeError:
        raise RuntimeError(f"bandit produced unparseable output: {proc.stderr[:200]}")


def _run_semgrep(paths: list[str], repo: Path) -> list[dict] | None:
    if shutil.which("semgrep") is None:
        return None
    proc = subprocess.run(
        [
            "semgrep",
            "scan",
            "--config",
            str(rules_path()),
            "--json",
            "--quiet",
            "--metrics=off",
            "--disable-version-check",
            *paths,
        ],
        capture_output=True,
        text=True,
        timeout=SCAN_TIMEOUT,
        cwd=repo,
    )
    try:
        return json.loads(proc.stdout).get("results", [])
    except json.JSONDecodeError:
        raise RuntimeError(f"semgrep produced unparseable output: {proc.stderr[:200]}")


def run(changeset: Changeset) -> LayerResult:
    result = LayerResult(layer=LAYER, status="")
    py_files = changeset.python_files
    if not py_files:
        result.status = "n/a"
        result.detail = "no Python in scope"
        return result

    paths = [str(changeset.repo / f.path) for f in py_files if (changeset.repo / f.path).is_file()]
    if not paths:
        result.status = "n/a"
        result.detail = "changed Python files not present in working tree"
        return result

    changed_lines = {
        str((changeset.repo / f.path).resolve()): f.changed_lines for f in py_files
    }

    def is_new(abs_file: str, line: int) -> bool:
        lines = changed_lines.get(str(Path(abs_file).resolve()))
        return lines is not None and line in lines

    def rel(abs_file: str) -> str:
        try:
            return str(Path(abs_file).resolve().relative_to(changeset.repo.resolve()))
        except ValueError:
            return abs_file

    ran = []
    try:
        bandit_results = _run_bandit(paths, changeset.repo)
        semgrep_results = _run_semgrep(paths, changeset.repo)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        result.status = "error"
        result.detail = f"security scan failed: {exc}"
        return result

    if bandit_results is not None:
        ran.append("bandit")
        for item in bandit_results:
            line = int(item.get("line_number", 0))
            abs_file = str(changeset.repo / item.get("filename", ""))
            if not is_new(abs_file, line):
                continue
            sev = _BANDIT_SEVERITY.get(item.get("issue_severity", "LOW"), "LOW")
            result.findings.append(
                Finding(
                    layer=LAYER,
                    rule_id=f"bandit-{item.get('test_id', '?')}",
                    message=f"[{sev}] {item.get('issue_text', '')}",
                    file=rel(abs_file),
                    line=line,
                    blocking=sev == "HIGH",
                    tool="bandit",
                )
            )

    if semgrep_results is not None:
        ran.append("semgrep")
        for item in semgrep_results:
            line = int(item.get("start", {}).get("line", 0))
            abs_file = str(changeset.repo / item.get("path", ""))
            if not is_new(abs_file, line):
                continue
            meta = item.get("extra", {})
            sev = meta.get("metadata", {}).get(
                "swe_gate_severity",
                _SEMGREP_SEVERITY.get(meta.get("severity", "INFO"), "LOW"),
            )
            rule = item.get("check_id", "?").rsplit(".", 1)[-1]
            result.findings.append(
                Finding(
                    layer=LAYER,
                    rule_id=f"semgrep-{rule}",
                    message=f"[{sev}] {meta.get('message', '').strip()}",
                    file=rel(abs_file),
                    line=line,
                    blocking=sev == "HIGH",
                    tool="semgrep",
                )
            )

    if not ran:
        result.status = "skipped"
        result.detail = "bandit and semgrep not installed — security layer skipped (non-blocking)"
        return result

    # Dedup: bandit and semgrep often flag the same line for the same class of
    # issue. Keep both messages but they count as one gate decision anyway.
    result.detail = f"{' + '.join(ran)} over {len(paths)} changed file(s); new findings only"
    return result.finalize()
