# SkillForge: Teaching AI Agents to Fix Their Own Skill Gaps

**A closed-loop self-improvement pipeline for multi-agent systems**

*April 11, 2026*

## The Counter-Intuitive Finding That Started This

When AI systems try to write their own instruction manuals, they usually make things worse. That's the uncomfortable finding from SkillsBench research on self-generated agent skills. Not marginally worse. Consistently, measurably worse.

The failure modes are specific and repeatable: skills too broad to trigger correctly, skills with contradictory instructions, skills that nail the example that created them but completely miss adjacent cases. Naive self-generation without verification produces a growing library of unreliable skills that degrades overall system performance. It's self-sabotage dressed up as self-improvement.

Here's the meta-recursive twist we arrived at: to fix this, we built SkillForge, a system that generates skills automatically. But the core tool it uses internally is `skill-creator`, an existing skill that codifies our best practices for writing skills. So we have an agent skill that teaches the system how to create new agent skills. An agent that uses instructions about instructions to write new instructions.

That's either deeply elegant or slightly unhinged. Probably both. Either way, it shipped yesterday, and here's how it works.

## Why We Built This

CABAL is our production multi-agent system. It coordinates a set of specialized agents: PreCog handles research, DAEDALUS does technical content, REHOBOAM handles creative work, LEGION runs enhancement passes, MasterControl owns engineering tasks, TheMatrix runs simulations, TACITUS manages homelab ops, and HAL9000 handles home automation. Each agent is guided by "skills" -- structured SKILL.md files that tell it how to handle specific situations.

These skills are human-authored. They work well. But keeping them current is a bottleneck, and scaling that bottleneck linearly with agent complexity is a problem I wanted to avoid.

PreCog runs against a constant stream of research tasks, and its failure patterns are a natural signal for skill gaps. Something fails, the session logs capture it, and if that failure pattern recurs, it probably means there's a missing or outdated skill. The question was: can we automate skill creation from those failures? And more importantly, can we trust the output?

The SkillsBench answer was clear: not without verification. So we built verification in from the start.

## The Research Foundation

Three papers shaped the design. Worth knowing what they actually found before getting into implementation.

**SkillsBench** ran systematic experiments on self-generated skills across different agent architectures and task types. Two findings mattered most for our design.

First: compact beats comprehensive. Counterintuitively, shorter and more narrowly scoped skills outperformed longer, more detailed ones. Skills that tried to cover everything included contradictory advice and triggered in the wrong contexts. The best performers were laser-focused on a specific situation.

Second: verification is not optional. Skills that went through format checking, test scenario execution, and regression testing had dramatically higher success rates than skills deployed immediately after generation. The verification step isn't administrative overhead. It's load-bearing.

**EvoSkills** proposed treating skill generation and validation as co-evolving processes rather than a one-shot pipeline. As skills grow more sophisticated, the validation criteria grow more sophisticated too. The loop: detect failures, generate skills, validate them, deploy only what passes, monitor post-deployment, refine or retire based on results. The "co-evolutionary" part means the validator learns what to look for as the skill library matures.

**SkillFoundry** extended this to library-scale maintenance. They identified four operations needed to keep a healthy skill library: expand (add new skills), repair (update degraded ones), merge (combine overlapping skills), and prune (remove stale ones). The insight worth keeping: skill libraries are living systems that need continuous curation, not static collections you build once and forget.

SkillForge is our production implementation of these ideas, wired to CABAL's real infrastructure.

## Architecture: Decisions and Tradeoffs

The pipeline has five stages. Here's what each does and why we made the choices we did.

### Stage 1: Monitor

We parse PreCog's actual production session logs in structured JSONL format, not synthetic data. This distinction matters. Synthetic failure data teaches you to handle synthetic failures. Real logs capture the weird, contextual, edge-case failures that actually happen in production.

The monitor clusters similar failures by signature (task type, failure type, key terms) and checks each cluster against the existing skill inventory. If no existing skill covers the pattern, it's a genuine gap worth addressing.

One deliberate constraint: this is scoped to PreCog only for now. Starting narrow kept the build manageable. Adding more agents is possible but requires understanding their specific log formats and failure semantics first.

### Stage 2: Analyzer

Not all gaps are equally important or equally fixable. The analyzer classifies each gap (missing skill, outdated skill, wrong skill being selected, or not actually a skill problem) and scores priority from three factors: failure frequency (40%), impact severity (40%), and feasibility of fixing it with a skill (20%). That last category -- "not a skill problem" -- is important. Some failures need code fixes or architectural changes, not a better instruction file. Routing those to a PR queue would be noise.

It also checks proposed skills against existing ones for overlap. High keyword overlap triggers a merge recommendation rather than creating a duplicate. Library bloat is a real problem; the SkillFoundry research was clear on that.

### Stage 3: Drafter

This is where the meta-recursive part lives. The drafter loads our `skill-creator` skill as a meta-template and provides it to Claude as context when generating new skills:

```python
template = self.load_skill_creator_template()

prompt = f"""You are creating a new agent skill.
Use this template as a guide for structure and style:

{template}

Now create a skill for: {spec.proposed_scope}
"""
```

The `skill-creator` skill was hand-authored and captures years of accumulated lessons about what makes a good skill: required frontmatter fields, how to write trigger conditions, how to scope instructions without overreaching. Using it as a template grounds generation in proven patterns. Generated skills come out with the right structure instead of the LLM inventing its own format.

The drafter can also iterate. If validation fails, the specific issues come back as feedback and it regenerates, up to three times. Refinement in a loop, not a single shot.

### Stage 4: Validator

Two-tier validation, following the EvoSkills design.

