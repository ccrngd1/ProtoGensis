"""
Tests for research completeness evaluation.

Validates structural requirements and quality scoring.
"""

import os
from pathlib import Path

import pytest

from evaluators.completeness import CompletenessEvaluator


def test_complete_research(research_file_complete):
    """Test that complete research passes evaluation."""
    with open(research_file_complete) as f:
        content = f.read()

    evaluator = CompletenessEvaluator()
    result = evaluator.evaluate_research_output(content)

    assert result.passed, f"Complete research failed: {result.warnings}"
    assert result.overall_score >= 0.8


def test_incomplete_research(research_file_incomplete):
    """Test that incomplete research fails evaluation."""
    with open(research_file_incomplete) as f:
        content = f.read()

    evaluator = CompletenessEvaluator()
    result = evaluator.evaluate_research_output(content)

    assert not result.passed, "Incomplete research should fail"
    assert result.overall_score < 0.8


def test_overview_check(sample_research_complete, sample_research_incomplete):
    """Test detection of overview section."""
    evaluator = CompletenessEvaluator()

    # Complete has overview
    check = evaluator._check_has_overview(sample_research_complete)
    assert check.passed, "Should find overview section"

    # Incomplete missing overview
    check = evaluator._check_has_overview(sample_research_incomplete)
    assert not check.passed, "Should detect missing overview"


def test_findings_check(sample_research_complete):
    """Test detection of findings sections."""
    evaluator = CompletenessEvaluator()

    check = evaluator._check_has_findings(sample_research_complete)
    assert check.passed, "Should find multiple findings sections"
    assert check.score == 1.0


def test_sources_check(sample_research_complete, sample_research_incomplete):
    """Test detection and validation of sources section."""
    evaluator = CompletenessEvaluator()

    # Complete has sources
    check = evaluator._check_has_sources(sample_research_complete)
    assert check.passed, "Should find sources section with URLs"

    # Incomplete missing sources
    check = evaluator._check_has_sources(sample_research_incomplete)
    assert not check.passed, "Should detect missing sources"


def test_status_check(sample_research_complete):
    """Test detection of status field."""
    evaluator = CompletenessEvaluator()

    check = evaluator._check_has_status(sample_research_complete)
    assert check.passed, "Should find status field"


def test_minimum_length_check():
    """Test minimum content length requirement."""
    evaluator = CompletenessEvaluator()

    # Too short
    short_content = "# Research\n\nThis is short."
    check = evaluator._check_minimum_length(short_content, min_words=300)
    assert not check.passed, "Should fail length check"

    # Long enough
    long_content = " ".join(["word"] * 350)
    check = evaluator._check_minimum_length(long_content, min_words=300)
    assert check.passed, "Should pass length check"


def test_section_balance_check():
    """Test that sections have reasonable content."""
    evaluator = CompletenessEvaluator()

    # Well-balanced sections
    balanced = """# Research

## Section 1

This section has plenty of content with many words to ensure it meets the minimum
threshold for what we consider a substantial section. More words here to reach fifty
words total in this section. We need to add enough content to make this section pass
the balance check with at least fifty words of actual substantive content.

## Section 2

Another substantial section with enough content to be considered complete and valuable.
We need to make sure this has at least fifty words as well. Adding more content here
to ensure that this section also meets the minimum word count requirement for balanced
sections in the research output evaluation.
"""

    check = evaluator._check_section_balance(balanced)
    assert check.passed, "Balanced sections should pass"

    # Unbalanced (short sections)
    unbalanced = """# Research

## Section 1

Short.

## Section 2

Also short.
"""

    check = evaluator._check_section_balance(unbalanced)
    assert not check.passed, "Short sections should fail"


def test_build_output_evaluation(tmp_path):
    """Test evaluation of build output."""
    # Create a mock build directory
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    # Create expected files
    (build_dir / "README.md").write_text("# Project")
    (build_dir / "pyproject.toml").write_text("[project]")

    # Create source files
    src_dir = build_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')")

    # Create test files
    tests_dir = build_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_main(): pass")

    evaluator = CompletenessEvaluator()
    result = evaluator.evaluate_build_output(build_dir)

    assert result.passed, f"Build evaluation failed: {result.warnings}"
    assert result.overall_score >= 0.8


