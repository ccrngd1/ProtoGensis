"""
Handoff delivery reliability evaluator.

Validates handoff JSON structure, checks delivery to correct directory,
and verifies timing SLAs. Deterministic evaluation only.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from dateutil.parser import parse as parse_datetime


class HandoffSchema(BaseModel):
    """Expected schema for CABAL handoff files."""

    from_agent: str = Field(..., alias="from")
    type: str
    task: str
    priority: str
    timestamp: str
    target: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    deadline: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid_priorities = ["low", "normal", "high", "critical"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of {valid_priorities}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = ["request", "response", "status", "alert"]
        if v not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}")
        return v

    @field_validator("timestamp", "deadline")
    @classmethod
    def validate_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            parse_datetime(v)
            return v
        except Exception:
            raise ValueError(f"Invalid ISO timestamp format: {v}")


class HandoffResult(BaseModel):
    """Result from evaluating a handoff."""

    passed: bool
    handoff_file: str
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}


class HandoffEvaluator:
    """Evaluates handoff delivery reliability."""

    def __init__(self, handoff_dir: Optional[Path] = None):
        """
        Initialize the evaluator.

        Args:
            handoff_dir: Directory where handoffs are delivered. Defaults to
                         /root/.openclaw/handoffs
        """
        self.handoff_dir = handoff_dir or Path("/root/.openclaw/handoffs")

    def evaluate_handoff_file(self, handoff_file: Path) -> HandoffResult:
        """
        Evaluate a single handoff file.

        Args:
            handoff_file: Path to handoff JSON file

        Returns:
            HandoffResult with validation details
        """
        errors = []
        warnings = []
        metadata = {}

        # Check file exists
        if not handoff_file.exists():
            return HandoffResult(
                passed=False,
                handoff_file=str(handoff_file),
                errors=[f"Handoff file does not exist: {handoff_file}"],
            )

        # Load and parse JSON
        try:
            with open(handoff_file) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return HandoffResult(
                passed=False,
                handoff_file=str(handoff_file),
                errors=[f"Invalid JSON: {e}"],
            )

        # Validate against schema
        try:
            handoff = HandoffSchema(**data)
            metadata["from_agent"] = handoff.from_agent
            metadata["type"] = handoff.type
            metadata["priority"] = handoff.priority
            metadata["timestamp"] = handoff.timestamp
        except ValidationError as e:
            errors.extend([f"Schema validation error: {err['msg']}" for err in e.errors()])

        # Check file naming convention
        filename = handoff_file.name
        if not self._validate_filename(filename, data.get("type")):
            warnings.append(
                f"Filename '{filename}' does not match expected pattern "
                f"for type '{data.get('type')}'"
            )

        # Check delivery location
        if not self._validate_delivery_location(handoff_file):
            errors.append(
                f"Handoff delivered to unexpected location: {handoff_file.parent}"
            )

        # Check timestamp freshness
        if "timestamp" in data:
            try:
                timestamp = parse_datetime(data["timestamp"])
                age = datetime.now() - timestamp.replace(tzinfo=None)
                metadata["age_minutes"] = age.total_seconds() / 60

                if age > timedelta(hours=24):
                    warnings.append(f"Handoff is stale (age: {age})")
            except Exception as e:
                errors.append(f"Could not parse timestamp: {e}")

        return HandoffResult(
            passed=len(errors) == 0,
            handoff_file=str(handoff_file),
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def evaluate_trace_handoffs(self, trace: Dict[str, Any]) -> List[HandoffResult]:
        """
        Evaluate all handoffs created during a trace.

        Args:
            trace: Agent execution trace

        Returns:
            List of HandoffResult objects
        """
        results = []

        # Look for handoff creation in tool calls
        messages = trace.get("messages", [])
        for message in messages:
            if message.get("role") == "assistant" and "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    if tool_call.get("function", {}).get("name") == "handoff_create":
                        args = tool_call.get("function", {}).get("arguments", {})
                        if isinstance(args, str):
                            args = json.loads(args)

                        # Simulate handoff file path
                        handoff_type = args.get("type", "request")
                        filename = f"{handoff_type}-test.json"
                        handoff_path = self.handoff_dir / filename

                        # Evaluate the handoff data structure
                        result = self._evaluate_handoff_data(args, str(handoff_path))
                        results.append(result)

        return results

    def _evaluate_handoff_data(
        self, data: Dict[str, Any], handoff_path: str
    ) -> HandoffResult:
        """Evaluate handoff data structure without requiring file existence."""
        errors = []
        warnings = []
        metadata = {}

        try:
            handoff = HandoffSchema(**data)
            metadata["from_agent"] = handoff.from_agent
            metadata["type"] = handoff.type
            metadata["priority"] = handoff.priority
        except ValidationError as e:
            errors.extend([f"Schema validation error: {err['msg']}" for err in e.errors()])

        return HandoffResult(
            passed=len(errors) == 0,
            handoff_file=handoff_path,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

    def _validate_filename(self, filename: str, handoff_type: Optional[str]) -> bool:
        """Check if filename follows expected naming convention."""
        if not handoff_type:
            return True  # Can't validate without type

        expected_prefix = f"{handoff_type}-"
        return filename.startswith(expected_prefix) and filename.endswith(".json")

    def _validate_delivery_location(self, handoff_file: Path) -> bool:
        """Check if handoff was delivered to correct directory."""
        # Check if file is in handoff_dir or a subdirectory
        try:
            handoff_file.relative_to(self.handoff_dir)
            return True
        except ValueError:
            return False

    def check_handoff_sla(
        self,
        request_time: datetime,
        delivery_time: datetime,
        max_cycles: int = 2,
        cycle_duration_minutes: int = 60,
    ) -> bool:
        """
        Check if handoff was delivered within SLA.

        Args:
            request_time: When the handoff was requested
            delivery_time: When the handoff was delivered
            max_cycles: Maximum number of heartbeat cycles allowed
            cycle_duration_minutes: Duration of one heartbeat cycle

        Returns:
            True if within SLA, False otherwise
        """
        max_duration = timedelta(minutes=max_cycles * cycle_duration_minutes)
        actual_duration = delivery_time - request_time
        return actual_duration <= max_duration


def evaluate_handoff_directory(handoff_dir: Path) -> Dict[str, Any]:
    """
    Evaluate all handoff files in a directory.

    Args:
        handoff_dir: Directory containing handoff files

    Returns:
        Dictionary with evaluation results
    """
    evaluator = HandoffEvaluator(handoff_dir)
    results = []

    for handoff_file in handoff_dir.glob("*.json"):
        result = evaluator.evaluate_handoff_file(handoff_file)
        results.append(result)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    return {
        "handoff_dir": str(handoff_dir),
        "total_handoffs": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "results": [r.model_dump() for r in results],
    }


def evaluate_trace_handoffs(trace_file: Path) -> Dict[str, Any]:
    """
    Evaluate handoffs created during a trace.

    Args:
        trace_file: Path to JSON trace file

    Returns:
        Dictionary with evaluation results
    """
    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = HandoffEvaluator()
    results = evaluator.evaluate_trace_handoffs(trace)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    return {
        "trace_file": str(trace_file),
        "total_handoffs": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "results": [r.model_dump() for r in results],
    }
