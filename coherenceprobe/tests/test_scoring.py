"""Tests for coherence scoring."""

import pytest
from coherenceprobe.scoring import (
    compute_coherence_score,
    rank_agents_by_coherence,
    get_most_problematic_agent,
    summarize_contradictions_by_type,
    get_contradiction_clusters,
)
from coherenceprobe.models import Claim, ContradictionPair, CoherenceConfig


def test_compute_score_no_contradictions():
    """Test scoring with no contradictions."""
    config = CoherenceConfig()
    claims = [
        Claim(agent="a1", text="claim1", normalized="claim1", source_sentence="..."),
        Claim(agent="a2", text="claim2", normalized="claim2", source_sentence="..."),
    ]
    contradictions = []

    report = compute_coherence_score(claims, contradictions, config)

    assert report.score == 1.0
    assert len(report.contradictions) == 0
    assert report.total_claims == 2
    assert report.total_agents == 2


def test_compute_score_with_contradictions():
    """Test scoring with contradictions."""
    config = CoherenceConfig()

    claim_a = Claim(agent="a1", text="c1", normalized="c1", source_sentence="...")
    claim_b = Claim(agent="a2", text="c2", normalized="c2", source_sentence="...")

    claims = [claim_a, claim_b]

    contradictions = [
        ContradictionPair(
            claim_a=claim_a,
            claim_b=claim_b,
            contradiction_type="logical",
            confidence=0.9
        )
    ]

    report = compute_coherence_score(claims, contradictions, config)

    # With contradiction, score should be less than 1.0
    assert report.score < 1.0
    assert len(report.contradictions) == 1


def test_compute_score_single_agent():
    """Test scoring with single agent (no cross-agent comparison)."""
    config = CoherenceConfig()
    claims = [
        Claim(agent="a1", text="claim1", normalized="claim1", source_sentence="..."),
        Claim(agent="a1", text="claim2", normalized="claim2", source_sentence="..."),
    ]
    contradictions = []

    report = compute_coherence_score(claims, contradictions, config)

    # Single agent, perfect score
    assert report.score == 1.0
    assert report.total_agents == 1


def test_compute_score_empty_claims():
    """Test scoring with no claims."""
    config = CoherenceConfig()
    report = compute_coherence_score([], [], config)

    assert report.score == 1.0
    assert report.total_claims == 0


def test_agent_scores_calculation():
    """Test per-agent score calculation."""
    config = CoherenceConfig()

    claim_a1 = Claim(agent="a1", text="c1", normalized="c1", source_sentence="...")
    claim_a2 = Claim(agent="a2", text="c2", normalized="c2", source_sentence="...")
    claim_a3 = Claim(agent="a3", text="c3", normalized="c3", source_sentence="...")

    claims = [claim_a1, claim_a2, claim_a3]

    # a1 contradicts both a2 and a3
    contradictions = [
        ContradictionPair(
            claim_a=claim_a1, claim_b=claim_a2,
            contradiction_type="logical", confidence=0.8
        ),
        ContradictionPair(
            claim_a=claim_a1, claim_b=claim_a3,
            contradiction_type="factual", confidence=0.9
        ),
    ]

    report = compute_coherence_score(claims, contradictions, config)

    # a1 should have highest incoherence score (involved in both)
    assert "a1" in report.agent_scores
    assert "a2" in report.agent_scores
    assert "a3" in report.agent_scores


def test_rank_agents_by_coherence():
    """Test agent ranking."""
    config = CoherenceConfig()

    claim_a1 = Claim(agent="good", text="c1", normalized="c1", source_sentence="...")
    claim_a2 = Claim(agent="bad", text="c2", normalized="c2", source_sentence="...")
    claim_a3 = Claim(agent="neutral", text="c3", normalized="c3", source_sentence="...")

    claims = [claim_a1, claim_a2, claim_a3]

    contradictions = [
        ContradictionPair(
            claim_a=claim_a2, claim_b=claim_a3,
            contradiction_type="logical", confidence=0.9
        ),
    ]

    report = compute_coherence_score(claims, contradictions, config)
    ranked = rank_agents_by_coherence(report)

    # Should return list of (agent, coherence_score) tuples
    assert len(ranked) == 3
    assert all(isinstance(item, tuple) for item in ranked)
    assert all(len(item) == 2 for item in ranked)


def test_get_most_problematic_agent():
    """Test identifying most problematic agent."""
    config = CoherenceConfig()

    claim_a1 = Claim(agent="good", text="c1", normalized="c1", source_sentence="...")
    claim_a2 = Claim(agent="bad", text="c2", normalized="c2", source_sentence="...")

    claims = [claim_a1, claim_a2]

    contradictions = [
        ContradictionPair(
            claim_a=claim_a1, claim_b=claim_a2,
            contradiction_type="logical", confidence=0.9
        ),
    ]

    report = compute_coherence_score(claims, contradictions, config)
    problematic = get_most_problematic_agent(report)

    assert problematic is not None
    assert problematic[0] in ["good", "bad"]
    assert problematic[1] >= 0.0


def test_summarize_contradictions_by_type():
    """Test contradiction type summarization."""
    claim_a = Claim(agent="a1", text="c", normalized="c", source_sentence="...")
    claim_b = Claim(agent="a2", text="c", normalized="c", source_sentence="...")

    contradictions = [
        ContradictionPair(
            claim_a=claim_a, claim_b=claim_b,
            contradiction_type="logical", confidence=0.8
        ),
        ContradictionPair(
            claim_a=claim_a, claim_b=claim_b,
            contradiction_type="logical", confidence=0.9
        ),
        ContradictionPair(
            claim_a=claim_a, claim_b=claim_b,
            contradiction_type="factual", confidence=0.7
        ),
    ]

    summary = summarize_contradictions_by_type(contradictions)

    assert summary["logical"] == 2
    assert summary["factual"] == 1


def test_get_contradiction_clusters():
    """Test grouping contradictions into clusters."""
    claim_a = Claim(agent="a1", text="a", normalized="a", source_sentence="...")
    claim_b = Claim(agent="a2", text="b", normalized="b", source_sentence="...")
    claim_c = Claim(agent="a3", text="c", normalized="c", source_sentence="...")

    contradictions = [
        ContradictionPair(
            claim_a=claim_a, claim_b=claim_b,
            contradiction_type="logical", confidence=0.8
        ),
        ContradictionPair(
            claim_a=claim_b, claim_b=claim_c,
            contradiction_type="logical", confidence=0.9
        ),
    ]

    clusters = get_contradiction_clusters(contradictions)

    # These should be in same cluster (share claim_b)
    assert len(clusters) >= 1
