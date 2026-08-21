"""LLM judge for the semantic dimensions (specificity, contradiction).

Uses litellm against Bedrock. Model is pinned (anthropic.claude-sonnet-4-5),
temperature 0, responses cached on a content hash so re-scans of unchanged
files make zero calls. Sections are batched into as few calls as possible.
An optional Haiku prepass (--prepass) cheaply screens sections so only
suspicious ones reach the pinned judge model.

The judge prompt text is loaded verbatim from docprobe/rubric.md — the rubric
file IS the prompt (see README).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from docprobe.dimensions import (
    DIMENSIONS,
    GRADE_MIDPOINTS,
    contradiction_candidate_pairs,
)
from docprobe.models import DimensionScore, Flag
from docprobe.parser import ParsedDoc

DEFAULT_MODEL = "bedrock/anthropic.claude-sonnet-4-5"
PREPASS_MODEL = "bedrock/anthropic.claude-haiku-4-5"
MAX_SECTIONS_PER_CALL = 12

_RUBRIC_PATH = Path(__file__).parent / "rubric.md"


def load_rubric() -> str:
    return _RUBRIC_PATH.read_text(encoding="utf-8")


def _rubric_section(rubric: str, marker: str) -> str:
    """Extract one '### LLM judge instructions — <marker>' block from the rubric."""
    pattern = rf"### LLM judge instructions — {marker}\n(.*?)(?=\n## |\n### |\Z)"
    m = re.search(pattern, rubric, re.DOTALL)
    if not m:
        raise ValueError(f"rubric.md is missing judge instructions for {marker!r}")
    return m.group(1).strip()


class JudgeCache:
    """Content-hash → judge-response cache, persisted as JSON files."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.dir = Path(
            cache_dir
            or os.environ.get("DOCPROBE_CACHE_DIR")
            or Path.home() / ".cache" / "docprobe"
        )
        self.hits = 0

    @staticmethod
    def key(model: str, prompt: str, payload: str) -> str:
        h = hashlib.sha256()
        for part in (model, prompt, payload):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def get(self, key: str) -> Optional[dict]:
        path = self.dir / f"{key}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.hits += 1
                return data
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def put(self, key: str, value: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{key}.json").write_text(
            json.dumps(value), encoding="utf-8"
        )


