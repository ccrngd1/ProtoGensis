"""Tests for semantic extraction with mocked boto3."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from xmemory.models import Episode, SemanticNode
from xmemory.schema import init_db
from xmemory.semantics import extract_facts_from_episode, extract_semantics, is_duplicate
from xmemory.store import MemoryStore


def make_mock_client_sequence(responses: list) -> MagicMock:
    """Return mock client that cycles through response strings."""
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


def make_episode(eid: int = 1, summary: str = "Test episode summary") -> Episode:
    ep = Episode(session_id="s1", summary=summary, message_ids=[1, 2, 3])
    ep.id = eid
    return ep


class TestExtractFactsFromEpisode:
    def test_parses_json_array(self):
        facts_json = '["User prefers dark mode.", "Database is PostgreSQL.", "API uses JWT auth."]'
        mock_client = make_mock_client_sequence([facts_json])
        ep = make_episode()
        facts = extract_facts_from_episode(ep, client=mock_client)
        assert len(facts) == 3
        assert "User prefers dark mode." in facts

    def test_handles_markdown_fences(self):
        response = '```json\n["Fact one.", "Fact two."]\n```'
        mock_client = make_mock_client_sequence([response])
        ep = make_episode()
        facts = extract_facts_from_episode(ep, client=mock_client)
        assert len(facts) == 2

    def test_fallback_line_split(self):
        response = "- The system uses Redis.\n- Authentication is JWT-based.\n- Deployment is on AWS."
        mock_client = make_mock_client_sequence([response])
        ep = make_episode()
        facts = extract_facts_from_episode(ep, client=mock_client)
        assert len(facts) >= 2


class TestIsDuplicate:
    def test_returns_false_for_empty_existing(self):
        mock_client = MagicMock()
        is_dup, matching_fact = is_duplicate("Some fact", [], client=mock_client)
        assert is_dup is False
        assert matching_fact is None
        mock_client.invoke_model.assert_not_called()

    def test_parses_duplicate_true(self):
        response = '{"duplicate": true, "reason": "same as existing"}'
        mock_client = make_mock_client_sequence([response])
        is_dup, matching_fact = is_duplicate("New fact", ["Existing fact"], client=mock_client)
        assert is_dup is True
        assert matching_fact is not None

    def test_parses_duplicate_false(self):
        response = '{"duplicate": false, "reason": "different topic"}'
        mock_client = make_mock_client_sequence([response])
        is_dup, matching_fact = is_duplicate("New fact", ["Different fact"], client=mock_client)
        assert is_dup is False
        assert matching_fact is None


class TestExtractSemantics:
    def _make_store_with_episode(self) -> tuple:
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        ep = Episode(session_id="s1", summary="We chose PostgreSQL and JWT.", message_ids=[])
        ep = store.add_episode(ep)
        return store, ep

    def test_creates_semantic_nodes(self):
        store, ep = self._make_store_with_episode()
        facts_json = '["PostgreSQL is the database.", "JWT is used for auth."]'
        dedup_resp = '{"duplicate": false, "reason": "new"}'
        mock_client = make_mock_client_sequence([facts_json, dedup_resp, dedup_resp])

        nodes = extract_semantics(store, episodes=[ep], client=mock_client)
        assert len(nodes) == 2

    def test_deduplication_skips_existing(self):
        store, ep = self._make_store_with_episode()
        # First add an existing semantic
        existing = SemanticNode(fact="PostgreSQL is the database.", source_episode_ids=[])
        store.add_semantic(existing)

        facts_json = '["PostgreSQL is the database.", "JWT is used for auth."]'
        # First fact is a duplicate, second is not
        responses = [facts_json, '{"duplicate": true, "reason": "same"}', '{"duplicate": false, "reason": "new"}']
        mock_client = make_mock_client_sequence(responses)

        nodes = extract_semantics(store, episodes=[ep], client=mock_client)
        assert len(nodes) == 1
        assert nodes[0].fact == "JWT is used for auth."

    def test_no_processing_when_no_episodes(self):
        conn = init_db(":memory:")
        store = MemoryStore(conn)
        mock_client = MagicMock()
        nodes = extract_semantics(store, episodes=[], client=mock_client)
        assert nodes == []
        mock_client.invoke_model.assert_not_called()

    def test_source_episode_ids_set(self):
        store, ep = self._make_store_with_episode()
        facts_json = '["Fact about the system."]'
        dedup_resp = '{"duplicate": false, "reason": "new"}'
        mock_client = make_mock_client_sequence([facts_json, dedup_resp])
        nodes = extract_semantics(store, episodes=[ep], client=mock_client)
        assert ep.id in nodes[0].source_episode_ids

    def test_dedup_merge_persists_to_database(self):
        """Test fix #1: semantic dedup merge updates are persisted to DB."""
        store, ep1 = self._make_store_with_episode()

        # Add first episode with fact
        facts_json1 = '["PostgreSQL is the database."]'
        dedup_resp1 = '{"duplicate": false, "reason": "new"}'
        mock_client1 = make_mock_client_sequence([facts_json1, dedup_resp1])
        nodes1 = extract_semantics(store, episodes=[ep1], client=mock_client1)
        assert len(nodes1) == 1
        original_semantic_id = nodes1[0].id

        # Add second episode with duplicate fact (LLM says duplicate)
        ep2 = Episode(session_id="s1", summary="Another discussion of PostgreSQL.", message_ids=[])
        ep2 = store.add_episode(ep2)

        facts_json2 = '["PostgreSQL is our database choice."]'
        # LLM says it's a duplicate
        dedup_resp2 = '{"duplicate": true, "reason": "PostgreSQL is the database"}'
        mock_client2 = make_mock_client_sequence([facts_json2, dedup_resp2])
        nodes2 = extract_semantics(store, episodes=[ep2], client=mock_client2)

        # Should not create a new node (merge happened)
        assert len(nodes2) == 0

        # Verify the merge was persisted: reload from DB and check source_episode_ids
        all_semantics = store.get_all_semantics()
        merged_node = [n for n in all_semantics if n.id == original_semantic_id][0]

        # Should contain both episode IDs
        assert ep1.id in merged_node.source_episode_ids
        assert ep2.id in merged_node.source_episode_ids

    def test_dedup_uses_llm_verdict_not_string_match(self):
        """Test fix #2: dedup logic uses LLM's verdict, not exact string matching."""
        store, ep1 = self._make_store_with_episode()

        # Add first fact
        facts_json1 = '["We use PostgreSQL for the database."]'
        dedup_resp1 = '{"duplicate": false, "reason": "new"}'
        mock_client1 = make_mock_client_sequence([facts_json1, dedup_resp1])
        nodes1 = extract_semantics(store, episodes=[ep1], client=mock_client1)
        assert len(nodes1) == 1

        # Add second episode with semantically equivalent but differently worded fact
        ep2 = Episode(session_id="s1", summary="Database discussion continued.", message_ids=[])
        ep2 = store.add_episode(ep2)

        # Different wording: "PostgreSQL is our primary database"
        facts_json2 = '["PostgreSQL is our primary database."]'
        # LLM correctly identifies semantic equivalence
        dedup_resp2 = '{"duplicate": true, "reason": "PostgreSQL for the database"}'
        mock_client2 = make_mock_client_sequence([facts_json2, dedup_resp2])
        nodes2 = extract_semantics(store, episodes=[ep2], client=mock_client2)

        # Should merge (no new node created)
        assert len(nodes2) == 0

        # Verify the original node was updated
        all_semantics = store.get_all_semantics()
        assert len(all_semantics) == 1
        assert ep2.id in all_semantics[0].source_episode_ids
