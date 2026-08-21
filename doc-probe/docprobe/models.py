"""Pydantic models defining DocProbe's stable JSON output schema.

The shape of ``ScanResult`` is the documented, stable contract (see README
"JSON output schema"). Additive changes only; field removals or renames bump
the major version.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Grade = Literal["A", "B", "C", "D", "F"]
EvidenceTier = Literal["grounded", "partial", "opinionated"]
Method = Literal["deterministic", "llm"]


class Flag(BaseModel):
    """One flagged passage inside a dimension."""

    passage: str = Field(description="Quoted passage from the file ('' for whole-file findings)")
    line: Optional[int] = Field(default=None, description="1-based line number, if known")
    rationale: str = Field(description="One-line reason this passage was flagged")
    suggestion: Optional[str] = Field(default=None, description="Suggested rewrite or action")
    related_passage: Optional[str] = Field(
        default=None, description="Second passage, for pairwise findings (contradictions)"
    )
    related_line: Optional[int] = None


class DimensionScore(BaseModel):
    """Score for one of the five dimensions, with its evidence tier."""

    name: str
    grade: Grade
    score: float = Field(description="0-100; for LLM dimensions this is the letter's midpoint")
    evidence_tier: EvidenceTier
    evidence_source: str
    weight: float
    method: Method
    flags: list[Flag] = Field(default_factory=list)


class FileResult(BaseModel):
    path: str
    overall_grade: Optional[Grade] = None
    overall_score: Optional[float] = None
    dimensions: list[DimensionScore] = Field(default_factory=list)
    skipped_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimensions not graded (e.g. LLM dimensions under --no-llm)",
    )
    error: Optional[str] = Field(default=None, description="Per-file read/parse error, if any")
    stats: dict[str, float] = Field(default_factory=dict)


class LLMInfo(BaseModel):
    enabled: bool
    model: Optional[str] = None
    prepass_model: Optional[str] = None
    calls: int = 0
    cache_hits: int = 0


class ScanResult(BaseModel):
    """Top-level scan output. This is the stable JSON schema."""

    docprobe_version: str
    rubric_version: str
    llm: LLMInfo
    files: list[FileResult] = Field(default_factory=list)


class Fix(BaseModel):
    """A suggested edit produced by ``docprobe fix``."""

    path: str
    line: Optional[int] = None
    dimension: str
    kind: Literal["attach_rationale", "rewrite", "restructure"]
    original: str
    suggestion: str
    why: str
