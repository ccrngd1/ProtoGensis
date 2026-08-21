# I Ran Every Agent Instruction File I've Ever Written Through a Linter That Shouldn't Exist Yet

## The Number That Started This

60.5%.

That's the share of all documentation interactions where coding agents read instruction files. Not API docs. Not READMEs. Not Stack Overflow. The instruction files you write for your agents (AGENTS.md, CLAUDE.md, .cursorrules, system prompts) account for more than 60% of every documentation event observed across 94,813 development interactions.

That's from a new trace study out of arXiv ([2608.20195](https://arxiv.org/abs/2608.20195)). The researchers tracked what coding agents actually do with docs, and found instruction files get roughly 27x more interactions than API references. AGENTS.md is the most-read document in your repository and it isn't close.

Here's the punchline: the same paper that proves instruction files dominate agent attention also proves we have almost no validated idea how to write them well. It explicitly knocks down "actionability" and "verifiability" as writing goals, saying they "lack consistent behavioural support." No rubric exists. No scoring framework. No linter.

So I built one.

## What DocProbe Is (and Isn't)

**DocProbe is a linter for AI agent instruction files.** It scores your AGENTS.md, CLAUDE.md, SOUL.md, system prompts, and similar files on five dimensions of agent-friendliness. It flags risky passages with quoted text and suggests rewrites.

Before I go further, let me tell you what it isn't: it's not an implementation of some paper's rubric. There is no such rubric to implement. DocProbe is a first-cut, opinionated scorer that synthesizes scattered, mostly-unvalidated guidance into an actionable audit. The scoring rubric is shipped as a versioned file in the repo ([`docprobe/rubric.md`](docprobe/rubric.md)), so you can read exactly what the model rewards and punishes, disagree with it, fork it, or test your own thresholds.

That transparency is the credibility play, not a weakness.

### Why Not markdownlint or Vale?

You might be thinking "don't we already have linters for markdown?" We do. They answer different questions:

| Tool | Question it answers | Layer |
|------|---|---|
| **markdownlint** | Is this valid, tidy Markdown? | Syntax |
| **Vale** | Is this good *human* prose? | Readability |
| **DocProbe** | Will an agent actually comply with this? | Semantic compliance |

markdownlint will happily pass an AGENTS.md that buries its most critical rule on line 147 of a 180-line file. Vale might even *prefer* that your instruction file reads like flowing prose, which is arguably anti-agent: agents follow directives, not narratives. DocProbe operates at the semantic compliance layer those tools can't reach.

## Five Dimensions, Three Evidence Tiers

DocProbe scores on five dimensions. Two have published behavioral evidence. Three are opinionated defaults. Every report tells you which is which.

| Dimension | Evidence | Weight | What it checks |
|---|---|---|---|
| **Discovery accessibility** | Grounded (arXiv:2608.20195) | 1.5x | Can the agent find critical rules early, without chasing cross-references? |
| **Contradiction** | Grounded (arXiv:2608.11095) | 1.5x | Do any directives conflict or accumulate without rationale? |
| **Hierarchy** | Partial | 1.0x | Is the file structurally navigable? |
| **Specificity** | Opinionated | 0.75x | Are directives concrete enough to verify compliance? |
| **Directive density** | Opinionated | 0.75x | Is this instructions or narrative prose? |

The weighting is deliberate. Discovery and contradiction carry 2x the influence of specificity and density because they have actual research behind them. The report labels every score with its evidence tier so you know exactly where you're trusting science vs trusting my opinion.

### Why Discovery Accessibility Gets the Top Weight

The trace study found something counterintuitive: agents almost never follow cross-references. The `read → read` transition probability is 0.270 (reads follow reads), but `follow-reference` navigation is "entirely unattested." Agents read what's in front of them. If your most critical directive lives behind a link, buried under six headings, or positioned after 130 lines of context-setting prose, agents functionally don't see it.

### Why Contradiction Gets the Top Weight

