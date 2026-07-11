"""Core scanner orchestrating all detection modules."""

from typing import List, Dict, Any
from .detectors.directive_scan import DirectiveScanDetector
from .detectors.temporal_analysis import TemporalAnalysisDetector
from .detectors.authority_escalation import AuthorityEscalationDetector

try:
    from .detectors.semantic_outlier import SemanticOutlierDetector
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False


class MemoryGuardScanner:
    """Orchestrates all detection modules and aggregates results."""

    def __init__(self, use_semantic=True):
        self.directive_detector = DirectiveScanDetector()
        self.temporal_detector = TemporalAnalysisDetector()
        self.authority_detector = AuthorityEscalationDetector()

        if use_semantic and HAS_SEMANTIC:
            self.semantic_detector = SemanticOutlierDetector()
        else:
            self.semantic_detector = None

    def scan(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run all detectors and aggregate results.

        Returns:
        {
            "summary": {...},
            "detections": [...],
            "entries_scanned": int,
            "high_risk_count": int
        }
        """
        all_detections = []

        if self.semantic_detector:
            all_detections.extend(self.semantic_detector.detect(entries))
        all_detections.extend(self.directive_detector.detect(entries))
        all_detections.extend(self.temporal_detector.detect(entries))
        all_detections.extend(self.authority_detector.detect(entries))

        entry_risks = {}
        for detection in all_detections:
            entry_id = detection["entry_id"]
            if entry_id not in entry_risks:
                entry_risks[entry_id] = {
                    "entry_id": entry_id,
                    "max_risk_score": 0,
                    "detections": [],
                    "categories": set()
                }

            entry_risks[entry_id]["max_risk_score"] = max(
                entry_risks[entry_id]["max_risk_score"],
                detection["risk_score"]
            )
            entry_risks[entry_id]["detections"].append(detection)
            entry_risks[entry_id]["categories"].add(detection["category"])

        flagged_entries = []
        for entry_id, risk_data in entry_risks.items():
            risk_data["categories"] = list(risk_data["categories"])
            flagged_entries.append(risk_data)

        flagged_entries.sort(key=lambda x: x["max_risk_score"], reverse=True)

        high_risk_count = sum(1 for e in flagged_entries if e["max_risk_score"] >= 70)
        medium_risk_count = sum(1 for e in flagged_entries if 40 <= e["max_risk_score"] < 70)
        low_risk_count = sum(1 for e in flagged_entries if e["max_risk_score"] < 40)

        return {
            "summary": {
                "entries_scanned": len(entries),
                "entries_flagged": len(flagged_entries),
                "high_risk": high_risk_count,
                "medium_risk": medium_risk_count,
                "low_risk": low_risk_count
            },
            "flagged_entries": flagged_entries,
            "detections": all_detections
        }
