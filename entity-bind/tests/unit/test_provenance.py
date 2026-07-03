"""Unit tests for provenance store."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from entity_bind.provenance import ProvenanceStore, ProvenanceRecord


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def test_provenance_record_creation():
    """Test creating a provenance record."""
    record = ProvenanceRecord(
        tool_name="send_email",
        slot="recipient",
        mention="Alex",
        chosen_id="person_alex_chen",
        chosen_score=0.85,
        runner_up_id="person_alex_kumar",
        runner_up_score=0.82,
        matched_fields=["name", "alias"],
        decision="act",
        candidates_count=2,
        timestamp=datetime.now().isoformat()
    )

    assert record.tool_name == "send_email"
    assert record.chosen_id == "person_alex_chen"
    assert abs(record.margin - 0.03) < 0.001  # 0.85 - 0.82 (within tolerance)


def test_jsonl_store(temp_dir):
    """Test JSONL provenance store."""
    store_path = temp_dir / "provenance.jsonl"
    store = ProvenanceStore.jsonl(store_path)

    # Add records
    record1 = ProvenanceRecord(
        tool_name="send_email",
        slot="recipient",
        mention="Alice",
        chosen_id="person_alice",
        chosen_score=0.95,
        matched_fields=["name"],
        decision="act",
        candidates_count=1,
        timestamp=datetime.now().isoformat()
    )

    record2 = ProvenanceRecord(
        tool_name="send_email",
        slot="recipient",
        mention="Bob",
        chosen_id="person_bob",
        chosen_score=0.90,
        matched_fields=["name"],
        decision="act",
        candidates_count=1,
        timestamp=datetime.now().isoformat()
    )

    store.add(record1)
    store.add(record2)

    # Verify file exists and is valid JSONL
    assert store_path.exists()

    lines = store_path.read_text().strip().split('\n')
    assert len(lines) == 2

    # Each line should be valid JSON
    for line in lines:
        data = json.loads(line)
        assert "tool_name" in data
        assert "chosen_id" in data


def test_sqlite_store(temp_dir):
    """Test SQLite provenance store."""
    db_path = temp_dir / "provenance.db"
    store = ProvenanceStore.sqlite(db_path)

    # Add record
    record = ProvenanceRecord(
        tool_name="delete_document",
        slot="document",
        mention="Q1 Report",
        chosen_id="doc_q1_2025",
        chosen_score=0.88,
        runner_up_id="doc_q1_2024",
        runner_up_score=0.65,
        matched_fields=["title"],
        decision="clarify",
        candidates_count=2,
        timestamp=datetime.now().isoformat()
    )

    store.add(record)

    # Query by tool
    results = store.query_by_tool("delete_document")
    assert len(results) == 1
    assert results[0].slot == "document"

    # Query by decision
    clarified = store.query_by_decision("clarify")
    assert len(clarified) == 1


def test_query_by_entity(temp_dir):
    """Test querying provenance by entity ID."""
    store = ProvenanceStore.sqlite(temp_dir / "test.db")

    # Add records for same entity
    for i in range(3):
        record = ProvenanceRecord(
            tool_name=f"tool_{i}",
            slot="target",
            mention="Alex",
            chosen_id="person_alex",
            chosen_score=0.90,
            matched_fields=["name"],
            decision="act",
            candidates_count=1,
            timestamp=datetime.now().isoformat()
        )
        store.add(record)

    # Query by entity
    results = store.query_by_entity("person_alex")
    assert len(results) == 3


def test_query_high_confidence(temp_dir):
    """Test querying high-confidence bindings."""
    store = ProvenanceStore.sqlite(temp_dir / "test.db")

    # Add records with varying confidence
    for score in [0.95, 0.75, 0.60, 0.50]:
        record = ProvenanceRecord(
            tool_name="send_email",
            slot="recipient",
            mention="test",
            chosen_id=f"person_{score}",
            chosen_score=score,
            matched_fields=["name"],
            decision="act",
            candidates_count=1,
            timestamp=datetime.now().isoformat()
        )
        store.add(record)

    # Query high confidence (>= 0.8)
    high_conf = store.query_high_confidence(min_score=0.8)
    assert len(high_conf) == 1
    assert high_conf[0].chosen_score == 0.95


def test_query_narrow_margins(temp_dir):
    """Test querying bindings with narrow margins (potential errors)."""
    store = ProvenanceStore.sqlite(temp_dir / "test.db")

    # Add records with varying margins
    margins = [(0.95, 0.90), (0.85, 0.55), (0.70, 0.68)]  # margins: 0.05, 0.30, 0.02

    for i, (top, second) in enumerate(margins):
        record = ProvenanceRecord(
            tool_name="send_email",
            slot="recipient",
            mention=f"test_{i}",
            chosen_id=f"person_{i}",
            chosen_score=top,
            runner_up_id=f"person_{i}_alt",
            runner_up_score=second,
            matched_fields=["name"],
            decision="act",
            candidates_count=2,
            timestamp=datetime.now().isoformat()
        )
        store.add(record)

    # Query narrow margins (<= 0.1)
    narrow = store.query_narrow_margins(max_margin=0.1)
    assert len(narrow) == 2  # margins 0.05 and 0.02


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