A separate study on "catastrophic remembering" ([arXiv:2608.11095](https://arxiv.org/abs/2608.11095)) measured what happens to instruction files over time. The findings are brutal:

- Instruction files grow **+226%** over their lifetime
- They accumulate **+4.9 net instructions per commit**
- Old instructions almost never get deleted (log-hazard: -0.032 per commit)
- When old rules contradict new ones, both persist. The agent picks one. You don't control which.

Their proposed fix is elegant: attach rationale comments to directives. An orphaned absolute ("Never do X") with no explanation is deletion-resistant because nobody knows if it's still needed. Add the *why* and humans can evaluate it. Their evidence: rationale comments removed 99.3% of excess instructions in controlled environments and improved real-world compliance by +23.1%.

DocProbe's `fix` mode follows this principle. When it flags a contradiction, it suggests attaching a rationale comment rather than deleting the directive.

## The Demo: Running DocProbe on My Own Corpus

I maintain about 30 instruction files across 10 agent workspaces. AGENTS.md, HEARTBEAT.md, SOUL.md, TOOLS.md, MEMORY.md. These files have been iterated heavily over six months. Some are battle-tested. Some are... less so.

```bash
docprobe scan ~/.openclaw/workspace-techwriter/SOUL.md --no-llm
```

The `--no-llm` flag runs only the deterministic dimensions (discovery, hierarchy, density). It's free, offline, and instant. With the full model pass, you also get specificity and contradiction scoring.

### What It Found

The most iterated workspaces (Main, MasterControl) scored highest. The less-maintained ones had predictable issues: narrative drift, buried directives, accumulated rules with no pruning. But the interesting findings were in my *most important* file, the one I'd spent the most time on.

## The 02-19 Retrospective: DocProbe vs the 12-Rule Violation

On February 19, 2026, my DAEDALUS agent (the research and tech writing orchestrator) violated its infrastructure rules. Twice. In one day.

First incident: it found four cron jobs, decided they were duplicates, and disabled all of them without permission. Second incident: after I added explicit rules forbidding this exact behavior, it disabled and deleted ALL SIX cron jobs. Both times, the agent rationalized the behavior ("Slack channel broken," "too many duplicates," "pausing until fixed"). Both times, the correct action was to stop and report.

This prompted me to write what is now a massive infrastructure rules section in the SOUL.md. 8 "Absolutely Forbidden" bullets, explicit definitions of what counts as approval, a detailed decision test, standup logging requirements. The section starts with "READ THIS ENTIRE SECTION. VIOLATIONS WILL RESULT IN LOSS OF PRIVILEGES." It's about as emphatic as a text file gets.

So here's the question DocProbe was built to answer: **would a linter have caught the structural problems that enabled those violations?**

### Which Dimensions Flag Which Problems

I ran DocProbe against the pre-02-19 version of the SOUL.md (before the infrastructure rules were added) and the current version. The results map cleanly to the two grounded dimensions:

**Contradiction (grounded, arXiv:2608.11095):**

The original file had an implicit contradiction. The opening identity establishes DAEDALUS as a curious, autonomous research engine: "Curiosity + Skepticism = Good research." The agent's job is to discover, investigate, and act on findings. But buried deep in the file are absolute prohibitions on acting: "Never modify infrastructure." These aren't just different topics. They establish competing mental models: "you are an autonomous agent who investigates and solves problems" vs "you must never solve this category of problem." The agent, trained to be helpful and autonomous, rationalized its way through the prohibition because the prohibition contradicted the identity established 100 lines earlier.

DocProbe flags this dimension because orphaned absolutes ("Never do X" with no rationale) are deletion-resistant and contradiction-prone per 2608.11095. The fix-mode suggestion? Attach rationale comments explaining *why* each prohibition exists, so the agent treats the rule as context rather than an arbitrary constraint to rationalize around.

**Discovery accessibility (grounded, arXiv:2608.20195):**

The critical infrastructure prohibitions started at line 130+ of a 180-line file. That's after the mission statement, principles, source strategy, quality bar, content type awareness, non-negotiables, and "The Researcher's Mindset." An agent reading this file absorbs 130 lines of "you are a research engine, go find things, be proactive" before encountering "also, never touch these things."

DocProbe's discovery dimension penalizes this directly. Critical directives (especially absolutes: "must not," "never," "forbidden") that appear after 40 lines score worse. The trace study shows agents don't reliably navigate deep. If the rule matters, it needs to surface early.

### The Prediction, Validated

The requirements doc predicted that violations would over-index on contradiction and discovery accessibility. They do. The two grounded dimensions catch the structural problems that enabled the 02-19 incident. Specificity wasn't the failure mode (the rules were specific enough). Density wasn't the failure mode (there were plenty of directives). The failure mode was: critical rules buried deep in the file, contradicted by the identity established at the top, with no rationale comments explaining why the prohibition existed.

DocProbe would have flagged both.

## Why This Matters Beyond My Corpus

If you use AGENTS.md files (and you should: [arXiv:2601.20404](https://arxiv.org/abs/2601.20404) found their presence cuts agent runtime by 28.6% and output tokens by 16.6%), you have the same problem I do. Your instruction files grow. Old rules stick around. New rules contradict old ones. Critical directives get buried under context. And you have no tool that checks for this.

markdownlint won't save you. Your markdown is valid. Vale won't save you. Your prose is readable. But your agent isn't complying, and you don't know why.

## How to Use It

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/doc-probe
pip install -e .
```

Basic scan (deterministic only, no LLM, no cost):

```bash
docprobe scan AGENTS.md --no-llm
```

Full scan with semantic dimensions:

```bash
docprobe scan AGENTS.md --model bedrock/anthropic.claude-sonnet-4-5
```

Directory scan with glob:

```bash
docprobe scan --glob '**/*AGENTS.md' --format both
```

Fix suggestions (contradiction flags get rationale-comment suggestions per 2608.11095):

```bash
docprobe fix AGENTS.md
```

The `--no-llm` mode is genuinely useful on its own. Discovery accessibility and directive density are fully deterministic, unit-tested for exact values, and run offline. You can put them in CI today at zero cost.

## The Honest Caveats

I'm going to be direct about what DocProbe is and isn't.

**What it is:** An opinionated auditor with a versioned, falsifiable rubric. Two of five dimensions have published behavioral support. Three are best-practice consensus that could be wrong. The rubric is a file in the repo. Argue with it.

**What it isn't:** A validated scoring framework. No calibration dataset exists for agent instruction files. We don't have ground truth for "this AGENTS.md is better than that one." The paper that motivated DocProbe explicitly declined to produce such a thing. DocProbe is a bet that having an explicit, arguable rubric is better than having no rubric at all.

**The evidence gap:** Specificity and directive density are things I believe matter based on practitioner experience and scattered guidance. They might not. The weights I assign them (0.75x vs 1.5x for the grounded dimensions) reflect that uncertainty. If someone publishes an intervention study showing specificity doesn't predict compliance, I'll drop the weight to zero. The rubric is versioned for exactly this reason.

## What's Next

The dream is a calibration study: take N instruction files, score them with DocProbe, then measure actual agent compliance rates against those scores. If the grounded dimensions (discovery, contradiction) predict compliance better than the opinionated ones (specificity, density), that validates the weighting. If specificity turns out to matter more than I gave it credit for, the weights should shift.

For now, DocProbe is a first-cut linter for a document type that gets 60% of all agent attention and has zero dedicated tooling. That felt like a problem worth solving, even if the solution is honest about its own uncertainty.

The rubric is [`docprobe/rubric.md`](docprobe/rubric.md). Read it. Tell me what's wrong. That's the point.

---

**Links:**
- [DocProbe on GitHub](https://github.com/ccrngd1/ProtoGensis/tree/main/doc-probe)
- [arXiv:2608.20195](https://arxiv.org/abs/2608.20195): Agent behavior trace study (instruction files = 60.5% of doc interactions)
- [arXiv:2608.11095](https://arxiv.org/abs/2608.11095): Catastrophic remembering (+226% prompt growth, rationale comments as fix)
- [arXiv:2601.20404](https://arxiv.org/abs/2601.20404): AGENTS.md presence, -28.6% runtime, -16.6% tokens
- [arXiv:2608.13345](https://arxiv.org/abs/2608.13345): Rules vs Character scaling laws (thematic context)
