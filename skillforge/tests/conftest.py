"""
Pytest fixtures and test configuration.
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from skillforge.models import (
    PipelineConfig, SkillGap, SkillSpec, SkillPackage,
    FailureType, GapClassification, RecommendedAction, ConflictAnalysis
)


@pytest.fixture
def mock_config():
    """Create a mock PipelineConfig for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PipelineConfig(
            skills_dir=str(Path(tmpdir) / "skills"),
            output_skills_dir=str(Path(tmpdir) / "output"),
            tracker_db_path=str(Path(tmpdir) / "tracker.jsonl"),
            mock_mode=True,
            dry_run=True,
            create_pr=False
        )
        # Create directories
        Path(config.skills_dir).mkdir(parents=True, exist_ok=True)
        Path(config.output_skills_dir).mkdir(parents=True, exist_ok=True)
        yield config


@pytest.fixture
def sample_skill_gap():
    """Create a sample SkillGap for testing."""
    return SkillGap(
        failure_context="[PreCog] code_generation: Failed to generate valid Python code",
        failure_type=FailureType.ERROR,
        frequency=5,
        affected_agents=["PreCog"],
        cluster_id="abc123",
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_skill_spec():
    """Create a sample SkillSpec for testing."""
    return SkillSpec(
        gap_id="abc123",
        root_cause="Failed to generate valid Python code",
        proposed_scope="Create a skill to handle Python code generation errors",
        priority_score=0.75,
        conflict_analysis=ConflictAnalysis(
            has_conflict=False,
            conflicting_skills=[],
            overlap_description="",
            merge_recommended=False
        ),
        recommended_action=RecommendedAction.CREATE_NEW,
        classification=GapClassification.MISSING_SKILL,
        metadata={'frequency': 5}
    )


@pytest.fixture
def sample_skill_package():
    """Create a sample SkillPackage for testing."""
    skill_content = """---
name: test-skill
description: A test skill
allowed-tools: [Read, Write]
version: 1.0.0
---

# Instructions

Test skill instructions.

## When to Use

Use this skill for testing.

## Steps

1. First step
2. Second step

## Test Scenarios

1. Test scenario 1
"""
    return SkillPackage(
        skill_name="test-skill",
        skill_md_content=skill_content,
        supporting_files={},
        metadata={'iteration': 1}
    )


@pytest.fixture
def temp_skills_dir():
    """Create a temporary skills directory with sample skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        # Create a sample skill
        skill_dir = skills_dir / "sample-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: sample-skill
description: A sample skill for testing
allowed-tools: [Read, Write, Bash]
version: 1.0.0
---

# Instructions

This is a sample skill for testing purposes.

## When to Use

Use this skill when you need to test skill loading.
""")

        yield skills_dir