class Judge:
    """Scores the two semantic dimensions for a parsed document."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        prepass: bool = False,
        prepass_model: str = PREPASS_MODEL,
        cache: Optional[JudgeCache] = None,
    ):
        self.model = model
        self.prepass = prepass
        self.prepass_model = prepass_model
        self.cache = cache or JudgeCache()
        self.calls = 0
        self.rubric = load_rubric()

    # -- transport ---------------------------------------------------------

    def _complete(self, model: str, system: str, user: str) -> dict:
        """One judge call, cached on (model, system, user) content hash."""
        key = JudgeCache.key(model, system, user)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        import litellm  # imported lazily so --no-llm never touches it

        response = litellm.completion(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        self.calls += 1
        text = response["choices"][0]["message"]["content"]
        parsed = self._parse_json(text)
        self.cache.put(key, parsed)
        return parsed

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Extract the first JSON object from a judge reply."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {"grade": "C", "flags": [], "parse_error": True}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {"grade": "C", "flags": [], "parse_error": True}

    # -- prepass -----------------------------------------------------------

    def _prepass_filter(self, sections: list[dict]) -> list[dict]:
        """Cheap Haiku screen: keep only sections the small model finds suspicious."""
        if not self.prepass or not sections:
            return sections
        system = (
            "You screen AI-agent instruction-file sections for a detailed audit. "
            "Reply with JSON: {\"suspicious\": [<index>, ...]} listing indices of "
            "sections containing vague directives, potential contradictions, or "
            "unexplained absolute rules. When unsure, include the index."
        )
        user = json.dumps({"sections": sections})
        result = self._complete(self.prepass_model, system, user)
        idx = result.get("suspicious")
        if not isinstance(idx, list):
            return sections
        keep = {i for i in idx if isinstance(i, int)}
        filtered = [s for s in sections if s["index"] in keep]
        return filtered if filtered else sections

    # -- dimensions --------------------------------------------------------

    def score_specificity(self, doc: ParsedDoc) -> DimensionScore:
        spec = DIMENSIONS["specificity"]
        prompt = _rubric_section(self.rubric, "specificity")
        sections = [
            {"index": i, "heading": s.heading, "text": s.body}
            for i, s in enumerate(doc.sections)
            if s.body
        ]
        if not sections:
            return self._empty_dimension("specificity")
        sections = self._prepass_filter(sections)

        grades: list[str] = []
        flags: list[Flag] = []
        for batch_start in range(0, len(sections), MAX_SECTIONS_PER_CALL):
            batch = sections[batch_start : batch_start + MAX_SECTIONS_PER_CALL]
            system = prompt + (
                "\n\nReply ONLY with JSON: "
                '{"grade": "A|B|C|D|F", "flags": [{"passage": str, '
                '"rationale": str, "suggestion": str}]}'
            )
            result = self._complete(self.model, system, json.dumps({"sections": batch}))
            grades.append(str(result.get("grade", "C")))
            flags.extend(self._to_flags(doc, result.get("flags", [])))
        grade = _worst_grade(grades)
        return DimensionScore(
            name="specificity",
            grade=grade,  # type: ignore[arg-type]
            score=GRADE_MIDPOINTS[grade],
            evidence_tier=spec.tier,  # type: ignore[arg-type]
            evidence_source=spec.source,
            weight=spec.weight,
            method="llm",
            flags=flags,
        )

    def score_contradiction(self, doc: ParsedDoc) -> DimensionScore:
        spec = DIMENSIONS["contradiction"]
        prompt = _rubric_section(self.rubric, "contradiction")
        pairs = contradiction_candidate_pairs(doc)
        directives = doc.directives
        if not directives:
            return self._empty_dimension("contradiction")
        payload = {
            "directives": [
                {"index": i, "line": d.line, "text": d.text}
                for i, d in enumerate(directives[: len(directives)])
            ],
            "candidate_pairs": pairs,
        }
        system = prompt + (
            "\n\nReply ONLY with JSON: "
            '{"grade": "A|B|C|D|F", "flags": [{"passage": str, '
            '"related_passage": str, "rationale": str, "suggestion": str}]}'
        )
        result = self._complete(self.model, system, json.dumps(payload))
        grade = str(result.get("grade", "C"))
        if grade not in GRADE_MIDPOINTS:
            grade = "C"
        return DimensionScore(
            name="contradiction",
            grade=grade,  # type: ignore[arg-type]
            score=GRADE_MIDPOINTS[grade],
            evidence_tier=spec.tier,  # type: ignore[arg-type]
            evidence_source=spec.source,
            weight=spec.weight,
            method="llm",
            flags=self._to_flags(doc, result.get("flags", [])),
        )

    # -- helpers -----------------------------------------------------------

    def _empty_dimension(self, key: str) -> DimensionScore:
        spec = DIMENSIONS[key]
        return DimensionScore(
            name=key,
            grade="F",
            score=0.0,
            evidence_tier=spec.tier,  # type: ignore[arg-type]
            evidence_source=spec.source,
            weight=spec.weight,
            method="llm",
            flags=[Flag(passage="", rationale="No content to judge")],
        )

    @staticmethod
    def _to_flags(doc: ParsedDoc, raw: Any) -> list[Flag]:
        flags: list[Flag] = []
        if not isinstance(raw, list):
            return flags
        for item in raw:
            if not isinstance(item, dict):
                continue
            passage = str(item.get("passage", ""))
            flags.append(
                Flag(
                    passage=passage,
                    line=_find_line(doc, passage),
                    rationale=str(item.get("rationale", "")),
                    suggestion=item.get("suggestion"),
                    related_passage=item.get("related_passage"),
                    related_line=_find_line(doc, item.get("related_passage")),
                )
            )
        return flags


def _find_line(doc: ParsedDoc, passage: Optional[str]) -> Optional[int]:
    if not passage:
        return None
    needle = passage.strip()[:80]
    for i, line in enumerate(doc.lines, start=1):
        if needle and needle in line:
            return i
    return None


_GRADE_ORDER = "ABCDF"


def _worst_grade(grades: list[str]) -> str:
    valid = [g for g in grades if g in _GRADE_ORDER]
    if not valid:
        return "C"
    return max(valid, key=_GRADE_ORDER.index)
