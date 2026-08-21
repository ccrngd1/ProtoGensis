"""Scan orchestration: glob → parse → score → aggregate."""

from __future__ import annotations

import glob as globmod
from pathlib import Path
from typing import Optional

import docprobe
from docprobe.dimensions import (
    DIMENSIONS,
    score_directive_density,
    score_discovery,
    score_hierarchy,
    score_to_grade,
)
from docprobe.judge import Judge
from docprobe.models import FileResult, LLMInfo, ScanResult
from docprobe.parser import looks_like_markdown, parse

DETERMINISTIC_DIMS = ("discovery_accessibility", "hierarchy", "directive_density")
LLM_DIMS = ("specificity", "contradiction")

DEFAULT_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    "**/AGENTS.md",
    "**/CLAUDE.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
)


def expand_targets(patterns: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for pattern in patterns:
        p = Path(pattern)
        if p.is_file():
            seen.setdefault(str(p), None)
            continue
        for match in sorted(globmod.glob(pattern, recursive=True)):
            if Path(match).is_file():
                seen.setdefault(match, None)
    return list(seen)


def scan_file(path: str, judge: Optional[Judge]) -> FileResult:
    result = FileResult(path=path)
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        result.error = f"unreadable: {exc}"
        return result
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        result.error = "not a text file (binary or non-UTF-8 content)"
        return result

    if not looks_like_markdown(path):
        # Score anyway (plain-text rules files are common) but note it.
        result.stats["non_markdown"] = 1.0

    doc = parse(path, text)
    result.stats.update(
        {
            "lines": float(doc.total_lines),
            "prose_lines": float(doc.prose_lines),
            "directives": float(len(doc.directives)),
            "headings": float(len(doc.headings)),
            "words": float(doc.word_count),
        }
    )

    result.dimensions.append(score_discovery(doc))
    result.dimensions.append(score_hierarchy(doc))
    result.dimensions.append(score_directive_density(doc))

    if judge is not None:
        result.dimensions.append(judge.score_specificity(doc))
        result.dimensions.append(judge.score_contradiction(doc))
    else:
        result.skipped_dimensions = list(LLM_DIMS)

    total_weight = sum(d.weight for d in result.dimensions)
    if total_weight:
        result.overall_score = round(
            sum(d.score * d.weight for d in result.dimensions) / total_weight, 1
        )
        result.overall_grade = score_to_grade(result.overall_score)
    return result


def run_scan(
    patterns: list[str],
    judge: Optional[Judge] = None,
) -> ScanResult:
    paths = expand_targets(patterns)
    files = [scan_file(p, judge) for p in paths]
    llm = LLMInfo(
        enabled=judge is not None,
        model=judge.model if judge else None,
        prepass_model=(judge.prepass_model if judge and judge.prepass else None),
        calls=judge.calls if judge else 0,
        cache_hits=judge.cache.hits if judge else 0,
    )
    return ScanResult(
        docprobe_version=docprobe.__version__,
        rubric_version=docprobe.RUBRIC_VERSION,
        llm=llm,
        files=files,
    )


__all__ = [
    "DEFAULT_GLOBS",
    "DETERMINISTIC_DIMS",
    "LLM_DIMS",
    "DIMENSIONS",
    "expand_targets",
    "scan_file",
    "run_scan",
]
