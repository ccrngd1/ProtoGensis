"""Path traversal detection scanner."""

import re
from typing import Optional


class PathTraversalScanner:
    """Detects path traversal attempts."""

    TRAVERSAL_PATTERNS = [
        r'\.\.[/\\]',  # ../or ..\
        r'[/\\]\.\.[/\\]',  # /../ or \..\
        r'\.\.%2[fF]',  # URL-encoded ../
        r'%2[eE]%2[eE]%2[fF]',  # URL-encoded ../
        r'\.\.\\',  # Windows-style
    ]

    SENSITIVE_PATHS = [
        r'/etc/passwd',
        r'/etc/shadow',
        r'/root/',
        r'C:\\Windows\\System32',
        r'C:\\Users\\',
        r'/proc/',
        r'/sys/',
        r'\.ssh/',
        r'\.aws/',
        r'\.git/',
    ]

    def __init__(self):
        self.traversal_regex = re.compile('|'.join(self.TRAVERSAL_PATTERNS), re.IGNORECASE)
        self.sensitive_regex = re.compile('|'.join(self.SENSITIVE_PATHS), re.IGNORECASE)

    def scan(self, text: str) -> Optional[dict]:
        """
        Scan text for path traversal patterns.

        Returns:
            Detection dict if found, None otherwise
        """
        # Check for traversal sequences
        traversal_match = self.traversal_regex.search(text)
        if traversal_match:
            return {
                'type': 'path_traversal',
                'pattern': traversal_match.group(),
                'severity': 'high',
                'message': f'Path traversal sequence detected: {traversal_match.group()}'
            }

        # Check for sensitive paths
        sensitive_match = self.sensitive_regex.search(text)
        if sensitive_match:
            return {
                'type': 'path_traversal',
                'pattern': sensitive_match.group(),
                'severity': 'medium',
                'message': f'Sensitive path access detected: {sensitive_match.group()}'
            }

        return None
