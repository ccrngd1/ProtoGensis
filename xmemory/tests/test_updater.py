"""Tests for the incremental updater with mocked boto3."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from xmemory.models import Message, SemanticNode, Theme
from xmemory.schema import init_db
from xmemory.store import MemoryStore
from xmemory.updater import MemoryUpdater


def make_mock_client(responses: list) -> MagicMock:
    mock_client = MagicMock()
    call_count = {"n": 0}

    def invoke_model(**kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        text = responses[idx]
        call_count["n"] += 1
        return {
            "body": MagicMock(
                read=MagicMock(
                    return_value=json.dumps(
                        {"content": [{"text": text}]}
                    ).encode()
                )
            )
        }

    mock_client.invoke_model.side_effect = invoke_model
    return mock_client


def add_messages(store: MemoryStore, session_id: str, n: int, offset: int = 0) -> list:
    msgs = []
    for i in range(n):
        msg = store.add_message(
            Message(
                session_id=session_id,
                content=f"Message {offset+i+1} in session {session_id}",
                timestamp=datetime(2025, 1, 1, 9, offset + i),
            )
        )
        msgs.append(msg)
    return msgs


class TestMemoryUpdater:
    def _make_llm_responses(self) -> list:
        """Sequence of responses: episode summary, facts JSON, dedup checks, cluster assignments."""
        return [
            # Episode summary (Haiku)
            "Summary of the conversation block.",
            # Fact extraction (Haiku)
            '["Fact A about the system.", "Fact B about the API."]',
            # Dedup check for Fact A (not duplicate)
            '{"duplicate": false, "reason": "new"}',
            # Dedup check for Fact B (not duplicate)
            '{"duplicate": false, "reason": "new"}',
            # Theme clustering
            json.dumps({"assignments": [[1, "System Info"], [2, "API Info"]]}),
        ]

    def test_full_run_creates_hierarchy(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        add_messages(store, "s1", 10)

        mock_client = make_mock_client(self._make_llm_responses())
        updater = MemoryUpdater(store, client=mock_client, episode_block_size=10)
        result = updater.run()

        assert len(result.new_episodes) == 1
        assert len(result.new_semantics) >= 1
        assert len(result.touched_themes) >= 1

        stats = store.stats()
        assert stats["messages"] == 10
        assert stats["episodes"] >= 1
        assert stats["semantics"] >= 1
        assert stats["themes"] >= 1

    def test_incremental_no_rebuild(self):
        """Second run only processes new messages."""
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        add_messages(store, "s1", 5)

        # First run
        responses1 = [
            "First batch summary.",
            '["Fact 1.", "Fact 2."]',
            '{"duplicate": false, "reason": "new"}',
            '{"duplicate": false, "reason": "new"}',
            json.dumps({"assignments": [[1, "Topic A"], [2, "Topic A"]]}),
        ]
        mock_client1 = make_mock_client(responses1)
        updater = MemoryUpdater(store, client=mock_client1, episode_block_size=5)
        result1 = updater.run()

        assert len(result1.new_episodes) == 1
        initial_semantic_count = store.stats()["semantics"]

        # Add new messages
        add_messages(store, "s1", 5, offset=5)

        # Second run
        responses2 = [
            "Second batch summary.",
            '["Fact 3.", "Fact 4."]',
            '{"duplicate": false, "reason": "new"}',
            '{"duplicate": false, "reason": "new"}',
            json.dumps({"assignments": [[3, "Topic A"], [4, "Topic B"]]}),
        ]
        mock_client2 = make_mock_client(responses2)
        updater2 = MemoryUpdater(store, client=mock_client2, episode_block_size=5)
        result2 = updater2.run()

        assert len(result2.new_episodes) == 1
        assert store.stats()["semantics"] == initial_semantic_count + len(result2.new_semantics)
        # All 10 messages now assigned
        unprocessed = store.get_unprocessed_messages()
        assert len(unprocessed) == 0

    def test_empty_run_does_nothing(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        mock_client = MagicMock()
        updater = MemoryUpdater(store, client=mock_client)
        result = updater.run()
        assert result.new_episodes == []
        assert result.new_semantics == []
        assert result.touched_themes == []
        mock_client.invoke_model.assert_not_called()

    def test_session_filter(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        add_messages(store, "s1", 5)
        add_messages(store, "s2", 5)

        responses = [
            "Session 1 only summary.",
            '["Fact from s1."]',
            '{"duplicate": false, "reason": "new"}',
            json.dumps({"assignments": [[1, "S1 Topic"]]}),
        ]
        mock_client = make_mock_client(responses)
        updater = MemoryUpdater(store, client=mock_client, episode_block_size=5)
        result = updater.run(session_id="s1")

        # Only s1 messages processed into episodes
        assert all(e.session_id == "s1" for e in result.new_episodes)
        # s2 messages still unprocessed
        s2_msgs = store.get_messages_by_session("s2")
        assert all(m.episode_id is None for m in s2_msgs)

    def test_summary_contains_counts(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        add_messages(store, "s1", 5)
        responses = [
            "Summary.",
            '["Fact X."]',
            '{"duplicate": false, "reason": "new"}',
            json.dumps({"assignments": [[1, "Topic"]]}),
        ]
        mock_client = make_mock_client(responses)
        updater = MemoryUpdater(store, client=mock_client, episode_block_size=5)
        result = updater.run()
        summary = result.summary
        assert "episode" in summary.lower()
        assert "semantic" in summary.lower()
        assert "theme" in summary.lower()
