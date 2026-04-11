"""
Stage 4: Validator - Two-tier validation (Tier 1 automated, Tier 2 scored).
"""
from typing import List, Dict, Tuple, Optional
import re
import yaml

from .models import SkillPackage, ValidationResult, ValidationIssue, PipelineConfig


class FormatValidator:
    """Validate SKILL.md frontmatter schema."""

    REQUIRED_FIELDS = ['name', 'description', 'allowed-tools', 'version']

    def validate(self, package: SkillPackage) -> Tuple[bool, List[ValidationIssue]]:
        """Validate frontmatter format."""
        issues = []
        content = package.skill_md_content

        # Check for frontmatter
        if not content.startswith('---'):
            issues.append(ValidationIssue(
                severity='error',
                category='format',
                message='Missing YAML frontmatter (should start with ---)',
            ))
            return False, issues

        # Extract frontmatter
        try:
            end_marker = content.find('---', 3)
            if end_marker == -1:
                issues.append(ValidationIssue(
                    severity='error',
                    category='format',
                    message='Malformed frontmatter (missing closing ---)',
                ))
                return False, issues

            frontmatter_text = content[3:end_marker].strip()
            frontmatter = yaml.safe_load(frontmatter_text)

            if not isinstance(frontmatter, dict):
                issues.append(ValidationIssue(
                    severity='error',
                    category='format',
                    message='Frontmatter is not a valid dictionary',
                ))
                return False, issues

        except yaml.YAMLError as e:
            issues.append(ValidationIssue(
                severity='error',
                category='format',
                message=f'Invalid YAML in frontmatter: {e}',
            ))
            return False, issues

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in frontmatter:
                issues.append(ValidationIssue(
                    severity='error',
                    category='format',
                    message=f'Missing required field: {field}',
                ))

        # Validate field types
        if 'name' in frontmatter and not isinstance(frontmatter['name'], str):
            issues.append(ValidationIssue(
                severity='error',
                category='format',
                message='Field "name" must be a string',
            ))

        if 'allowed-tools' in frontmatter:
            if not isinstance(frontmatter['allowed-tools'], list):
                issues.append(ValidationIssue(
                    severity='error',
                    category='format',
                    message='Field "allowed-tools" must be a list',
                ))

        # Check for common sections
        required_sections = ['# Instructions', '## When to Use', '## Steps']
        for section in required_sections:
            if section not in content:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='format',
                    message=f'Missing recommended section: {section}',
                ))

        passed = not any(i.severity == 'error' for i in issues)
        return passed, issues


class LoadValidator:
    """Verify skill package can be parsed without errors."""

    def validate(self, package: SkillPackage) -> Tuple[bool, List[ValidationIssue]]:
        """Validate skill can be loaded."""
        issues = []

        try:
            content = package.skill_md_content

            # Try to extract frontmatter
            if not content.startswith('---'):
                issues.append(ValidationIssue(
                    severity='error',
                    category='load',
                    message='Cannot load skill: missing frontmatter',
                ))
                return False, issues

            end_marker = content.find('---', 3)
            if end_marker == -1:
                issues.append(ValidationIssue(
                    severity='error',
                    category='load',
                    message='Cannot load skill: malformed frontmatter',
                ))
                return False, issues

            frontmatter_text = content[3:end_marker].strip()
            metadata = yaml.safe_load(frontmatter_text)

            # Verify skill name matches
            if metadata.get('name') != package.skill_name:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='load',
                    message=f"Skill name mismatch: package='{package.skill_name}' vs frontmatter='{metadata.get('name')}'",
                ))

            # Check for content after frontmatter
            body = content[end_marker + 3:].strip()
            if len(body) < 100:
                issues.append(ValidationIssue(
                    severity='error',
                    category='load',
                    message='Skill content is too short (< 100 chars)',
                ))
                return False, issues

        except Exception as e:
            issues.append(ValidationIssue(
                severity='error',
                category='load',
                message=f'Failed to load skill: {e}',
            ))
            return False, issues

        return True, issues


