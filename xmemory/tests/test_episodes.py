"""Tests for episode construction with mocked boto3."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from xmemory.episodes import construct_episodes, summarize_block
from xmemory.models import Message
from xmemory.schema import init_db
from xmemory.store import MemoryStore


def make_mock_client(response_text: str = "This is a test summary.") -> MagicMock:
    """Create a mock boto3 bedrock-runtime client."""
    mock_client = MagicMock()
    mock_response = {
        "body": MagicMock(
            read=MagicMock(
                return_value=json.dumps(
                    {"content": [{"text": response_text}]}
                ).encode()
            )
        )
    }
    mock_client.invoke_model.return_value = mock_response
    return mock_client


def make_store_with_messages(session_id: str = "s1", n: int = 15) -> MemoryStore:
    conn = init_db(":memory:")
    store = MemoryStore(conn)
    for i in range(n):
        store.add_message(
            Message(
                session_id=session_id,
                content=f"Message {i+1} in session {session_id}",
                timestamp=datetime(2025, 1, 1, 9, i),
            )
        )
    return store


class TestSummarizeBlock:
    def test_calls_llm(self):
        mock_client = make_mock_client("Summary of messages.")
        msgs = [
            Message(session_id="s1", content="Hello", timestamp=datetime.now(timezone.utc))
        ]
        result = summarize_block(msgs, client=mock_client)
        assert result == "Summary of messages."
        mock_client.invoke_model.assert_called_once()

    def test_prompt_contains_content(self):
        mock_client = make_mock_client("ok")
        msgs = [
            Message(
                session_id="s1",
                content="Unique content xyz",
                timestamp=datetime.now(timezone.utc),
            )
        ]
        summarize_block(msgs, client=mock_client)
        call_kwargs = mock_client.invoke_model.call_args
        body = json.loads(call_kwargs[1]["body"])
        assert "Unique content xyz" in body["messages"][0]["content"]


class TestConstructEpisodes:
    def test_creates_episodes_for_messages(self):
        store = make_store_with_messages("sess1", n=25)
        mock_client = make_mock_client("Episode summary.")
        episodes = construct_episodes(store, client=mock_client)
        # 25 messages with block_size=10 → 3 episodes
        assert len(episodes) == 3

    def test_messages_assigned_to_episodes(self):
        store = make_store_with_messages("sess1", n=10)
        mock_client = make_mock_client("Summary.")
        episodes = construct_episodes(store, block_size=10, client=mock_client)
        assert len(episodes) == 1
        # All messages should now have episode_id set
        msgs = store.get_messages_by_session("sess1")
        for msg in msgs:
            assert msg.episode_id == episodes[0].id

    def test_no_double_processing(self):
        store = make_store_with_messages("sess1", n=10)
        mock_client = make_mock_client("Summary.")
        episodes1 = construct_episodes(store, client=mock_client)
        episodes2 = construct_episodes(store, client=mock_client)
        assert len(episodes1) == 1
        assert len(episodes2) == 0  # Already processed

    def test_session_filter(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        for i in range(5):
            store.add_message(Message(session_id="A", content=f"A{i}", timestamp=datetime(2025, 1, 1, 9, i)))
        for i in range(5):
            store.add_message(Message(session_id="B", content=f"B{i}", timestamp=datetime(2025, 1, 1, 10, i)))

        mock_client = make_mock_client("Summary.")
        episodes = construct_episodes(store, session_id="A", client=mock_client)
        assert len(episodes) == 1
        assert episodes[0].session_id == "A"

    def test_episode_has_summary(self):
        store = make_store_with_messages("sess1", n=5)
        mock_client = make_mock_client("This is the summary text.")
        episodes = construct_episodes(store, block_size=5, client=mock_client)
        assert episodes[0].summary == "This is the summary text."

    def test_episode_message_ids_match(self):
        store = make_store_with_messages("sess1", n=5)
        mock_client = make_mock_client("Summary.")
        episodes = construct_episodes(store, block_size=5, client=mock_client)
        assert len(episodes[0].message_ids) == 5
