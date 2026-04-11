# SkillForge

**A closed-loop skill self-improvement pipeline for CABAL multi-agent systems.**

SkillForge automatically detects skill gaps from agent task failures, drafts new AgentSkill packages, validates them through a two-tier system, and publishes them for human review and deployment.

## Overview

SkillForge implements a 5-stage pipeline inspired by research findings from SkillsBench and EvoSkills:

1. **Monitor** — Parse PreCog session logs for failures, cluster similar issues, compare against existing skill inventory
2. **Analyzer** — Classify gaps, define narrow focused scopes, score priorities, check for conflicts
3. **Drafter** — Generate SKILL.md using Bedrock Claude with skill-creator as meta-template, with iterative refinement
4. **Validator** — Two-tier validation (Tier 1: automated checks, Tier 2: LLM-judged quality scores)
5. **Publisher** — Write skills to disk, create git commits with structured messages, generate PRs for human review

## Key Features

- **Co-evolutionary verification**: Following SkillsBench findings that self-generated skills fail without validation
- **Compact over comprehensive**: Focused, minimal skills perform better (per SkillsBench)
- **Human-in-the-loop**: V1 requires human review for all generated skills (no auto-deploy)
- **Budget enforcement**: Prevents skill library bloat, suggests merging similar skills
- **Feedback tracking**: Monitors skill deployment success rates, detects performance drift
- **Mock mode**: Full pipeline testing without LLM calls, git ops, or AWS credentials

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### Run Full Pipeline

```bash
# With mock mode (no LLM calls, no git ops)
skillforge run --mock --dry-run

# With real PreCog logs
skillforge run --log-file /path/to/precog.log

# Limit skills per run
skillforge run --log-file precog.log --max-skills 2
```

### Run Individual Stages

```bash
# Monitor: Detect skill gaps
skillforge monitor --log-file precog.log --output-json gaps.json

# Analyze: Generate specifications
skillforge analyze --gaps-file gaps.json --output-json specs.json

# Draft: Generate SKILL.md
skillforge draft --spec-file spec.json --output-file skill.md

# Validate: Check skill quality
skillforge validate --skill-file skill.md

# Publish: Deploy skill
skillforge publish --skill-file skill.md --skill-name my-skill
```

### Library Health Report

```bash
skillforge health
```

## Architecture

### Data Models (`skillforge/models.py`)

- `SkillGap`: Detected failure cluster requiring new/updated skill
- `SkillSpec`: Specification for skill to be created (scope, priority, conflicts)
- `SkillPackage`: Complete skill with SKILL.md content and metadata
- `ValidationResult`: Two-tier validation results with scores and issues
- `PipelineConfig`: Configuration for all pipeline stages

### Stage Modules

- `monitor.py`: PreCogLogParser, FailureClusterer, SkillInventoryChecker, MockLogGenerator
- `analyzer.py`: GapClassifier, ScopeDefiner, PriorityScorer, ConflictChecker
- `drafter.py`: SkillMdGenerator (uses Bedrock Claude), MockDrafter for testing
- `validator.py`: Tier 1 (Format, Load, Smoke, Replay) + Tier 2 (LLMJudge, Regression, Compactness)
- `publisher.py`: SkillWriter, GitCommitter, PRCreator
- `tracker.py`: SkillTracker, SuccessRateTracker, DriftDetector, LibraryHealthReporter

### Pipeline Orchestration

- `pipeline.py`: SkillForgePipeline (full 5-stage flow), StageRunner (individual stages)
- `cli.py`: Command-line interface with subcommands for all operations

## Configuration

Configure via `PipelineConfig` or environment variables:

```python
from skillforge.models import PipelineConfig

config = PipelineConfig(
    skills_dir="/usr/lib/node_modules/openclaw/skills",
    bedrock_model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    bedrock_region="us-east-1",
    max_skills_per_run=3,
    max_validation_iterations=3,
    dry_run=False,
    mock_mode=False,
    create_pr=True
)
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=skillforge --cov-report=html

# Run specific test files
pytest tests/test_pipeline.py
pytest tests/test_regression.py

# Run in mock mode (no external dependencies)
pytest tests/ -v
```

## Design Principles

### 1. Compact > Comprehensive (SkillsBench Finding)

SkillForge generates focused, minimal skills. The ScopeDefiner limits scopes to 150 characters, and the CompactnessChecker penalizes skills over 200 lines.

### 2. Co-evolutionary Verification (EvoSkills)

Skills go through two-tier validation before deployment:
- **Tier 1**: Automated checks (format, loading, smoke tests)
- **Tier 2**: Scored quality checks (LLM judge, regression, compactness)

### 3. Human-in-the-Loop Governance

V1 requires human review via GitHub PRs. No auto-deployment ensures safety and quality control.

### 4. Iterative Refinement

The Drafter uses validation feedback to refine skills across up to 3 iterations before final validation.

### 5. Library Maintenance

- **Conflict detection**: Prevents overlapping skills
- **Budget enforcement**: Suggests merging when approaching max skills per domain
- **Drift detection**: Monitors performance degradation post-deployment
- **Staleness tracking**: Identifies unused skills for potential removal

## Meta-Recursive Design

SkillForge uses the `skill-creator` skill (if available) as a meta-template for generating new skills. This meta-recursive approach allows the system to leverage existing best practices for skill creation.

## AWS Bedrock Integration

SkillForge uses AWS Bedrock (not the Anthropic SDK) for LLM calls:

```python
# Uses boto3/botocore
import boto3

client = boto3.client('bedrock-runtime', region_name='us-east-1')
response = client.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    body=json.dumps(request)
)
```

Mock mode works without AWS credentials for testing.

## Research Context

### SkillsBench

Research showing that self-generated skills fail without proper validation. SkillForge addresses this through two-tier validation.

### EvoSkills

Co-evolutionary verification framework where skills and tasks evolve together. SkillForge implements this via validation feedback loops.

### SkillFoundry

Library maintenance model (expand/repair/merge/prune). SkillForge implements all four operations through its pipeline stages and budget enforcement.

## Constraints

- **No executable code**: Generated SKILL.md files contain only markdown/instructions
- **Rate limiting**: Max 2-3 skills per pipeline run (configurable)
- **Human review required**: V1 does not auto-deploy (creates PRs instead)
- **Git operations**: Uses subprocess (not gitpython)

## Contributing

See BLOG.md for a detailed technical walkthrough of the architecture and design decisions.

## License

MIT License - See LICENSE file for details.

## See Also

- [BLOG.md](BLOG.md) - Technical deep dive and architecture walkthrough
- [SkillsBench Paper](https://arxiv.org/abs/xxxx) - Research on skill self-generation
- [EvoSkills Paper](https://arxiv.org/abs/yyyy) - Co-evolutionary verification framework
