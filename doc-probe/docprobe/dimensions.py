"""The five scoring dimensions, their evidence tiers, and the deterministic scorers.

Evidence tiers (visible in all output — see README):

- ``grounded``     — up-weighted; direct empirical support in a cited paper.
- ``partial``      — partially supported; related but not direct evidence.
- ``opinionated``  — DocProbe's explicit default opinion; no validated evidence.

The deterministic dimensions (directive_density, discovery, hierarchy) are
computed here with NO LLM call and are unit-tested for exact values. The
semantic dimensions (specificity, contradiction) are scored by the LLM judge
(judge.py); this module only defines their metadata and, for contradiction,
the capped candidate-pair generator.
"""

from __future__ import annotations

from dataclasses import dataclass

from docprobe.models import DimensionScore, Flag, Grade
from docprobe.parser import ParsedDoc


@dataclass(frozen=True)
class DimensionSpec:
    key: str
    tier: str  # grounded | partial | opinionated
    source: str
    weight: float
    method: str  # deterministic | llm


# Weights are driven by evidence tier: grounded 1.5, partial 1.0, opinionated 0.75.
DIMENSIONS: dict[str, DimensionSpec] = {
    "discovery_accessibility": DimensionSpec(
        key="discovery_accessibility",
        tier="grounded",
        source="arXiv:2608.20195 (instruction files are the #1 doc type agents read)",
        weight=1.5,
        method="deterministic",
    ),
    "contradiction": DimensionSpec(
        key="contradiction",
        tier="grounded",
        source="arXiv:2608.11095 (contradictory/orphaned directives degrade compliance)",
        weight=1.5,
        method="llm",
    ),
    "hierarchy": DimensionSpec(
        key="hierarchy",
        tier="partial",
        source="partial support: structure aids retrieval; no direct instruction-file study",
        weight=1.0,
        method="deterministic",
    ),
    "specificity": DimensionSpec(
        key="specificity",
        tier="opinionated",
        source="opinionated default (DocProbe rubric v1); no validated evidence",
        weight=0.75,
        method="llm",
    ),
    "directive_density": DimensionSpec(
        key="directive_density",
        tier="opinionated",
        source="opinionated default (DocProbe rubric v1); no validated evidence",
        weight=0.75,
        method="deterministic",
    ),
}

GRADE_BANDS: list[tuple[float, Grade]] = [
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
    (0.0, "F"),
]

GRADE_MIDPOINTS: dict[str, float] = {"A": 95.0, "B": 85.0, "C": 75.0, "D": 65.0, "F": 30.0}


def score_to_grade(score: float) -> Grade:
    for floor, grade in GRADE_BANDS:
        if score >= floor:
            return grade
    return "F"


def _make(spec: DimensionSpec, score: float, flags: list[Flag]) -> DimensionScore:
    score = max(0.0, min(100.0, round(score, 1)))
    return DimensionScore(
        name=spec.key,
        grade=score_to_grade(score),
        score=score,
        evidence_tier=spec.tier,  # type: ignore[arg-type]
        evidence_source=spec.source,
        weight=spec.weight,
        method=spec.method,  # type: ignore[arg-type]
        flags=flags,
    )


# ---------------------------------------------------------------------------
# Deterministic dimension: directive density (opinionated)
# ---------------------------------------------------------------------------

# Opinionated sweet spot: 0.25–0.60 directives per prose line. Below = the file
# is mostly narrative an agent can't act on; above = wall of rules (per
# arXiv:2608.13345 — thematic analogy only: dense rule lists are brittle).
DENSITY_LOW = 0.25
DENSITY_HIGH = 0.60