class SmokeValidator:
    """Verify skill can be invoked on synthetic task."""

    def validate(self, package: SkillPackage) -> Tuple[bool, List[ValidationIssue]]:
        """Run smoke test."""
        issues = []

        # Check for executable code (should not have any)
        if self._contains_executable_code(package.skill_md_content):
            issues.append(ValidationIssue(
                severity='error',
                category='smoke',
                message='Skill contains executable code (not allowed)',
                details='Skills should only contain markdown/instructions'
            ))
            return False, issues

        # Check for reasonable length
        lines = package.skill_md_content.split('\n')
        if len(lines) > 300:
            issues.append(ValidationIssue(
                severity='warning',
                category='smoke',
                message=f'Skill is very long ({len(lines)} lines > 300 recommended)',
                details='Per SkillsBench: compact > comprehensive'
            ))

        # Check for actionable instructions
        if not self._has_actionable_instructions(package.skill_md_content):
            issues.append(ValidationIssue(
                severity='warning',
                category='smoke',
                message='Skill appears to lack actionable instructions',
            ))

        return True, issues

    def _contains_executable_code(self, content: str) -> bool:
        """Check if content contains executable code patterns."""
        # Look for code fence blocks with language specifiers that suggest executable code
        code_blocks = re.findall(r'```(\w+)\n', content)

        executable_languages = ['python', 'javascript', 'bash', 'sh', 'js', 'py', 'ruby', 'go']
        return any(lang.lower() in executable_languages for lang in code_blocks)

    def _has_actionable_instructions(self, content: str) -> bool:
        """Check if content has actionable instructions."""
        # Look for imperative verbs
        imperative_patterns = [
            r'\b(use|create|update|check|verify|ensure|run|execute|analyze|apply)\b',
            r'\d+\.\s+\w+',  # Numbered steps
        ]

        return any(re.search(pattern, content, re.IGNORECASE)
                  for pattern in imperative_patterns)


class ReplayValidator:
    """Simulate re-running original failing scenario."""

    def validate(
        self,
        package: SkillPackage,
        original_gap: Optional[Dict] = None
    ) -> Tuple[bool, List[ValidationIssue]]:
        """Validate skill addresses the original failure."""
        issues = []

        if not original_gap:
            # Can't replay without original gap info
            issues.append(ValidationIssue(
                severity='info',
                category='replay',
                message='Skipping replay (no original failure context)',
            ))
            return True, issues

        # Mock check: verify skill mentions key concepts from failure
        failure_context = original_gap.get('failure_context', '')
        failure_type = original_gap.get('failure_type', '')

        # Extract key terms from failure
        key_terms = self._extract_key_terms(failure_context)

        # Check if skill addresses these terms
        skill_content_lower = package.skill_md_content.lower()
        coverage = sum(1 for term in key_terms if term in skill_content_lower)

        if len(key_terms) > 0:
            coverage_pct = (coverage / len(key_terms)) * 100
            if coverage_pct < 30:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='replay',
                    message=f'Low coverage of original failure concepts ({coverage_pct:.0f}%)',
                    details=f'Key terms from failure: {", ".join(key_terms[:5])}'
                ))

        return True, issues

    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text."""
        words = re.findall(r'\b\w{4,}\b', text.lower())
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                    'for', 'with', 'from', 'this', 'that', 'which', 'when'}
        return [w for w in words if w not in stopwords][:10]


class LLMJudge:
    """Before/after task quality comparison using Bedrock Claude."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def evaluate(self, package: SkillPackage) -> Tuple[float, List[ValidationIssue]]:
        """Evaluate skill quality using LLM."""
        issues = []

        if self.config.mock_mode:
            # Mock evaluation - return reasonable score
            score = 0.75
            issues.append(ValidationIssue(
                severity='info',
                category='quality',
                message=f'Mock LLM evaluation score: {score}',
            ))
            return score, issues

        # Real LLM evaluation would go here
        try:
            from .drafter import BedrockClient
            client = BedrockClient(self.config)

            prompt = self._build_evaluation_prompt(package)
            response = client.generate(prompt, max_tokens=500)

            # Parse score from response
            score = self._parse_score(response)
            issues.append(ValidationIssue(
                severity='info',
                category='quality',
                message=f'LLM evaluation score: {score}',
                details=response[:200]
            ))

            return score, issues

        except Exception as e:
            issues.append(ValidationIssue(
                severity='warning',
                category='quality',
                message=f'LLM evaluation failed: {e}',
            ))
            return 0.5, issues

    def _build_evaluation_prompt(self, package: SkillPackage) -> str:
        """Build evaluation prompt."""
        return f"""Evaluate this AI agent skill on a scale of 0.0 to 1.0:

{package.skill_md_content[:1500]}

Criteria:
- Clarity of instructions (0-0.3)
- Specificity of trigger conditions (0-0.3)
- Actionability of steps (0-0.2)
- Completeness of test scenarios (0-0.2)

Provide your score as a decimal (e.g., 0.75) followed by brief justification."""

    def _parse_score(self, response: str) -> float:
        """Parse score from LLM response."""
        # Look for decimal number
        match = re.search(r'0\.\d+', response)
        if match:
            return float(match.group())
        return 0.5  # Default


