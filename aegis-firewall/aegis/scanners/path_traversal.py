"""Path traversal scanner."""

import re
from typing import List, Dict, Any
import os


class PathTraversalScanner:
    """Detects path traversal attempts."""

    # Dangerous path patterns
    TRAVERSAL_PATTERNS = [
        "../", "..\\",
        "%2e%2e%2f", "%2e%2e/", "..%2f", "%2e%2e%5c",
        "....//", "....\\\\",
    ]

    SENSITIVE_PATHS = [
        "/etc/passwd", "/etc/shadow", "/etc/hosts",
        "/root/", "/.ssh/", "/.aws/",
        "/proc/", "/sys/",
        "c:\\windows", "c:\\boot.ini", "/boot/",
        "/.env", "/.git/", "/config",
        "/private/", "/var/log/",
    ]

    def __init__(self, allow_absolute: bool = False):
        """
        Initialize scanner.

        Args:
            allow_absolute: Whether to allow absolute paths
        """
        self.allow_absolute = allow_absolute

    def scan(self, strings: List[str]) -> Dict[str, Any]:
        """
        Scan strings for path traversal patterns.

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

            # Check for traversal patterns
            for pattern in self.TRAVERSAL_PATTERNS:
                if pattern.lower() in s_lower:
                    findings.append({
                        "type": "traversal_pattern",
                        "pattern": pattern,
                        "text": s[:100],
                        "severity": "high"
                    })

            # Check for sensitive paths
            for sensitive in self.SENSITIVE_PATHS:
                if sensitive.lower() in s_lower:
                    findings.append({
                        "type": "sensitive_path",
                        "pattern": sensitive,
                        "text": s[:100],
                        "severity": "high"
                    })

            # Check for absolute paths if not allowed
            if not self.allow_absolute:
                if s.startswith('/') or re.match(r'^[A-Za-z]:\\', s):
                    findings.append({
                        "type": "absolute_path",
                        "pattern": "absolute_path",
                        "text": s[:100],
                        "severity": "medium"
                    })

            # Check for null byte injection
            if '\x00' in s or '%00' in s:
                findings.append({
                    "type": "null_byte",
                    "pattern": "null_byte",
                    "text": s[:100],
                    "severity": "high"
                })

            # Check for symlink-related patterns
            if re.search(r'\.\./\.\./\.\./', s) or re.search(r'\.\.\\\.\.\\\.\.\\', s):
                findings.append({
                    "type": "deep_traversal",
                    "pattern": "deep_traversal",
                    "text": s[:100],
                    "severity": "high"
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
            "scanner": "path_traversal"
        }