Tier 1 is binary pass/fail. Does the skill have required frontmatter fields? Valid YAML? Sufficient content? No executable code blocks? The "no executable code" check is worth calling out: a SKILL.md with embedded Python or bash in code fences is a hallucination. Skills should be markdown instructions, not runnable scripts.

Tier 2 is scored. An LLM judge evaluates clarity, trigger specificity, and actionability on a 0-1 scale. A regression checker scans for anti-patterns like overly broad triggers or contradictory instructions ("always do X... never do X"). A compactness checker applies the SkillsBench compact-beats-comprehensive finding directly: skills under 100 lines score well, skills over 300 lines get penalized. Average score across Tier 2 must hit 0.6 to pass.

If validation fails, the feedback goes back to the drafter for another attempt. The loop can run three times before the whole attempt is marked failed and logged for manual review.

### Stage 5: Publisher

Generated skills become pull requests. Every PR includes the skill file, validation scores, the original failure context that triggered generation, and an explicit note that human review is required before merging.

This is non-negotiable for V1. The system generates; humans decide what goes to production.

A `.skillforge_metadata.json` file accompanies each skill with generation details, priority score, and validation results. Git commits get structured messages with all the relevant context so the history is readable months later.

### Monitoring and Drift Detection

The Tracker system closes the EvoSkills loop. After deployment, it logs skill usage events and tracks success rates over rolling windows. The drift detector compares a 7-day window against a 30-day baseline. If success rate drops more than 30%, it fires an alert.

This enables the SkillFoundry maintenance operations: repair skills where drift is detected, flag skills that haven't been triggered in 30+ days for pruning, identify overlapping skills for merge candidates.

## What We Expect to Learn

SkillForge shipped yesterday. We do not have production data yet. What follows are the hypotheses we designed around, stated honestly as hypotheses.

**Validation will prove its worth early.** The SkillsBench research showed dramatic performance gaps between validated and unvalidated generation. We built our two-tier validator specifically to catch the failure modes they documented. If the research holds in our context, we should see a clear signal in validation scores correlating with actual deployment success.

**Compact skills will outperform comprehensive ones.** This was one of the clearest SkillsBench findings, and we embedded it in the compactness checker and the scope definer (maximum 150-character scope descriptions, forcing narrow framing). We'll track whether generated skills that score high on compactness actually outperform ones that scraped through at the 300-line boundary.

**Human review will catch things validation misses.** The PR review step is partly a safety net and partly a learning mechanism. Reviewers will see what the automated system passed that shouldn't have shipped. The patterns in their change requests should tell us where our validation is weakest. Our specific prediction: reviewers will most often flag overly broad trigger conditions -- the kind of thing that looks reasonable in isolation but would cause incorrect skill selection in practice.

**Drift detection will surface silent degradation.** Some skills will probably become stale as the underlying system evolves, without any obvious failure event to trigger manual review. APIs change, workflows shift, context drifts. Our hypothesis is that without drift detection, we'd only notice these failures after a cluster of unexplained agent behavior -- not proactively.

**The meta-recursive template approach will produce better structural quality.** We haven't run a controlled comparison of skill-creator-templated generation versus unconstrained generation in our specific environment. The SkillsBench research suggests structural quality matters for downstream success rates. We're betting that grounding generation in an existing high-quality skill produces better results than prompting from scratch. We'll have a clearer picture after reviewing the first wave of generated skills through the PR queue.

What we'll actually measure: skill success rates post-deployment, validation score distributions across generated skills, how often human reviewers request changes before merging, and how often drift detection fires in the first three months. After that data accumulates, there's a real follow-up post worth writing.

## What's Next

**V2 conditional auto-deploy.** For skills scoring above 0.90 across all Tier 2 metrics with no conflicts, we could enable auto-deployment with post-deployment review instead of blocking on pre-deployment approval. We need to earn trust in the validation system first. A few months of data showing which high-scoring skills reviewers wave through without changes will be the signal.

**Embedding-based conflict detection.** Current conflict detection uses keyword overlap, which is fast but shallow. Sentence transformer embeddings would catch semantic overlap that keyword matching misses -- skills covering the same ground with different vocabulary.

**Cross-agent patterns.** SkillForge is wired to PreCog right now. If PreCog develops a skill for handling a certain class of research failures, MasterControl or TACITUS might benefit from a version tuned to their context. There's probably pattern transfer value to explore there.

**Validation fine-tuning.** The LLM judge in Tier 2 is currently zero-shot. Once we accumulate human review decisions, we can use those as training signal to improve what the judge considers "quality." The closed loop tightens over time.

## The Honest Takeaway

The SkillsBench finding is real and worth taking seriously: naive self-generation doesn't work. The instinct to just let agents write their own skills and ship them is wrong. The verification step isn't overhead. It's the whole point.

The meta-recursive angle felt right during design, but it's still unproven in our context. Using `skill-creator` as a template produced clean, well-structured output in testing. Whether it meaningfully outperforms a well-crafted prompt without the template is a question we'll answer with data.

Human review is the right call for V1. Not because we distrust the system, but because we haven't yet earned enough trust in it to remove humans from the loop. The PR review step is how we build the empirical basis for better automation later.

And the compact-beats-comprehensive finding is probably the single most actionable insight from the underlying research. Most people's instinct when a skill fails is to make it more comprehensive, more detailed, more complete. The data says the opposite is usually true. That's the kind of counter-intuitive result that's actually useful once you internalize it.

SkillForge is live as of yesterday. Check back in a few months when there's real data to report.

---

**SkillForge** is part of the ProtoGensis monorepo: [https://github.com/ccrngd1/ProtoGensis](https://github.com/ccrngd1/ProtoGensis). See the README.md for setup instructions and configuration details.

*April 11, 2026*