class RegressionChecker:
    """Verify adjacent tasks don't degrade."""

    def check(self, package: SkillPackage) -> Tuple[float, List[ValidationIssue]]:
        """Check for potential regressions."""
        issues = []

        # Mock implementation - in real version would test against existing tasks
        # For now, just check for common anti-patterns

        content = package.skill_md_content
        score = 1.0  # Start with perfect score

        # Check for overly broad instructions
        if self._is_overly_broad(content):
            score -= 0.2
            issues.append(ValidationIssue(
                severity='warning',
                category='regression',
                message='Skill may be overly broad (risk of incorrect activation)',
            ))

        # Check for conflicting guidance
        if self._has_conflicting_patterns(content):
            score -= 0.3
            issues.append(ValidationIssue(
                severity='warning',
                category='regression',
                message='Skill contains potentially conflicting guidance',
            ))

        return max(score, 0.0), issues

    def _is_overly_broad(self, content: str) -> bool:
        """Check if skill is overly broad."""
        broad_patterns = [
            r'\balways\b.*\ball\b',
            r'\bany\b.*\beverything\b',
            r'\ball\b.*\btasks\b',
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in broad_patterns)

    def _has_conflicting_patterns(self, content: str) -> bool:
        """Check for conflicting patterns."""
        # Look for contradictory instructions
        has_never = bool(re.search(r'\bnever\b', content, re.IGNORECASE))
        has_always = bool(re.search(r'\balways\b', content, re.IGNORECASE))

        return has_never and has_always


class CompactnessChecker:
    """Check skill instructions length/focus."""

    def check(self, package: SkillPackage) -> Tuple[float, List[ValidationIssue]]:
        """Check compactness."""
        issues = []
        content = package.skill_md_content

        lines = content.split('\n')
        line_count = len(lines)

        # Scoring based on length (SkillsBench: compact > comprehensive)
        if line_count <= 100:
            score = 1.0
        elif line_count <= 200:
            score = 0.8
        elif line_count <= 300:
            score = 0.6
        else:
            score = 0.4
            issues.append(ValidationIssue(
                severity='warning',
                category='quality',
                message=f'Skill is too long ({line_count} lines)',
                details='Per SkillsBench findings: compact skills perform better'
            ))

        # Check focus (number of main topics)
        sections = re.findall(r'^##?\s+(.+)$', content, re.MULTILINE)
        if len(sections) > 10:
            score *= 0.8
            issues.append(ValidationIssue(
                severity='warning',
                category='quality',
                message=f'Skill may lack focus ({len(sections)} sections)',
            ))

        return score, issues


