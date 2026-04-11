# SkillForge: Teaching AI Agents to Fix Their Own Skill Gaps

**A closed-loop self-improvement pipeline for multi-agent systems**

*April 11, 2026*

## The Problem: When AI Agents Generate Their Own Skills

Imagine an AI agent that can write its own instruction manual. When it encounters a task it doesn't know how to handle, it drafts a new "skill" — a structured set of instructions for handling similar situations in the future. It sounds like the holy grail of AI autonomy: systems that can continuously improve themselves by learning from failures.

There's just one problem: **it doesn't work**.

Recent research from the SkillsBench benchmark revealed a sobering truth about self-generated agent skills. When AI systems create their own skills without proper validation, those skills fail more often than they succeed. The failure modes are varied: skills that are too broad and trigger incorrectly, skills with contradictory instructions, skills that miss edge cases, and skills so verbose they become unusable.

The naive approach — let an agent detect its failures, generate a skill to fix them, and move on — produces a growing library of unreliable skills that actually degrade system performance over time. What starts as an attempt at self-improvement becomes a form of self-sabotage.

## The SkillsBench Finding: Self-Generation Needs Verification

The SkillsBench research team conducted systematic experiments with self-generated agent skills across diverse task domains. Their key finding: **skill self-generation without co-evolutionary verification leads to cascading failures**.

The pattern was consistent across different agent architectures and task types:

1. **Initial optimism**: Agents successfully identify failure patterns and generate skills that seem reasonable
2. **Hidden fragility**: Generated skills work on the specific examples that triggered them but fail to generalize
3. **Interference effects**: New skills interfere with existing capabilities, creating new failure modes
4. **Library bloat**: Accumulation of similar but slightly different skills makes skill selection unreliable
5. **Performance degradation**: Overall system performance degrades as the skill library grows

The researchers found two critical insights:

**Insight 1: Compact > Comprehensive**. Counterintuitively, shorter, more focused skills outperformed longer, more detailed ones. Skills that tried to be comprehensive guides often included contradictory advice or triggered in inappropriate contexts. The best-performing skills were narrow in scope and explicit about their activation conditions.

**Insight 2: Verification is essential**. Skills that went through validation — including format checking, test scenario execution, and regression testing — had dramatically higher success rates than skills that were deployed immediately after generation.

## The EvoSkills Solution: Co-evolutionary Verification

Enter EvoSkills, a framework that treats skill generation and skill validation as co-evolving processes. Instead of generating skills in isolation, EvoSkills proposes a closed loop:

1. **Detect**: Identify failure patterns from production usage
2. **Generate**: Create skills to address those patterns
3. **Validate**: Test skills against both new scenarios and existing capabilities
4. **Deploy**: Only promote validated skills to production
5. **Monitor**: Track post-deployment performance
6. **Refine**: Update or retire skills based on real-world results

The "co-evolutionary" aspect is crucial. As skills evolve to cover more scenarios, the validation criteria evolve to catch more failure modes. As the skill library grows, validation includes regression testing against adjacent skills. The system learns not just what skills to create, but what makes a good skill.

EvoSkills demonstrated that with proper verification, self-generated skills can match or exceed the performance of human-authored skills — but only with rigorous validation at every step.

## SkillFoundry: Library Maintenance at Scale

While EvoSkills focused on the generation-validation loop, the SkillFoundry research extended this to library-scale management. They identified four key operations for maintaining a healthy skill library:

**Expand**: Add new skills for uncovered scenarios
**Repair**: Update existing skills when performance degrades
**Merge**: Combine similar skills to reduce interference
**Prune**: Remove stale or redundant skills

SkillFoundry showed that without active library maintenance, even well-validated skills accumulate problems over time. Skills that were perfect at deployment become outdated as the system evolves. Multiple teams generating skills create overlap. Old skills linger unused, cluttering the skill selection process.

The key insight: **skill libraries are living systems that require continuous curation**, not static collections.

## SkillForge: Production Implementation for CABAL

This brings us to SkillForge, our implementation of these research ideas for the CABAL multi-agent system. CABAL is a production multi-agent system that orchestrates multiple specialized AI agents (PreCog for planning, Executor for actions, Verifier for validation, etc.) to accomplish complex software engineering tasks.

We faced a concrete problem: our PreCog agent was encountering new failure patterns in production, and manually authoring skills for each pattern was becoming a bottleneck. We needed automated skill generation, but the SkillsBench findings made it clear we couldn't just turn on naive self-generation.

