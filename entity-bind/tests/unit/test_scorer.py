"""Unit tests for RapidFuzz scorer."""

import pytest
from entity_bind.catalog import Entity
from entity_bind.scoring import RapidFuzzScorer


@pytest.fixture
def scorer():
    """Create a RapidFuzz scorer."""
    return RapidFuzzScorer()


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    return [
        Entity(
            id="person_alex_chen",
            type="person",
            name="Alex Chen",
            email="alex.chen@company.com",
            aliases=["A. Chen"],
            metadata="Engineering team, backend developer"
        ),
        Entity(
            id="person_alex_kumar",
            type="person",
            name="Alex Kumar",
            email="alex.kumar@company.com",
            aliases=["A. Kumar"],
            metadata="Customer success team, account manager"
        ),
        Entity(
            id="person_priya",
            type="person",
            name="Priya Shah",
            email="priya@company.com",
            metadata="Product manager"
        ),
        Entity(
            id="doc_launch_2025",
            type="document",
            title="Product Launch Plan 2025",
            owner="person_priya",
            updated_at="2025-03-15",
            metadata="Q1 2025 launch strategy"
        ),
        Entity(
            id="doc_launch_2024",
            type="document",
            title="Product Launch Plan 2024",
            owner="person_alex_chen",
            updated_at="2024-03-15",
            metadata="Q1 2024 launch strategy"
        )
    ]


def test_exact_match(scorer, sample_entities):
    """Test exact name match gets high score."""
    results = scorer.score_all(
        mention="Priya Shah",
        candidates=sample_entities,
        expected_type="person"
    )

    # Should have high confidence for exact match
    best = max(results, key=lambda x: x.score)
    assert best.entity.id == "person_priya"
    assert best.score >= 0.9


def test_partial_match(scorer, sample_entities):
    """Test partial name match."""
    results = scorer.score_all(
        mention="Alex",
        candidates=[e for e in sample_entities if e.type == "person"],
        expected_type="person"
    )

    # Should find both Alex entries
    alex_results = [r for r in results if "alex" in r.entity.name.lower()]
    assert len(alex_results) == 2
    assert all(r.score > 0.5 for r in alex_results)


def test_alias_match(scorer, sample_entities):
    """Test matching against aliases."""
    results = scorer.score_all(
        mention="A. Chen",
        candidates=sample_entities,
        expected_type="person"
    )

    # Should match via alias
    best = max(results, key=lambda x: x.score)
    assert best.entity.id == "person_alex_chen"
    # Check for alias match (can be "alias" or "alias:X")
    assert any("alias" in field for field in best.matched_fields)


def test_type_mismatch_penalty(scorer, sample_entities):
    """Test that type mismatches get penalized."""
    # Search for "Launch" expecting person (wrong type)
    person_results = scorer.score_all(
        mention="Launch",
        candidates=sample_entities,
        expected_type="person"
    )

    # Search for "Launch" expecting document (correct type)
    doc_results = scorer.score_all(
        mention="Launch",
        candidates=sample_entities,
        expected_type="document"
    )

    # Document results should score higher
    best_person = max(person_results, key=lambda x: x.score)
    best_doc = max(doc_results, key=lambda x: x.score)

    assert best_doc.score > best_person.score
    assert best_doc.entity.type == "document"


def test_recency_boost(scorer, sample_entities):
    """Test that recent entities get a boost."""
    # Both documents have similar titles, but different dates
    doc_entities = [e for e in sample_entities if e.type == "document"]

    results = scorer.score_all(
        mention="Launch Plan",
        candidates=doc_entities,
        expected_type="document"
    )

    # 2025 document (more recent) should score higher than 2024
    scores_by_id = {r.entity.id: r.score for r in results}

    # Both should be found
    assert "doc_launch_2025" in scores_by_id
    assert "doc_launch_2024" in scores_by_id

    # More recent should score higher
    assert scores_by_id["doc_launch_2025"] > scores_by_id["doc_launch_2024"]


def test_phonetic_similarity(scorer):
    """Test phonetic matching for similar sounding names."""
    entities = [
        Entity(id="person_jon", type="person", name="Jon"),
        Entity(id="person_john", type="person", name="John"),
        Entity(id="person_mike", type="person", name="Mike")
    ]

    # "John" and "Jon" sound similar
    results = scorer.score_all(
        mention="John",
        candidates=entities,
        expected_type="person"
    )

    # Both Jon and John should score reasonably high
    jon_score = next(r.score for r in results if r.entity.id == "person_jon")
    john_score = next(r.score for r in results if r.entity.id == "person_john")
    mike_score = next(r.score for r in results if r.entity.id == "person_mike")

    # John (exact) should score highest
    assert john_score > jon_score
    # Jon (phonetically similar) should score higher than Mike (unrelated)
    assert jon_score > mike_score


def test_metadata_context_match(scorer, sample_entities):
    """Test that metadata helps disambiguation."""
    # "Alex from engineering" should prefer Alex Chen
    results = scorer.score_all(
        mention="Alex from engineering",
        candidates=[e for e in sample_entities if e.type == "person"],
        expected_type="person",
        context="engineering backend developer"
    )

    best = max(results, key=lambda x: x.score)
    # Should match Alex Chen who is in engineering
    assert best.entity.id == "person_alex_chen"


def test_empty_candidates(scorer):
    """Test scoring with empty candidate list."""
    results = scorer.score_all(
        mention="Nobody",
        candidates=[],
        expected_type="person"
    )

    assert len(results) == 0


def test_no_mention(scorer, sample_entities):
    """Test scoring with empty mention."""
    results = scorer.score_all(
        mention="",
        candidates=sample_entities,
        expected_type="person"
    )

    # Should still return results but with low scores
    assert len(results) > 0
    assert all(r.score < 0.5 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
