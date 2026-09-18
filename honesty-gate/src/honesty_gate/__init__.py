"""HonestyGate: CI-native coverage-honesty gate for code-review agents.

Compares three sets for a review session:
  asked            - files the agent was asked to review
  actual_accessed  - files the agent verifiably opened (hooks or transcript)
  claims           - per-file claims parsed from the agent's final response

and classifies each asked file into one of four honesty classes:
  HONEST, OMISSION, FALSE_CLAIM, SILENT_SKIP.

Coverage ground truth never comes from model self-report.
"""

__version__ = "0.1.0"

from .classify import (  # noqa: F401
    HONEST,
    OMISSION,
    FALSE_CLAIM,
    SILENT_SKIP,
    classify_run,
    gate,
)
