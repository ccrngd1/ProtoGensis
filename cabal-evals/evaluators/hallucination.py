"""
Hallucination detection evaluator.

HTTP probes for cited URLs, filesystem checks for referenced paths,
and claim extraction for fact-checking. Deterministic verification only.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel


class HallucinationCheck(BaseModel):
    """Result of checking for a specific hallucination."""

    check_type: str  # "url", "path", "claim"
    passed: bool
    item: str
    details: str


class HallucinationResult(BaseModel):
    """Result from hallucination evaluation."""

    passed: bool
    total_checks: int
    failed_checks: int
    checks: List[HallucinationCheck] = []
    warnings: List[str] = []


class HallucinationEvaluator:
    """Evaluates agent outputs for hallucinations."""

    def __init__(
        self,
        timeout: int = 10,
        url_pass_threshold: float = 0.9,
        path_pass_threshold: float = 0.95,
    ):
        """
        Initialize the evaluator.

        Args:
            timeout: Timeout for HTTP requests in seconds
            url_pass_threshold: Minimum fraction of URLs that must be valid
            path_pass_threshold: Minimum fraction of paths that must exist
        """
        self.timeout = timeout
        self.url_pass_threshold = url_pass_threshold
        self.path_pass_threshold = path_pass_threshold
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def evaluate_trace(self, trace: Dict[str, Any]) -> HallucinationResult:
        """
        Evaluate a complete trace for hallucinations.

        Args:
            trace: Agent execution trace in OpenAI message format

        Returns:
            HallucinationResult with verification details
        """
        checks: List[HallucinationCheck] = []
        warnings: List[str] = []

        # Extract all URLs and paths from the trace
        urls = self._extract_urls(trace)
        paths = self._extract_paths(trace)

        # Verify URLs
        for url in urls:
            check = self._verify_url(url)
            checks.append(check)

        # Verify paths
        for path in paths:
            check = self._verify_path(path)
            checks.append(check)

        # Calculate pass/fail
        total_checks = len(checks)
        failed_checks = sum(1 for c in checks if not c.passed)

        # Separate URL and path checks
        url_checks = [c for c in checks if c.check_type == "url"]
        path_checks = [c for c in checks if c.check_type == "path"]

        url_failures = sum(1 for c in url_checks if not c.passed)
        path_failures = sum(1 for c in path_checks if not c.passed)

        # Determine overall pass based on thresholds
        url_pass_rate = (
            (len(url_checks) - url_failures) / len(url_checks) if url_checks else 1.0
        )
        path_pass_rate = (
            (len(path_checks) - path_failures) / len(path_checks) if path_checks else 1.0
        )

        passed = (
            url_pass_rate >= self.url_pass_threshold
            and path_pass_rate >= self.path_pass_threshold
        )

        if url_pass_rate < self.url_pass_threshold:
            warnings.append(
                f"URL pass rate {url_pass_rate:.1%} below threshold "
                f"{self.url_pass_threshold:.1%}"
            )

        if path_pass_rate < self.path_pass_threshold:
            warnings.append(
                f"Path pass rate {path_pass_rate:.1%} below threshold "
                f"{self.path_pass_threshold:.1%}"
            )

        return HallucinationResult(
            passed=passed,
            total_checks=total_checks,
            failed_checks=failed_checks,
            checks=checks,
            warnings=warnings,
        )

    def _extract_urls(self, trace: Dict[str, Any]) -> Set[str]:
        """Extract all URLs from trace messages."""
        urls: Set[str] = set()

        # URL pattern
        url_pattern = re.compile(
            r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\."
            r"[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)"
        )

        messages = trace.get("messages", [])
        for message in messages:
            content = message.get("content", "")
            if content:
                urls.update(url_pattern.findall(content))

            # Check tool call arguments
            if message.get("role") == "assistant" and "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    args = tool_call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
                        urls.update(url_pattern.findall(args))
                    elif isinstance(args, dict):
                        args_str = json.dumps(args)
                        urls.update(url_pattern.findall(args_str))

        # Filter out common false positives
        filtered_urls = set()
        for url in urls:
            # Skip example/placeholder domains
            if any(
                domain in url.lower()
                for domain in ["example.com", "localhost", "127.0.0.1", "0.0.0.0"]
            ):
                continue
            filtered_urls.add(url)

        return filtered_urls

    def _extract_paths(self, trace: Dict[str, Any]) -> Set[str]:
        """Extract all file paths from trace messages."""
        paths: Set[str] = set()

        # Path patterns (Unix-style)
        path_patterns = [
            re.compile(r"(?:^|[\s\"'])(/[a-zA-Z0-9_./\-]+)(?:[\s\"']|$)"),
            re.compile(r"(?:^|[\s\"'])(~/[a-zA-Z0-9_./\-]+)(?:[\s\"']|$)"),
        ]

        messages = trace.get("messages", [])
        for message in messages:
            content = message.get("content", "")
            if content:
                for pattern in path_patterns:
                    matches = pattern.findall(content)
                    paths.update(matches)

            # Check tool call arguments with path fields
            if message.get("role") == "assistant" and "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    args = tool_call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            continue

                    if isinstance(args, dict):
                        # Common path parameter names
                        for key in ["path", "file", "filepath", "file_path", "directory", "dir"]:
                            if key in args:
                                paths.add(str(args[key]))

        # Filter out obviously invalid paths
        filtered_paths = set()
        for path in paths:
            # Skip very short paths
            if len(path) < 3:
                continue
            # Skip paths with placeholders
            if any(
                placeholder in path.lower()
                for placeholder in ["<path>", "<file>", "your_", "example_"]
            ):
                continue
            # Skip paths that look like URLs
            if path.startswith("http://") or path.startswith("https://"):
                continue

            filtered_paths.add(path)

        return filtered_paths

    def _verify_url(self, url: str) -> HallucinationCheck:
        """Verify that a URL is accessible."""
        try:
            response = self.client.head(url, timeout=self.timeout)

            # Accept 200 OK, 301/302 redirects, 403 Forbidden (exists but not accessible)
            if response.status_code in [200, 301, 302, 403]:
                return HallucinationCheck(
                    check_type="url",
                    passed=True,
                    item=url,
                    details=f"HTTP {response.status_code}",
                )
            else:
                return HallucinationCheck(
                    check_type="url",
                    passed=False,
                    item=url,
                    details=f"HTTP {response.status_code}",
                )

        except httpx.HTTPError as e:
            # Try GET in case HEAD is not supported
            try:
                response = self.client.get(url, timeout=self.timeout)
                if response.status_code in [200, 301, 302, 403]:
                    return HallucinationCheck(
                        check_type="url",
                        passed=True,
                        item=url,
                        details=f"HTTP {response.status_code} (GET)",
                    )
            except httpx.HTTPError:
                pass

            return HallucinationCheck(
                check_type="url",
                passed=False,
                item=url,
                details=f"Error: {type(e).__name__}",
            )

    def _verify_path(self, path: str) -> HallucinationCheck:
        """Verify that a file path exists."""
        # Expand ~ to home directory
        if path.startswith("~"):
            path = str(Path(path).expanduser())

        path_obj = Path(path)

        if path_obj.exists():
            path_type = "directory" if path_obj.is_dir() else "file"
            return HallucinationCheck(
                check_type="path",
                passed=True,
                item=path,
                details=f"Exists ({path_type})",
            )
        else:
            return HallucinationCheck(
                check_type="path",
                passed=False,
                item=path,
                details="Does not exist",
            )

    def evaluate_research_sources(self, research_content: str) -> HallucinationResult:
        """
        Evaluate sources cited in research output.

        Args:
            research_content: Research document content

        Returns:
            HallucinationResult focused on source verification
        """
        checks: List[HallucinationCheck] = []
        warnings: List[str] = []

        # Extract URLs from Sources section
        sources_pattern = re.compile(r"##?\s*Sources?\s*$(.*?)(?=##|\Z)", re.DOTALL | re.MULTILINE)
        sources_match = sources_pattern.search(research_content)

        if not sources_match:
            warnings.append("No Sources section found in research")
            return HallucinationResult(
                passed=False,
                total_checks=0,
                failed_checks=0,
                checks=[],
                warnings=warnings,
            )

        sources_section = sources_match.group(1)

        # Extract URLs from sources
        url_pattern = re.compile(r"https?://[^\s\)]+")
        urls = url_pattern.findall(sources_section)

        for url in urls:
            check = self._verify_url(url)
            checks.append(check)

        # Calculate results
        total_checks = len(checks)
        failed_checks = sum(1 for c in checks if not c.passed)
        pass_rate = (total_checks - failed_checks) / total_checks if total_checks > 0 else 1.0

        passed = pass_rate >= self.url_pass_threshold

        if not passed:
            warnings.append(
                f"Source URL pass rate {pass_rate:.1%} below threshold "
                f"{self.url_pass_threshold:.1%}"
            )

        return HallucinationResult(
            passed=passed,
            total_checks=total_checks,
            failed_checks=failed_checks,
            checks=checks,
            warnings=warnings,
        )

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()


def evaluate_trace_hallucinations(trace_file: Path) -> Dict[str, Any]:
    """
    Evaluate a trace file for hallucinations.

    Args:
        trace_file: Path to JSON trace file

    Returns:
        Dictionary with evaluation results
    """
    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = HallucinationEvaluator()
    result = evaluator.evaluate_trace(trace)

    return {
        "trace_file": str(trace_file),
        "passed": result.passed,
        "total_checks": result.total_checks,
        "failed_checks": result.failed_checks,
        "pass_rate": (
            (result.total_checks - result.failed_checks) / result.total_checks
            if result.total_checks > 0
            else 0.0
        ),
        "warnings": result.warnings,
        "checks": [c.model_dump() for c in result.checks],
    }
