"""CoherenceProbe - Detect contradictions in multi-agent AI pipelines.

Example usage:

    from coherenceprobe import check, LogCapture

    # Capture agent outputs
    capture = LogCapture()
    capture.capture("summarizer", "text", "summary")
    capture.capture("critic", "text", "critique")

    # Check coherence
    report = check(capture.get_outputs())
    print(f"Coherence score: {report.score}")

    # Async version
    report = await acheck(outputs)
"""

__version__ = "0.1.0"

from .models import (
    AgentOutput,
    Claim,
    ContradictionPair,
    CoherenceReport,
    CoherenceConfig,
)

from .capture import (
    LogCapture,
    FileCapture,
    DecoratorCapture,
    load_outputs_from_jsonl,
    load_outputs_from_directory,
)

from .extraction import extract_claims, aextract_claims
from .detection import detect_contradictions, adetect_contradictions
from .scoring import compute_coherence_score
from .reporting import format_report, save_report


def check(
    outputs: list[AgentOutput],
    config: CoherenceConfig = None
) -> CoherenceReport:
    """Check coherence of agent outputs (main API).

    This is the primary synchronous function for checking coherence.
    It runs the full pipeline: extraction -> detection -> scoring.

    Args:
        outputs: List of agent outputs to analyze
        config: Optional configuration (uses defaults if not provided)

    Returns:
        Complete coherence report

    Example:
        >>> from coherenceprobe import check, AgentOutput
        >>> outputs = [
        ...     AgentOutput(agent="a1", timestamp="2026-01-01T00:00:00Z",
        ...                 input="x", output="The port is 8080"),
        ...     AgentOutput(agent="a2", timestamp="2026-01-01T00:00:01Z",
        ...                 input="x", output="The port is 3000"),
        ... ]
        >>> report = check(outputs)
        >>> print(report.score)
    """
    if config is None:
        config = CoherenceConfig()

    # Run pipeline
    claims = extract_claims(outputs, config)
    contradictions = detect_contradictions(claims, config)
    report = compute_coherence_score(claims, contradictions, config)

    return report


async def acheck(
    outputs: list[AgentOutput],
    config: CoherenceConfig = None
) -> CoherenceReport:
    """Async version of check.

    Args:
        outputs: List of agent outputs to analyze
        config: Optional configuration

    Returns:
        Complete coherence report

    Example:
        >>> import asyncio
        >>> from coherenceprobe import acheck, AgentOutput
        >>> async def main():
        ...     outputs = [...]
        ...     report = await acheck(outputs)
        ...     print(report.score)
        >>> asyncio.run(main())
    """
    if config is None:
        config = CoherenceConfig()

    # Run async pipeline
    claims = await aextract_claims(outputs, config)
    contradictions = await adetect_contradictions(claims, config)
    report = compute_coherence_score(claims, contradictions, config)

    return report


# Context manager for capturing outputs
class capture:
    """Context manager for capturing agent outputs.

    Example:
        >>> from coherenceprobe import capture, check
        >>> with capture() as c:
        ...     c.capture("agent1", "input", "output1")
        ...     c.capture("agent2", "input", "output2")
        ...     report = check(c.get_outputs())
    """

    def __init__(self, backend=None):
        """Initialize capture context.

        Args:
            backend: Optional capture backend (defaults to LogCapture)
        """
        self.backend = backend or LogCapture()

    def __enter__(self):
        """Enter context."""
        return self.backend

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass

    def capture(self, agent: str, input_data: str, output: str, metadata: dict = None):
        """Capture an agent output."""
        self.backend.capture(agent, input_data, output, metadata)

    def get_outputs(self) -> list[AgentOutput]:
        """Get all captured outputs."""
        return self.backend.get_outputs()


__all__ = [
    # Version
    "__version__",

    # Models
    "AgentOutput",
    "Claim",
    "ContradictionPair",
    "CoherenceReport",
    "CoherenceConfig",

    # Main API
    "check",
    "acheck",
    "capture",

    # Capture backends
    "LogCapture",
    "FileCapture",
    "DecoratorCapture",
    "load_outputs_from_jsonl",
    "load_outputs_from_directory",

    # Individual pipeline stages (for advanced use)
    "extract_claims",
    "aextract_claims",
    "detect_contradictions",
    "adetect_contradictions",
    "compute_coherence_score",

    # Reporting
    "format_report",
    "save_report",
]
