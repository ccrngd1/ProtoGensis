"""Shell injection scanner."""

import re
from typing import List, Dict, Any


class ShellInjectionScanner:
    """Detects potential shell injection attempts."""

    # Dangerous shell characters and patterns
    SHELL_METACHARACTERS = [
        ";", "|", "&", "$", "`", "$(", "||", "&&", ">", ">>", "<",
        "\n", "\r", "\\", "!", "{", "}", "[", "]", "(", ")"
    ]

    DANGEROUS_COMMANDS = [
        "rm ", "rmdir", "del ", "format", "mkfs",
        "dd ", "wget ", "curl ", "nc ", "netcat",
        "chmod", "chown", "kill", "pkill",
        "> /dev/", "sudo ", "su ", "eval", "exec",
        "bash ", "sh ", "zsh ", "/bin/", "python -c",
        "perl -e", "ruby -e", "node -e"
    ]

    def __init__(self, severity_threshold: str = "medium"):
        """
        Initialize scanner.

        Args:
            severity_threshold: Minimum severity to report (low/medium/high)
        """
        self.severity_threshold = severity_threshold

    def scan(self, strings: List[str]) -> Dict[str, Any]:
        """
        Scan strings for shell injection patterns.

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

            # Check for shell metacharacters
            for meta in self.SHELL_METACHARACTERS:
                if meta in s:
                    findings.append({
                        "type": "shell_metacharacter",
                        "pattern": meta,
                        "text": s[:100],  # Truncate for logging
                        "severity": "medium"
                    })

            # Check for dangerous commands
            for cmd in self.DANGEROUS_COMMANDS:
                if cmd in s_lower:
                    findings.append({
                        "type": "dangerous_command",
                        "pattern": cmd.strip(),
                        "text": s[:100],
                        "severity": "high"
                    })

            # Check for command substitution
            if re.search(r'\$\(.*?\)', s) or re.search(r'`.*?`', s):
                findings.append({
                    "type": "command_substitution",
                    "pattern": "command_substitution",
                    "text": s[:100],
                    "severity": "high"
                })

            # Check for environment variable expansion with suspicious patterns
            if re.search(r'\$\{.*?\}', s) or re.search(r'\$[A-Z_]+', s):
                findings.append({
                    "type": "env_var_expansion",
                    "pattern": "env_expansion",
                    "text": s[:100],
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
            "scanner": "shell_injection"
        }
