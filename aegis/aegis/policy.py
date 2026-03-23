"""YAML-based policy engine for AEGIS firewall."""

import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path


class PolicyEngine:
    """YAML policy engine with first-match-wins rule evaluation."""

    def __init__(self, policy_path: Optional[Path] = None):
        """
        Initialize policy engine.

        Args:
            policy_path: Path to YAML policy file, or None to use default
        """
        self.policy_path = policy_path
        self.policy: Dict[str, Any] = {}

        if policy_path:
            self.load_policy(policy_path)

    def load_policy(self, policy_path: Path) -> None:
        """Load policy from YAML file."""
        with open(policy_path, 'r') as f:
            self.policy = yaml.safe_load(f)

    def evaluate(self, tool_call: Dict[str, Any], scan_results: List[Dict[str, Any]]) -> str:
        """
        Evaluate tool call against policy rules.

        Args:
            tool_call: MCP tool call dict with 'name' and 'arguments'
            scan_results: List of scanner detection results

        Returns:
            Decision: 'allow', 'deny', or 'escalate'
        """
        tool_name = tool_call.get('name', '')

        # Get rules from policy (defaults to empty list)
        rules = self.policy.get('rules', [])

        # First-match-wins evaluation
        for rule in rules:
            if self._matches_rule(rule, tool_name, scan_results):
                action = rule.get('action', 'deny')
                return action

        # Default action if no rules match
        default_action = self.policy.get('default_action', 'allow')
        return default_action

    def _matches_rule(self, rule: Dict[str, Any], tool_name: str, scan_results: List[Dict[str, Any]]) -> bool:
        """Check if rule matches the current tool call and scan results."""
        # Check tool name pattern
        if 'tool_pattern' in rule:
            import re
            pattern = rule['tool_pattern']
            if not re.search(pattern, tool_name, re.IGNORECASE):
                return False

        # Check specific tool names
        if 'tools' in rule:
            tool_list = rule['tools']
            if tool_name not in tool_list:
                return False

        # Check threat types
        if 'threat_types' in rule:
            required_threats = set(rule['threat_types'])
            detected_threats = {result['type'] for result in scan_results}

            # Match if any required threat is detected
            if not required_threats.intersection(detected_threats):
                return False

        # Check severity levels
        if 'min_severity' in rule:
            min_severity = rule['min_severity']
            severity_levels = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
            min_level = severity_levels.get(min_severity, 0)

            # Check if any scan result meets minimum severity
            has_severe_enough = any(
                severity_levels.get(result.get('severity', 'low'), 0) >= min_level
                for result in scan_results
            )

            if not has_severe_enough:
                return False

        # All conditions matched
        return True


def get_builtin_policy_path(profile: str) -> Path:
    """Get path to built-in policy file."""
    policies_dir = Path(__file__).parent.parent / 'policies'
    return policies_dir / f'{profile}.yaml'