class Validator:
    """Main Validator stage coordinator - two-tier validation."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.format_validator = FormatValidator()
        self.load_validator = LoadValidator()
        self.smoke_validator = SmokeValidator()
        self.replay_validator = ReplayValidator()
        self.llm_judge = LLMJudge(config)
        self.regression_checker = RegressionChecker()
        self.compactness_checker = CompactnessChecker()

    def run(
        self,
        package: SkillPackage,
        original_gap: Optional[Dict] = None
    ) -> ValidationResult:
        """Run two-tier validation."""
        all_issues = []
        scores = {}

        # Tier 1: Automated checks (must pass)
        tier1_passed = True

        # Format validation
        format_ok, format_issues = self.format_validator.validate(package)
        all_issues.extend(format_issues)
        if not format_ok:
            tier1_passed = False

        # Load validation
        load_ok, load_issues = self.load_validator.validate(package)
        all_issues.extend(load_issues)
        if not load_ok:
            tier1_passed = False

        # Smoke validation
        smoke_ok, smoke_issues = self.smoke_validator.validate(package)
        all_issues.extend(smoke_issues)
        if not smoke_ok:
            tier1_passed = False

        # Replay validation
        replay_ok, replay_issues = self.replay_validator.validate(package, original_gap)
        all_issues.extend(replay_issues)
        # Replay is informational, doesn't fail tier 1

        # Tier 2: Scored checks (threshold-based pass)
        tier2_passed = True

        # LLM judge
        quality_score, quality_issues = self.llm_judge.evaluate(package)
        scores['quality'] = quality_score
        all_issues.extend(quality_issues)

        # Regression check
        regression_score, regression_issues = self.regression_checker.check(package)
        scores['regression'] = regression_score
        all_issues.extend(regression_issues)

        # Compactness check
        compactness_score, compactness_issues = self.compactness_checker.check(package)
        scores['compactness'] = compactness_score
        all_issues.extend(compactness_issues)

        # Tier 2 passes if average score >= 0.6
        avg_tier2_score = sum(scores.values()) / len(scores) if scores else 0.0
        scores['tier2_average'] = avg_tier2_score

        if avg_tier2_score < 0.6:
            tier2_passed = False

        # Generate feedback for drafter if validation failed
        feedback = None
        if not (tier1_passed and tier2_passed):
            feedback = self._generate_feedback(all_issues, scores)

        return ValidationResult(
            tier1_passed=tier1_passed,
            tier2_passed=tier2_passed,
            scores=scores,
            issues=all_issues,
            iteration_count=package.metadata.get('iteration', 1),
            feedback_for_drafter=feedback
        )

    def _generate_feedback(
        self,
        issues: List[ValidationIssue],
        scores: Dict[str, float]
    ) -> str:
        """Generate feedback for drafter."""
        feedback_parts = ["Validation feedback:"]

        # Summarize errors and warnings
        errors = [i for i in issues if i.severity == 'error']
        warnings = [i for i in issues if i.severity == 'warning']

        if errors:
            feedback_parts.append(f"\nErrors ({len(errors)}):")
            for issue in errors[:5]:  # Limit to top 5
                feedback_parts.append(f"  - {issue.message}")

        if warnings:
            feedback_parts.append(f"\nWarnings ({len(warnings)}):")
            for issue in warnings[:5]:
                feedback_parts.append(f"  - {issue.message}")

        # Add score information
        if scores:
            feedback_parts.append(f"\nScores:")
            for key, value in scores.items():
                feedback_parts.append(f"  - {key}: {value:.2f}")

        return "\n".join(feedback_parts)


class MockValidator:
    """Deterministic validator for testing."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, package: SkillPackage, original_gap: Optional[Dict] = None) -> ValidationResult:
        """Run mock validation."""
        # Deterministic pass for well-formed skills
        issues = []
        scores = {
            'quality': 0.8,
            'regression': 0.9,
            'compactness': 0.85,
            'tier2_average': 0.85
        }

        # Basic checks
        tier1_passed = package.skill_md_content.startswith('---')
        tier2_passed = True

        return ValidationResult(
            tier1_passed=tier1_passed,
            tier2_passed=tier2_passed,
            scores=scores,
            issues=issues,
            iteration_count=package.metadata.get('iteration', 1),
            feedback_for_drafter=None
        )
