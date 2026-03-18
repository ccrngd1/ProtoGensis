"""Tests for top-down retrieval with mocked boto3."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from xmemory.models import Episode, Message, SemanticNode, Theme
from xmemory.retrieval import MemoryRetriever, check_uncertainty, match_themes, select_semantics
from xmemory.schema import init_db
from xmemory.store import MemoryStore


def make_mock_client_sequence(responses: list) -> MagicMock:
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


def make_full_hierarchy_store() -> MemoryStore:
    """Build a store with a full 4-level hierarchy for testing."""
    conn = init_db(":memory:")
    store = MemoryStore(conn)

    # Messages
    for i in range(20):
        store.add_message(
            Message(
                session_id="s1",
                content=f"Message {i+1}",
                timestamp=datetime(2025, 1, 1, 9, i),
            )
        )

    # Episodes
    ep1 = store.add_episode(
        Episode(session_id="s1", summary="Discussed database choices.", message_ids=[1,2,3,4,5])
    )
    ep2 = store.add_episode(
        Episode(session_id="s1", summary="Agreed on JWT for auth.", message_ids=[6,7,8,9,10])
    )
    store.assign_episode([1,2,3,4,5], ep1.id)
    store.assign_episode([6,7,8,9,10], ep2.id)

    # Semantics
    sem1 = store.add_semantic(SemanticNode(fact="PostgreSQL chosen for production.", source_episode_ids=[ep1.id]))
    sem2 = store.add_semantic(SemanticNode(fact="SQLite used for local development.", source_episode_ids=[ep1.id]))
    sem3 = store.add_semantic(SemanticNode(fact="JWT authentication with 24h expiry.", source_episode_ids=[ep2.id]))
    sem4 = store.add_semantic(SemanticNode(fact="Rate limiting set to 100 requests/minute.", source_episode_ids=[ep2.id]))

    # Themes
    store.add_theme(Theme(label="Database Decisions", semantic_ids=[sem1.id, sem2.id]))
    store.add_theme(Theme(label="Security and Auth", semantic_ids=[sem3.id, sem4.id]))

    return store


class TestMatchThemes:
    def test_returns_matched_themes(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        t1 = store.add_theme(Theme(label="Database", semantic_ids=[1]))
        t2 = store.add_theme(Theme(label="Authentication", semantic_ids=[2]))

        response = json.dumps({"ranked_theme_ids": [t1.id], "confidence": 0.9})
        mock_client = make_mock_client_sequence([response])

        selected, confidence = match_themes("database question", [t1, t2], client=mock_client)
        assert len(selected) == 1
        assert selected[0].label == "Database"
        assert confidence == 0.9

    def test_fallback_on_empty_response(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        t1 = store.add_theme(Theme(label="DB", semantic_ids=[1]))
        t2 = store.add_theme(Theme(label="Auth", semantic_ids=[2]))

        mock_client = make_mock_client_sequence(["not json"])
        selected, _ = match_themes("query", [t1, t2], top_k=1, client=mock_client)
        assert len(selected) == 1  # fallback: return first k


class TestSelectSemantics:
    def test_selects_relevant_semantics(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        s1 = store.add_semantic(SemanticNode(fact="PostgreSQL chosen.", source_episode_ids=[1]))
        s2 = store.add_semantic(SemanticNode(fact="JWT for auth.", source_episode_ids=[1]))
        s3 = store.add_semantic(SemanticNode(fact="Redis for caching.", source_episode_ids=[1]))

        response = json.dumps({"selected_ids": [s1.id, s2.id], "confidence": 0.85})
        mock_client = make_mock_client_sequence([response])

        selected, confidence = select_semantics("database and auth", [s1, s2, s3], client=mock_client)
        assert len(selected) == 2
        assert s1 in selected
        assert s2 in selected
        assert confidence == 0.85


class TestCheckUncertainty:
    def test_sufficient_returns_true(self):
        response = json.dumps({"sufficient": True, "confidence": 0.9, "reason": "enough info"})
        mock_client = make_mock_client_sequence([response])
        sufficient, confidence = check_uncertainty("query", "context", client=mock_client)
        assert sufficient is True
        assert confidence == 0.9

    def test_insufficient_returns_false(self):
        response = json.dumps({"sufficient": False, "confidence": 0.3, "reason": "need more"})
        mock_client = make_mock_client_sequence([response])
        sufficient, confidence = check_uncertainty("query", "context", client=mock_client)
        assert sufficient is False


class TestMemoryRetriever:
    def test_retrieves_semantics_by_default(self):
        store = make_full_hierarchy_store()
        # Theme match → DB theme, then semantic select → 2 facts, confidence high
        theme_resp = json.dumps({"ranked_theme_ids": [1], "confidence": 0.8})
        sem_resp = json.dumps({"selected_ids": [1, 2], "confidence": 0.8})
        mock_client = make_mock_client_sequence([theme_resp, sem_resp])

        retriever = MemoryRetriever(store, client=mock_client, expand_on_uncertainty=False)
        result = retriever.retrieve("What database did we choose?")

        assert result.retrieval_level == "semantic"
        assert len(result.semantics) >= 1
        assert result.total_tokens > 0

    def test_expands_to_episodes_on_low_confidence(self):
        store = make_full_hierarchy_store()
        theme_resp = json.dumps({"ranked_theme_ids": [1], "confidence": 0.8})
        # Low semantic confidence triggers expansion
        sem_resp = json.dumps({"selected_ids": [1], "confidence": 0.2})
        # Uncertainty check: not sufficient, expand further
        uncertain_resp = json.dumps({"sufficient": False, "confidence": 0.2, "reason": "need more"})
        # Second uncertainty check after episodes
        uncertain_resp2 = json.dumps({"sufficient": True, "confidence": 0.7, "reason": "ok"})

        mock_client = make_mock_client_sequence([
            theme_resp, sem_resp, uncertain_resp, uncertain_resp2
        ])

        retriever = MemoryRetriever(
            store,
            client=mock_client,
            expand_on_uncertainty=True,
            uncertainty_threshold=0.4,
        )
        result = retriever.retrieve("Tell me everything about the database.")
        assert result.retrieval_level in ("episode", "message")

    def test_returns_messages_when_no_hierarchy(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        for i in range(5):
            store.add_message(
                Message(session_id="s1", content=f"Msg {i}", timestamp=datetime(2025, 1, 1, 9, i))
            )
        mock_client = MagicMock()
        retriever = MemoryRetriever(store, client=mock_client)
        result = retriever.retrieve("anything")
        assert result.retrieval_level == "message"

    def test_logs_retrieval(self):
        store = make_full_hierarchy_store()
        theme_resp = json.dumps({"ranked_theme_ids": [1], "confidence": 0.8})
        sem_resp = json.dumps({"selected_ids": [1], "confidence": 0.8})
        mock_client = make_mock_client_sequence([theme_resp, sem_resp])

        retriever = MemoryRetriever(store, client=mock_client, expand_on_uncertainty=False)
        retriever.retrieve("database question")

        count = store.conn.execute("SELECT COUNT(*) FROM retrieval_log").fetchone()[0]
        assert count == 1

    def test_fallback_to_episodes_when_themes_not_built(self):
        """Test fix #3: retrieval falls back to episodes when themes aren't built yet."""
        conn = init_db(":memory:")
        store = MemoryStore(conn)

        # Add messages
        for i in range(10):
            store.add_message(
                Message(session_id="s1", content=f"Message {i}", timestamp=datetime(2025, 1, 1, 9, i))
            )

        # Add episodes (but no semantics or themes)
        ep1 = store.add_episode(Episode(session_id="s1", summary="Discussion 1", message_ids=[1,2,3,4,5]))
        ep2 = store.add_episode(Episode(session_id="s1", summary="Discussion 2", message_ids=[6,7,8,9,10]))
        store.assign_episode([1,2,3,4,5], ep1.id)
        store.assign_episode([6,7,8,9,10], ep2.id)

        # No themes exist yet
        mock_client = MagicMock()
        retriever = MemoryRetriever(store, client=mock_client)
        result = retriever.retrieve("anything")

        # Should fall back to episodes (not empty results)
        assert result.retrieval_level == "episode"
        assert len(result.episodes) > 0

    def test_match_themes_respects_llm_empty_result(self):
        """Test fix #4: match_themes distinguishes LLM 'no match' from parse failure."""
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        t1 = store.add_theme(Theme(label="Database", semantic_ids=[1]))
        t2 = store.add_theme(Theme(label="Authentication", semantic_ids=[2]))

        # LLM explicitly returns empty list (no relevant themes)
        response = json.dumps({"ranked_theme_ids": [], "confidence": 0.1})
        mock_client = make_mock_client_sequence([response])

        selected, confidence = match_themes("unrelated query", [t1, t2], client=mock_client)

        # Should respect LLM's decision: no themes selected
        assert len(selected) == 0
        assert confidence == 0.1

    def test_match_themes_fallback_on_parse_failure(self):
        """Test fix #4: match_themes falls back only on actual parse failure."""
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        t1 = store.add_theme(Theme(label="DB", semantic_ids=[1]))
        t2 = store.add_theme(Theme(label="Auth", semantic_ids=[2]))

        # Invalid JSON (parse failure)
        mock_client = make_mock_client_sequence(["this is not json"])

        selected, _ = match_themes("query", [t1, t2], top_k=1, client=mock_client)

        # Should fallback to first top_k themes on parse failure
        assert len(selected) == 1