def score_directive_density(doc: ParsedDoc) -> DimensionScore:
    spec = DIMENSIONS["directive_density"]
    flags: list[Flag] = []
    if doc.prose_lines == 0:
        return _make(spec, 0.0, [Flag(passage="", rationale="No prose content to score")])

    density = len(doc.directives) / doc.prose_lines
    if DENSITY_LOW <= density <= DENSITY_HIGH:
        score = 100.0
    elif density < DENSITY_LOW:
        score = 100.0 * (density / DENSITY_LOW)
        flags.append(
            Flag(
                passage="",
                rationale=(
                    f"Low directive density ({density:.2f}/line): mostly narrative, "
                    "little for an agent to act on"
                ),
                suggestion="Convert narrative prose into explicit, imperative directives",
            )
        )
    else:
        # Linearly decay past the high bound; at 2x the bound, score 50.
        over = min((density - DENSITY_HIGH) / DENSITY_HIGH, 1.0)
        score = 100.0 - 50.0 * over
        flags.append(
            Flag(
                passage="",
                rationale=(
                    f"Very high directive density ({density:.2f}/line): dense rule walls "
                    "are hard to comply with (thematic analogy: arXiv:2608.13345 — "
                    "'rules are brittle'; not a validated formula)"
                ),
                suggestion="Group related rules and cut low-value ones",
            )
        )

    vague = [d for d in doc.directives if d.vague]
    if doc.directives and vague:
        vague_ratio = len(vague) / len(doc.directives)
        score -= 30.0 * vague_ratio
        for d in vague[:5]:
            flags.append(
                Flag(
                    passage=d.text,
                    line=d.line,
                    rationale="Directive weakened by a vague qualifier",
                    suggestion="Replace the vague qualifier with a concrete criterion",
                )
            )
    return _make(spec, score, flags)


# ---------------------------------------------------------------------------
# Deterministic dimension: discovery accessibility (grounded)
# ---------------------------------------------------------------------------

# Grounded framing (arXiv:2608.20195): instruction files are the single most
# read doc type in agent sessions (60.5% of doc interactions), so actionable
# content must surface early and the file must stay small enough to be read
# whole. The exact thresholds below are still DocProbe's choices.
FIRST_SCREEN_LINES = 40
IDEAL_MAX_LINES = 300
HARD_MAX_LINES = 1000


def score_discovery(doc: ParsedDoc) -> DimensionScore:
    spec = DIMENSIONS["discovery_accessibility"]
    flags: list[Flag] = []
    if not doc.text.strip():
        return _make(spec, 0.0, [Flag(passage="", rationale="Empty file")])

    score = 100.0

    # 1. First directive position (0-40 pts of penalty).
    if doc.directives:
        first_line = doc.directives[0].line
        if first_line > FIRST_SCREEN_LINES:
            penalty = min(40.0, (first_line - FIRST_SCREEN_LINES) / 10.0 * 5.0)
            score -= penalty
            flags.append(
                Flag(
                    passage=doc.directives[0].text,
                    line=first_line,
                    rationale=(
                        f"First actionable directive appears at line {first_line} "
                        f"(after the first {FIRST_SCREEN_LINES}-line screenful)"
                    ),
                    suggestion="Move key directives to the top of the file",
                )
            )
    else:
        score -= 40.0
        flags.append(
            Flag(
                passage="",
                rationale="No actionable directives found anywhere in the file",
                suggestion="Add explicit instructions an agent can follow",
            )
        )

    # 2. Length (0-40 pts of penalty). Oversized files bury instructions.
    if doc.total_lines > HARD_MAX_LINES:
        score -= 40.0
        flags.append(
            Flag(
                passage="",
                rationale=f"File is {doc.total_lines} lines (> {HARD_MAX_LINES}); "
                "instructions this deep are unlikely to be read",
                suggestion="Split into linked topic files; keep the entry file short",
            )
        )
    elif doc.total_lines > IDEAL_MAX_LINES:
        score -= 40.0 * (doc.total_lines - IDEAL_MAX_LINES) / (HARD_MAX_LINES - IDEAL_MAX_LINES)
        flags.append(
            Flag(
                passage="",
                rationale=f"File is {doc.total_lines} lines (> {IDEAL_MAX_LINES} ideal max)",
                suggestion="Trim or split; agents weight early content more heavily",
            )
        )

    # 3. Navigability (0-20 pts): headings make sections skimmable/greppable.
    if doc.total_lines > FIRST_SCREEN_LINES and not doc.headings:
        score -= 20.0
        flags.append(
            Flag(
                passage="",
                rationale="No headings: the file cannot be skimmed or navigated by section",
                suggestion="Add markdown headings for each topic",
            )
        )
    return _make(spec, score, flags)


# ---------------------------------------------------------------------------
# Deterministic dimension: hierarchy (partial)
# ---------------------------------------------------------------------------


