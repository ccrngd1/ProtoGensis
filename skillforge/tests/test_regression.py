"""
Regression tests - Ensure generated SKILL.md doesn't break existing skill parsing.
"""
import pytest
from pathlib import Path
import tempfile

from skillforge.monitor import SkillInventoryChecker
from skillforge.validator import FormatValidator, LoadValidator
from skillforge.models import PipelineConfig, SkillPackage


def test_generated_skill_parses_correctly(mock_config, sample_skill_package):
    """Test that generated skill can be parsed correctly."""
    validator = FormatValidator()
    passed, issues = validator.validate(sample_skill_package)

    # Should parse without errors
    errors = [i for i in issues if i.severity == 'error']
    assert len(errors) == 0


def test_generated_skill_loads_correctly(mock_config, sample_skill_package):
    """Test that generated skill loads correctly."""
    validator = LoadValidator()
    passed, issues = validator.validate(sample_skill_package)

    assert passed is True


def test_generated_skill_doesnt_break_skill_inventory(mock_config):
    """Test that generated skill doesn't break skill inventory loading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        # Create a generated skill
        skill_dir = skills_dir / "generated-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: generated-skill
description: A generated skill
allowed-tools: [Read, Write]
version: 1.0.0
---

# Instructions

Generated instructions.

## When to Use

Use when testing.

## Steps

1. Step one
2. Step two
""")

        # Try to load with SkillInventoryChecker
        config = PipelineConfig(skills_dir=str(skills_dir))
        checker = SkillInventoryChecker(config)

        skills = checker.load_existing_skills()

        # Should load successfully
        assert 'generated-skill' in skills
        assert skills['generated-skill']['name'] == 'generated-skill'


def test_multiple_generated_skills_coexist(mock_config):
    """Test that multiple generated skills can coexist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"
        skills_dir.mkdir()

        # Create multiple generated skills
        for i in range(3):
            skill_dir = skills_dir / f"skill-{i}"
            skill_dir.mkdir()

            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(f"""---
name: skill-{i}
description: Generated skill {i}
allowed-tools: [Read]
version: 1.0.0
---

# Instructions

Skill {i} instructions.
""")

        # Load all skills
        config = PipelineConfig(skills_dir=str(skills_dir))
        checker = SkillInventoryChecker(config)

        skills = checker.load_existing_skills()

        # All should load
        assert len(skills) == 3
        for i in range(3):
            assert f'skill-{i}' in skills


def test_generated_skill_metadata_format(sample_skill_package):
    """Test that generated skill metadata is in correct format."""
    # Extract and parse frontmatter
    content = sample_skill_package.skill_md_content
    assert content.startswith('---')

    # Find end of frontmatter
    end_idx = content.find('---', 3)
    assert end_idx > 0

    frontmatter_text = content[3:end_idx].strip()

    # Should be valid YAML
    import yaml
    metadata = yaml.safe_load(frontmatter_text)

    # Check required fields
    assert 'name' in metadata
    assert 'description' in metadata
    assert 'allowed-tools' in metadata
    assert 'version' in metadata

    # Check types
    assert isinstance(metadata['name'], str)
    assert isinstance(metadata['description'], str)
    assert isinstance(metadata['allowed-tools'], list)


def test_generated_skill_has_required_sections(sample_skill_package):
    """Test that generated skill has required sections."""
    content = sample_skill_package.skill_md_content

    # Check for required sections
    assert '# Instructions' in content
    assert '## When to Use' in content
    assert '## Steps' in content


def test_generated_skill_no_executable_code(sample_skill_package):
    """Test that generated skill doesn't contain executable code."""
    from skillforge.validator import SmokeValidator

    validator = SmokeValidator()
    passed, issues = validator.validate(sample_skill_package)

    # Should not have executable code errors
    code_errors = [i for i in issues
                   if i.severity == 'error' and 'executable code' in i.message.lower()]
    assert len(code_errors) == 0


def test_skill_naming_conventions():
    """Test that skill names follow conventions."""
    from skillforge.drafter import SkillMdGenerator
    from skillforge.models import SkillSpec, ConflictAnalysis, RecommendedAction, GapClassification

    config = PipelineConfig(mock_mode=True)
    generator = SkillMdGenerator(config)

    spec = SkillSpec(
        gap_id="test",
        root_cause="Test",
        proposed_scope="Handle python code generation errors",
        priority_score=0.5,
        conflict_analysis=ConflictAnalysis(has_conflict=False),
        recommended_action=RecommendedAction.CREATE_NEW,
        classification=GapClassification.MISSING_SKILL,
        metadata={}
    )

    skill_name = generator._generate_skill_name(spec)

    # Should be lowercase with hyphens
    assert skill_name.islower() or '-' in skill_name
    # Should not be empty
    assert len(skill_name) > 0
    # Should not have spaces
    assert ' ' not in skill_name


def test_backward_compatibility_with_existing_skills(temp_skills_dir):
    """Test that existing skills still load after generating new ones."""
    # Load existing skills
    config = PipelineConfig(skills_dir=str(temp_skills_dir))
    checker = SkillInventoryChecker(config)

    skills_before = checker.load_existing_skills()
    existing_count = len(skills_before)

    # Add a generated skill
    new_skill_dir = temp_skills_dir / "generated-test"
    new_skill_dir.mkdir()

    (new_skill_dir / "SKILL.md").write_text("""---
name: generated-test
description: Test skill
allowed-tools: [Read]
version: 1.0.0
---

# Instructions

Test.
""")

    # Reload all skills
    checker2 = SkillInventoryChecker(config)
    skills_after = checker2.load_existing_skills()

    # Should have one more skill
    assert len(skills_after) == existing_count + 1

    # Existing skills should still be present
    for skill_name in skills_before:
        assert skill_name in skills_after
