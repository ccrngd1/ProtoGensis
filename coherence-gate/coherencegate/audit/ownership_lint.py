"""Ownership-alignment lint (Prediction 7 / the paper's Panel 1 failure).

A guard constrains the state it owns and nothing else. If the guard counts
`tool_call:name=write_file` while the grader counts `tool_call:name=run`,
the guard is active but useless. Static mode compares the declarations;
replay mode re-counts both units from the JSONL run log and flags divergence.

Lint codes:
  OWN001 - guard counts <A>, grader counts <B> (declared unit mismatch)
  OWN002 - guard active but grader-unit limit exceeded (replay divergence)
Exit codes: 0 aligned, 1 misaligned, 2 config/parse error.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class LintResult:
    findings: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def exit_code(self) -> int:
        if self.error:
            return 2
        return 1 if self.findings else 0


def _unit_str(unit: dict) -> str:
    return f"{unit.get('kind', '?')}:name={unit.get('name', '?')}"


def lint_static(config: dict) -> LintResult:
    """Compare the guard's declared counted unit against the grader's."""
    result = LintResult()
    try:
        guard_unit = config["guard"]["unit"]
        graded_unit = config["task"]["graded_unit"]
    except (KeyError, TypeError) as exc:
        result.error = f"config missing required field: {exc}"
        return result
    if (guard_unit.get("kind"), guard_unit.get("name")) != \
            (graded_unit.get("kind"), graded_unit.get("name")):
        result.findings.append({
            "code": "OWN001",
            "message": (f"OWN001 guard counts {_unit_str(guard_unit)}, "
                        f"grader counts {_unit_str(graded_unit)}"),
            "guard_unit": _unit_str(guard_unit),
            "graded_unit": _unit_str(graded_unit),
        })
    return result


def _count_unit(events: list[dict], unit: dict) -> int:
    """Count run-log draw events whose resource/unit matches."""
    name = unit.get("name")
    total = 0
    for ev in events:
        if ev.get("kind") != "draw":
            continue
        payload = ev.get("payload", {})
        if payload.get("unit_name", payload.get("resource")) == name:
            total += payload.get("amount", 1)
    return total


def lint_replay(config: dict, events: list[dict]) -> LintResult:
    """Static lint plus a re-count of both units from the run log."""
    result = lint_static(config)
    if result.error:
        return result
    guard_unit = config["guard"]["unit"]
    graded_unit = config["task"]["graded_unit"]
    limit = config["guard"].get("limit")
    guard_count = _count_unit(events, guard_unit)
    graded_count = _count_unit(events, graded_unit)
    divergence = graded_count - guard_count
    if result.findings:
        result.findings[0]["guard_count"] = guard_count
        result.findings[0]["graded_count"] = graded_count
        result.findings[0]["divergence"] = divergence
    if limit is not None and guard_count != graded_count and graded_count > limit:
        result.findings.append({
            "code": "OWN002",
            "message": (f"OWN002 guard active but grader-unit limit exceeded "
                        f"(guard counted {guard_count} {_unit_str(guard_unit)}, "
                        f"grader counted {graded_count} {_unit_str(graded_unit)} "
                        f"> limit {limit})"),
            "guard_count": guard_count,
            "graded_count": graded_count,
            "limit": limit,
        })
    return result


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def run(config_path: str, runlog_path: str | None = None) -> LintResult:
    try:
        config = load_config(config_path)
    except (OSError, json.JSONDecodeError) as exc:
        return LintResult(error=f"cannot load config {config_path}: {exc}")
    if runlog_path is None:
        return lint_static(config)
    try:
        from ..runlog import RunLog
        events = RunLog.load(runlog_path)
    except (OSError, json.JSONDecodeError) as exc:
        return LintResult(error=f"cannot load runlog {runlog_path}: {exc}")
    return lint_replay(config, events)