def score_hierarchy(doc: ParsedDoc) -> DimensionScore:
    spec = DIMENSIONS["hierarchy"]
    flags: list[Flag] = []
    if not doc.text.strip():
        return _make(spec, 0.0, [Flag(passage="", rationale="Empty file")])

    if not doc.headings:
        if doc.total_lines <= FIRST_SCREEN_LINES:
            # Tiny flat files don't need hierarchy.
            return _make(spec, 80.0, [])
        return _make(
            spec,
            40.0,
            [
                Flag(
                    passage="",
                    rationale="No heading structure in a multi-screen file",
                    suggestion="Organize content under level-appropriate headings",
                )
            ],
        )

    score = 100.0

    # Level jumps (h1 -> h3 skips h2).
    prev_level = 0
    jumps = 0
    for h in doc.headings:
        if prev_level and h.level > prev_level + 1:
            jumps += 1
            if jumps <= 3:
                flags.append(
                    Flag(
                        passage=h.text,
                        line=h.line,
                        rationale=f"Heading level jumps from h{prev_level} to h{h.level}",
                        suggestion="Use consecutive heading levels",
                    )
                )
        prev_level = h.level
    score -= 10.0 * jumps

    # Multiple h1s.
    h1s = [h for h in doc.headings if h.level == 1]
    if len(h1s) > 1:
        score -= 5.0 * (len(h1s) - 1)
        flags.append(
            Flag(
                passage=h1s[1].text,
                line=h1s[1].line,
                rationale=f"{len(h1s)} top-level headings; the document has no single root",
                suggestion="Keep one h1 and demote the rest",
            )
        )

    # Empty sections (heading with no body). A parent heading immediately
    # followed by a deeper child heading is structural, not empty.
    sections = [s for s in doc.sections if s.level > 0]
    empty = []
    for i, s in enumerate(sections):
        if s.body:
            continue
        nxt = sections[i + 1] if i + 1 < len(sections) else None
        if nxt is not None and nxt.level > s.level:
            continue
        empty.append(s)
    score -= 5.0 * len(empty)
    for s in empty[:3]:
        flags.append(
            Flag(
                passage=s.heading,
                line=s.start_line,
                rationale="Heading with no content beneath it",
                suggestion="Add content or remove the heading",
            )
        )

    # Excessive depth.
    max_depth = max(h.level for h in doc.headings)
    if max_depth > 4:
        score -= 10.0
        flags.append(
            Flag(
                passage="",
                rationale=f"Headings nest to h{max_depth}; deep nesting hurts retrieval",
                suggestion="Flatten to at most 4 levels",
            )
        )
    return _make(spec, score, flags)


# ---------------------------------------------------------------------------
# Contradiction candidate pairs (deterministic pre-filter feeding the LLM judge)
# ---------------------------------------------------------------------------

# Cap for the O(n^2) pairwise check on huge files. Beyond MAX_DIRECTIVES
# directives we only pair the first MAX_DIRECTIVES; total pairs are capped at
# MAX_PAIRS regardless.
MAX_DIRECTIVES = 150
MAX_PAIRS = 500

_STOPWORDS = frozenset(
    "the a an and or but of to in on for with is are be do not don't never always "
    "must should you your it this that when if all any use only".split()
)


def _topic_tokens(text: str) -> frozenset[str]:
    # Crude 6-char stem so "indent"/"indentation" and "test"/"tests" match.
    tokens = set()
    for w in text.split():
        w = w.lower().strip(".,;:!?()`'\"")
        if len(w) > 3 and w not in _STOPWORDS:
            tokens.add(w[:6])
    return frozenset(tokens)


def contradiction_candidate_pairs(doc: ParsedDoc) -> list[tuple[int, int]]:
    """Indices of directive pairs that share topic vocabulary.

    Deterministic and capped: at most MAX_DIRECTIVES directives are considered
    and at most MAX_PAIRS pairs are returned, so huge files stay tractable.
    """
    directives = doc.directives[:MAX_DIRECTIVES]
    tokens = [_topic_tokens(d.text) for d in directives]
    pairs: list[tuple[int, int]] = []
    for i in range(len(directives)):
        for j in range(i + 1, len(directives)):
            if tokens[i] & tokens[j]:
                pairs.append((i, j))
                if len(pairs) >= MAX_PAIRS:
                    return pairs
    return pairs
