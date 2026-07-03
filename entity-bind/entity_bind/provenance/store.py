"""
Provenance Store

Records binding decisions for auditability and debugging.
Supports JSONL (append-only) and SQLite (queryable) backends.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from entity_bind.core.gate import GateResult
from entity_bind.core.resolver import BindingResult


class ProvenanceRecord:
    """
    Single provenance record for an entity binding.

    Records why a binding was chosen (or why it failed).
    """

    def __init__(
        self,
        timestamp: str,
        tool_name: str,
        slot: str,
        mention: str,
        decision: str,
        chosen_id: Optional[str] = None,
        chosen_score: float = 0.0,
        runner_up_id: Optional[str] = None,
        runner_up_score: float = 0.0,
        margin: Optional[float] = None,
        matched_fields: Optional[List[str]] = None,
        clarification: Optional[str] = None,
        tau: float = 0.0,
        delta: float = 0.0,
        passed_tau: bool = False,
        passed_delta: bool = False,
        context: Optional[Dict[str, Any]] = None,
        candidates_count: Optional[int] = None  # For test compatibility
    ):
        self.timestamp = timestamp
        self.tool_name = tool_name
        self.slot = slot
        self.mention = mention
        self.decision = decision
        self.chosen_id = chosen_id
        self.chosen_score = chosen_score
        self.runner_up_id = runner_up_id
        self.runner_up_score = runner_up_score
        # Auto-calculate margin if not provided
        self.margin = margin if margin is not None else (chosen_score - runner_up_score)
        self.matched_fields = matched_fields or []
        self.clarification = clarification
        self.tau = tau
        self.delta = delta
        self.passed_tau = passed_tau
        self.passed_delta = passed_delta
        self.context = context or {}
        self.candidates_count = candidates_count  # Store for test compatibility

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "slot": self.slot,
            "mention": self.mention,
            "decision": self.decision,
            "chosen_id": self.chosen_id,
            "chosen_score": self.chosen_score,
            "runner_up_id": self.runner_up_id,
            "runner_up_score": self.runner_up_score,
            "margin": self.margin,
            "matched_fields": self.matched_fields,
            "clarification": self.clarification,
            "tau": self.tau,
            "delta": self.delta,
            "passed_tau": self.passed_tau,
            "passed_delta": self.passed_delta,
            "context": self.context
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceRecord":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_gate_result(cls, gate_result: GateResult) -> List["ProvenanceRecord"]:
        """
        Create provenance records from a GateResult.

        Returns one record per binding slot.
        """
        timestamp = datetime.utcnow().isoformat()
        records = []

        if not gate_result.bindings:
            return records

        for slot, binding in gate_result.bindings.items():
            record = cls(
                timestamp=timestamp,
                tool_name=gate_result.tool_name,
                slot=slot,
                mention=binding.mention,
                decision=gate_result.decision.value,
                chosen_id=binding.entity.id if binding.entity else None,
                chosen_score=binding.confidence,
                runner_up_id=binding.runner_up.id if binding.runner_up else None,
                runner_up_score=binding.runner_up_score,
                margin=binding.margin,
                matched_fields=binding.matched_fields,
                clarification=binding.clarification,
                tau=binding.tau,
                delta=binding.delta,
                passed_tau=binding.passed_tau,
                passed_delta=binding.passed_delta
            )
            records.append(record)

        return records


class ProvenanceStore:
    """
    Base provenance store interface.

    Stores binding decisions for after-the-fact auditing.
    """

    def record(self, gate_result: GateResult) -> None:
        """Record a gate result."""
        records = ProvenanceRecord.from_gate_result(gate_result)
        for record in records:
            self._write_record(record)

    def add(self, record: ProvenanceRecord) -> None:
        """Add a single provenance record (alias for tests)."""
        self._write_record(record)

    def _write_record(self, record: ProvenanceRecord) -> None:
        """Write a single record (implemented by subclasses)."""
        raise NotImplementedError

    @classmethod
    def jsonl(cls, path: Union[str, Path]) -> "JSONLProvenanceStore":
        """Factory method for JSONL store."""
        return JSONLProvenanceStore(path)

    @classmethod
    def sqlite(cls, path: Union[str, Path]) -> "SQLiteProvenanceStore":
        """Factory method for SQLite store."""
        return SQLiteProvenanceStore(path)


class JSONLProvenanceStore(ProvenanceStore):
    """
    JSONL provenance store (append-only log).

    Simple, portable, easy to process with standard tools.
    """

    def __init__(self, log_path: Union[str, Path]):
        """
        Initialize JSONL store.

        Args:
            log_path: Path to JSONL log file (created if missing)
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_record(self, record: ProvenanceRecord) -> None:
        """Append record to JSONL file."""
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(record.to_dict()) + '\n')

    def read_all(self) -> List[ProvenanceRecord]:
        """Read all records from log."""
        if not self.log_path.exists():
            return []

        records = []
        with open(self.log_path, 'r') as f:
            for line in f:
                if line.strip():
                    records.append(ProvenanceRecord.from_dict(json.loads(line)))
        return records

    def read_for_tool(self, tool_name: str) -> List[ProvenanceRecord]:
        """Read records for a specific tool."""
        return [r for r in self.read_all() if r.tool_name == tool_name]

    def query_by_tool(self, tool_name: str) -> List[ProvenanceRecord]:
        """Query records by tool name (alias for tests)."""
        return self.read_for_tool(tool_name)

    def query_by_decision(self, decision: str) -> List[ProvenanceRecord]:
        """Query records by decision."""
        return [r for r in self.read_all() if r.decision == decision]


