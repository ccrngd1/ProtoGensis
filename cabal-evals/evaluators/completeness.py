"""
Completeness and quality evaluator.

Structural checks on research/build outputs (required sections present,
minimum content thresholds). LLM-as-judge reserved for genuinely subjective
quality assessment only.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # LLM-as-judge features disabled without anthropic
from pydantic import BaseModel


class CompletenessCheck(BaseModel):
    """Result of a single completeness check."""

    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str


class CompletenessResult(BaseModel):
    """Result from completeness evaluation."""

    passed: bool
    overall_score: float  # 0.0 to 1.0
    checks: List[CompletenessCheck] = []
    warnings: List[str] = []


class CompletenessEvaluator:
    """Evaluates output completeness and quality."""

    def __init__(self, llm_client: Optional[Anthropic] = None, pass_threshold: float = 0.8):
        """
        Initialize the evaluator.

        Args:
            llm_client: Anthropic client for LLM-as-judge (optional)
            pass_threshold: Minimum overall score to pass
        """
        self.llm_client = llm_client
        self.pass_threshold = pass_threshold

    def evaluate_research_output(self, research_content: str) -> CompletenessResult:
        """
        Evaluate research output completeness.

        Args:
            research_content: Research document content

        Returns:
            CompletenessResult with structural and quality scores
        """
        checks: List[CompletenessCheck] = []
        warnings: List[str] = []

        # Structural checks (deterministic)
        checks.append(self._check_has_overview(research_content))
        checks.append(self._check_has_findings(research_content))
        checks.append(self._check_has_sources(research_content))
        checks.append(self._check_has_status(research_content))
        checks.append(self._check_minimum_length(research_content, min_words=300))
        checks.append(self._check_section_balance(research_content))

        # Calculate structural score
        structural_score = sum(c.score for c in checks) / len(checks)

        # Quality checks (LLM-as-judge, only if client provided)
        quality_score = structural_score  # Default to structural score
        if self.llm_client:
            quality_check = self._evaluate_research_quality(research_content)
            checks.append(quality_check)
            # Weight: 70% structural, 30% quality
            quality_score = 0.7 * structural_score + 0.3 * quality_check.score

        overall_score = quality_score
        passed = overall_score >= self.pass_threshold

        if not passed:
            warnings.append(
                f"Overall score {overall_score:.2f} below threshold {self.pass_threshold}"
            )

        return CompletenessResult(
            passed=passed,
            overall_score=overall_score,
            checks=checks,
            warnings=warnings,
        )

    def evaluate_build_output(self, build_dir: Path) -> CompletenessResult:
        """
        Evaluate build output completeness.

        Args:
            build_dir: Directory containing build artifacts

        Returns:
            CompletenessResult with structural checks
        """
        checks: List[CompletenessCheck] = []
        warnings: List[str] = []

        # Check for expected files
        checks.append(self._check_file_exists(build_dir / "README.md", "README.md"))
        checks.append(self._check_file_exists(build_dir / "pyproject.toml", "pyproject.toml"))

        # Check for source code
        src_files = list(build_dir.rglob("*.py"))
        checks.append(
            CompletenessCheck(
                check_name="source_files",
                passed=len(src_files) > 0,
                score=1.0 if len(src_files) > 0 else 0.0,
                details=f"Found {len(src_files)} Python files",
            )
        )

        # Check for tests
        test_files = list(build_dir.rglob("test_*.py"))
        checks.append(
            CompletenessCheck(
                check_name="test_files",
                passed=len(test_files) > 0,
                score=1.0 if len(test_files) > 0 else 0.0,
                details=f"Found {len(test_files)} test files",
            )
        )

        overall_score = sum(c.score for c in checks) / len(checks) if checks else 0.0
        passed = overall_score >= self.pass_threshold

        return CompletenessResult(
            passed=passed,
            overall_score=overall_score,
            checks=checks,
            warnings=warnings,
        )

    def _check_has_overview(self, content: str) -> CompletenessCheck:
        """Check for overview/summary section."""
        patterns = [
            r"##?\s*Overview",
            r"##?\s*Summary",
            r"##?\s*Introduction",
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return CompletenessCheck(
                    check_name="has_overview",
                    passed=True,
                    score=1.0,
                    details="Overview section found",
                )

        return CompletenessCheck(
            check_name="has_overview",
            passed=False,
            score=0.0,
            details="No overview section found",
        )

    def _check_has_findings(self, content: str) -> CompletenessCheck:
        """Check for findings/results section."""
        # Count major sections (## and ###)
        h2_sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        h3_sections = re.findall(r"^###\s+(.+)$", content, re.MULTILINE)
        all_sections = h2_sections + h3_sections

        # Exclude metadata sections
        content_sections = [
            s
            for s in all_sections
            if not any(
                keyword in s.lower()
                for keyword in ["overview", "summary", "sources", "status", "metadata"]
            )
        ]

        if len(content_sections) >= 3:
            return CompletenessCheck(
                check_name="has_findings",
                passed=True,
                score=1.0,
                details=f"Found {len(content_sections)} content sections",
            )
        else:
            return CompletenessCheck(
                check_name="has_findings",
                passed=False,
                score=len(content_sections) / 3.0,
                details=f"Only {len(content_sections)} content sections (expected 3+)",
            )

    def _check_has_sources(self, content: str) -> CompletenessCheck:
        """Check for sources section."""
        sources_pattern = re.compile(r"##?\s*Sources?\s*$", re.MULTILINE | re.IGNORECASE)

        if sources_pattern.search(content):
            # Count URLs in sources
            url_pattern = re.compile(r"https?://[^\s\)]+")
            urls = url_pattern.findall(content)

            if len(urls) >= 5:
                return CompletenessCheck(
                    check_name="has_sources",
                    passed=True,
                    score=1.0,
                    details=f"Sources section with {len(urls)} URLs",
                )
            else:
                return CompletenessCheck(
                    check_name="has_sources",
                    passed=len(urls) >= 3,
                    score=len(urls) / 5.0,
                    details=f"Sources section with only {len(urls)} URLs (expected 5+)",
                )
        else:
            return CompletenessCheck(
                check_name="has_sources",
                passed=False,
                score=0.0,
                details="No sources section found",
            )

    def _check_has_status(self, content: str) -> CompletenessCheck:
        """Check for status field."""
        status_patterns = [
            r"\*\*Status:\*\*\s*\w+",
            r"Status:\s*\w+",
            r"##?\s*Status",
        ]

        for pattern in status_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return CompletenessCheck(
                    check_name="has_status",
                    passed=True,
                    score=1.0,
                    details="Status field found",
                )

        return CompletenessCheck(
            check_name="has_status",
            passed=False,
            score=0.0,
            details="No status field found",
        )

    def _check_minimum_length(self, content: str, min_words: int) -> CompletenessCheck:
        """Check for minimum content length."""
        words = len(content.split())

        if words >= min_words:
            return CompletenessCheck(
                check_name="minimum_length",
                passed=True,
                score=1.0,
                details=f"{words} words (minimum {min_words})",
            )
        else:
            return CompletenessCheck(
                check_name="minimum_length",
                passed=False,
                score=words / min_words,
                details=f"Only {words} words (minimum {min_words})",
            )

    def _check_section_balance(self, content: str) -> CompletenessCheck:
        """Check that sections have reasonable content."""
        # Split by both ## and ### to get all sections
        sections = re.split(r"^###?\s+", content, flags=re.MULTILINE)

        if len(sections) < 2:
            return CompletenessCheck(
                check_name="section_balance",
                passed=False,
                score=0.0,
                details="No sections found",
            )

        # Check each section has at least 50 words
        short_sections = 0
        for section in sections[1:]:  # Skip pre-first-section content
            words = len(section.split())
            if words < 50:
                short_sections += 1

        balance_score = 1.0 - (short_sections / len(sections))

        return CompletenessCheck(
            check_name="section_balance",
            passed=short_sections == 0,
            score=max(0.0, balance_score),
            details=f"{short_sections} sections under 50 words",
        )

    def _check_file_exists(self, file_path: Path, name: str) -> CompletenessCheck:
        """Check if a file exists."""
        if file_path.exists():
            size = file_path.stat().st_size
            return CompletenessCheck(
                check_name=f"file_exists_{name}",
                passed=True,
                score=1.0,
                details=f"File exists ({size} bytes)",
            )
        else:
            return CompletenessCheck(
                check_name=f"file_exists_{name}",
                passed=False,
                score=0.0,
                details="File does not exist",
            )

    def _evaluate_research_quality(self, research_content: str) -> CompletenessCheck:
        """
        Use LLM-as-judge to evaluate research quality.

        This is reserved for genuinely subjective assessment that cannot be
        done deterministically.
        """
        if not self.llm_client:
            return CompletenessCheck(
                check_name="llm_quality_assessment",
                passed=True,
                score=1.0,
                details="LLM judge not configured, skipping",
            )

        prompt = f"""Evaluate the quality of this research brief on a scale of 0.0 to 1.0.

