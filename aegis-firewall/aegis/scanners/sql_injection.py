"""SQL injection scanner."""

import re
from typing import List, Dict, Any


class SQLInjectionScanner:
    """Detects SQL injection attempts."""

    # SQL keywords and patterns
    SQL_KEYWORDS = [
        "union", "select", "insert", "update", "delete", "drop", "create",
        "alter", "exec", "execute", "script", "javascript", "xp_",
        "sp_", "0x", "||", "&&", "char(", "nchar(", "varchar(", "nvarchar(",
        "waitfor", "delay", "benchmark", "sleep(", "pg_sleep",
        "load_file", "into outfile", "into dumpfile"
    ]

    # SQL comment patterns
    SQL_COMMENTS = [
        "--", "/*", "*/", "#", ";--", "';--", "\";--"
    ]

    # SQL injection patterns
    SQL_PATTERNS = [
        re.compile(r"('\s*(or|and)\s*'?\d+)", re.IGNORECASE),
        re.compile(r"('\s*(or|and)\s*'?[a-z]+\s*=\s*'?[a-z]+)", re.IGNORECASE),
        re.compile(r"(union\s+select)", re.IGNORECASE),
        re.compile(r"(select\s+.*\s+from)", re.IGNORECASE),
        re.compile(r"(insert\s+into\s+.*\s+values)", re.IGNORECASE),
        re.compile(r"(drop\s+table)", re.IGNORECASE),
        re.compile(r"(;.*\s*(drop|delete|update|insert))", re.IGNORECASE),
        re.compile(r"('\s*or\s*'1'\s*=\s*'1)", re.IGNORECASE),
        re.compile(r"('\s*or\s*1\s*=\s*1)", re.IGNORECASE),
        re.compile(r"('\s*;\s*drop\s+table)", re.IGNORECASE),
        re.compile(r"(0x[0-9a-f]{2,})", re.IGNORECASE),  # Hex encoding
        re.compile(r"(char\s*\(\s*\d+)", re.IGNORECASE),  # CHAR() encoding
        re.compile(r"(exec\s*\()", re.IGNORECASE),
        re.compile(r"(waitfor\s+delay)", re.IGNORECASE),
        re.compile(r"(benchmark\s*\()", re.IGNORECASE),
    ]

    def __init__(self, strict: bool = True):
        """
        Initialize scanner.

        Args:
            strict: Whether to use strict detection (more false positives)
        """
        self.strict = strict

    def scan(self, strings: List[str]) -> Dict[str, Any]:
        """
        Scan strings for SQL injection patterns.

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

            # Check for SQL keywords
            keyword_count = 0
            found_keywords = []
            for keyword in self.SQL_KEYWORDS:
                if keyword in s_lower:
                    keyword_count += 1
                    found_keywords.append(keyword)

            # Multiple keywords suggest SQL injection
            if keyword_count >= 2 or (self.strict and keyword_count >= 1):
                findings.append({
                    "type": "sql_keywords",
                    "pattern": ", ".join(found_keywords[:3]),
                    "text": s[:100],
                    "severity": "high" if keyword_count >= 2 else "medium"
                })

            # Check for SQL comments
            for comment in self.SQL_COMMENTS:
                if comment in s:
                    findings.append({
                        "type": "sql_comment",
                        "pattern": comment,
                        "text": s[:100],
                        "severity": "medium"
                    })

            # Check regex patterns
            for pattern in self.SQL_PATTERNS:
                if pattern.search(s):
                    findings.append({
                        "type": "sql_injection_pattern",
                        "pattern": pattern.pattern[:30],
                        "text": s[:100],
                        "severity": "high"
                    })

            # Check for common injection attempts
            if "' or 1=1" in s_lower or "' or '1'='1" in s_lower:
                findings.append({
                    "type": "classic_injection",
                    "pattern": "1=1 injection",
                    "text": s[:100],
                    "severity": "high"
                })

            # Check for stacked queries
            if ";" in s and any(kw in s_lower for kw in ["select", "insert", "update", "delete", "drop"]):
                findings.append({
                    "type": "stacked_query",
                    "pattern": "stacked_query",
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
            "scanner": "sql_injection"
        }
