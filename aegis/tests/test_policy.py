"""Tests for policy engine."""

import pytest
from pathlib import Path
from aegis.policy import PolicyEngine, get_builtin_policy_path


class TestPolicyEngine:
    """Test YAML policy engine."""

    def test_loads_yaml_policy(self, tmp_path):
        policy_file = tmp_path / "test.yaml"
        policy_file.write_text("""
default_action: deny
rules:
  - name: allow_safe
    tools: [read_file]
    action: allow
""")
        engine = PolicyEngine(policy_file)
        assert engine.policy['default_action'] == 'deny'
        assert len(engine.policy['rules']) == 1

    def test_default_action_when_no_rules_match(self):
        engine = PolicyEngine()
        engine.policy = {'default_action': 'allow', 'rules': []}

        tool_call = {'name': 'unknown_tool', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])

        assert decision == 'allow'

    def test_deny_action_when_no_rules_match(self):
        engine = PolicyEngine()
        engine.policy = {'default_action': 'deny', 'rules': []}

        tool_call = {'name': 'unknown_tool', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])

        assert decision == 'deny'

    def test_matches_tool_name(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_dangerous', 'tools': ['rm', 'delete'], 'action': 'deny'}
            ]
        }

        tool_call = {'name': 'rm', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'deny'

        tool_call = {'name': 'read', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'allow'

    def test_matches_tool_pattern(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_exec', 'tool_pattern': '(exec|run|shell)', 'action': 'deny'}
            ]
        }

        tool_call = {'name': 'execute_command', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'deny'

        tool_call = {'name': 'run_script', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'deny'

        tool_call = {'name': 'read_file', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'allow'

    def test_matches_threat_type(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {
                    'name': 'deny_injection',
                    'threat_types': ['shell_injection', 'sql_injection'],
                    'action': 'deny'
                }
            ]
        }

        tool_call = {'name': 'execute', 'arguments': {}}
        scan_results = [{'type': 'shell_injection', 'severity': 'high'}]
        decision = engine.evaluate(tool_call, scan_results)
        assert decision == 'deny'

        scan_results = [{'type': 'pii_detected', 'severity': 'medium'}]
        decision = engine.evaluate(tool_call, scan_results)
        assert decision == 'allow'

    def test_matches_severity(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_critical', 'min_severity': 'critical', 'action': 'deny'},
                {'name': 'escalate_high', 'min_severity': 'high', 'action': 'escalate'},
            ]
        }

        tool_call = {'name': 'execute', 'arguments': {}}

        scan_results = [{'type': 'shell_injection', 'severity': 'critical'}]
        decision = engine.evaluate(tool_call, scan_results)
        assert decision == 'deny'

        scan_results = [{'type': 'shell_injection', 'severity': 'high'}]
        decision = engine.evaluate(tool_call, scan_results)
        assert decision == 'escalate'

        scan_results = [{'type': 'pii_detected', 'severity': 'low'}]
        decision = engine.evaluate(tool_call, scan_results)
        assert decision == 'allow'

    def test_first_match_wins(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'deny',
            'rules': [
                {'name': 'allow_read', 'tools': ['read_file'], 'action': 'allow'},
                {'name': 'deny_all', 'tool_pattern': '.*', 'action': 'deny'},
            ]
        }

        # First rule matches, should allow
        tool_call = {'name': 'read_file', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'allow'

        # Second rule matches, should deny
        tool_call = {'name': 'write_file', 'arguments': {}}
        decision = engine.evaluate(tool_call, [])
        assert decision == 'deny'

    def test_builtin_policy_paths(self):
        default_path = get_builtin_policy_path('default')
        assert default_path.name == 'default.yaml'
        assert 'policies' in str(default_path)

        strict_path = get_builtin_policy_path('strict')
        assert strict_path.name == 'strict.yaml'

        permissive_path = get_builtin_policy_path('permissive')
        assert permissive_path.name == 'permissive.yaml'
