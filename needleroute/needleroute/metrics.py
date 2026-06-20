"""Metrics collection and storage with SQLite."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from needleroute.config import MetricsConfig


class MetricsCollector:
    """Collects and stores routing metrics in SQLite."""

    def __init__(self, config: MetricsConfig):
        """
        Initialize metrics collector.

        Args:
            config: Metrics configuration
        """
        self.config = config
        self.db_path = Path(config.db_path).expanduser()

        if config.enabled:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                query TEXT,
                selected_tool TEXT,
                confidence REAL,
                escalated INTEGER,
                escalation_reason TEXT,
                latency_ms REAL,
                tokens_saved INTEGER,
                tokens_used INTEGER,
                metadata TEXT
            )
        """)

        # Create index on timestamp for fast time-range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON metrics(timestamp)
        """)

        # Create index on event_type
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type
            ON metrics(event_type)
        """)

        conn.commit()
        conn.close()

    def record(
        self,
        event_type: str,
        query: Optional[str] = None,
        selected_tool: Optional[str] = None,
        confidence: Optional[float] = None,
        escalated: bool = False,
        escalation_reason: Optional[str] = None,
        latency_ms: Optional[float] = None,
        tokens_saved: int = 0,
        tokens_used: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a metrics event.

        Args:
            event_type: Type of event (e.g., 'route', 'escalate', 'call_tool')
            query: User query
            selected_tool: Selected tool name
            confidence: Confidence score
            escalated: Whether request was escalated
            escalation_reason: Reason for escalation
            latency_ms: Latency in milliseconds
            tokens_saved: Estimated tokens saved
            tokens_used: Tokens used (for escalation)
            metadata: Additional metadata
        """
        if not self.config.enabled:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO metrics (
                    timestamp, event_type, query, selected_tool,
                    confidence, escalated, escalation_reason,
                    latency_ms, tokens_saved, tokens_used, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                event_type,
                query,
                selected_tool,
                confidence,
                1 if escalated else 0,
                escalation_reason,
                latency_ms,
                tokens_saved,
                tokens_used,
                json.dumps(metadata) if metadata else None,
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            # Don't let metrics failures break the system
            print(f"Warning: Failed to record metrics: {e}")

    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get statistics for the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with statistics
        """
        if not self.config.enabled:
            return {"error": "Metrics not enabled"}

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate cutoff time
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            # Total routing decisions
            cursor.execute("""
                SELECT COUNT(*) FROM metrics
                WHERE event_type = 'route' AND timestamp > ?
            """, (cutoff,))
            total_routes = cursor.fetchone()[0]

            # Escalation rate
            cursor.execute("""
                SELECT COUNT(*) FROM metrics
                WHERE event_type = 'route' AND escalated = 1 AND timestamp > ?
            """, (cutoff,))
            escalated_count = cursor.fetchone()[0]

            escalation_rate = escalated_count / total_routes if total_routes > 0 else 0.0

            # Average confidence (non-escalated)
            cursor.execute("""
                SELECT AVG(confidence) FROM metrics
                WHERE event_type = 'route' AND escalated = 0 AND timestamp > ?
            """, (cutoff,))
            avg_confidence = cursor.fetchone()[0] or 0.0

            # Average latency
            cursor.execute("""
                SELECT AVG(latency_ms) FROM metrics
                WHERE event_type = 'route' AND timestamp > ?
            """, (cutoff,))
            avg_latency_ms = cursor.fetchone()[0] or 0.0

            # Total tokens saved
            cursor.execute("""
                SELECT SUM(tokens_saved) FROM metrics
                WHERE event_type = 'route' AND escalated = 0 AND timestamp > ?
            """, (cutoff,))
            total_tokens_saved = cursor.fetchone()[0] or 0

            # Total tokens used (escalations)
            cursor.execute("""
                SELECT SUM(tokens_used) FROM metrics
                WHERE event_type = 'route' AND escalated = 1 AND timestamp > ?
            """, (cutoff,))
            total_tokens_used = cursor.fetchone()[0] or 0

            # Escalation reasons breakdown
            cursor.execute("""
                SELECT escalation_reason, COUNT(*) FROM metrics
                WHERE event_type = 'route' AND escalated = 1 AND timestamp > ?
                GROUP BY escalation_reason
            """, (cutoff,))
            escalation_reasons = dict(cursor.fetchall())

            # Top tools
            cursor.execute("""
                SELECT selected_tool, COUNT(*) FROM metrics
                WHERE event_type = 'route' AND timestamp > ?
                GROUP BY selected_tool
                ORDER BY COUNT(*) DESC
                LIMIT 10
            """, (cutoff,))
            top_tools = dict(cursor.fetchall())

            conn.close()

            return {
                "period_hours": hours,
                "total_routes": total_routes,
                "escalated_count": escalated_count,
                "escalation_rate": escalation_rate,
                "avg_confidence": avg_confidence,
                "avg_latency_ms": avg_latency_ms,
                "total_tokens_saved": total_tokens_saved,
                "total_tokens_used": total_tokens_used,
                "escalation_reasons": escalation_reasons,
                "top_tools": top_tools,
            }

        except Exception as e:
            return {"error": str(e)}

    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        if not self.config.enabled:
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT timestamp, event_type, query, selected_tool,
                       confidence, escalated, escalation_reason, latency_ms
                FROM metrics
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            events = []
            for row in rows:
                events.append({
                    "timestamp": row[0],
                    "event_type": row[1],
                    "query": row[2],
                    "selected_tool": row[3],
                    "confidence": row[4],
                    "escalated": bool(row[5]),
                    "escalation_reason": row[6],
                    "latency_ms": row[7],
                })

            return events

        except Exception as e:
            print(f"Error fetching recent events: {e}")
            return []
