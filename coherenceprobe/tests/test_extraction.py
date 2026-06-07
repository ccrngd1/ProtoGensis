"""Tests for claim extraction."""

import pytest
from coherenceprobe.extraction import extract_claims, _normalize_claim
from coherenceprobe.models import AgentOutput, CoherenceConfig


def test_normalize_claim_removes_hedging():
    """Test that normalization removes hedging phrases."""
    assert _normalize_claim("I think that the port is 8080") == "the port is 8080"
    assert _normalize_claim("It seems that users are active") == "users are active"
    assert _normalize_claim("Perhaps the system is down") == "the system is down"


def test_normalize_claim_removes_punctuation():
    """Test that normalization removes trailing punctuation."""
    assert _normalize_claim("The port is 8080.") == "the port is 8080"
    assert _normalize_claim("The system is down!") == "the system is down"


def test_normalize_claim_lowercase():
    """Test that normalization converts to lowercase."""
    assert _normalize_claim("The Port Is 8080") == "the port is 8080"


def test_extract_claims_local_mode(local_config):
    """Test claim extraction in local mode (spaCy)."""
    # Skip if spaCy not available
    pytest.importorskip("spacy")

    outputs = [
        AgentOutput(
            agent="test",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="The server runs on port 8080. The system is operational. It handles many requests.",
            metadata={}
        )
    ]

    claims = extract_claims(outputs, local_config)

    # Should extract multiple declarative sentences
    assert len(claims) > 0
    assert all(claim.agent == "test" for claim in claims)


def test_extract_claims_filters_questions(local_config):
    """Test that local extraction filters out questions."""
    pytest.importorskip("spacy")

    outputs = [
        AgentOutput(
            agent="test",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="The port is 8080. What is the status? The system is up.",
            metadata={}
        )
    ]

    claims = extract_claims(outputs, local_config)

    # Questions should be filtered out
    claim_texts = [c.text for c in claims]
    assert not any("?" in text for text in claim_texts)


def test_extract_claims_filters_uncertainty(local_config):
    """Test that local extraction filters uncertain statements."""
    pytest.importorskip("spacy")

    outputs = [
        AgentOutput(
            agent="test",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="The port is 8080. Maybe the system is down. The server might be slow.",
            metadata={}
        )
    ]

    claims = extract_claims(outputs, local_config)

    # Uncertain statements should be filtered
    claim_texts = [c.normalized for c in claims]
    assert not any("maybe" in text or "might" in text for text in claim_texts)


def test_extract_claims_empty_output(local_config):
    """Test extraction with empty output."""
    pytest.importorskip("spacy")

    outputs = [
        AgentOutput(
            agent="test",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="",
            metadata={}
        )
    ]

    claims = extract_claims(outputs, local_config)
    assert len(claims) == 0


def test_extract_claims_multiple_agents(local_config):
    """Test extraction from multiple agents."""
    pytest.importorskip("spacy")

    outputs = [
        AgentOutput(
            agent="agent1",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="The port is 8080.",
            metadata={}
        ),
        AgentOutput(
            agent="agent2",
            timestamp="2026-01-01T00:00:01Z",
            input="test",
            output="The system is operational.",
            metadata={}
        ),
    ]

    claims = extract_claims(outputs, local_config)

    agents = {c.agent for c in claims}
    assert "agent1" in agents
    assert "agent2" in agents
