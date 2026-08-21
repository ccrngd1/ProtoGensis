"""Deterministic dimension scorers — exact values, no LLM."""

from docprobe.dimensions import (
    DIMENSIONS,
    contradiction_candidate_pairs,
    score_directive_density,
    score_discovery,
    score_hierarchy,
    score_to_grade,
)
from docprobe.parser import parse


def test_evidence_tiers_and_weights():
    assert DIMENSIONS["discovery_accessibility"].tier == "grounded"
    assert DIMENSIONS["contradiction"].tier == "grounded"
    assert DIMENSIONS["hierarchy"].tier == "partial"
    assert DIMENSIONS["specificity"].tier == "opinionated"
    assert DIMENSIONS["directive_density"].tier == "opinionated"
    # Grounded dimensions are up-weighted relative to opinionated ones.
    assert DIMENSIONS["discovery_accessibility"].weight == 1.5
    assert DIMENSIONS["contradiction"].weight == 1.5
    assert DIMENSIONS["hierarchy"].weight == 1.0
    assert DIMENSIONS["specificity"].weight == 0.75
    assert DIMENSIONS["directive_density"].weight == 0.75


def test_grade_bands_exact():
    assert score_to_grade(90.0) == "A"
    assert score_to_grade(89.9) == "B"
    assert score_to_grade(80.0) == "B"
    assert score_to_grade(70.0) == "C"
    assert score_to_grade(60.0) == "D"
    assert score_to_grade(59.9) == "F"
    assert score_to_grade(0.0) == "F"


def test_density_in_band_scores_100():
    # 2 directives / 5 prose lines = 0.4 → inside [0.25, 0.60] → 100
    text = "\n".join(
        [
            "- Always run tests.",
            "- Never push to main.",
            "plain line one",
            "plain line two",
            "plain line three",
        ]
    )
    doc = parse("AGENTS.md", text)
    assert doc.prose_lines == 5
    assert len(doc.directives) == 2
    d = score_directive_density(doc)
    assert d.score == 100.0
    assert d.grade == "A"
    assert d.flags == []


def test_density_low_is_proportional():
    # 1 directive / 10 prose lines = 0.1 → 100 * (0.1/0.25) = 40.0
    lines = ["- Always run tests."] + [f"narrative line {i}" for i in range(9)]
    doc = parse("AGENTS.md", "\n".join(lines))
    assert doc.prose_lines == 10
    d = score_directive_density(doc)
    assert d.score == 40.0
    assert d.grade == "F"
    assert any("Low directive density" in f.rationale for f in d.flags)


def test_density_empty_file_scores_zero():
    d = score_directive_density(parse("AGENTS.md", ""))
    assert d.score == 0.0
    assert d.grade == "F"


def test_discovery_perfect_file():
    doc = parse("AGENTS.md", "# T\n\n- Always run make test.\n")
    d = score_discovery(doc)
    assert d.score == 100.0
    assert d.grade == "A"


def test_discovery_no_directives_penalty_exact():
    doc = parse("AGENTS.md", "just some narrative\nnothing actionable here\n")
    d = score_discovery(doc)
    assert d.score == 60.0  # 100 - 40 (no directives); short file, no other penalty
    assert any("No actionable directives" in f.rationale for f in d.flags)


def test_discovery_late_first_directive_penalty_exact():
    # First directive at line 61: penalty = min(40, (61-40)/10*5) = 10.5 → 89.5
    filler = [f"line {i}" for i in range(1, 61)]
    text = "\n".join(filler + ["- Always run tests."])
    doc = parse("AGENTS.md", text)
    assert doc.directives[0].line == 61
    d = score_discovery(doc)
    # 100 - 10.5 (late directive) - 20 (no headings in a >40-line file) = 69.5
    assert d.score == 69.5
    assert d.grade == "D"


def test_discovery_huge_file_capped_penalty():
    text = "\n".join(["- Always run tests."] + ["x"] * 1200)
    doc = parse("AGENTS.md", text)
    d = score_discovery(doc)
    # 100 - 40 (over hard max) - 20 (no headings) = 40
    assert d.score == 40.0
    assert any("1201 lines" in f.rationale for f in d.flags)


def test_hierarchy_clean_structure_scores_100():
    text = "# A\n\nbody\n\n## B\n\nbody b\n\n## C\n\nbody c\n"
    d = score_hierarchy(parse("AGENTS.md", text))
    assert d.score == 100.0
    assert d.grade == "A"


def test_hierarchy_level_jump_penalty_exact():
    text = "# A\n\nbody\n\n#### Deep\n\nbody\n"
    d = score_hierarchy(parse("AGENTS.md", text))
    assert d.score == 90.0  # one h1→h4 jump = -10
    assert any("jumps from h1 to h4" in f.rationale for f in d.flags)


def test_hierarchy_no_headings_long_file():
    text = "\n".join(f"line {i}" for i in range(60))
    d = score_hierarchy(parse("AGENTS.md", text))
    assert d.score == 40.0


def test_hierarchy_tiny_flat_file_ok():
    d = score_hierarchy(parse("AGENTS.md", "- Always run tests.\n"))
    assert d.score == 80.0


def test_hierarchy_empty_section_penalty():
    text = "# A\n\nbody\n\n## Empty\n\n## Full\n\ncontent\n"
    d = score_hierarchy(parse("AGENTS.md", text))
    assert d.score == 95.0  # one empty section = -5


def test_contradiction_pairs_share_topic():
    text = "- Always use tabs for indentation.\n- Indent with 4 spaces, never tabs.\n- Update the changelog weekly.\n"
    doc = parse("AGENTS.md", text)
    pairs = contradiction_candidate_pairs(doc)
    assert (0, 1) in pairs  # both mention tabs/indentation
    assert (0, 2) not in pairs  # no shared topic tokens


def test_contradiction_pairs_capped_on_huge_files():
    # 300 directives sharing one topic word would be ~44k pairs uncapped.
    text = "\n".join(f"- Always update the changelog entry {i}." for i in range(300))
    doc = parse("AGENTS.md", text)
    pairs = contradiction_candidate_pairs(doc)
    assert len(pairs) <= 500
    assert max(max(p) for p in pairs) < 150  # only first MAX_DIRECTIVES considered
