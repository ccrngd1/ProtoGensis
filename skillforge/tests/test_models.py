"""
Tests for data models.
"""
import pytest
from datetime import datetime

from skillforge.models import (
    SkillGap, SkillSpec, SkillPackage, ValidationResult, ValidationIssue,
    PipelineConfig, FailureType, GapClassification, RecommendedAction,
    ConflictAnalysis
)


def test_skill_gap_creation():
    """Test SkillGap creation and serialization."""
    gap = SkillGap(
        failure_context="Test context",
        failure_type=FailureType.ERROR,
        frequency=3,
        affected_agents=["Agent1"],
        cluster_id="test123"
    )

    assert gap.failure_context == "Test context"
    assert gap.frequency == 3
    assert len(gap.affected_agents) == 1


def test_skill_gap_to_dict():
    """Test SkillGap serialization."""
    gap = SkillGap(
        failure_context="Test",
        failure_type=FailureType.ERROR,
        frequency=1,
        affected_agents=["A"],
        cluster_id="id"
    )

    data = gap.to_dict()
    assert 'failure_context' in data
    assert data['failure_type'] == 'error'
    assert 'timestamp' in data


def test_skill_gap_from_dict():
    """Test SkillGap deserialization."""
    data = {
        'failure_context': 'Test',
        'failure_type': 'error',
        'frequency': 1,
        'affected_agents': ['A'],
        'cluster_id': 'id',
        'timestamp': datetime.now().isoformat()
    }

    gap = SkillGap.from_dict(data)
    assert gap.failure_context == 'Test'
    assert gap.failure_type == FailureType.ERROR


def test_skill_spec_creation():
    """Test SkillSpec creation."""
    conflict = ConflictAnalysis(
        has_conflict=False,
        conflicting_skills=[],
        overlap_description="",
        merge_recommended=False
    )

    spec = SkillSpec(
        gap_id="gap123",
        root_cause="Test root cause",
        proposed_scope="Test scope",
        priority_score=0.8,
        conflict_analysis=conflict,
        recommended_action=RecommendedAction.CREATE_NEW,
        classification=GapClassification.MISSING_SKILL
    )

    assert spec.priority_score == 0.8
    assert spec.classification == GapClassification.MISSING_SKILL


def test_skill_spec_serialization():
    """Test SkillSpec to/from dict."""
    conflict = ConflictAnalysis(has_conflict=False)
    spec = SkillSpec(
        gap_id="gap123",
        root_cause="Root",
        proposed_scope="Scope",
        priority_score=0.5,
        conflict_analysis=conflict,
        recommended_action=RecommendedAction.CREATE_NEW,
        classification=GapClassification.MISSING_SKILL
    )

    data = spec.to_dict()
    spec2 = SkillSpec.from_dict(data)

    assert spec2.gap_id == spec.gap_id
    assert spec2.priority_score == spec.priority_score


def test_validation_result():
    """Test ValidationResult."""
    result = ValidationResult(
        tier1_passed=True,
        tier2_passed=True,
        scores={'quality': 0.8},
        issues=[],
        iteration_count=1
    )

    assert result.passed is True


def test_validation_result_failed():
    """Test ValidationResult when failed."""
    result = ValidationResult(
        tier1_passed=True,
        tier2_passed=False,
        scores={'quality': 0.4},
        issues=[],
        iteration_count=2
    )

    assert result.passed is False


def test_skill_package():
    """Test SkillPackage."""
    package = SkillPackage(
        skill_name="test-skill",
        skill_md_content="# Test",
        supporting_files={'file.txt': 'content'},
        metadata={'key': 'value'}
    )

    assert package.skill_name == "test-skill"
    assert len(package.supporting_files) == 1


def test_skill_package_serialization():
    """Test SkillPackage serialization."""
    package = SkillPackage(
        skill_name="test",
        skill_md_content="content"
    )

    data = package.to_dict()
    package2 = SkillPackage.from_dict(data)

    assert package2.skill_name == package.skill_name


def test_pipeline_config_defaults():
    """Test PipelineConfig default values."""
    config = PipelineConfig()

    assert config.max_skills_per_run == 3
    assert config.max_validation_iterations == 3
    assert config.dry_run is False
    assert config.mock_mode is False


def test_pipeline_config_to_dict():
    """Test PipelineConfig serialization."""
    config = PipelineConfig(
        max_skills_per_run=5,
        dry_run=True
    )

    data = config.to_dict()
    assert data['max_skills_per_run'] == 5
    assert data['dry_run'] is True
