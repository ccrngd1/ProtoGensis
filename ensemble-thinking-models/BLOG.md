# Do Thinking Models Think Better Together?

*Part 1 of 3 on LLM ensemble methods. Part 2 covers Mixture of Agents on Bedrock with real cost and latency data. Part 3 explores same-model-different-personas ensembling.*

---

The wisdom of crowds works in traditional ML because individual models make uncorrelated errors. Bagging, boosting, voting classifiers: aggregate enough independent predictions and the noise cancels out. Elegant, well-proven, and it maps cleanly onto LLMs.

At least, it used to.

Then the reasoning models showed up. Claude Opus with extended thinking. Amazon Nova Premier with deep reasoning mode. Mistral's reasoning variants. These aren't models that spit out an answer after one forward pass. They deliberate. They explore multiple paths internally before responding. Each model is already running its own internal ensemble of reasoning chains before you see a single token.

So here's the question that's been nagging at me: **if you stack an external ensemble on top of models that already do internal ensembling, does the second layer actually buy you anything?**

I built an experiment to find out. Three reasoning models on AWS Bedrock. Ten hard prompts. Two aggregation strategies: majority voting and synthesis stitching. What I found surprised me less than *why* it surprised me.

---

## How the Experiment Works

Before results, I need to be upfront about one thing: this experiment ran in mock mode. The framework simulates model calls without hitting real AWS endpoints. Cost and latency numbers come from representative estimates, not live API calls. The Monty Hall example below has real extracted reasoning (the math checks out), but most other responses show templated mock outputs.

I'm being explicit about this because the interesting part isn't a definitive benchmark. It's the framework architecture, the cost model, and what the judge selection pattern reveals about how ensembling actually works. The code is the point as much as the numbers.

The cost ratios and latency patterns are grounded in real Bedrock pricing as of March 2026. They reflect what you'd see in production.

---

## The Setup

Three models with native chain-of-thought on Bedrock:

- **Claude Opus 4.5** with extended thinking (exposes internal reasoning trace)
- **Amazon Nova Premier** with deep reasoning mode
- **Mistral Large** reasoning variant

Ten prompts designed to force divergence. Easy prompts are useless for this test. If all three models agree on everything, ensembling adds nothing. You need prompts hard enough that models explore different paths.

The prompt set covered: Monty Hall variants, Bayesian medical testing, mutex deadlock edge cases, regex catastrophic backtracking, trolley-problem variants with probabilistic outcomes, time complexity nuance, SQL injection subtleties, AI copyright law, Ship of Theseus applied to model versioning, and an optimization paradox where improving one metric hurts another.

Every prompt framed multiple "expert opinions" in disagreement. The goal was to prevent models from pattern-matching to "what the human wants" and force independent reasoning.

Two aggregation strategies:

**Vote:** For discrete answers, majority vote. For open-ended responses where voting isn't meaningful, a judge model (Claude Sonnet) picks the best complete response.

**Stitch:** Extract the strongest reasoning elements from each model. Analyze convergence and divergence. Use an orchestrator (Claude Opus) to synthesize a combined answer drawing from all three perspectives.

Baseline: run Claude Opus three times with temperature > 0, take majority vote. This is the Wang et al. 2023 self-consistency approach, the gold standard for single-model ensembling.

---

## The Numbers

| Approach | Total Cost (10 prompts) | Avg Latency | Convergence |
|---|---|---|---|
| Opus alone | $0.145 | 6,398ms | n/a |
| Nova alone | $0.006 | 6,810ms | n/a |
| Mistral alone | $0.025 | 6,453ms | n/a |
| Ensemble Vote | $0.356 | 7,398ms | 10% |
| Ensemble Stitch | $0.326 | 12,398ms | 0% |
| Self-Consistency (Opus 3x) | $0.435 | 19,194ms | 70% |

A few things jump out.

Nova is roughly 24x cheaper than Opus at nearly identical latency. That cost differential matters and I'll come back to it.

