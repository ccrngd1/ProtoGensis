"""Tests for policy engine."""

import pytest
import tempfile
import os
from aegis.policy import PolicyEngine


class TestPolicyEngine:
    """Test policy evaluation."""

    @pytest.fixture
    def simple_policy_file(self):
        content = """
name: test
default_action: deny

rules:
  - name: allow_safe_tools
    tools:
      - read_file
      - search
    action: allow
    reason: Safe tools

  - name: block_high_severity
    tools: '*'
    min_severity: high
    action: deny
    reason: High severity blocked

  - name: escalate_medium
    tools: '*'
    min_severity: medium
    action: escalate
    reason: Needs review
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        yield path
        os.unlink(path)

    def test_load_policy(self, simple_policy_file):
        engine = PolicyEngine(simple_policy_file)
        assert engine.policy['name'] == 'test'
        assert len(engine.policy['rules']) == 3

    def test_allow_safe_tool(self, simple_policy_file):
        engine = PolicyEngine(simple_policy_file)
        scanner_results = [
            {'scanner': 'shell', 'detected': False, 'severity': 'none'}
        ]
        decision = engine.evaluate('read_file', scanner_results)
        assert decision['action'] == 'allow'

    def test_deny_high_severity(self, simple_policy_file):
        engine = PolicyEngine(simple_policy_file)
        scanner_results = [
            {'scanner': 'shell', 'detected': True, 'severity': 'high'}
        ]
        decision = engine.evaluate('exec', scanner_results)
        assert decision['action'] == 'deny'

    def test_escalate_medium_severity(self, simple_policy_file):
        engine = PolicyEngine(simple_policy_file)
        scanner_results = [
            {'scanner': 'pii', 'detected': True, 'severity': 'medium'}
        ]
        decision = engine.evaluate('send_email', scanner_results)
        assert decision['action'] == 'escalate'

    def test_default_action(self, simple_policy_file):
        engine = PolicyEngine(simple_policy_file)
        scanner_results = [
            {'scanner': 'shell', 'detected': False, 'severity': 'none'}
        ]
        # Tool not in allow list, no severity, should use default
        decision = engine.evaluate('unknown_tool', scanner_results)
        # First rule won't match (tool not in list)
        # Second rule won't match (severity not high)
        # Third rule won't match (severity not medium)
        # Should use default: deny
        assert decision['action'] == 'deny'
