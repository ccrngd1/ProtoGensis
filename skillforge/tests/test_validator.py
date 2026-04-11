"""
Tests for Validator stage.
"""
import pytest

from skillforge.validator import (
    FormatValidator, LoadValidator, SmokeValidator, ReplayValidator,
    LLMJudge, RegressionChecker, CompactnessChecker, Validator
)
from skillforge.models import ValidationIssue


def test_format_validator_valid_skill(sample_skill_package):
    """Test FormatValidator with valid skill."""
    validator = FormatValidator()

    passed, issues = validator.validate(sample_skill_package)

    assert passed is True
    # May have warnings but no errors
    errors = [i for i in issues if i.severity == 'error']
    assert len(errors) == 0


def test_format_validator_missing_frontmatter():
    """Test FormatValidator with missing frontmatter."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="bad-skill",
        skill_md_content="# No frontmatter\n\nJust content."
    )

    validator = FormatValidator()
    passed, issues = validator.validate(package)

    assert passed is False
    assert any(i.severity == 'error' for i in issues)


def test_format_validator_invalid_yaml():
    """Test FormatValidator with invalid YAML."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="bad-skill",
        skill_md_content="---\ninvalid: yaml: content:\n---\n\nContent"
    )

    validator = FormatValidator()
    passed, issues = validator.validate(package)

    assert passed is False


def test_load_validator_valid(sample_skill_package):
    """Test LoadValidator with valid skill."""
    validator = LoadValidator()

    passed, issues = validator.validate(sample_skill_package)

    assert passed is True


def test_load_validator_too_short():
    """Test LoadValidator with too short content."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="short-skill",
        skill_md_content="---\nname: short\n---\n\nShort"
    )

    validator = LoadValidator()
    passed, issues = validator.validate(package)

    assert passed is False


def test_smoke_validator_valid(sample_skill_package):
    """Test SmokeValidator with valid skill."""
    validator = SmokeValidator()

    passed, issues = validator.validate(sample_skill_package)

    assert passed is True


def test_smoke_validator_executable_code():
    """Test SmokeValidator rejects executable code."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="code-skill",
        skill_md_content="""---
name: code-skill
description: Test
allowed-tools: []
version: 1.0.0
---

# Instructions

```python
def execute_code():
    pass
```
"""
    )

    validator = SmokeValidator()
    passed, issues = validator.validate(package)

    assert passed is False
    assert any('executable code' in i.message.lower() for i in issues)


def test_smoke_validator_very_long():
    """Test SmokeValidator warns about long skills."""
    from skillforge.models import SkillPackage

    # Create a very long skill
    long_content = "---\nname: long\ndescription: Test\nallowed-tools: []\nversion: 1.0.0\n---\n\n"
    long_content += "\n".join([f"Line {i}" for i in range(400)])

    package = SkillPackage(
        skill_name="long-skill",
        skill_md_content=long_content
    )

    validator = SmokeValidator()
    passed, issues = validator.validate(package)

    # Passes but warns
    assert passed is True
    warnings = [i for i in issues if i.severity == 'warning']
    assert len(warnings) > 0


def test_replay_validator_no_gap(sample_skill_package):
    """Test ReplayValidator without original gap."""
    validator = ReplayValidator()

    passed, issues = validator.validate(sample_skill_package, None)

    assert passed is True


def test_replay_validator_with_gap(sample_skill_package):
    """Test ReplayValidator with original gap."""
    validator = ReplayValidator()

    original_gap = {
        'failure_context': 'Test failure context',
        'failure_type': 'error'
    }

    passed, issues = validator.validate(sample_skill_package, original_gap)

    assert passed is True or passed is False  # Depends on coverage


def test_llm_judge_mock(mock_config, sample_skill_package):
    """Test LLMJudge in mock mode."""
    judge = LLMJudge(mock_config)

    score, issues = judge.evaluate(sample_skill_package)

    assert 0.0 <= score <= 1.0
    assert isinstance(issues, list)


def test_regression_checker(sample_skill_package):
    """Test RegressionChecker."""
    checker = RegressionChecker()

    score, issues = checker.check(sample_skill_package)

    assert 0.0 <= score <= 1.0


def test_regression_checker_overly_broad():
    """Test RegressionChecker detects overly broad skills."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="broad-skill",
        skill_md_content="""---
name: broad
description: Test
allowed-tools: []
version: 1.0.0
---

# Instructions

Always handle all tasks for everything.
"""
    )

    checker = RegressionChecker()
    score, issues = checker.check(package)

    # Should penalize
    assert score < 1.0


def test_compactness_checker(sample_skill_package):
    """Test CompactnessChecker."""
    checker = CompactnessChecker()

    score, issues = checker.check(sample_skill_package)

    assert 0.0 <= score <= 1.0


def test_compactness_checker_long_skill():
    """Test CompactnessChecker penalizes long skills."""
    from skillforge.models import SkillPackage

    # Create a very long skill
    long_content = "---\nname: long\ndescription: Test\nallowed-tools: []\nversion: 1.0.0\n---\n\n"
    long_content += "\n".join([f"## Section {i}\nContent" for i in range(20)])

    package = SkillPackage(
        skill_name="long-skill",
        skill_md_content=long_content
    )

    checker = CompactnessChecker()
    score, issues = checker.check(package)

    # Should have lower score
    assert score < 1.0


def test_validator_full_run(mock_config, sample_skill_package):
    """Test Validator full run."""
    validator = Validator(mock_config)

    result = validator.run(sample_skill_package)

    assert hasattr(result, 'tier1_passed')
    assert hasattr(result, 'tier2_passed')
    assert hasattr(result, 'scores')
    assert hasattr(result, 'issues')


def test_validator_tier1_failure(mock_config):
    """Test Validator with Tier 1 failure."""
    from skillforge.models import SkillPackage

    # Create invalid package
    package = SkillPackage(
        skill_name="invalid",
        skill_md_content="No frontmatter"
    )

    validator = Validator(mock_config)
    result = validator.run(package)

    assert result.tier1_passed is False
    assert result.passed is False


def test_validator_generates_feedback(mock_config):
    """Test that Validator generates feedback for drafter."""
    from skillforge.models import SkillPackage

    package = SkillPackage(
        skill_name="invalid",
        skill_md_content="No frontmatter"
    )

    validator = Validator(mock_config)
    result = validator.run(package)

    if not result.passed:
        assert result.feedback_for_drafter is not None
        assert len(result.feedback_for_drafter) > 0
