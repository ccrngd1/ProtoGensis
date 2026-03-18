"""Tests for Ingest, Consolidate, and Query agents (boto3 mocked)."""
from __future__ import annotations

import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from memory.store import MemoryStore
from memory.models import Memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    return MemoryStore(db_path=str(tmp_path / "test.db"))


def _bedrock_response(text: str):
    """Build a fake boto3 invoke_model response."""
    body_content = json.dumps({"content": [{"text": text}]})
    mock_body = MagicMock()
    mock_body.read.return_value = body_content.encode()
    return {"body": mock_body}


# ---------------------------------------------------------------------------
# Ingest Agent
# ---------------------------------------------------------------------------

class TestIngestAgent:
    def test_ingest_parses_llm_output(self, tmp_path):
        store = _make_store(tmp_path)
        llm_json = json.dumps({
            "summary": "Alice joined the project on Monday.",
            "entities": ["Alice", "project"],
            "topics": ["team", "onboarding"],
            "importance": 0.7,
        })

        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response(llm_json)
            from agents.ingest import IngestAgent
            agent = IngestAgent(store=store)
            memory = agent.ingest("Alice joined the project.", source="slack")

        assert memory.summary == "Alice joined the project on Monday."
        assert "Alice" in memory.entities
        assert "onboarding" in memory.topics
        assert abs(memory.importance - 0.7) < 1e-6
        assert memory.source == "slack"

    def test_ingest_fallback_on_bad_json(self, tmp_path):
        store = _make_store(tmp_path)
        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response("not valid json {{{")
            from agents.ingest import IngestAgent
            agent = IngestAgent(store=store)
            text = "Some raw text that should still be stored."
            memory = agent.ingest(text, source="test")

        # Should fall back to raw text as summary
        assert text[:500] in memory.summary
        assert memory.source == "test"

    def test_ingest_persists_to_store(self, tmp_path):
        store = _make_store(tmp_path)
        llm_json = json.dumps({"summary": "Persisted memory.", "entities": [], "topics": [], "importance": 0.5})
        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response(llm_json)
            from agents.ingest import IngestAgent
            agent = IngestAgent(store=store)
            memory = agent.ingest("Some text")

        assert store.get_memory(memory.id) is not None
        assert store.count_memories() == 1


# ---------------------------------------------------------------------------
# Consolidation Agent
# ---------------------------------------------------------------------------

class TestConsolidateAgent:
    def _seed_memories(self, store, n=6):
        for i in range(n):
            store.add_memory(Memory(summary=f"Memory {i}", entities=[f"Entity{i}"], topics=["topic"]))

    def test_skips_when_too_few_memories(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed_memories(store, n=3)
        from agents.consolidate import ConsolidateAgent
        agent = ConsolidateAgent(store=store, min_memories=5)
        result = agent.run()
        assert result is None

    def test_consolidates_when_enough_memories(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed_memories(store, n=6)
        llm_json = json.dumps({
            "connections": "All memories relate to testing.",
            "insights": "User is writing tests frequently.",
        })
        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response(llm_json)
            from agents.consolidate import ConsolidateAgent
            agent = ConsolidateAgent(store=store, min_memories=5)
            result = agent.run()

        assert result is not None
        assert result.connections == "All memories relate to testing."
        assert result.insights == "User is writing tests frequently."
        assert len(result.memory_ids) == 6

    def test_marks_memories_consolidated(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed_memories(store, n=6)
        llm_json = json.dumps({"connections": "c", "insights": "i"})
        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response(llm_json)
            from agents.consolidate import ConsolidateAgent
            agent = ConsolidateAgent(store=store, min_memories=5)
            agent.run()

        assert len(store.get_unconsolidated()) == 0


# ---------------------------------------------------------------------------
# Query Agent
# ---------------------------------------------------------------------------

class TestQueryAgent:
    def test_query_returns_answer(self, tmp_path):
        store = _make_store(tmp_path)
        store.add_memory(Memory(summary="Python is a programming language.", entities=["Python"], topics=["programming"]))

        expected_answer = "Python is a high-level programming language. [memory:abc123]"
        with patch("agents.bedrock_client.get_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = _bedrock_response(expected_answer)
            from agents.query import QueryAgent
            agent = QueryAgent(store=store)
            answer = agent.query("What is Python?")

        assert answer == expected_answer

    def test_query_returns_no_memories_message(self, tmp_path):
        store = _make_store(tmp_path)
        from agents.query import QueryAgent
        agent = QueryAgent(store=store)
        answer = agent.query("What do you know?")
        assert "no memories" in answer.lower()