Consider:
- Clarity and organization of findings
- Depth of analysis (not just summary)
- Practical applicability of insights
- Critical evaluation (pros/cons, tradeoffs)

Respond with ONLY a JSON object in this format:
{{"score": 0.85, "reasoning": "Clear findings with practical examples..."}}

Research to evaluate:

{research_content[:4000]}
"""

        try:
            response = self.llm_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            result = json.loads(response_text)

            score = float(result.get("score", 0.5))
            reasoning = result.get("reasoning", "No reasoning provided")

            return CompletenessCheck(
                check_name="llm_quality_assessment",
                passed=score >= 0.7,
                score=score,
                details=f"LLM judge: {reasoning}",
            )

        except Exception as e:
            return CompletenessCheck(
                check_name="llm_quality_assessment",
                passed=True,
                score=0.7,
                details=f"LLM evaluation failed: {e}",
            )


def evaluate_research_completeness(research_file: Path) -> Dict[str, Any]:
    """
    Evaluate research completeness from a file.

    Args:
        research_file: Path to research markdown file

    Returns:
        Dictionary with evaluation results
    """
    with open(research_file) as f:
        content = f.read()

    # Initialize LLM client if API key is available
    llm_client = None
    if os.getenv("ANTHROPIC_API_KEY"):
        llm_client = Anthropic()

    evaluator = CompletenessEvaluator(llm_client=llm_client)
    result = evaluator.evaluate_research_output(content)

    return {
        "research_file": str(research_file),
        "passed": result.passed,
        "overall_score": result.overall_score,
        "warnings": result.warnings,
        "checks": [c.model_dump() for c in result.checks],
    }


def evaluate_trace_completeness(trace_file: Path) -> Dict[str, Any]:
    """
    Evaluate completeness of outputs in a trace.

    Args:
        trace_file: Path to JSON trace file

    Returns:
        Dictionary with evaluation results
    """
    with open(trace_file) as f:
        trace = json.load(f)

    # Extract final output from trace
    messages = trace.get("messages", [])
    final_content = ""

    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("content"):
            final_content = message["content"]
            break

    if not final_content:
        return {
            "trace_file": str(trace_file),
            "passed": False,
            "overall_score": 0.0,
            "warnings": ["No final output found in trace"],
            "checks": [],
        }

    # Initialize LLM client if API key is available
    llm_client = None
    if os.getenv("ANTHROPIC_API_KEY"):
        llm_client = Anthropic()

    evaluator = CompletenessEvaluator(llm_client=llm_client)
    result = evaluator.evaluate_research_output(final_content)

    return {
        "trace_file": str(trace_file),
        "passed": result.passed,
        "overall_score": result.overall_score,
        "warnings": result.warnings,
        "checks": [c.model_dump() for c in result.checks],
    }
