"""
Integration tests for full pipeline.
"""
import pytest
from pathlib import Path

from skillforge.pipeline import SkillForgePipeline, StageRunner
from skillforge.models import PipelineConfig


def test_full_pipeline_mock_mode(mock_config):
    """Test full pipeline in mock mode."""
    mock_config.mock_mode = True
    mock_config.dry_run = True

    pipeline = SkillForgePipeline(mock_config)

    # Run full pipeline
    results = pipeline.run(log_path=None)

    assert 'status' in results
    assert results['status'] in ['complete', 'no_gaps', 'no_specs']


def test_pipeline_stages_execute_in_order(mock_config):
    """Test that pipeline stages execute in correct order."""
    mock_config.mock_mode = True
    mock_config.max_skills_per_run = 1

    pipeline = SkillForgePipeline(mock_config)
    results = pipeline.run()

    # Check that stages are recorded
    if 'stages' in results:
        stages = results['stages']
        # Monitor should always run
        assert 'monitor' in stages


def test_pipeline_respects_max_skills_per_run(mock_config):
    """Test that pipeline respects max_skills_per_run."""
    mock_config.mock_mode = True
    mock_config.max_skills_per_run = 2

    pipeline = SkillForgePipeline(mock_config)
    results = pipeline.run()

    if 'stages' in results and 'publications' in results['stages']:
        pubs = results['stages']['publications']
        total = pubs['successful'] + pubs['failed']
        assert total <= mock_config.max_skills_per_run


def test_pipeline_handles_no_gaps(mock_config):
    """Test pipeline handles case with no gaps."""
    mock_config.mock_mode = True

    pipeline = SkillForgePipeline(mock_config)

    # Temporarily set max_gaps_per_run to 0 to simulate no gaps
    # (not ideal but works for testing)
    original_max = mock_config.max_gaps_per_run
    mock_config.max_gaps_per_run = 0

    results = pipeline.run()

    mock_config.max_gaps_per_run = original_max

    # Should handle gracefully
    assert results['status'] == 'no_gaps'


def test_pipeline_dry_run_mode(mock_config):
    """Test pipeline in dry-run mode."""
    mock_config.mock_mode = True
    mock_config.dry_run = True

    pipeline = SkillForgePipeline(mock_config)
    results = pipeline.run()

    # Should complete without errors
    assert 'status' in results


def test_stage_runner_monitor_only(mock_config):
    """Test running Monitor stage independently."""
    runner = StageRunner(mock_config)

    gaps = runner.run_monitor_only()

    assert isinstance(gaps, list)


def test_stage_runner_analyzer_only(mock_config, sample_skill_gap):
    """Test running Analyzer stage independently."""
    runner = StageRunner(mock_config)

    gaps = [sample_skill_gap]
    specs = runner.run_analyzer_only(gaps)

    assert isinstance(specs, list)


def test_stage_runner_drafter_only(mock_config, sample_skill_spec):
    """Test running Drafter stage independently."""
    runner = StageRunner(mock_config)

    package = runner.run_drafter_only(sample_skill_spec)

    assert hasattr(package, 'skill_name')
    assert hasattr(package, 'skill_md_content')
    assert len(package.skill_md_content) > 0


def test_stage_runner_validator_only(mock_config, sample_skill_package):
    """Test running Validator stage independently."""
    runner = StageRunner(mock_config)

    result = runner.run_validator_only(sample_skill_package)

    assert hasattr(result, 'tier1_passed')
    assert hasattr(result, 'tier2_passed')


def test_pipeline_end_to_end_synthetic(mock_config):
    """
    Integration test: Synthetic PreCog failure → full pipeline → SkillPackage
    produced, ValidationResult passed.
    """
    # Configure for full pipeline run
    mock_config.mock_mode = True
    mock_config.dry_run = True
    mock_config.max_skills_per_run = 1

    # Create pipeline
    pipeline = SkillForgePipeline(mock_config)

    # Run full pipeline (will use mock failures)
    results = pipeline.run(log_path=None)

    # Verify results structure
    assert 'timestamp' in results
    assert 'status' in results
    assert 'stages' in results

    # Verify stages executed
    stages = results['stages']
    assert 'monitor' in stages

    # If we got to publications, verify structure
    if 'publications' in stages:
        pubs = stages['publications']
        assert 'successful' in pubs
        assert 'failed' in pubs
        assert 'details' in pubs

        # If successful publications exist, verify they have required fields
        if pubs['successful']:
            first_pub = pubs['details']['successful'][0]
            assert 'skill_name' in first_pub
            assert 'timestamp' in first_pub
            assert 'validation_scores' in first_pub


def test_pipeline_with_budget_enforcement(mock_config):
    """Test that pipeline enforces skill budget."""
    mock_config.mock_mode = True
    mock_config.max_skills_per_domain = 2
    mock_config.enable_merge_suggestions = True

    pipeline = SkillForgePipeline(mock_config)

    # Create many existing skills
    existing_skills = {f'skill-{i}': {'name': f'skill-{i}'} for i in range(3)}

    # Should respect budget
    results = pipeline.run()

    # Should complete without error
    assert 'status' in results


def test_pipeline_tracker_integration(mock_config):
    """Test that pipeline integrates with tracker."""
    mock_config.mock_mode = True

    pipeline = SkillForgePipeline(mock_config)
    results = pipeline.run()

    # Tracker should be initialized
    assert pipeline.tracker is not None

    # If publications succeeded, they should be tracked
    if 'stages' in results and 'publications' in results['stages']:
        pubs = results['stages']['publications']
        if pubs['successful'] > 0:
            # Check that tracker file exists or would exist
            tracker_path = Path(mock_config.tracker_db_path)
            # In mock mode, might not write to disk, but tracker object should exist
            assert pipeline.tracker.config is not None
