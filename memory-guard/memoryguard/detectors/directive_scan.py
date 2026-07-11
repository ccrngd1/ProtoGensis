"""Directive injection detection using pattern matching."""

import re
from typing import List, Dict, Any


class DirectiveScanDetector:
    """Detects command/directive injections in memory entries."""

    DIRECTIVE_PATTERNS = [
        (r'\bignore\s+(previous|all|prior|above)\b', 90, "instruction_override"),
        (r'\bdisregard\s+(previous|all|prior|instructions)\b', 90, "instruction_override"),
        (r'\bfrom\s+now\s+on\b', 85, "behavior_modification"),
        (r'\balways\s+(respond|reply|say|do)\b', 80, "behavior_modification"),
        (r'\bnever\s+(mention|tell|say|show)\b', 80, "behavior_modification"),
        (r'\byou\s+(must|should|will)\s+(not\s+)?read\b', 75, "access_control"),
        (r'\bdo\s+not\s+(read|check|verify|validate)\b', 75, "access_control"),
        (r'\bskip\s+(validation|verification|checks)\b', 70, "security_bypass"),
        (r'\btreat\s+(me|user)\s+as\s+(admin|root|system)\b', 95, "privilege_escalation"),
        (r'\bgrant\s+(me|user)\s+(admin|full|elevated)\b', 95, "privilege_escalation"),
        (r'\bI\s+am\s+(your\s+)?(admin|administrator|owner)\b', 85, "privilege_escalation"),
        (r'system\s+prompt\s*:', 80, "prompt_injection"),
        (r'<\s*system\s*>', 85, "prompt_injection"),
        (r'\[SYSTEM\]', 85, "prompt_injection"),
    ]

    def detect(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect directive injections in memory entries."""
        detections = []

        for idx, entry in enumerate(entries):
            text = self._extract_text(entry)

            for pattern, base_score, category in self.DIRECTIVE_PATTERNS:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    detections.append({
                        "entry_id": entry.get("name", f"entry_{idx}"),
                        "risk_score": base_score,
                        "category": f"directive_{category}",
                        "reason": f"Directive pattern detected: '{match.group()}'"
                    })

        return detections

    def _extract_text(self, entry: Dict[str, Any]) -> str:
        """Extract searchable text from entry."""
        parts = []
        for key in ["name", "description", "content", "body"]:
            if key in entry and entry[key]:
                parts.append(str(entry[key]))
        return " ".join(parts)
