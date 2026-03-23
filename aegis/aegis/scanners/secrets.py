"""Secret detection scanner using entropy and pattern matching."""

import re
import math
from collections import Counter
from typing import Optional


class SecretScanner:
    """Detects potential secrets using entropy analysis and pattern matching."""

    # Known secret patterns
    SECRET_PATTERNS = {
        'aws_key': (r'AKIA[0-9A-Z]{16}', 'critical'),
        'generic_api_key': (r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9_\-]{32,})["\']?', 'high'),
        'jwt': (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', 'high'),
        'github_token': (r'gh[pousr]_[0-9a-zA-Z]{30,}', 'critical'),
        'slack_token': (r'xox[baprs]-[0-9a-zA-Z-]{10,}', 'critical'),
        'private_key': (r'-----BEGIN[A-Z ]+PRIVATE KEY-----', 'critical'),
        'password_assignment': (r'password["\s:=]+["\']([^"\']{8,})["\']', 'high'),
    }

    # High entropy threshold (Shannon entropy)
    ENTROPY_THRESHOLD = 4.5
    MIN_LENGTH_FOR_ENTROPY = 20

    def __init__(self):
        self.compiled_patterns = {
            name: (re.compile(pattern, re.IGNORECASE), severity)
            for name, (pattern, severity) in self.SECRET_PATTERNS.items()
        }

    def calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0.0

        counter = Counter(text)
        length = len(text)
        entropy = 0.0

        for count in counter.values():
            probability = count / length
            entropy -= probability * math.log2(probability)

        return entropy

    def scan(self, text: str) -> Optional[dict]:
        """
        Scan text for secrets using pattern matching and entropy analysis.

        Returns:
            Detection dict if secret found, None otherwise
        """
        # Check known patterns first
        for secret_type, (regex, severity) in self.compiled_patterns.items():
            match = regex.search(text)
            if match:
                # Mask the secret
                matched_text = match.group()
                masked = matched_text[:4] + '*' * (len(matched_text) - 8) + matched_text[-4:] if len(matched_text) > 8 else '*' * len(matched_text)

                return {
                    'type': 'secret_detected',
                    'pattern': secret_type,
                    'severity': severity,
                    'message': f'Known secret pattern detected ({secret_type}): {masked}'
                }

        # Check for high-entropy strings (potential unknown secrets)
        # Look for long alphanumeric sequences
        high_entropy_pattern = re.compile(r'[a-zA-Z0-9_\-+/=]{20,}')
        for match in high_entropy_pattern.finditer(text):
            candidate = match.group()
            entropy = self.calculate_entropy(candidate)

            if entropy >= self.ENTROPY_THRESHOLD and len(candidate) >= self.MIN_LENGTH_FOR_ENTROPY:
                masked = candidate[:4] + '*' * (len(candidate) - 8) + candidate[-4:] if len(candidate) > 8 else '*' * len(candidate)
                return {
                    'type': 'secret_detected',
                    'pattern': 'high_entropy',
                    'severity': 'medium',
                    'message': f'High-entropy string detected (entropy={entropy:.2f}): {masked}'
                }

        return None
