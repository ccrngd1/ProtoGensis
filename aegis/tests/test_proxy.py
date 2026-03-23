"""Tests for MCP proxy functionality."""

import pytest
import json
from aegis.extractor import extract_strings
from aegis.decision import DecisionEngine
from aegis.policy import PolicyEngine


class TestExtractor:
    """Test deep string extraction."""

    def test_extracts_simple_string(self):
        strings = list(extract_strings("hello"))
        assert strings == ["hello"]

    def test_extracts_from_dict(self):
        obj = {"key": "value", "nested": {"inner": "text"}}
        strings = list(extract_strings(obj))
        assert set(strings) == {"value", "text"}

    def test_extracts_from_list(self):
        obj = ["one", "two", "three"]
        strings = list(extract_strings(obj))
        assert strings == ["one", "two", "three"]

    def test_extracts_from_nested_structure(self):
        obj = {
            "command": "execute",
            "args": ["rm", "-rf", "/tmp"],
            "options": {"force": True, "path": "/home/user"}
        }
        strings = list(extract_strings(obj))
        assert set(strings) == {"execute", "rm", "-rf", "/tmp", "/home/user"}

    def test_ignores_non_strings(self):
        obj = {
            "number": 42,
            "bool": True,
            "null": None,
            "text": "actual string"
        }
        strings = list(extract_strings(obj))
        assert strings == ["actual string"]

    def test_handles_deep_nesting(self):
        obj = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        strings = list(extract_strings(obj))
        assert strings == ["deep"]

    def test_respects_max_depth(self):
        # Create very deep structure
        obj = {"a": {"b": {"c": {"d": {"e": "too deep"}}}}}
        # With max_depth=3, shouldn't reach "too deep"
        strings = list(extract_strings(obj, max_depth=3))
        assert "too deep" not in strings


class TestDecisionEngine:
    """Test three-stage decision pipeline."""

    def test_allows_clean_tool_call(self):
        engine = PolicyEngine()
        engine.policy = {'default_action': 'allow', 'rules': []}
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'read_file',
            'arguments': {'path': '/home/user/document.txt'}
        }

        decision, scan_results = decision_engine.decide(tool_call)

        assert decision == 'allow'
        assert len(scan_results) == 0

    def test_denies_shell_injection(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_critical', 'min_severity': 'critical', 'action': 'deny'}
            ]
        }
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'execute',
            'arguments': {'command': 'ls; rm -rf /tmp'}
        }

        decision, scan_results = decision_engine.decide(tool_call)

        assert decision == 'deny'
        assert len(scan_results) > 0
        assert any(r['type'] == 'shell_injection' for r in scan_results)

    def test_denies_path_traversal(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_high', 'min_severity': 'high', 'action': 'deny'}
            ]
        }
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'read_file',
            'arguments': {'path': '../../etc/passwd'}
        }

        decision, scan_results = decision_engine.decide(tool_call)

        assert decision == 'deny'
        assert any(r['type'] == 'path_traversal' for r in scan_results)

    def test_detects_secrets(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_secrets', 'threat_types': ['secret_detected'], 'action': 'deny'}
            ]
        }
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'send_message',
            'arguments': {'message': 'AWS key: AKIAIOSFODNN7EXAMPLE'}
        }

        decision, scan_results = decision_engine.decide(tool_call)

        assert decision == 'deny'
        assert any(r['type'] == 'secret_detected' for r in scan_results)

    def test_extracts_strings_from_nested_args(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_injection', 'threat_types': ['shell_injection'], 'action': 'deny'}
            ]
        }
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'complex_operation',
            'arguments': {
                'config': {
                    'commands': ['ls', 'cat file.txt | grep secret']
                }
            }
        }

        decision, scan_results = decision_engine.decide(tool_call)

        # Should detect shell injection in nested structure
        assert any(r['type'] == 'shell_injection' for r in scan_results)

    def test_multiple_scanners_detect_issues(self):
        engine = PolicyEngine()
        engine.policy = {
            'default_action': 'allow',
            'rules': [
                {'name': 'deny_any', 'min_severity': 'high', 'action': 'deny'}
            ]
        }
        decision_engine = DecisionEngine(engine)

        tool_call = {
            'name': 'dangerous_operation',
            'arguments': {
                'command': 'rm -rf /tmp',  # Shell injection
                'path': '../../etc/passwd',  # Path traversal
                'data': 'SSN: 123-45-6789'  # PII
            }
        }

        decision, scan_results = decision_engine.decide(tool_call)

        assert decision == 'deny'
        # Multiple threats should be detected
        assert len(scan_results) >= 2
        threat_types = {r['type'] for r in scan_results}
        assert 'shell_injection' in threat_types or 'path_traversal' in threat_types
