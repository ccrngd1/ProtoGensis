"""Tests for decision engine."""

import pytest
import tempfile
import os
from aegis.engine import DecisionEngine


class TestDecisionEngine:
    """Test decision engine integration."""

    @pytest.fixture
    def policy_file(self):
        content = """
name: test
default_action: deny

rules:
  - name: block_high
    tools: '*'
    min_severity: high
    action: deny
    reason: High severity

  - name: allow_none
    tools: '*'
    min_severity: none
    action: allow
    reason: Clean
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        yield path
        os.unlink(path)

    def test_evaluate_clean_request(self, policy_file):
        engine = DecisionEngine(policy_file)

        decision = engine.evaluate(
            tool_name='read_file',
            arguments={'path': 'safe.txt'}
        )

        assert decision['action'] == 'allow'
        assert decision['tool_name'] == 'read_file'

    def test_evaluate_shell_injection(self, policy_file):
        engine = DecisionEngine(policy_file)

        decision = engine.evaluate(
            tool_name='exec',
            arguments={'command': 'ls; rm -rf /'}
        )

        assert decision['action'] == 'deny'
        assert decision['policy_decision']['max_severity'] == 'high'

    def test_evaluate_path_traversal(self, policy_file):
        engine = DecisionEngine(policy_file)

        decision = engine.evaluate(
            tool_name='read_file',
            arguments={'path': '../../../etc/passwd'}
        )

        assert decision['action'] == 'deny'

    def test_scanner_results_included(self, policy_file):
        engine = DecisionEngine(policy_file)

        decision = engine.evaluate(
            tool_name='test',
            arguments={'data': 'normal'}
        )

        assert 'scanner_results' in decision
        assert len(decision['scanner_results']) == 5  # All 5 scanners

    def test_strings_extracted_count(self, policy_file):
        engine = DecisionEngine(policy_file)

        decision = engine.evaluate(
            tool_name='test',
            arguments={'a': 'b', 'c': ['d', 'e']}
        )

        assert decision['strings_extracted'] > 0
