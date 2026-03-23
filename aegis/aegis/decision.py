"""Decision engine for AEGIS firewall."""

from typing import Dict, Any, List, Tuple
from .extractor import extract_strings
from .scanners import (
    ShellInjectionScanner,
    PathTraversalScanner,
    PIIScanner,
    SecretScanner,
    SQLInjectionScanner,
)
from .policy import PolicyEngine


class DecisionEngine:
    """Three-stage decision pipeline: extract -> scan -> policy."""

    def __init__(self, policy_engine: PolicyEngine):
        """
        Initialize decision engine.

        Args:
            policy_engine: Configured PolicyEngine instance
        """
        self.policy_engine = policy_engine

        # Initialize all scanners
        self.scanners = [
            ShellInjectionScanner(),
            PathTraversalScanner(),
            PIIScanner(),
            SecretScanner(),
            SQLInjectionScanner(),
        ]

    def decide(self, tool_call: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Execute three-stage decision pipeline.

        Args:
            tool_call: MCP tool call dict with 'name' and 'arguments'

        Returns:
            Tuple of (decision, scan_results) where decision is 'allow', 'deny', or 'escalate'
        """
        # Stage 1: Deep string extraction
        arguments = tool_call.get('arguments', {})
        strings = list(extract_strings(arguments))

        # Stage 2: Content risk scanning
        scan_results = []
        for text in strings:
            for scanner in self.scanners:
                result = scanner.scan(text)
                if result:
                    scan_results.append(result)

        # Stage 3: Policy evaluation
        decision = self.policy_engine.evaluate(tool_call, scan_results)

        return decision, scan_results
