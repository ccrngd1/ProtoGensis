"""Tests for the FastAPI endpoints."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from memory.models import Memory, Consolidation


# ---------------------------------------------------------------------------
# App fixture with mocked orchestrator
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_orchestrator():
    orc = MagicMock()
    orc.status.return_value = {
        "memory_count": 5,
        "consolidation_count": 1,
        "unconsolidated_count": 2,
        "background_consolidation_running": False,
    }
    return orc


@pytest.fixture
def client(mock_orchestrator):
    """Create a test client with a mocked orchestrator attached."""
    # Import here so patching works correctly
    from api.main import create_app

    app = create_app()

    with TestClient(app, raise_server_exceptions=True) as c:
        # Ensure orchestrator is set on app state for test client
        app.state.orchestrator = mock_orchestrator
        yield c, mock_orchestrator


# ---------------------------------------------------------------------------
# /ingest
# ---------------------------------------------------------------------------

class TestIngestEndpoint:
    def test_ingest_success(self, client):
        c, orc = client
        memory = Memory(
            summary="Paris is the capital of France.",
            entities=["Paris", "France"],
            topics=["geography"],
            importance=0.9,
            source="test",
        )
        orc.ingest.return_value = memory

        resp = c.post("/ingest", json={"text": "Paris is the capital of France.", "source": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "Paris is the capital of France."
        assert "Paris" in data["entities"]
        assert data["importance"] == pytest.approx(0.9)
        orc.ingest.assert_called_once_with("Paris is the capital of France.", source="test")


# ---------------------------------------------------------------------------
# /query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_query_success(self, client):
        c, orc = client
        orc.query.return_value = "The capital of France is Paris [memory:abc]."

        resp = c.get("/query", params={"q": "What is the capital of France?"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "The capital of France is Paris [memory:abc]."

    def test_query_empty_string(self, client):
        c, orc = client
        resp = c.get("/query", params={"q": "   "})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

class TestStatusEndpoint:
    def test_status(self, client):
        c, orc = client
        resp = c.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["memory_count"] == 5
        assert data["consolidation_count"] == 1


# ---------------------------------------------------------------------------
# /consolidate
# ---------------------------------------------------------------------------

class TestConsolidateEndpoint:
    def test_consolidate_success(self, client):
        c, orc = client
        consolidation = Consolidation(
            memory_ids=["id1", "id2", "id3", "id4", "id5"],
            connections="connected",
            insights="insightful",
        )
        orc.consolidate.return_value = consolidation

        resp = c.post("/consolidate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["consolidated"] is True
        assert data["memory_count"] == 5

    def test_consolidate_not_enough_memories(self, client):
        c, orc = client
        orc.consolidate.return_value = None

        resp = c.post("/consolidate")
        assert resp.status_code == 200
        assert resp.json()["consolidated"] is False
