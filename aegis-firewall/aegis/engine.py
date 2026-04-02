"""Decision engine that aggregates scanner results and policy evaluation."""

from typing import Dict, Any, List, Optional
from .scanners import (
    extract_strings,
    ShellInjectionScanner,
    PathTraversalScanner,
    PIIDetector,
    SecretScanner,
    SQLInjectionScanner
)
from .policy import PolicyEngine


class DecisionEngine:
    """
    Main decision engine that coordinates scanning and policy evaluation.

    Pipeline:
    1. Extract strings from tool call arguments
    2. Run all scanners
    3. Evaluate results against policy
    4. Return Allow/Deny/Escalate decision
    """

    def __init__(self, policy_path: str, scanner_config: Optional[Dict[str, Any]] = None):
        """
        Initialize decision engine.

        Args:
            policy_path: Path to YAML policy file
            scanner_config: Optional configuration for scanners
        """
        self.policy_engine = PolicyEngine(policy_path)

        # Initialize scanners with optional config
        config = scanner_config or {}
        self.scanners = {
            'shell_injection': ShellInjectionScanner(
                severity_threshold=config.get('shell_threshold', 'medium')
            ),
            'path_traversal': PathTraversalScanner(
                allow_absolute=config.get('allow_absolute_paths', False)
            ),
            'pii_detector': PIIDetector(
                sensitivity=config.get('pii_sensitivity', 'medium')
            ),
            'secret_scanner': SecretScanner(
                check_entropy=config.get('check_entropy', True)
            ),
            'sql_injection': SQLInjectionScanner(
                strict=config.get('sql_strict', True)
            )
        }

    def evaluate(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a tool call and return a decision.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool call arguments (nested dict/list structure)
            metadata: Optional metadata (agent_id, session_id, etc.)

        Returns:
            Decision dict with keys:
            - action: 'allow', 'deny', or 'escalate'
            - reason: Human-readable explanation
            - scanner_results: Results from all scanners
            - policy_decision: Policy evaluation result
            - strings_extracted: Number of strings analyzed
        """
        # Step 1: Extract strings from arguments
        strings = extract_strings(arguments)

        # Step 2: Run all scanners
        scanner_results = []
        for scanner_name, scanner in self.scanners.items():
            try:
                result = scanner.scan(strings)
                scanner_results.append(result)
            except Exception as e:
                # Log error but continue with other scanners
                scanner_results.append({
                    'scanner': scanner_name,
                    'detected': False,
                    'severity': 'none',
                    'error': str(e),
                    'findings': []
                })

        # Step 3: Evaluate against policy
        policy_decision = self.policy_engine.evaluate(
            tool_name=tool_name,
            scanner_results=scanner_results,
            metadata=metadata
        )

        # Step 4: Build final decision
        decision = {
            'action': policy_decision['action'],
            'reason': policy_decision['reason'],
            'tool_name': tool_name,
            'scanner_results': scanner_results,
            'policy_decision': policy_decision,
            'strings_extracted': len(strings),
            'metadata': metadata or {}
        }

        return decision

    def reload_policy(self):
        """Reload policy from disk."""
        self.policy_engine.reload()

    def get_scanner_summary(self, scanner_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of scanner results.

        Args:
            scanner_results: List of scanner result dicts

        Returns:
            Summary dict with threat counts and severity
        """
        total_findings = sum(len(r.get('findings', [])) for r in scanner_results)
        detected_scanners = [r['scanner'] for r in scanner_results if r.get('detected')]

        severity_counts = {'none': 0, 'low': 0, 'medium': 0, 'high': 0}
        for result in scanner_results:
            sev = result.get('severity', 'none')
            severity_counts[sev] += 1

        return {
            'total_findings': total_findings,
            'scanners_triggered': len(detected_scanners),
            'detected_by': detected_scanners,
            'severity_counts': severity_counts
        }