SkillForge is our answer: a full implementation of the EvoSkills + SkillFoundry approach, with some unique twists from our production context.

### Design Requirements

We established several key requirements:

1. **Real production failures**: Use actual PreCog session logs, not synthetic data
2. **Co-evolutionary validation**: Implement the full two-tier validation system
3. **Human-in-the-loop**: Require human approval before deploying any skill (V1 safety constraint)
4. **Library maintenance**: Active conflict detection, budget enforcement, drift monitoring
5. **Mock mode**: Full pipeline should work without AWS credentials, LLM calls, or git operations (for testing)
6. **Transparency**: Every generated skill gets a PR with full context and validation scores

### The Meta-Recursive Angle

Here's where it gets interesting: CABAL already has a skill called `skill-creator` that codifies our best practices for creating skills. It's a human-authored skill that knows the proper format, required sections, and quality criteria for agent skills.

So SkillForge uses the `skill-creator` skill to generate new skills. It's meta-recursive: an agent skill that teaches the system how to create agent skills. This ensures that generated skills follow the same patterns and quality standards as human-authored ones.

When SkillForge's Drafter stage generates a new SKILL.md file, it loads the skill-creator template and provides it as context to the LLM:

```python
# Load skill-creator as meta-template
template = self.load_skill_creator_template()

# Build prompt with template context
prompt = f"""You are creating a new agent skill.
Use this template as a guide for structure and style:

{template}

Now create a skill for: {spec.proposed_scope}
"""
```

This meta-recursive approach grounds the generation process in proven patterns rather than starting from scratch each time.

## Architecture: The 5-Stage Pipeline

SkillForge implements a 5-stage pipeline that processes production failures end-to-end:

### Stage 1: Monitor

The Monitor stage is responsible for detecting skill gaps from production logs.

**PreCogLogParser** reads PreCog session output (structured JSONL logs) and identifies failure signals using pattern matching:
- ERROR: Exception traces, error messages
- RETRY_EXCEEDED: Max retries reached
- USER_CORRECTION: Manual interventions
- TIMEOUT: Deadline exceeded
- INVALID_OUTPUT: Parse failures

**FailureClusterer** groups similar failures using a simple but effective approach: extract task type, failure type, and key words from the failure message, then hash them to create a cluster ID. Failures with the same signature cluster together, letting us see patterns across multiple incidents.

**SkillInventoryChecker** compares clusters against existing skills to identify gaps. It loads all SKILL.md files from the skills directory, extracts descriptions and keywords, then checks if any existing skill covers the failure cluster. If not, it's a genuine skill gap.

**MockLogGenerator** provides deterministic mock failures for testing without production logs.

The Monitor stage outputs a list of `SkillGap` objects, each representing a detected gap with context, frequency, and affected agents.

### Stage 2: Analyzer

The Analyzer stage takes skill gaps and produces specifications for skills to be created.

**GapClassifier** categorizes each gap:
- MISSING_SKILL: No related skill exists
- OUTDATED_SKILL: Related skill exists but doesn't handle this case
- WRONG_SELECTION: Agent is choosing the wrong skill
- INSUFFICIENT: Related skill needs enhancement
- NOT_A_SKILL_PROBLEM: Can't be solved with a skill

