"""
Stage 3: Drafter - Generate SKILL.md using Bedrock Claude with skill-creator as meta-template.
"""
from typing import Optional, Tuple
from pathlib import Path
import json
import re

from .models import SkillSpec, SkillPackage, ValidationResult, PipelineConfig


class SkillCreatorTemplateLoader:
    """Load skill-creator skill as meta-template."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.template_cache = None

    def load_template(self) -> str:
        """Load skill-creator SKILL.md if available."""
        if self.template_cache:
            return self.template_cache

        skill_creator_path = Path(self.config.skills_dir) / "skill-creator" / "SKILL.md"

        if skill_creator_path.exists():
            with open(skill_creator_path, 'r') as f:
                self.template_cache = f.read()
                return self.template_cache

        # Return embedded template if skill-creator not found
        return self._get_embedded_template()

    def _get_embedded_template(self) -> str:
        """Return embedded skill template."""
        return """---
name: example-skill
description: Brief description of what this skill does
allowed-tools: [Read, Write, Bash]
version: 1.0.0
---

# Instructions

Clear, focused instructions for the agent on when and how to use this skill.

## When to Use

Specific triggers or scenarios that should activate this skill.

## Steps

1. First step
2. Second step
3. Third step

## Examples

Provide concrete examples of using this skill.

## Test Scenarios

