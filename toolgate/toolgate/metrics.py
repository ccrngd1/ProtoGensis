"""Metrics tracking with SQLite and token counting."""

import sqlite3
import time
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import tiktoken

from toolgate.config import MetricsConfig
from toolgate.schemas import MetricsRecord, MCPTool


class MetricsCollector:
    """Collects and persists metrics to SQLite."""

    def __init__(self, config: MetricsConfig):
        self.config = config
        self.db_path = Path(config.db_path).expanduser()
        self.enabled = config.enabled

        try:
            self.encoding = tiktoken.get_encoding(config.token_model)
        except Exception:
            # Fallback to cl100k_base if model not found
            self.encoding = tiktoken.get_encoding("cl100k_base")

        if self.enabled:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    tool_name TEXT,
                    tools_returned INTEGER,
                    tokens_saved INTEGER,
                    latency_ms REAL,
                    query_text TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON metrics(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON metrics(event_type)
            """)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        if not text:
            return 0
        try:
            return len(self.encoding.encode(text))
        except Exception:
            # Fallback: estimate 4 chars per token
            return len(text) // 4

    def count_tool_tokens(self, tool: MCPTool) -> int:
        """Count tokens in a full tool definition."""
        # Serialize tool to JSON and count tokens
        tool_json = tool.model_dump_json()
        return self.count_tokens(tool_json)

    def calculate_tokens_saved(
        self,
        all_tools: List[MCPTool],
        returned_tools: List[str]
    ) -> int:
        """Calculate token savings from filtering."""
        total_tokens = sum(self.count_tool_tokens(tool) for tool in all_tools)
        returned_tokens = sum(
            self.count_tool_tokens(tool)
            for tool in all_tools
            if tool.name in returned_tools
        )
        return total_tokens - returned_tokens

    def record(
        self,
        event_type: str,
        tool_name: Optional[str] = None,
        tools_returned: Optional[int] = None,
        tokens_saved: Optional[int] = None,
        latency_ms: Optional[float] = None,
        query_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a metrics event."""
        if not self.enabled:
            return

        record = MetricsRecord(
            timestamp=time.time(),
            event_type=event_type,
            tool_name=tool_name,
            tools_returned=tools_returned,
            tokens_saved=tokens_saved,
            latency_ms=latency_ms,
            query_text=query_text,
            metadata=metadata,
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO metrics (
                        timestamp, event_type, tool_name, tools_returned,
                        tokens_saved, latency_ms, query_text, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.timestamp,
                        record.event_type,
                        record.tool_name,
                        record.tools_returned,
                        record.tokens_saved,
                        record.latency_ms,
                        record.query_text,
                        json.dumps(record.metadata) if record.metadata else None,
                    ),
                )
        except Exception as e:
            # Don't fail the request if metrics fail
            pass

    def get_stats(
        self,
        event_type: Optional[str] = None,
        since: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get aggregated statistics."""
        if not self.enabled:
            return {}

        conditions = []
        params = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"""
                SELECT
                    COUNT(*) as count,
                    AVG(latency_ms) as avg_latency,
                    SUM(tokens_saved) as total_tokens_saved,
                    AVG(tools_returned) as avg_tools_returned
                FROM metrics
                {where_clause}
                """,
                params,
            )
            row = cursor.fetchone()

            return {
                "count": row["count"],
                "avg_latency_ms": row["avg_latency"],
                "total_tokens_saved": row["total_tokens_saved"] or 0,
                "avg_tools_returned": row["avg_tools_returned"],
            }

    def get_recent_events(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent events."""
        if not self.enabled:
            return []

        where_clause = "WHERE event_type = ?" if event_type else ""
        params = [event_type] if event_type else []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"""
                SELECT * FROM metrics
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                params + [limit],
            )

            return [dict(row) for row in cursor.fetchall()]
