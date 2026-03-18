"""Tests for theme clustering with mocked boto3."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from xmemory.models import SemanticNode, Theme
from xmemory.schema import init_db
from xmemory.store import MemoryStore
from xmemory.themes import cluster_semantics_batch, cluster_themes


def make_mock_client(response_text: str) -> MagicMock:
    mock_client = MagicMock()
    mock_client.invoke_model.return_value = {
        "body": MagicMock(
            read=MagicMock(
                return_value=json.dumps(
                    {"content": [{"text": response_text}]}
                ).encode()
            )
        )
    }
    return mock_client


def make_semantic(sid: int, fact: str) -> SemanticNode:
    node = SemanticNode(fact=fact, source_episode_ids=[1])
    node.id = sid
    return node


class TestClusterSemanticsBatch:
    def test_parses_assignments(self):
        nodes = [
            make_semantic(1, "PostgreSQL is the database."),
            make_semantic(2, "JWT is used for auth."),
            make_semantic(3, "Redis is used for caching."),
        ]
        response = json.dumps({
            "assignments": [[1, "Database"], [2, "Authentication"], [3, "Caching"]]
        })
        mock_client = make_mock_client(response)
        result = cluster_semantics_batch(nodes, client=mock_client)
        assert "Database" in result
        assert 1 in result["Database"]
        assert "Authentication" in result
        assert 2 in result["Authentication"]

    def test_fallback_on_bad_json(self):
        nodes = [make_semantic(1, "Fact A"), make_semantic(2, "Fact B")]
        mock_client = make_mock_client("not valid json")
        result = cluster_semantics_batch(nodes, client=mock_client)
        assert "General" in result
        assert len(result["General"]) == 2

    def test_unassigned_nodes_go_to_miscellaneous(self):
        nodes = [
            make_semantic(1, "Fact A"),
            make_semantic(2, "Fact B"),
            make_semantic(3, "Fact C"),
        ]
        # Only assign nodes 1 and 2
        response = json.dumps({"assignments": [[1, "Topic X"], [2, "Topic X"]]})
        mock_client = make_mock_client(response)
        result = cluster_semantics_batch(nodes, client=mock_client)
        assert 3 in result.get("Miscellaneous", [])


class TestClusterThemes:
    def _make_store_with_semantics(self, n: int = 6) -> MemoryStore:
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        topics = ["Database", "Auth", "Performance"]
        for i in range(n):
            node = SemanticNode(
                fact=f"Fact {i+1} about {topics[i % len(topics)]}.",
                source_episode_ids=[i + 1],
            )
            store.add_semantic(node)
        return store

    def test_creates_themes(self):
        store = self._make_store_with_semantics(6)
        response = json.dumps({
            "assignments": [
                [1, "Database"], [2, "Authentication"],
                [3, "Performance"], [4, "Database"],
                [5, "Authentication"], [6, "Performance"],
            ]
        })
        mock_client = make_mock_client(response)
        themes = cluster_themes(store, client=mock_client)
        assert len(themes) >= 2
        labels = {t.label for t in themes}
        assert "Database" in labels or "Authentication" in labels

    def test_merges_into_existing_theme(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)

        # Add an existing theme
        existing = Theme(label="Database", semantic_ids=[1])
        store.add_theme(existing)

        # Add a new semantic node
        node = SemanticNode(fact="PostgreSQL version is 15.", source_episode_ids=[2])
        node = store.add_semantic(node)

        # Cluster returns same label "Database"
        response = json.dumps({"assignments": [[1, "Database"]]})
        mock_client = make_mock_client(response)
        themes = cluster_themes(store, nodes=[node], client=mock_client)

        # Should update the existing theme, not create a new one
        all_themes = store.get_all_themes()
        db_themes = [t for t in all_themes if t.label == "Database"]
        assert len(db_themes) == 1
        assert node.id in db_themes[0].semantic_ids

    def test_no_processing_for_already_themed(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        node = SemanticNode(fact="Some fact.", source_episode_ids=[1])
        node = store.add_semantic(node)
        theme = Theme(label="General", semantic_ids=[node.id])
        store.add_theme(theme)

        mock_client = MagicMock()
        themes = cluster_themes(store, client=mock_client)
        assert themes == []
        mock_client.invoke_model.assert_not_called()
