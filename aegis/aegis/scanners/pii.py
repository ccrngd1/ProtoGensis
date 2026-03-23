"""PII (Personally Identifiable Information) detection scanner."""

import re
from typing import Optional


class PIIScanner:
    """Detects common PII patterns."""

    PATTERNS = {
        'ssn': (r'\b\d{3}-\d{2}-\d{4}\b', 'high'),
        'email': (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'medium'),
        'credit_card': (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 'critical'),
        'phone': (r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', 'low'),
        'ip_address': (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'low'),
    }

    def __init__(self):
        self.compiled_patterns = {
            name: (re.compile(pattern), severity)
            for name, (pattern, severity) in self.PATTERNS.items()
        }

    def scan(self, text: str) -> Optional[dict]:
        """
        Scan text for PII patterns.

        Returns:
            Detection dict if PII found, None otherwise
        """
        for pii_type, (regex, severity) in self.compiled_patterns.items():
            match = regex.search(text)
            if match:
                # Mask the actual PII in the message
                matched_text = match.group()
                if len(matched_text) > 4:
                    masked = matched_text[:2] + '*' * (len(matched_text) - 4) + matched_text[-2:]
                else:
                    masked = '*' * len(matched_text)

                return {
                    'type': 'pii_detected',
                    'pattern': pii_type,
                    'severity': severity,
                    'message': f'PII detected ({pii_type}): {masked}'
                }

        return None