class SQLiteProvenanceStore(ProvenanceStore):
    """
    SQLite provenance store (queryable).

    Better for production - supports indexed queries, aggregations, etc.
    """

    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database (created if missing)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create provenance table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provenance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                slot TEXT NOT NULL,
                mention TEXT NOT NULL,
                decision TEXT NOT NULL,
                chosen_id TEXT,
                chosen_score REAL,
                runner_up_id TEXT,
                runner_up_score REAL,
                margin REAL,
                matched_fields TEXT,
                clarification TEXT,
                tau REAL,
                delta REAL,
                passed_tau INTEGER,
                passed_delta INTEGER,
                context TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tool_name ON provenance(tool_name)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_decision ON provenance(decision)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON provenance(timestamp)
        """)
        self.conn.commit()

    def _write_record(self, record: ProvenanceRecord) -> None:
        """Insert record into database."""
        self.conn.execute("""
            INSERT INTO provenance (
                timestamp, tool_name, slot, mention, decision,
                chosen_id, chosen_score, runner_up_id, runner_up_score, margin,
                matched_fields, clarification, tau, delta, passed_tau, passed_delta, context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.timestamp,
            record.tool_name,
            record.slot,
            record.mention,
            record.decision,
            record.chosen_id,
            record.chosen_score,
            record.runner_up_id,
            record.runner_up_score,
            record.margin,
            json.dumps(record.matched_fields),
            record.clarification,
            record.tau,
            record.delta,
            int(record.passed_tau),
            int(record.passed_delta),
            json.dumps(record.context)
        ))
        self.conn.commit()

    def query(
        self,
        tool_name: Optional[str] = None,
        decision: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ProvenanceRecord]:
        """
        Query provenance records.

        Args:
            tool_name: Filter by tool name
            decision: Filter by decision (act/clarify/defer)
            limit: Max records to return

        Returns:
            List of matching records
        """
        query = "SELECT * FROM provenance WHERE 1=1"
        params = []

        if tool_name:
            query += " AND tool_name = ?"
            params.append(tool_name)

        if decision:
            query += " AND decision = ?"
            params.append(decision)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        records = []

        for row in cursor.fetchall():
            record = ProvenanceRecord(
                timestamp=row['timestamp'],
                tool_name=row['tool_name'],
                slot=row['slot'],
                mention=row['mention'],
                decision=row['decision'],
                chosen_id=row['chosen_id'],
                chosen_score=row['chosen_score'],
                runner_up_id=row['runner_up_id'],
                runner_up_score=row['runner_up_score'],
                margin=row['margin'],
                matched_fields=json.loads(row['matched_fields']) if row['matched_fields'] else [],
                clarification=row['clarification'],
                tau=row['tau'],
                delta=row['delta'],
                passed_tau=bool(row['passed_tau']),
                passed_delta=bool(row['passed_delta']),
                context=json.loads(row['context']) if row['context'] else {}
            )
            records.append(record)

        return records

    def query_by_tool(self, tool_name: str) -> List[ProvenanceRecord]:
        """Query records by tool name."""
        return self.query(tool_name=tool_name)

    def query_by_decision(self, decision: str) -> List[ProvenanceRecord]:
        """Query records by decision."""
        return self.query(decision=decision)

    def query_by_entity(self, entity_id: str) -> List[ProvenanceRecord]:
        """Query records by entity ID (chosen_id)."""
        query = "SELECT * FROM provenance WHERE chosen_id = ? ORDER BY timestamp DESC"
        cursor = self.conn.execute(query, (entity_id,))
        records = []

        for row in cursor.fetchall():
            record = ProvenanceRecord(
                timestamp=row['timestamp'],
                tool_name=row['tool_name'],
                slot=row['slot'],
                mention=row['mention'],
                decision=row['decision'],
                chosen_id=row['chosen_id'],
                chosen_score=row['chosen_score'],
                runner_up_id=row['runner_up_id'],
                runner_up_score=row['runner_up_score'],
                margin=row['margin'],
                matched_fields=json.loads(row['matched_fields']) if row['matched_fields'] else [],
                clarification=row['clarification'],
                tau=row['tau'],
                delta=row['delta'],
                passed_tau=bool(row['passed_tau']),
                passed_delta=bool(row['passed_delta']),
                context=json.loads(row['context']) if row['context'] else {}
            )
            records.append(record)

        return records

    def query_high_confidence(self, min_score: float) -> List[ProvenanceRecord]:
        """Query records with high confidence scores."""
        query = "SELECT * FROM provenance WHERE chosen_score >= ? ORDER BY chosen_score DESC"
        cursor = self.conn.execute(query, (min_score,))
        records = []

        for row in cursor.fetchall():
            record = ProvenanceRecord(
                timestamp=row['timestamp'],
                tool_name=row['tool_name'],
                slot=row['slot'],
                mention=row['mention'],
                decision=row['decision'],
                chosen_id=row['chosen_id'],
                chosen_score=row['chosen_score'],
                runner_up_id=row['runner_up_id'],
                runner_up_score=row['runner_up_score'],
                margin=row['margin'],
                matched_fields=json.loads(row['matched_fields']) if row['matched_fields'] else [],
                clarification=row['clarification'],
                tau=row['tau'],
                delta=row['delta'],
                passed_tau=bool(row['passed_tau']),
                passed_delta=bool(row['passed_delta']),
                context=json.loads(row['context']) if row['context'] else {}
            )
            records.append(record)

        return records

    def query_narrow_margins(self, max_margin: float) -> List[ProvenanceRecord]:
        """Query records with narrow margins (potential ambiguity)."""
        query = "SELECT * FROM provenance WHERE margin <= ? ORDER BY margin ASC"
        cursor = self.conn.execute(query, (max_margin,))
        records = []

        for row in cursor.fetchall():
            record = ProvenanceRecord(
                timestamp=row['timestamp'],
                tool_name=row['tool_name'],
                slot=row['slot'],
                mention=row['mention'],
                decision=row['decision'],
                chosen_id=row['chosen_id'],
                chosen_score=row['chosen_score'],
                runner_up_id=row['runner_up_id'],
                runner_up_score=row['runner_up_score'],
                margin=row['margin'],
                matched_fields=json.loads(row['matched_fields']) if row['matched_fields'] else [],
                clarification=row['clarification'],
                tau=row['tau'],
                delta=row['delta'],
                passed_tau=bool(row['passed_tau']),
                passed_delta=bool(row['passed_delta']),
                context=json.loads(row['context']) if row['context'] else {}
            )
            records.append(record)

        return records

    def stats(self) -> Dict[str, Any]:
        """Get provenance statistics."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN decision = 'act' THEN 1 ELSE 0 END) as act_count,
                SUM(CASE WHEN decision = 'clarify' THEN 1 ELSE 0 END) as clarify_count,
                SUM(CASE WHEN decision = 'defer' THEN 1 ELSE 0 END) as defer_count,
                AVG(CASE WHEN decision = 'act' THEN chosen_score ELSE NULL END) as avg_act_score,
                AVG(CASE WHEN decision = 'act' THEN margin ELSE NULL END) as avg_act_margin
            FROM provenance
        """)
        row = cursor.fetchone()

        return {
            "total_records": row['total'],
            "act_count": row['act_count'],
            "clarify_count": row['clarify_count'],
            "defer_count": row['defer_count'],
            "avg_act_score": row['avg_act_score'],
            "avg_act_margin": row['avg_act_margin']
        }

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __del__(self):
        """Ensure connection is closed."""
        if hasattr(self, 'conn'):
            self.conn.close()


# ============================================================================
# Factory
# ============================================================================


def create_provenance_store(
    path: Union[str, Path],
    store_type: str = "auto"
) -> ProvenanceStore:
    """
    Factory function to create a provenance store.

    Args:
        path: Path to log file or database
        store_type: "auto", "jsonl", or "sqlite"

    Returns:
        ProvenanceStore instance
    """
    path = Path(path)

    if store_type == "auto":
        if path.suffix == '.db':
            store_type = "sqlite"
        else:
            store_type = "jsonl"

    if store_type == "jsonl":
        return JSONLProvenanceStore(path)
    elif store_type == "sqlite":
        return SQLiteProvenanceStore(path)
    else:
        raise ValueError(f"Unknown store type: {store_type}")