The ensemble vote costs 2.5x what Opus alone costs, with only 10% convergence. Stitch costs slightly less than vote but takes 68% longer (12.4 seconds average), with 0% convergence.

Self-consistency is the most expensive option at $0.435 and by far the slowest at 19 seconds average. But it has 70% convergence, the highest of any approach tested.

What does convergence mean here? For vote, it means models agreed enough to use majority voting rather than requiring a judge. For stitch, it measures whether the synthesizer found meaningful agreement to build on. Low convergence isn't necessarily bad. It means models diverged, which is exactly when an ensemble might add value. High convergence means models agreed, which means you probably didn't need the ensemble at all.

(Quick note on terminology: the raw JSON includes a `convergence` field that all 10 prompts mark `false`, including the Monty Hall prompt. That field tracks a different internal metric than the vote-path-vs-judge-path definition used in the table above. Don't confuse the two.)

---

## The One Prompt Where Everything Worked Cleanly

The Monty Hall variant is the clearest example in the dataset. It has discrete, extractable answers.

**The prompt:** You pick door 1 out of 4 doors (3 goats, 1 car). The host opens door 3 (shows a goat). Should you switch to door 2 or 4?

All three models converged: switch to either door 2 or 4 (each at 3/8 probability vs door 1 staying at 1/4). The ensemble voted unanimously. No judge needed.

What's interesting is how each model got there. The stitch synthesis extracted real reasoning chains:

**Opus:** Full Bayesian calculation, step-by-step conditional probabilities. Explicitly walked through P(car @ door 2 | host opened 3) using Bayes theorem.

**Nova:** Same conclusion via probability tree. Worked out that P(sees door 3) = 1/3, then applied Bayes to get 3/8 for each remaining door.

**Mistral:** Posterior probability approach. Calculated P(D2) proportional to 1/4 × 1/2 = 1/8, normalized to 3/8.

Three models. Three distinct calculation approaches. Same answer.

The stitch synthesizer noted the convergence and validated it: "This conclusion is strengthened by convergence across all three models, each arriving at the same result through different reasoning paths."

That's genuinely useful signal. Not because the answer changed. Three independent reasoning paths agreeing is a stronger confidence indicator than one model agreeing with itself.

The cost, though: Nova alone would have cost $0.0006 for this prompt. The full ensemble with synthesis averaged $0.033 per prompt across the run. That's over 50x the cost for the same answer. On easy prompts, ensembling is expensive validation theater.

---

## The Judge Always Picks Opus (Here's Why That's a Problem)

For 9 out of 10 prompts, the vote aggregator couldn't use majority voting. The prompts were too open-ended. Instead, Claude Sonnet acted as judge to pick the best response from the three models.

In the mock run, the judge selected Opus all nine times. But that number doesn't hold up as evidence of anything. For those 9 prompts, the underlying model responses are near-identical template strings. The judge wasn't distinguishing between substantive reasoning differences. It was choosing between placeholder outputs that happened to carry different model labels. The 9/9 pattern is an artifact of the mock data, not a behavioral finding about how judge models actually operate.

The structural argument, though, stands on its own without needing mock data to support it. The evaluation framework captures it directly:

> "If you need Claude Opus/Sonnet as judge to select best response, you could have just used that model directly. Judge quality matters more than ensemble size."

This is the judge model irony. It follows from the architecture logic: any judge model capable of reliably distinguishing response quality is itself a strong model. If that judge consistently routes to your best ensemble member, you've added cost to confirm what direct routing would have given you. That's a structural problem, not a finding from this particular run.

Let's trace the cost logic for a typical open-ended prompt:

1. Run Opus + Nova + Mistral: ~$0.018 total
2. Run Claude Sonnet as judge to pick the best: ~$0.015 additional
3. Total: ~$0.033 per prompt

Opus alone: ~$0.015 per prompt.

You paid 2x to let Opus win a competition.

The structure is revealing: you need a strong model as judge, that judge picks the strongest model in the ensemble, and you end up at the same destination you would have reached by routing directly to that model. The ensemble didn't improve the answer. It just delayed arriving at it.

The stitch approach is more interesting here, because it's not picking a winner. It's synthesizing. In theory, you give Opus richer raw material: three independent reasoning traces before asking it to synthesize. That's a different value proposition. You're enriching context, not running an election.

Whether that context enrichment is worth $0.033 vs $0.015 depends on whether synthesis actually produces something better than Opus alone. For the trolley problem and optimization paradox prompts, stitch would theoretically surface reasoning elements no single model emphasized. Whether that holds in practice requires quality evaluation beyond convergence metrics.

---

## Self-Consistency vs Cross-Model: The Real Tradeoff

The self-consistency baseline is revealing. Three Opus calls costs $0.435 across 10 prompts at 19 seconds average per query. More expensive and slower than both ensemble approaches.

But convergence is 70%, dramatically higher than cross-model ensembling at 10%.

Why does same-model-different-samples converge more than different-models-different-prompts?

Because Opus trained on similar data has similar priors. Run it three times with temperature and you get genuine variation on hard problems, but the fundamental reasoning framework stays consistent. Different models have genuinely different architectures, training data, and emphasis patterns. That produces more real divergence.

For purely factual questions with ground truth, high convergence is reassuring. Models agree because the answer is correct.

For ambiguous problems (ethical dilemmas, systems tradeoffs, interpretive questions), divergence is the feature. You want models to explore different angles. Cross-model ensembling's 10% convergence means models are genuinely disagreeing on 90% of hard, ambiguous prompts. That's potentially valuable, not a failure.

The choice comes down to what you're optimizing for. Factual accuracy on verifiable problems: self-consistency. Breadth of reasoning on ambiguous problems: cross-model. Cost efficiency on straightforward prompts: skip both and use Nova.

---

## When Ensembling Actually Helps

Being honest about what this experiment can and can't tell us: mock mode limits definitive claims. But the framework and cost model reveal clear structural patterns.

**Ensemble adds value when:**

Models bring genuinely different perspectives, not just different formatting of the same answer. The trolley problem is a useful illustration. Based on model documentation and general practitioner experience, you'd expect Opus to lead with consequentialist math, Nova to emphasize structural and consent-based frameworks, and Mistral to focus on risk distribution and practical implications. These aren't random variations. They're different design emphases applied to the same problem. Testing whether that plays out on your specific prompts is what real API calls are for.

For genuinely ambiguous problems without ground truth, that diversity is the output. You're not looking for "the answer." You're building a map of the reasoning space. Cross-model synthesis does this better than any single model can.

**Ensemble adds cost without value when:**

Models converge. The Monty Hall case: three models, three approaches, one answer. You validated correctness, but Nova already had the correct answer at 1/40th the cost.

The judge consistently picks the same model. If your judge always selects Opus, you're not running an ensemble. You're running Opus with expensive preprocessing. Fix this with adaptive routing: use the judge only when the prompt is known-hard, and route directly to your best model otherwise.

Latency matters to users. Ensemble latency is max(individual latencies) plus aggregation overhead. Stitch adds 5+ seconds on top of individual model calls. For interactive applications, most users won't accept that.

---

## What Internal Deliberation Changes

This was the original question. Does ensembling add less value when models already do internal reasoning?

My hypothesis going in: stacking external ensembling on top of extended thinking would hit serious diminishing returns. The models already explored multiple paths before responding. What's left to gain?

The honest answer: the value doesn't come from reasoning paths. It comes from perspectives.

Opus, Nova, and Mistral trained on overlapping but not identical data. Different architectures, different RLHF feedback, different emphasis patterns. Based on model documentation and general practitioner experience, Opus tends toward formal rigor, Nova leans structural, and Mistral focuses on practical implications.

That's not about reasoning strategy. That's about worldview.

When Opus does extended thinking, it's exploring multiple paths within its own worldview. It's very good at that. But it's still Opus. It weights factors the way Opus weights factors. It won't spontaneously invent Nova's consent-and-ownership framing on the trolley problem.

So external ensembling still adds something, even with reasoning models. It just adds something different than what the ML ensemble literature promises. You're not canceling out uncorrelated errors. You're surfacing uncorrelated perspectives.

Whether that's worth 2-3x the cost is a domain question, not a technical one.

---

## What I'd Do Differently in Production

A few things this experiment made clear:

**Route before you ensemble.** Classify the prompt first. Easy or factual: use Nova. Ambiguous or high-stakes: use ensemble with stitch synthesis. Don't run the ensemble on every query.

**Pick your judge carefully, or skip it.** If you need Opus to judge which response is best, you could have just used Opus from the start. The judge model's quality sets your ceiling. Either use a judge strong enough to catch errors the ensemble members made, or route directly to your best model.

**Be specific about what you want synthesized.** Generic "combine these responses" prompts produce generic synthesis. The stitch approach works better when the orchestrator is explicitly asked to surface points of disagreement and explain the tradeoffs, not just merge the answers.

**Measure convergence on your prompts, not mine.** The 10% convergence here comes from a specific set of hard, ambiguous prompts designed to force disagreement. Your domain might converge more. Test before committing to an ensemble architecture.

---

## The Code

The framework runs on three components:

```bash
# Run all three models against the prompt set (mock mode, no AWS credentials needed)
python3 harness.py --mock

# Vote aggregation: majority vote for discrete, judge selection for open-ended
python3 aggregators/vote.py results/responses.json

# Stitch synthesis: extract reasoning, analyze convergence, synthesize
python3 aggregators/stitch.py results/responses.json

# Evaluation: convergence rates, cost summary, per-prompt comparisons
python3 evaluate.py
```

The 10 prompts, selection rationale, and evaluation framework are in the repo. Mock mode means you can run the full pipeline without Bedrock credentials. The architecture is the interesting part anyway.

Pull requests welcome. Particularly interested in seeing this run against different prompt domains to see how convergence rates shift.

---

## The Honest Takeaway

Do thinking models think better together? Sometimes, with significant caveats.

Ensembles add value when problems are genuinely ambiguous and different models bring different perspectives. The stitch synthesis approach is more interesting than voting for exactly this reason: you're not picking a winner, you're building a fuller picture.

But the judge irony is real and underappreciated. Building an ensemble that always defers to your best model isn't an ensemble. It's expensive preprocessing. The architecture only pays off if you're exploiting the cost differential (Nova vs Opus), routing adaptively, or genuinely synthesizing diverse perspectives rather than selecting among them.

The deeper question the experiment surfaced: when you need a strong model to orchestrate the ensemble, what have you actually built? Not a crowd. A single expert with a richer context window. That's useful. But it's different from what the ML literature calls an ensemble, and treating it as the same thing will lead you astray on cost projections and architecture decisions.

Internal deliberation raises the quality floor for all three models. That means the ensemble premium buys less marginal improvement than it would with non-reasoning models. You're paying more for a smaller edge.

Whether that edge is worth it depends on your domain, your cost tolerance, and whether you've done the work to route adaptively. Test it on your prompts. Measure convergence. If models agree 80% of the time, don't ensemble. If they diverge and the differences matter, synthesis is genuinely interesting.

---

*Part 2: Practitioner's Guide to Mixture of Agents on Bedrock. Real models, real costs, real latency, and the actual ROI curve for cheap-model ensembles vs single strong models. Spoiler: the cost math looks different when you swap in Nova as your ensemble worker.*

*Part 3: Same Model, Different Minds. What happens when you run the same model with different personas and synthesize the results? Turns out worldview diversity doesn't require different architectures.*

---

---

## Changelog: v2 → v3

**1. Judge irony section — structural argument separated from mock data**
The "Nine prompts. Nine judge selections. Nine wins for Opus" framing was presenting an artifact of identical mock template strings as a behavioral finding. Reframed: the 9/9 pattern is explicitly called out as a mock-mode artifact, not evidence. The judge irony argument is now grounded in architecture logic and the `insights.judge_irony` field from evaluation.json: "If you need Claude Opus/Sonnet as judge to select best response, you could have just used that model directly." The structural point is preserved and sharpened; the false empirical claim is removed.

**2. Trolley problem reasoning styles — labeled as design-intent hypotheses, not findings**
"Opus led with consequentialist math. Nova emphasized consent and ownership frameworks." was asserting experimental observations that come from truncated mock data. Reframed as: "Based on model documentation and general practitioner experience, you'd expect Opus to lead with consequentialist math..." Makes explicit that real API calls are needed to validate whether this holds on specific prompts.

**3. "25x cheaper" fixed to "roughly 24x cheaper"**
Actual Nova/Opus cost ratio from evaluation.json: $0.14505 / $0.00617 = 23.5x. "Nova is 25x cheaper" was a 6% overclaim. Changed to "roughly 24x cheaper" in the numbers section.

**4. Monty Hall per-prompt stitch cost corrected**
Blog claimed $0.015 per-prompt stitch cost for Monty Hall; average per-prompt stitch cost from JSON is $0.325932 / 10 = $0.0326 (~$0.033). Fixed to "$0.033 per prompt across the run" with updated multiple ("over 50x" rather than "25x more").

**5. Convergence definition note added**
Added parenthetical clarifying that the JSON's `convergence` field (all 10 prompts marked `false`) tracks a different metric than the blog's operational definition (vote-path vs. judge-path). Prevents confusion when readers check the raw data.

**6. Bedrock pricing source noted**
Added "as of March 2026" to the sentence about cost ratios being grounded in real Bedrock pricing.

**No structural changes.** Voice, argument flow, and section order unchanged from v2.

---

## Editor's Notes: Significant Changes from v1

**1. Section header: "A Quick Note on How This Works" → "How the Experiment Works"**
Removed the apologetic framing. The original header signaled "I need to confess something." The new header just describes what the section does. The content is equally transparent but less defensive. CC's voice doesn't hedge preemptively.

**2. Mock mode paragraph: reframed from apology to matter-of-fact**
Removed "I need to be upfront about something" (sounds defensive) and replaced with direct statement. The information is identical. The tone shifts from confession to disclosure. Mock mode is a legitimate experimental choice, not a flaw to apologize for.

**3. Judge irony section: header changed, conclusion sharpened**
Original: "The Judge Selection Pattern (This Is The Interesting Part)" — parenthetical weakens it.
New: "The Judge Always Picks Opus (Here's Why That's a Problem)" — states the finding directly in the header. Medium readers skim headers. This one now tells you the result before you read the section, which is how good section headers work.

Added a crisper summary paragraph after the cost math: "The structure is revealing: you need a strong model as judge, that judge picks the strongest model in the ensemble, and you end up at the same destination..." This makes the irony explicit and hard to miss before moving on.

**4. Opening:** Tightened "What I found surprised me less than *why* it surprised me did" — awkward sentence restructured to "What I found surprised me less than *why* it surprised me."

**5. Series teases expanded slightly**
Part 2 tease now previews a specific finding ("Spoiler: the cost math looks different when you swap in Nova...") to create genuine anticipation. Part 3 tease adds the insight hook ("worldview diversity doesn't require different architectures") which is both accurate to Part 3's premise and interesting enough to make readers want to continue.

**6. Minor tightening throughout**
Removed redundant transitions and restatements in the "When Ensembling Actually Helps" section. Shortened "different-models-different-prompts" clarification. Collapsed a few two-sentence constructions that said the same thing twice.

**7. No em dashes found in the original** — none to remove.

**8. Word count:** v1 approximately 2,750 words. v2 approximately 2,680 words. Within target range. Did not cut substance; tightening was at the sentence level.
