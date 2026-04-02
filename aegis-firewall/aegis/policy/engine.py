"""YAML-based policy engine with first-match-wins rule evaluation."""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path


class PolicyEngine:
    """
    Policy engine that evaluates tool calls against YAML-defined rules.

    Rules are evaluated in order (first-match-wins).
    Each rule can result in: allow, deny, or escalate.
    """

    def __init__(self, policy_path: str):
        """
        Initialize policy engine.

        Args:
            policy_path: Path to YAML policy file
        """
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        """Load and parse YAML policy file."""
        with open(self.policy_path, 'r') as f:
            policy = yaml.safe_load(f)

        # Validate policy structure
        if not isinstance(policy, dict):
            raise ValueError("Policy must be a dictionary")

        if 'rules' not in policy:
            raise ValueError("Policy must contain 'rules' key")

        return policy

    def evaluate(
        self,
        tool_name: str,
        scanner_results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a tool call against the policy.

        Args:
            tool_name: Name of the tool being called
            scanner_results: Results from all scanners
            metadata: Additional metadata (agent_id, etc.)

        Returns:
            Dict with 'action' (allow/deny/escalate), 'reason', 'rule'
        """
        metadata = metadata or {}

        # Get policy configuration
        default_action = self.policy.get('default_action', 'deny')
        rules = self.policy.get('rules', [])

        # Aggregate scanner findings
        max_severity = self._get_max_severity(scanner_results)
        detected_threats = [
            r['scanner'] for r in scanner_results if r.get('detected')
        ]

        # Evaluate rules in order (first-match-wins)
        for i, rule in enumerate(rules):
            if self._rule_matches(rule, tool_name, max_severity, detected_threats, metadata):
                action = rule.get('action', 'deny')
                reason = rule.get('reason', f"Matched rule {i+1}")

                return {
                    'action': action,
                    'reason': reason,
                    'rule_index': i,
                    'rule_name': rule.get('name', f'rule_{i}'),
                    'max_severity': max_severity,
                    'detected_threats': detected_threats
                }

        # No rule matched, use default action
        return {
            'action': default_action,
            'reason': f"No rule matched, using default action: {default_action}",
            'rule_index': -1,
            'rule_name': 'default',
            'max_severity': max_severity,
            'detected_threats': detected_threats
        }

    def _rule_matches(
        self,
        rule: Dict[str, Any],
        tool_name: str,
        max_severity: str,
        detected_threats: List[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Check if a rule matches the current context.

        Args:
            rule: Rule dictionary from policy
            tool_name: Tool being called
            max_severity: Maximum severity from scanners
            detected_threats: List of scanner names that detected threats
            metadata: Additional metadata

        Returns:
            True if rule matches
        """
        # Check tool name match
        if 'tools' in rule:
            tool_patterns = rule['tools']
            if tool_patterns != '*' and tool_name not in tool_patterns:
                return False

        # Check severity threshold
        if 'min_severity' in rule:
            min_sev = rule['min_severity']
            severity_order = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
            if severity_order.get(max_severity, 0) < severity_order.get(min_sev, 0):
                return False

        # Check specific threat types
        if 'threat_types' in rule:
            required_threats = rule['threat_types']
            if not any(t in detected_threats for t in required_threats):
                return False

        # Check agent whitelist/blacklist
        if 'agents' in rule and 'agent_id' in metadata:
            agent_list = rule['agents']
            if isinstance(agent_list, list):
                if metadata['agent_id'] not in agent_list:
                    return False

        # All conditions matched
        return True

    def _get_max_severity(self, scanner_results: List[Dict[str, Any]]) -> str:
        """
        Get maximum severity across all scanner results.

        Args:
            scanner_results: List of scanner result dicts

        Returns:
            Maximum severity level (none/low/medium/high)
        """
        severity_order = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}
        max_sev = 'none'
        max_val = 0

        for result in scanner_results:
            sev = result.get('severity', 'none')
            val = severity_order.get(sev, 0)
            if val > max_val:
                max_val = val
                max_sev = sev

        return max_sev

    def reload(self):
        """Reload policy from disk."""
        self.policy = self._load_policy()
