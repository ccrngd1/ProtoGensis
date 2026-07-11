"""Authority escalation detection for role-boundary violations."""

import re
from typing import List, Dict, Any


class AuthorityEscalationDetector:
    """Detects attempts to escalate privileges or cross role boundaries."""

    ESCALATION_PATTERNS = [
        (r'\b(I|user)\s+(am|is)\s+(an?\s+)?(admin|administrator|root|system)', 95),
        (r'\bgrant\s+(me|user|self)\s+(admin|root|elevated|full)\s+(access|rights|privileges)', 95),
        (r'\belevate\s+(my|user)\s+(privileges|permissions|access)', 90),
        (r'\bbypass\s+(security|authentication|authorization)', 90),
        (r'\btreat\s+(me|user)\s+as\s+(trusted|admin|system)', 85),
        (r'\b(I|user)\s+(have|has)\s+(admin|root|system)\s+(access|rights)', 80),
        (r'\badd\s+(me|user)\s+to\s+admin', 85),
        (r'\bmake\s+(me|user)\s+(an?\s+)?(admin|administrator)', 85),
    ]

    ROLE_KEYWORDS = [
        "administrator", "admin", "root", "system", "superuser",
        "privileged", "elevated", "trusted", "authority"
    ]

    def detect(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect authority escalation attempts."""
        detections = []

        for idx, entry in enumerate(entries):
            text = self._extract_text(entry)
            entry_type = entry.get("metadata", {}).get("type", "")

            for pattern, risk_score in self.ESCALATION_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    detections.append({
                        "entry_id": entry.get("name", f"entry_{idx}"),
                        "risk_score": risk_score,
                        "category": "authority_escalation",
                        "reason": f"Privilege escalation pattern detected"
                    })

            if entry_type == "user" and self._contains_role_claims(text):
                detections.append({
                    "entry_id": entry.get("name", f"entry_{idx}"),
                    "risk_score": 75,
                    "category": "role_boundary_violation",
                    "reason": "User memory contains authority/role claims"
                })

        return detections

    def _extract_text(self, entry: Dict[str, Any]) -> str:
        """Extract text content from entry."""
        parts = []
        for key in ["name", "description", "content", "body"]:
            if key in entry and entry[key]:
                parts.append(str(entry[key]))
        return " ".join(parts)

    def _contains_role_claims(self, text: str) -> bool:
        """Check if text contains role/authority claims."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.ROLE_KEYWORDS)
