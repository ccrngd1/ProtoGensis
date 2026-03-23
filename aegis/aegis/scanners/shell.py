"""Shell injection detection scanner."""

import re
from typing import Optional


class ShellInjectionScanner:
    """Detects potential shell injection patterns."""

    # Common shell metacharacters and command separators
    SHELL_PATTERNS = [
        r';',  # Command separator
        r'\|',  # Pipe
        r'&',  # Background/AND
        r'\$\(',  # Command substitution
        r'`',  # Backtick command substitution
        r'\$\{',  # Variable substitution
        r'>',  # Redirect
        r'<',  # Input redirect
        r'\n',  # Newline (can separate commands)
    ]

    # High-risk command patterns
    DANGEROUS_COMMANDS = [
        r'\brm\s+-rf\b',
        r'\bdd\b',
        r'\bmkfs\b',
        r'\bformat\b',
        r'\bcurl\b.*\|\s*sh\b',
        r'\bwget\b.*\|\s*sh\b',
        r'\bchmod\b.*777\b',
        r'\bnc\b.*-e\b',  # netcat with execute
        r'\b/dev/(null|zero|random)\b',
    ]

    def __init__(self):
        self.shell_regex = re.compile('|'.join(self.SHELL_PATTERNS))
        self.danger_regex = re.compile('|'.join(self.DANGEROUS_COMMANDS), re.IGNORECASE)

    def scan(self, text: str) -> Optional[dict]:
        """
        Scan text for shell injection patterns.

        Returns:
            Detection dict with 'type', 'pattern', 'severity' if found, None otherwise
        """
        # Check dangerous commands first (critical severity)
        danger_match = self.danger_regex.search(text)
        if danger_match:
            return {
                'type': 'shell_injection',
                'pattern': danger_match.group(),
                'severity': 'critical',
                'message': f'Dangerous shell command detected: {danger_match.group()}'
            }

        # Check shell metacharacters (high severity)
        shell_match = self.shell_regex.search(text)
        if shell_match:
            return {
                'type': 'shell_injection',
                'pattern': shell_match.group(),
                'severity': 'high',
                'message': f'Shell metacharacter detected: {repr(shell_match.group())}'
            }

        return None