def test_build_missing_files(tmp_path):
    """Test build evaluation with missing files."""
    build_dir = tmp_path / "incomplete_build"
    build_dir.mkdir()

    # Only create README, missing other files
    (build_dir / "README.md").write_text("# Project")

    evaluator = CompletenessEvaluator()
    result = evaluator.evaluate_build_output(build_dir)

    assert not result.passed, "Incomplete build should fail"


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set, skipping LLM judge test",
)
def test_llm_quality_assessment(sample_research_complete):
    """Test LLM-as-judge quality assessment."""
    from anthropic import Anthropic

    client = Anthropic()
    evaluator = CompletenessEvaluator(llm_client=client)

    check = evaluator._evaluate_research_quality(sample_research_complete)

    # Should get a valid score
    assert 0.0 <= check.score <= 1.0
    assert len(check.details) > 0


def test_llm_judge_fallback(sample_research_complete):
    """Test graceful fallback when LLM judge unavailable."""
    evaluator = CompletenessEvaluator(llm_client=None)

    check = evaluator._evaluate_research_quality(sample_research_complete)

    # Should skip and return neutral score
    assert check.passed
    assert "not configured" in check.details.lower()


def test_trace_completeness():
    """Test completeness evaluation from trace file."""
    trace_file = Path("traces/precog-research-complete.json")

    if not trace_file.exists():
        pytest.skip("Research trace not found")

    from evaluators.completeness import evaluate_trace_completeness

    result = evaluate_trace_completeness(trace_file)

    # Basic validation
    assert "trace_file" in result
    assert "passed" in result
    assert "overall_score" in result


def test_structural_score_weighting(sample_research_complete):
    """Test that structural and quality scores are weighted correctly."""
    evaluator = CompletenessEvaluator(llm_client=None, pass_threshold=0.8)

    result = evaluator.evaluate_research_output(sample_research_complete)

    # Without LLM judge, should use structural score only
    structural_checks = [c for c in result.checks if c.check_name != "llm_quality_assessment"]
    structural_score = sum(c.score for c in structural_checks) / len(structural_checks)

    # Overall score should be close to structural score
    assert abs(result.overall_score - structural_score) < 0.1


def test_pass_threshold_enforcement():
    """Test that pass threshold is properly enforced."""
    evaluator_strict = CompletenessEvaluator(pass_threshold=0.9)
    evaluator_lenient = CompletenessEvaluator(pass_threshold=0.5)

    # Mediocre content - scores around 0.5-0.6
    mediocre = """# Research Report

**Status:** draft

## Overview

This is a brief overview of the research topic. It provides some context and background
information about what was investigated. The overview explains the purpose and scope
of the research in a concise manner. This section gives readers a basic understanding
of what to expect in the findings below.

## Finding 1

First finding discusses one aspect of the research. This section contains enough detail
to be considered substantive but lacks the depth expected in excellent research. The
analysis is adequate but could be more thorough and comprehensive.

## Finding 2

Second finding covers another important aspect. Similar level of detail as the first
finding, providing decent coverage but not exceptional depth or analysis. The content
meets minimum requirements but doesn't exceed expectations for quality.

## Finding 3

Third finding addresses an additional dimension of the topic. Again, this provides
basic coverage with adequate detail but room for improvement in analysis depth and
insight quality. The section meets baseline standards for completeness.

## Sources

1. http://example.com/source1
2. http://example.com/source2
3. http://example.com/source3
4. http://example.com/source4
5. http://example.com/source5
"""

    result_strict = evaluator_strict.evaluate_research_output(mediocre)
    result_lenient = evaluator_lenient.evaluate_research_output(mediocre)

    # Should fail strict but pass lenient
    assert not result_strict.passed
    assert result_lenient.passed
