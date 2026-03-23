"""SQL injection detection scanner."""

import re
from typing import Optional


class SQLInjectionScanner:
    """Detects potential SQL injection patterns."""

    SQL_PATTERNS = [
        r"'\s*OR\s+'1'\s*=\s*'1",
        r'"\s*OR\s+"1"\s*=\s*"1',
        r"'\s*OR\s+1\s*=\s*1",
        r'--',  # SQL comment
        r'/\*.*\*/',  # Multi-line comment
        r';\s*DROP\s+TABLE',
        r';\s*DELETE\s+FROM',
        r';\s*UPDATE\s+',
        r';\s*INSERT\s+INTO',
        r'UNION\s+SELECT',
        r'EXEC\s*\(',
        r'EXECUTE\s*\(',
        r'xp_cmdshell',
    ]

    def __init__(self):
        self.sql_regex = re.compile('|'.join(self.SQL_PATTERNS), re.IGNORECASE)

    def scan(self, text: str) -> Optional[dict]:
        """
        Scan text for SQL injection patterns.

        Returns:
            Detection dict if SQL injection found, None otherwise
        """
        match = self.sql_regex.search(text)
        if match:
            return {
                'type': 'sql_injection',
                'pattern': match.group(),
                'severity': 'critical',
                'message': f'SQL injection pattern detected: {match.group()}'
            }

        return None
