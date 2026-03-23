"""Tests for content risk scanners."""

import pytest
from aegis.scanners import (
    ShellInjectionScanner,
    PathTraversalScanner,
    PIIScanner,
    SecretScanner,
    SQLInjectionScanner,
)


class TestShellInjectionScanner:
    """Test shell injection detection."""

    def test_detects_command_separator(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("ls -la; rm -rf /")
        assert result is not None
        assert result['type'] == 'shell_injection'
        assert result['severity'] == 'critical'

    def test_detects_pipe(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("cat file.txt | grep secret")
        assert result is not None
        assert result['type'] == 'shell_injection'

    def test_detects_command_substitution(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("echo $(whoami)")
        assert result is not None

    def test_detects_backtick_substitution(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("echo `whoami`")
        assert result is not None

    def test_detects_rm_rf(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("rm -rf /tmp")
        assert result is not None
        assert result['severity'] == 'critical'

    def test_clean_text_passes(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("hello world")
        assert result is None

    def test_clean_command_passes(self):
        scanner = ShellInjectionScanner()
        result = scanner.scan("ls -la /tmp")
        assert result is None


class TestPathTraversalScanner:
    """Test path traversal detection."""

    def test_detects_dot_dot_slash(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("../../etc/passwd")
        assert result is not None
        assert result['type'] == 'path_traversal'

    def test_detects_slash_dot_dot_slash(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("/var/www/../../../etc/shadow")
        assert result is not None

    def test_detects_windows_style(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("..\\..\\Windows\\System32")
        assert result is not None

    def test_detects_url_encoded(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("file%2e%2e%2fconfig")
        assert result is not None

    def test_detects_etc_passwd(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("/etc/passwd")
        assert result is not None
        assert result['severity'] == 'medium'

    def test_clean_path_passes(self):
        scanner = PathTraversalScanner()
        result = scanner.scan("/home/user/documents/file.txt")
        assert result is None


class TestPIIScanner:
    """Test PII detection."""

    def test_detects_ssn(self):
        scanner = PIIScanner()
        result = scanner.scan("My SSN is 123-45-6789")
        assert result is not None
        assert result['pattern'] == 'ssn'
        assert result['severity'] == 'high'
        assert '*' in result['message']  # Should be masked

    def test_detects_email(self):
        scanner = PIIScanner()
        result = scanner.scan("Contact me at user@example.com")
        assert result is not None
        assert result['pattern'] == 'email'

    def test_detects_credit_card(self):
        scanner = PIIScanner()
        result = scanner.scan("Card: 4532-1234-5678-9010")
        assert result is not None
        assert result['pattern'] == 'credit_card'
        assert result['severity'] == 'critical'

    def test_detects_phone(self):
        scanner = PIIScanner()
        result = scanner.scan("Call me at (555) 123-4567")
        assert result is not None
        assert result['pattern'] == 'phone'

    def test_clean_text_passes(self):
        scanner = PIIScanner()
        result = scanner.scan("This is a normal message")
        assert result is None


class TestSecretScanner:
    """Test secret detection."""

    def test_detects_aws_key(self):
        scanner = SecretScanner()
        result = scanner.scan("AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        assert result is not None
        assert result['pattern'] == 'aws_key'
        assert result['severity'] == 'critical'

    def test_detects_github_token(self):
        scanner = SecretScanner()
        result = scanner.scan("token: ghp_1234567890abcdefghijklmnopqrst")
        assert result is not None
        assert result['pattern'] == 'github_token'

    def test_detects_jwt(self):
        scanner = SecretScanner()
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scanner.scan(f"Authorization: Bearer {jwt}")
        assert result is not None
        assert result['pattern'] == 'jwt'

    def test_detects_private_key(self):
        scanner = SecretScanner()
        result = scanner.scan("-----BEGIN RSA PRIVATE KEY-----")
        assert result is not None
        assert result['pattern'] == 'private_key'

    def test_detects_high_entropy(self):
        scanner = SecretScanner()
        # High entropy random string (simulated API key)
        high_entropy = "aB3dE7fG9hJ2kL4mN6pQ8rS1tU5vW7xY0zA"
        result = scanner.scan(f"api_key={high_entropy}")
        assert result is not None
        assert result['pattern'] == 'high_entropy' or result['pattern'] == 'generic_api_key'

    def test_low_entropy_passes(self):
        scanner = SecretScanner()
        result = scanner.scan("hello world this is a normal message")
        assert result is None

    def test_entropy_calculation(self):
        scanner = SecretScanner()
        # Low entropy (repeated characters)
        assert scanner.calculate_entropy("aaaaaaaaaa") < 1.0
        # High entropy (random)
        assert scanner.calculate_entropy("aB3dE7fG9hJ2kL4m") > 3.5


class TestSQLInjectionScanner:
    """Test SQL injection detection."""

    def test_detects_or_1_equals_1(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("' OR '1'='1")
        assert result is not None
        assert result['type'] == 'sql_injection'

    def test_detects_union_select(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("1 UNION SELECT * FROM users")
        assert result is not None

    def test_detects_drop_table(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("'; DROP TABLE users;--")
        assert result is not None
        assert result['severity'] == 'critical'

    def test_detects_sql_comment(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("admin'--")
        assert result is not None

    def test_detects_xp_cmdshell(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("'; EXEC xp_cmdshell('dir');--")
        assert result is not None

    def test_clean_sql_like_text_passes(self):
        scanner = SQLInjectionScanner()
        result = scanner.scan("SELECT is a good name for a function")
        assert result is None
