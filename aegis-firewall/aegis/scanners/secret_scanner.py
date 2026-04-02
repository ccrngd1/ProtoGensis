"""Secret scanner for detecting API keys, tokens, and credentials."""

import re
from typing import List, Dict, Any


class SecretScanner:
    """Detects secrets, API keys, tokens, and credentials."""

    # Patterns for common secret formats
    PATTERNS = {
        "aws_access_key": re.compile(r'AKIA[0-9A-Z]{16}'),
        "aws_secret_key": re.compile(r'(?i)aws(.{0,20})?["\'][0-9a-zA-Z\/+]{40}["\']'),
        "github_token": re.compile(r'ghp_[0-9a-zA-Z]{36}'),
        "github_oauth": re.compile(r'gho_[0-9a-zA-Z]{36}'),
        "slack_token": re.compile(r'xox[baprs]-([0-9a-zA-Z]{10,48})'),
        "slack_webhook": re.compile(r'https://hooks.slack.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+'),
        "google_api": re.compile(r'AIza[0-9A-Za-z\\-_]{35}'),
        "stripe_key": re.compile(r'(?:r|s)k_live_[0-9a-zA-Z]{24}'),
        "heroku_api": re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'),
        "mailgun_api": re.compile(r'key-[0-9a-zA-Z]{32}'),
        "jwt": re.compile(r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*'),
        "private_key": re.compile(r'-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
        "password_in_url": re.compile(r'[a-zA-Z]{3,10}://[^/\s:@]{3,20}:[^/\s:@]{3,20}@.{1,100}'),
        "generic_api_key": re.compile(r'(?i)(api[_-]?key|apikey|api[_-]?secret|apisecret)[\s]*[=:][\s]*["\'][0-9a-zA-Z]{16,}["\']'),
        "generic_secret": re.compile(r'(?i)(secret|token|password|passwd|pwd)[\s]*[=:][\s]*["\'][^"\'\s]{8,}["\']'),
        "bearer_token": re.compile(r'[Bb]earer\s+[a-zA-Z0-9\-._~+/]+=*'),
    }

    # Additional keyword patterns
    SECRET_KEYWORDS = [
        "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
        "access_token", "auth_token", "private_key", "client_secret",
        "encryption_key", "master_key", "credentials"
    ]

    def __init__(self, check_entropy: bool = True):
        """
        Initialize scanner.

        Args:
            check_entropy: Whether to check for high-entropy strings
        """
        self.check_entropy = check_entropy

    def scan(self, strings: List[str]) -> Dict[str, Any]:
        """
        Scan strings for secrets.

        Args:
            strings: List of strings to scan

        Returns:
            Dict with 'detected' (bool), 'severity' (str), 'findings' (list)
        """
        findings = []

        for s in strings:
            if not isinstance(s, str):
                continue

            s_lower = s.lower()

            # Check regex patterns
            for secret_type, pattern in self.PATTERNS.items():
                matches = pattern.findall(s)
                for match in matches:
                    findings.append({
                        "type": secret_type,
                        "pattern": "REDACTED",  # Never log actual secrets
                        "text": "REDACTED",
                        "severity": "high"
                    })

            # Check for secret keywords
            for keyword in self.SECRET_KEYWORDS:
                if keyword in s_lower:
                    # Look for assignments
                    if re.search(rf'{keyword}[\s]*[=:]', s_lower):
                        findings.append({
                            "type": "secret_keyword",
                            "pattern": keyword,
                            "text": s[:30] + "...",
                            "severity": "medium"
                        })

            # Check for high entropy strings (potential secrets)
            if self.check_entropy:
                words = s.split()
                for word in words:
                    if len(word) >= 16 and self._calculate_entropy(word) > 4.5:
                        # Could be a base64 encoded secret or hash
                        findings.append({
                            "type": "high_entropy_string",
                            "pattern": "high_entropy",
                            "text": word[:10] + "...",
                            "severity": "medium"
                        })

        # Determine overall severity
        severity = "none"
        if findings:
            severities = [f["severity"] for f in findings]
            if "high" in severities:
                severity = "high"
            elif "medium" in severities:
                severity = "medium"
            else:
                severity = "low"

        return {
            "detected": len(findings) > 0,
            "severity": severity,
            "findings": findings,
            "scanner": "secret_scanner"
        }

    def _calculate_entropy(self, s: str) -> float:
        """
        Calculate Shannon entropy of a string.

        Args:
            s: String to analyze

        Returns:
            Entropy value
        """
        if not s:
            return 0.0

        import math
        from collections import Counter

        # Count character frequencies
        counts = Counter(s)
        length = len(s)

        # Calculate entropy
        entropy = 0.0
        for count in counts.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy
