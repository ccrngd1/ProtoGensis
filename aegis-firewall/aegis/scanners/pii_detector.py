"""PII (Personally Identifiable Information) detector."""

import re
from typing import List, Dict, Any


class PIIDetector:
    """Detects common PII patterns."""

    # Regex patterns for PII
    PATTERNS = {
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "ssn_no_dash": re.compile(r'\b\d{9}\b'),
        "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone": re.compile(r'\b(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        "passport": re.compile(r'\b[A-Z]{1,2}\d{6,9}\b'),
        "drivers_license": re.compile(r'\b[A-Z]{1,2}\d{6,8}\b'),
    }

    def __init__(self, sensitivity: str = "medium"):
        """
        Initialize detector.

        Args:
            sensitivity: Detection sensitivity (low/medium/high)
        """
        self.sensitivity = sensitivity

    def scan(self, strings: List[str]) -> Dict[str, Any]:
        """
        Scan strings for PII.

        Args:
            strings: List of strings to scan

        Returns:
            Dict with 'detected' (bool), 'severity' (str), 'findings' (list)
        """
        findings = []

        for s in strings:
            if not isinstance(s, str):
                continue

            for pii_type, pattern in self.PATTERNS.items():
                matches = pattern.findall(s)
                for match in matches:
                    # Validate certain patterns to reduce false positives
                    if pii_type == "credit_card" and self._validate_luhn(match):
                        findings.append({
                            "type": pii_type,
                            "pattern": "REDACTED",  # Don't log actual PII
                            "text": "REDACTED",
                            "severity": "high"
                        })
                    elif pii_type == "ssn":
                        findings.append({
                            "type": pii_type,
                            "pattern": "REDACTED",
                            "text": "REDACTED",
                            "severity": "high"
                        })
                    elif pii_type == "email":
                        findings.append({
                            "type": pii_type,
                            "pattern": match[:5] + "...",  # Partial redaction
                            "text": "REDACTED",
                            "severity": "medium"
                        })
                    elif pii_type in ["phone", "passport", "drivers_license"]:
                        findings.append({
                            "type": pii_type,
                            "pattern": "REDACTED",
                            "text": "REDACTED",
                            "severity": "medium"
                        })
                    elif pii_type == "ip_address" and self.sensitivity == "high":
                        findings.append({
                            "type": pii_type,
                            "pattern": match,
                            "text": s[:50],
                            "severity": "low"
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
            "scanner": "pii_detector"
        }

    def _validate_luhn(self, card_number: str) -> bool:
        """
        Validate credit card number using Luhn algorithm.

        Args:
            card_number: Card number string (may contain spaces/dashes)

        Returns:
            True if valid according to Luhn algorithm
        """
        # Remove non-digits
        digits = ''.join(c for c in card_number if c.isdigit())

        if len(digits) < 13 or len(digits) > 19:
            return False

        # Luhn algorithm
        checksum = 0
        reverse_digits = digits[::-1]

        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            checksum += n

        return checksum % 10 == 0