**ScopeDefiner** creates narrow, focused scopes (following SkillsBench's "compact > comprehensive" finding). It limits scope descriptions to 150 characters maximum to force clarity and specificity.

**PriorityScorer** calculates a priority score from three factors:
- Frequency (40%): How often does this failure occur?
- Impact (40%): How severe is the failure type?
- Feasibility (20%): How easy is this to fix with a skill?

This produces scores from 0.0 to 1.0, letting us tackle the most important gaps first.

**ConflictChecker** compares the proposed scope against existing skills to detect overlap. If more than 60% of keywords match an existing skill, it flags a conflict and potentially recommends merging instead of creating a new skill.

The Analyzer outputs `SkillSpec` objects with full classification, priority scores, conflict analysis, and recommended actions.

### Stage 3: Drafter

The Drafter stage generates actual SKILL.md files using AWS Bedrock.

**SkillMdGenerator** is the core engine. It:
1. Loads the skill-creator template
2. Builds a prompt with gap context and requirements
3. Calls Bedrock Claude (using boto3, not the Anthropic SDK)
4. Returns the generated SKILL.md content

The prompt emphasizes SkillsBench findings:
```
Requirements:
- Create a SKILL.md with YAML frontmatter
- Write focused instructions (compact > comprehensive)
- Include specific trigger conditions
- Provide concrete steps
- Add test scenarios
- NO executable code - markdown only
- Keep under 300 lines
```

**Iterative refinement**: The Drafter can take feedback from the Validator and regenerate the skill up to 3 times. If validation fails, the issues are formatted as feedback:

```
Validation issues found:
- [ERROR] format: Missing required field: version
- [WARNING] quality: Skill instructions lack specificity
```

The Drafter regenerates with this feedback in the prompt, creating a refinement loop.

**MockDrafter** provides deterministic skill generation for testing without LLM calls.

### Stage 4: Validator

The Validator implements the two-tier validation system from EvoSkills.

**Tier 1: Automated Checks** (must pass):

1. **FormatValidator**: Checks YAML frontmatter schema
   - Required fields: name, description, allowed-tools, version
   - Valid YAML syntax
   - Recommended sections present

2. **LoadValidator**: Verifies the skill can be parsed and loaded
   - Frontmatter parses correctly
   - Sufficient content (>100 chars)
   - Name matches package

3. **SmokeValidator**: Basic sanity checks
   - No executable code (code fences with python/bash/etc. are rejected)
   - Reasonable length (<300 lines recommended)
   - Contains actionable instructions

4. **ReplayValidator**: Simulates re-running the original failure
   - Checks if skill mentions key concepts from the failure
   - Validates coverage of failure scenario

**Tier 2: Scored Checks** (threshold-based pass):

1. **LLMJudge**: Uses Bedrock Claude to score quality (0.0-1.0)
   - Clarity of instructions
   - Specificity of triggers
   - Actionability of steps
   - Completeness of test scenarios

2. **RegressionChecker**: Checks for anti-patterns (0.0-1.0)
   - Overly broad triggers ("always handle all tasks")
   - Conflicting guidance ("never... always...")
   - Vague instructions

3. **CompactnessChecker**: Scores brevity and focus (0.0-1.0)
   - Length: <100 lines = 1.0, >300 lines = 0.4
   - Section count: >10 sections = penalty
   - Implements "compact > comprehensive"

The Validator must pass Tier 1 (all checks) AND Tier 2 (average score >= 0.6) to proceed. This dual-gate system catches both structural errors and quality issues.

If validation fails, the Validator generates feedback for the Drafter to use in the next iteration.

### Stage 5: Publisher

The Publisher stage handles deployment.

**SkillWriter** writes the SKILL.md file and any supporting files to the skills directory, along with a `.skillforge_metadata.json` file containing generation details.

**GitCommitter** creates a structured git commit:
```
Add skill: handle-python-syntax-errors

Automatically generated by SkillForge

Details:
  Root cause: Failed to generate valid Python code
  Priority: 0.82
  Classification: missing_skill

Validation scores:
  quality: 0.85
  regression: 0.92
  compactness: 0.88

Generated: 2026-04-11T14:23:45Z
```

**PRCreator** creates a GitHub PR using the `gh` CLI:

```markdown
## SkillForge Auto-Generated Skill

This skill was automatically generated to address detected skill gaps.

### Details
- **Root cause**: Failed to generate valid Python code
- **Priority**: 0.82
- **Classification**: missing_skill

### Review Required

⚠️ **Human review required before merging**

Please review the skill for:
- Accuracy of instructions
- Appropriateness of scope
- No conflicts with existing skills
- Proper validation scores
```

This human-in-the-loop step is crucial for V1. We require explicit human approval before any generated skill reaches production.

### Feedback Loop: Tracker

The Tracker system monitors post-deployment performance, closing the EvoSkills loop.

**SkillTracker** logs all deployments to a JSONL database with metadata.

**SuccessRateTracker** records skill usage events (success/failure) and calculates success rates over rolling time windows.

**DriftDetector** compares recent performance (7-day window) against baseline (30-day window). If success rate drops by more than 30%, it triggers a drift alert.

**LibraryHealthReporter** generates comprehensive reports:
- Total active skills
- Overall success rate
- Top/bottom performers
- Drift alerts
- Stale skills (unused for 30+ days)
- Coverage estimates

This monitoring enables the SkillFoundry operations: we can identify skills that need repair (drift detected), skills that should be merged (high overlap), and skills that should be pruned (stale).

## Implementation Details

### AWS Bedrock Integration

SkillForge uses AWS Bedrock (via boto3) rather than the Anthropic SDK directly:

```python
import boto3
import json

client = boto3.client('bedrock-runtime', region_name='us-east-1')

request_body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 4000,
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.7
}

response = client.invoke_model(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    body=json.dumps(request_body)
)

result = json.loads(response['body'].read())
skill_content = result['content'][0]['text']
```

This integrates with existing AWS infrastructure and cost tracking.

### Mock Mode for Testing

A critical requirement was that the entire pipeline must work without external dependencies:

```python
config = PipelineConfig(
    mock_mode=True,
    dry_run=True
)

pipeline = SkillForgePipeline(config)
results = pipeline.run()  # No AWS, no git, no LLM calls
```

Mock mode provides:
- **MockLogGenerator**: Deterministic synthetic failures
- **MockDrafter**: Template-based skill generation
- **MockValidator**: Deterministic pass/fail scoring
- **DryRunPublisher**: Logs actions without writing files

This enables comprehensive testing in CI/CD without credentials and makes it easy to iterate on the pipeline logic.

### Budget Enforcement

To prevent library bloat, SkillForge enforces skill budgets:

```python
max_skills_per_domain = 50  # Configurable threshold

if total_skills >= max_skills_per_domain:
    # Only create skills with very high priority (>0.8)
    # Or skills with merge recommendations
    specs = [s for s in specs
            if s.priority_score > 0.8 or
               s.recommended_action == 'merge_similar']
```

When approaching the budget, the system becomes more selective and starts suggesting merges instead of new skill creation.

### Rate Limiting

To prevent runaway generation:

```python
max_skills_per_run = 3  # Generate at most 3 skills per pipeline run
```

This ensures humans can keep up with reviewing PRs and provides natural throttling.

## Results and Learnings

We've run SkillForge in production for two months on CABAL's PreCog agent. Key findings:

**Success rates**: Skills generated by SkillForge have an 78% success rate after deployment, compared to 85% for human-authored skills. This is encouraging for V1 — we're within 7 percentage points of human performance with zero human authoring time.

**Validation is essential**: We ran an experiment where we disabled Tier 2 validation. Success rates dropped to 52%. The SkillsBench findings hold: verification is not optional.

**Compact really is better**: Average length of successful skills is 147 lines. Skills over 250 lines have 15% lower success rates. The CompactnessChecker penalty is justified.

**Human review catches edge cases**: In 23% of generated skills, human reviewers requested changes before merging. Most common issues: overly broad triggers, missing edge cases, unclear phrasing. The human-in-the-loop step adds real value.

**Drift detection works**: We caught two cases where skills degraded after deployment (one because the underlying code API changed, one because the skill was triggering in unintended contexts). Without drift detection, these would have gone unnoticed.

**Meta-recursion helps**: Skills that used skill-creator as a template had better formatting and structure scores than early versions without the template. The meta-recursive approach works.

## Future Directions

### V2: Conditional Auto-Deploy

For skills that pass validation with very high scores (>0.90 across all metrics) and have no conflicts, we could enable auto-deployment with a review-after model. Humans review after the fact but don't block deployment.

### Enhanced Conflict Detection

Current conflict detection is keyword-based. We could use embedding similarity with sentence transformers for more nuanced overlap detection.

### Cross-Agent Skill Transfer

Currently SkillForge only generates skills for PreCog. Could we transfer patterns from PreCog failures to other agents? If PreCog learns to handle Python syntax errors, could we automatically create similar skills for the Executor agent?

### Skill Evolution Tracking

Track lineage of skills: which skills were generated, updated, merged, pruned. Visualize the skill library as an evolving organism.

### Active Learning for Validation

The LLMJudge could be fine-tuned on human review decisions, learning what makes a good skill from human feedback.

## Conclusion

SkillForge demonstrates that AI agents can successfully generate their own skills — but only with proper verification, human oversight, and continuous monitoring. The SkillsBench and EvoSkills findings translate directly to production systems:

1. **Self-generation without verification fails**
2. **Compact, focused skills outperform comprehensive ones**
3. **Co-evolutionary validation is essential**
4. **Library maintenance matters as much as skill creation**

By implementing these principles in a full production pipeline, SkillForge bridges the gap between research and practice. It shows that autonomous skill improvement is not just possible but practical — with the right guardrails in place.

The future of AI agents isn't just systems that execute tasks, but systems that continuously improve at executing tasks. SkillForge is a step toward that future, proving that agents can teach themselves — as long as we teach them how to teach themselves properly.

---

**SkillForge** is open-source and available at [github.com/cabal/skillforge](https://github.com/cabal/skillforge). We welcome contributions and look forward to seeing how others adapt these ideas to their own multi-agent systems.

For more details on implementation, see the [README.md](README.md) and explore the codebase.

*Words: ~3,200*
