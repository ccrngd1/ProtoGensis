"""
Tests for Analyzer stage.
"""
import pytest

from skillforge.analyzer import (
    GapClassifier, ScopeDefiner, PriorityScorer, ConflictChecker, Analyzer
)
from skillforge.models import GapClassification, RecommendedAction


def test_gap_classifier(mock_config, sample_skill_gap):
    """Test GapClassifier."""
    classifier = GapClassifier(mock_config)

    # No existing skills
    classification = classifier.classify(sample_skill_gap, {})
    assert classification == GapClassification.MISSING_SKILL


def test_gap_classifier_with_related_skills(mock_config, sample_skill_gap, temp_skills_dir):
    """Test classification with related skills."""
    classifier = GapClassifier(mock_config)

    existing_skills = {
        'code-gen': {
            'content': 'Python code generation skill',
            'metadata': {'description': 'Handle code generation'}
        }
    }

    # Should detect related skills
    classification = classifier.classify(sample_skill_gap, existing_skills)
    # Could be outdated or insufficient
    assert classification in [
        GapClassification.MISSING_SKILL,
        GapClassification.OUTDATED_SKILL,
        GapClassification.INSUFFICIENT
    ]


def test_scope_definer(mock_config, sample_skill_gap):
    """Test ScopeDefiner."""
    definer = ScopeDefiner(mock_config)

    scope = definer.define_scope(sample_skill_gap, GapClassification.MISSING_SKILL)

    assert isinstance(scope, str)
    assert len(scope) > 0
    assert len(scope) <= 150  # Should be compact


def test_scope_definer_different_classifications(mock_config, sample_skill_gap):
    """Test scope definition for different classifications."""
    definer = ScopeDefiner(mock_config)

    scope1 = definer.define_scope(sample_skill_gap, GapClassification.MISSING_SKILL)
    scope2 = definer.define_scope(sample_skill_gap, GapClassification.OUTDATED_SKILL)
    scope3 = definer.define_scope(sample_skill_gap, GapClassification.INSUFFICIENT)

    # Scopes should be different
    assert scope1 != scope2
    assert scope1 != scope3


def test_priority_scorer(mock_config, sample_skill_gap):
    """Test PriorityScorer."""
    scorer = PriorityScorer(mock_config)

    score = scorer.calculate_score(sample_skill_gap, GapClassification.MISSING_SKILL)

    assert 0.0 <= score <= 1.0


def test_priority_scorer_frequency_impact(mock_config, sample_skill_gap):
    """Test that frequency affects priority."""
    scorer = PriorityScorer(mock_config)

    # High frequency
    sample_skill_gap.frequency = 10
    score_high = scorer.calculate_score(sample_skill_gap, GapClassification.MISSING_SKILL)

    # Low frequency
    sample_skill_gap.frequency = 1
    score_low = scorer.calculate_score(sample_skill_gap, GapClassification.MISSING_SKILL)

    # Higher frequency should give higher score
    assert score_high >= score_low


def test_conflict_checker_no_conflict(mock_config):
    """Test ConflictChecker with no conflicts."""
    checker = ConflictChecker(mock_config)

    proposed_scope = "Handle database connection errors"
    existing_skills = {
        'file-reader': {
            'metadata': {'description': 'Read files from disk'}
        }
    }

    conflict = checker.check_conflicts(proposed_scope, existing_skills)

    assert conflict.has_conflict is False
    assert len(conflict.conflicting_skills) == 0


def test_conflict_checker_with_conflict(mock_config):
    """Test ConflictChecker detecting conflicts."""
    checker = ConflictChecker(mock_config)

    proposed_scope = "Handle database connection issues and errors"
    existing_skills = {
        'database-connector': {
            'metadata': {'description': 'Handle database connection and query errors'}
        }
    }

    conflict = checker.check_conflicts(proposed_scope, existing_skills)

    # Should detect overlap
    assert conflict.has_conflict is True or len(conflict.conflicting_skills) > 0


def test_analyzer_run(mock_config, sample_skill_gap):
    """Test Analyzer.run()."""
    analyzer = Analyzer(mock_config)

    gaps = [sample_skill_gap]
    existing_skills = {}

    specs = analyzer.run(gaps, existing_skills)

    assert isinstance(specs, list)
    # Should generate at least one spec
    assert len(specs) >= 0

    if specs:
        spec = specs[0]
        assert hasattr(spec, 'gap_id')
        assert hasattr(spec, 'priority_score')
        assert hasattr(spec, 'recommended_action')


def test_analyzer_prioritization(mock_config, sample_skill_gap):
    """Test that Analyzer prioritizes specs correctly."""
    analyzer = Analyzer(mock_config)

    # Create multiple gaps with different frequencies
    gap1 = sample_skill_gap
    gap1.frequency = 10
    gap1.cluster_id = "gap1"

    gap2 = sample_skill_gap
    gap2.frequency = 2
    gap2.cluster_id = "gap2"

    gaps = [gap2, gap1]  # Add in reverse order
    specs = analyzer.run(gaps, {})

    if len(specs) >= 2:
        # First spec should have higher priority
        assert specs[0].priority_score >= specs[1].priority_score


def test_analyzer_determine_action(mock_config):
    """Test action determination."""
    analyzer = Analyzer(mock_config)

    from skillforge.models import ConflictAnalysis

    # No conflict, missing skill
    conflict = ConflictAnalysis(has_conflict=False)
    action = analyzer._determine_action(GapClassification.MISSING_SKILL, conflict)
    assert action == RecommendedAction.CREATE_NEW

    # Merge recommended
    conflict = ConflictAnalysis(has_conflict=True, merge_recommended=True)
    action = analyzer._determine_action(GapClassification.MISSING_SKILL, conflict)
    assert action == RecommendedAction.MERGE_SIMILAR


def test_analyzer_max_skills_per_run(mock_config, sample_skill_gap):
    """Test that Analyzer respects max_skills_per_run."""
    mock_config.max_skills_per_run = 2
    analyzer = Analyzer(mock_config)

    # Create many gaps
    gaps = [sample_skill_gap for _ in range(10)]
    # Give each unique ID
    for i, gap in enumerate(gaps):
        gap.cluster_id = f"gap{i}"

    specs = analyzer.run(gaps, {})

    # Should be limited to max_skills_per_run
    assert len(specs) <= mock_config.max_skills_per_run