How to verify this skill works correctly.
"""


class BedrockClient:
    """Client for AWS Bedrock Claude API."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.client = None

    def _init_client(self):
        """Initialize boto3 Bedrock client."""
        if self.client is None:
            try:
                import boto3
                self.client = boto3.client(
                    'bedrock-runtime',
                    region_name=self.config.bedrock_region
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Bedrock client: {e}")

    def generate(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate text using Bedrock Claude."""
        self._init_client()

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']

        except Exception as e:
            raise RuntimeError(f"Bedrock API call failed: {e}")


class SkillMdGenerator:
    """Generate SKILL.md using Bedrock Claude."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.template_loader = SkillCreatorTemplateLoader(config)
        self.bedrock_client = BedrockClient(config) if not config.mock_mode else None

    def generate(
        self,
        spec: SkillSpec,
        feedback: Optional[str] = None
    ) -> str:
        """Generate SKILL.md content."""
        if self.config.mock_mode:
            return self._generate_mock_skill(spec)

        # Load skill-creator template
        template = self.template_loader.load_template()

        # Build prompt
        prompt = self._build_prompt(spec, template, feedback)

        # Call Bedrock
        skill_content = self.bedrock_client.generate(prompt)

        return skill_content

    def _build_prompt(
        self,
        spec: SkillSpec,
        template: str,
        feedback: Optional[str] = None
    ) -> str:
        """Build prompt for LLM skill generation."""
        prompt_parts = [
            "You are a skill designer for AI agents. Your task is to create a focused, minimal SKILL.md file.",
            "",
            "# Context",
            f"Root cause: {spec.root_cause}",
            f"Proposed scope: {spec.proposed_scope}",
            f"Classification: {spec.classification.value}",
            f"Priority: {spec.priority_score}",
            "",
            "# Requirements",
            "- Create a SKILL.md file with YAML frontmatter (name, description, allowed-tools, version)",
            "- Write clear, focused instructions (compact > comprehensive per SkillsBench)",
            "- Include specific trigger conditions (When to Use)",
            "- Provide concrete steps",
            "- Add test scenarios for verification",
            "- NO executable code - markdown/instructions only",
            "- Keep total length under 300 lines",
            "",
            "# Template Reference",
            "Here's the skill-creator template as reference:",
            "```",
            template[:1000],  # Include partial template for structure
            "```",
            "",
        ]

        if feedback:
            prompt_parts.extend([
                "# Feedback from Previous Iteration",
                feedback,
                "",
                "Please address the issues mentioned above.",
                ""
            ])

        prompt_parts.append("Generate the complete SKILL.md file:")

        return "\n".join(prompt_parts)

    def _generate_mock_skill(self, spec: SkillSpec) -> str:
        """Generate deterministic mock SKILL.md for testing."""
        skill_name = self._generate_skill_name(spec)

        return f"""---
name: {skill_name}
description: {spec.proposed_scope[:100]}
allowed-tools: [Read, Write, Bash, Glob, Grep]
version: 1.0.0
---

# Instructions

This skill addresses: {spec.root_cause}

## When to Use

Use this skill when encountering failures related to:
- {spec.classification.value}
- Frequency: {spec.metadata.get('frequency', 0)} occurrences

## Steps

1. Analyze the failure context
2. Apply the appropriate remediation
3. Verify the fix
4. Document the resolution

## Examples

### Example 1

When encountering this type of failure, follow these steps...

## Test Scenarios

1. Simulate the original failure condition
2. Verify the skill provides correct guidance
3. Confirm successful resolution
"""

    def _generate_skill_name(self, spec: SkillSpec) -> str:
        """Generate a valid skill name from spec."""
        # Extract key words from scope
        words = re.findall(r'\b\w+\b', spec.proposed_scope.lower())
        # Filter and take first 3 meaningful words
        meaningful = [w for w in words if len(w) > 3 and
                     w not in ['skill', 'create', 'update', 'handle']][:3]

        name = '-'.join(meaningful) if meaningful else f"skill-{spec.gap_id[:6]}"
        return name


class Drafter:
    """Main Drafter stage coordinator with iterative refinement."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.generator = SkillMdGenerator(config)

    def run(
        self,
        spec: SkillSpec,
        validator = None  # Will be passed from pipeline for iteration
    ) -> Tuple[SkillPackage, int]:
        """
        Run the Drafter stage with iterative refinement.
        Returns (SkillPackage, iteration_count)
        """
        iteration = 0
        feedback = None

        for iteration in range(1, self.config.max_validation_iterations + 1):
            # Generate SKILL.md
            skill_content = self.generator.generate(spec, feedback)

            # Extract skill name from content
            skill_name = self._extract_skill_name(skill_content)

            # Create package
            package = SkillPackage(
                skill_name=skill_name,
                skill_md_content=skill_content,
                supporting_files={},
                metadata={
                    'gap_id': spec.gap_id,
                    'iteration': iteration,
                    'spec': spec.to_dict()
                }
            )

            # If validator provided, validate and refine
            if validator:
                validation_result = validator.run(package)

                if validation_result.passed:
                    return package, iteration

                # Prepare feedback for next iteration
                if validation_result.feedback_for_drafter:
                    feedback = validation_result.feedback_for_drafter
                else:
                    feedback = self._format_validation_feedback(validation_result)
            else:
                # No validator, return after first generation
                return package, iteration

        # Max iterations reached - return last attempt
        return package, iteration

    def _extract_skill_name(self, skill_content: str) -> str:
        """Extract skill name from SKILL.md frontmatter."""
        # Look for name in YAML frontmatter
        match = re.search(r'^\s*name:\s*([a-zA-Z0-9_-]+)', skill_content, re.MULTILINE)
        if match:
            return match.group(1)

        # Fallback
        return "generated-skill"

    def _format_validation_feedback(self, validation_result: ValidationResult) -> str:
        """Format validation issues as feedback for drafter."""
        feedback_parts = ["Validation issues found:"]

        for issue in validation_result.issues:
            if issue.severity in ['error', 'warning']:
                feedback_parts.append(
                    f"- [{issue.severity.upper()}] {issue.category}: {issue.message}"
                )
                if issue.details:
                    feedback_parts.append(f"  Details: {issue.details}")

        return "\n".join(feedback_parts)


class MockDrafter:
    """Deterministic drafter for testing without LLM calls."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.generator = SkillMdGenerator(config)

    def run(self, spec: SkillSpec) -> Tuple[SkillPackage, int]:
        """Generate mock skill package."""
        skill_content = self.generator._generate_mock_skill(spec)
        skill_name = self.generator._generate_skill_name(spec)

        package = SkillPackage(
            skill_name=skill_name,
            skill_md_content=skill_content,
            supporting_files={},
            metadata={
                'gap_id': spec.gap_id,
                'iteration': 1,
                'spec': spec.to_dict(),
                'mock': True
            }
        )

        return package, 1
