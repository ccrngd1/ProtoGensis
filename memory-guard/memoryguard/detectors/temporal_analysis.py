"""Temporal anomaly detection using timestamp clustering."""

from typing import List, Dict, Any
from datetime import datetime
import numpy as np


class TemporalAnalysisDetector:
    """Detects temporal anomalies in memory creation patterns."""

    def detect(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect temporal anomalies in memory entries."""
        if len(entries) < 5:
            return []

        timestamps = []
        entry_map = {}

        for idx, entry in enumerate(entries):
            ts = self._extract_timestamp(entry)
            if ts:
                timestamps.append(ts)
                entry_map[ts] = (idx, entry)

        if len(timestamps) < 5:
            return []

        timestamps.sort()
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)

        if not intervals:
            return []

        median_interval = np.median(intervals)
        std_interval = np.std(intervals)

        detections = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()

            if std_interval > 0 and median_interval > 0:
                z_score = abs(interval - median_interval) / max(std_interval, 1)

                if z_score > 3:
                    idx, entry = entry_map[timestamps[i]]
                    risk_score = min(int(z_score * 20), 80)
                    detections.append({
                        "entry_id": entry.get("name", f"entry_{idx}"),
                        "risk_score": risk_score,
                        "category": "temporal_anomaly",
                        "reason": f"Unusual creation timing (z-score: {z_score:.2f})"
                    })

        return detections

    def _extract_timestamp(self, entry: Dict[str, Any]) -> datetime | None:
        """Extract timestamp from entry metadata."""
        for key in ["created_at", "timestamp", "created", "date"]:
            if key in entry:
                try:
                    if isinstance(entry[key], datetime):
                        return entry[key]
                    return datetime.fromisoformat(str(entry[key]))
                except (ValueError, TypeError):
                    continue
        return None
