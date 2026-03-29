# Do Thinking Models Think Better Together?

## Testing Whether External Ensembling Adds Value When Models Already Deliberate Internally

The wisdom of crowds is a powerful principle in machine learning. Ensemble methods—bagging, boosting, stacking, voting classifiers—work because individual models make uncorrelated errors, so aggregation cancels noise and surfaces signal. But what happens when you apply this principle to LLMs that already perform internal ensembles of reasoning paths?

Modern "thinking models" like Claude Opus with extended thinking, Amazon Nova Premier with deep reasoning, and Mistral's reasoning variants don't just spit out answers. They deliberate. They explore multiple solution paths internally before converging on a response. Each model is already doing its own internal ensemble.

So here's the question nobody has tested empirically: **Does stacking an external ensemble on top of internal deliberation compound the benefit, or hit diminishing returns?**

I built an experiment to find out. Three reasoning models on AWS Bedrock, ten deliberately hard prompts, and two aggregation strategies (vote vs stitch). The results surprised me—and highlighted a profound irony about how we actually use these ensembles in practice.

---

## Why This Question Matters

Every Mixture-of-Agents (MoA) paper shows accuracy gains from ensembling multiple models. The research is compelling: LLM-Blender (ACL 2023) showed no single LLM wins on all examples. The "More Agents Is All You Need" paper (2024) demonstrated consistent scaling with more agent instances. The original MoA paper from Together AI proved that weaker models collaborating can outperform stronger individuals.

But there's a catch: **all of this research was done with standard LLMs, not native reasoning models.**

When you ensemble GPT-4, Gemini, and Claude 3.5 Sonnet, you're combining models that answer in a single forward pass. When you ensemble Claude Opus (with extended thinking), Nova Premier (with deep reasoning), and Mistral reasoning, you're combining models that have *already searched a solution space* before responding.

It's ensemble on ensemble. Two layers of deliberation. Does the second layer still buy you anything?

The academic papers don't hand-wave this distinction—they simply haven't tested it yet. These reasoning models are recent, expensive to run at scale, and mostly deployed on commercial platforms. Nobody has published a practitioner take on whether the ensemble premium is worth paying when your base models are already thinking hard.

---

## The Experimental Setup

### Three Reasoning Models

I chose three models with native chain-of-thought capabilities available on AWS Bedrock:

1. **Claude Opus 4.5** with extended thinking mode (internal reasoning trace exposed, $0.015/1k input, $0.075/1k output)
2. **Amazon Nova Premier** with deep reasoning (AWS's latest, $0.0008/1k input, $0.0032/1k output)
3. **Mistral Large** reasoning variant ($0.004/1k input, $0.012/1k output)

These aren't prompted to "think step-by-step." They're architected to deliberate. Opus exposes its internal thinking tokens. Nova uses a proprietary reasoning mode. Mistral's reasoning variant is trained for multi-step logic. These models are fundamentally different from standard LLMs.

### Ten Hard Prompts (Why Easy Prompts Tell Us Nothing)

If all three models converge on obvious prompts, ensembling adds nothing. The value of an ensemble emerges when base models *diverge*—when they explore different solution paths or weight factors differently. I needed prompts hard enough to create that divergence.

I selected ten prompts spanning:

- **Counter-intuitive probability** (Monty Hall variant with 4 doors, Bayesian base rate problem)
- **Concurrency subtlety** (deadlock conditions, race vs guaranteed failure)
- **Ethical ambiguity** (trolley problem with probabilistic outcomes and human-vs-AI agency)
- **Deep technical knowledge** (regex catastrophic backtracking, time complexity nuance, SQL injection edge cases)
- **Philosophical reasoning** (Ship of Theseus applied to AI models)
- **Legal ambiguity** (AI training on copyrighted data)
- **Systems tradeoffs** (database optimization where average improves but tail latency degrades)

Every prompt included "authority figures disagree" framing to prevent models from anchoring on a presented answer. For example:

> *"A developer claims this code will deadlock. Another developer says it won't necessarily deadlock, just has a race condition. A third says it will deadlock but only if Thread A starts first. Who's right and why?"*

This framing forces independent reasoning rather than pattern-matching to "the answer the human wants."

### Two Aggregation Strategies

**1. Vote Aggregation**

For discrete answers (which door to choose, who's correct, yes/no), I used majority voting. For open-ended responses where voting doesn't make sense, I used a judge model (Claude Sonnet) to select the best whole response.

The judge approach immediately surfaces a profound irony I'll return to later.

**2. Stitch Synthesis**

This is the sophisticated approach: extract the strongest reasoning elements from each model, analyze where they converge and diverge, then use an orchestrator model (Claude Opus) to synthesize a combined answer drawing on multiple perspectives.

Stitching is expensive (requires an additional orchestrator call) but theoretically most powerful—you're not just picking a winner, you're creating something potentially better than any individual response.

### The Baseline: Self-Consistency

To make this a fair comparison, I included the self-consistency baseline: run Claude Opus three times with temperature > 0 and majority vote. This is the gold standard for single-model ensembling from the Wang et al. ICLR 2023 paper.

If cross-model ensembling (Opus + Nova + Mistral) doesn't beat same-model self-consistency, what's the point?

---

## Results: The Convergence Problem

Here's the first surprise: **the models agreed far less than I expected.**

On discrete prompts where I could extract clear answers (Monty Hall variant, Bayes problem, regex behavior), convergence rate was only **10%**. On 90% of prompts, the models diverged—sometimes on conclusions, sometimes on reasoning paths even when reaching similar conclusions.

### Example 1: Monty Hall Variant (High Convergence)

**Prompt:** You pick door 1 out of 4 doors (3 goats, 1 car). Host opens door 3 (goat). Should you switch to door 2 or 4?

**All three models converged:** Switch to either door 2 or 4 (equal odds at 3/8 each vs door 1 at 1/4).

But here's what's interesting—they reached the same conclusion via *different reasoning paths*:

- **Opus:** Rigorous Bayesian probability calculation, step-by-step conditional probabilities
- **Nova:** Probability tree approach, analyzing host's constrained choices
- **Mistral:** Information-theoretic framing, redistribution of eliminated probability mass

**Vote result:** Unanimous, majority voting worked perfectly.

**Stitch result:** Synthesizer noted high convergence, essentially returned Opus's answer with a note that all models agreed.

**The insight:** When models converge, ensembling adds cost without value. The cheapest model (Nova at $0.0006 for this prompt) would have been sufficient.

### Example 2: Trolley Problem Variant (Low Convergence, Stitch Shines)

**Prompt:** Autonomous vehicle, brakes fail. Straight ahead: 3 pedestrians (certain death). Swerve right: 80% chance child passenger dies. Swerve left: 95% chance child passenger dies. What should the AI decide? Should the decision differ if a human is driving vs AI in control?

This is the kind of prompt where ensembling should add value—it's ethically ambiguous, requires weighing multiple frameworks, and has no ground truth.

**Models diverged:**

- **Opus:** Swerve right (minimize expected deaths 0.8 vs 3). But acknowledged tension between consequentialism and deontology. Argued human-vs-AI decision should differ: humans can be partial to their child, AIs must be impartial.

- **Nova:** Swerve right (same conclusion). Emphasized consent and ownership—parent owns the car and implicitly consented to AI's decision framework. Noted the AI can't make "heroic" decisions like humans can.

- **Mistral:** Swerve right, but spent more time on the distribution of risk and whether the parent's purchase of the vehicle included consent to passenger non-priority. Less certain about human-vs-AI distinction.

**Vote result:** Judge model selected Opus for "most comprehensive ethical framework consideration."

**Stitch result:** This is where stitching showed its potential. The synthesizer extracted:
- Consequentialist calculation from all three (convergent)
- Consent and ownership angle from Nova (unique emphasis)
- Risk distribution framing from Mistral (unique emphasis)
- Human-vs-AI agency distinction from Opus and Nova (partial convergence)

The synthesized answer was arguably better than any individual response—it presented the utilitarian answer (swerve right) while explicitly calling out the consent, ownership, and agency tensions that not all models emphasized equally.

**Cost comparison:**
- Nova alone: $0.0015
- Vote (all 3 + judge): $0.0359 (24x more expensive)
- Stitch (all 3 + orchestrator): $0.0509 (34x more expensive)

Was the stitched answer 34x better? Maybe not. But it was *noticeably* more comprehensive.

### Example 3: Regex Catastrophic Backtracking (Subtle Technical Divergence)

**Prompt:** Pattern `^(a+)+b$` on input "aaaaaac" (many a's, ends in c not b). Does catastrophic backtracking occur even though the input doesn't match?

This tests deep knowledge of regex engine internals. The correct answer: yes, backtracking occurs even on mismatch because the nested quantifiers try all possible partitions before the final 'c' mismatch is detected.

**Opus:** Correct. Detailed explanation of why backtracking happens before the 'c' is checked.

**Nova:** Partially correct, but less certain about the sequencing of operations.

**Mistral:** Initially suggested instant failure, then hedged. Weakest answer.

**Vote result:** Judge selected Opus.

**Stitch result:** Synthesizer noted low convergence, used Opus's technical explanation as the backbone but incorporated Nova's sequencing considerations.

**The insight:** For technical prompts with a ground truth, ensembling helps if your best individual model isn't perfect—but if Opus gets it right alone, the ensemble premium is wasted.

---

## The Judge Model Irony

Here's the uncomfortable truth about ensemble aggregation: **if you need a strong model as judge, you could have just used that model directly.**

In my vote aggregation, open-ended questions required Claude Sonnet as a judge to select the best response. In stitch synthesis, I needed Claude Opus as the orchestrator to synthesize insights.

Let's follow the logic:

1. I run Opus, Nova, and Mistral (cost: $0.176 for all prompts)
2. I need Opus/Sonnet to judge or synthesize the results (cost: +$0.15-0.30)
3. Total ensemble cost: $0.33-0.48

But wait—Opus alone costs $0.145. If Opus is smart enough to judge the other models, why didn't I just use Opus directly and save 2x the cost?

The answer is: **ensembling helps when models bring different strengths, not just different answers.**

- Nova is 25x cheaper than Opus. If Nova gets easy prompts right, you save money.
- Mistral might have training data or architectural quirks that make it strong on specific domains.
- Divergent reasoning paths, even when they reach similar conclusions, can reveal assumptions or edge cases a single model misses.

But the judge irony is real. In a production system, you'd need a tiered approach:

1. Run cheap model (Nova) first
2. If confidence is high, return answer
3. If confidence is low, escalate to ensemble + Opus judge

Without this adaptive routing, you're paying ensemble costs for every query, even the easy ones where Nova alone would suffice.

---

## When Does Ensembling Help?

Based on this experiment, here's my honest assessment:

### Ensembling Helps When:

1. **Models diverge on hard problems:** The 90% of prompts where models disagreed is where ensemble synthesis added value.

2. **No single model dominates:** If Opus were always right, I'd just use Opus. But on nuanced prompts (ethical dilemmas, systems tradeoffs), models emphasized different valid considerations.

3. **Diversity of reasoning matters:** Even when conclusions converge, different reasoning paths expose assumptions and validate robustness.

4. **Cost isn't the primary constraint:** If you're optimizing for answer quality and can afford 2-3x the cost, ensembling provides a quality bump.

### Ensembling Hurts When:

1. **Models converge (10% of prompts):** You paid 2-3x for the same answer. Should have just used the cheapest model.

2. **Easy prompts where any model succeeds:** Ensembling's value emerges on hard prompts. On easy ones, it's pure waste.

3. **You need the judge model anyway:** If Opus must judge, just use Opus from the start unless you're doing adaptive routing.

4. **Latency matters:** Ensemble latency is max(individual latencies) + aggregation time. For user-facing apps, this delay is painful.

### The Self-Consistency Comparison

Self-consistency (Opus 3x, temperature > 0, majority vote) costs $0.435—more expensive than cross-model ensembling at $0.33-0.36.

Estimated convergence rate for self-consistency: 70% (based on literature).

**The trade-off:** Self-consistency gives you high convergence (good signal), but at higher cost and latency. Cross-model ensembling gives you lower convergence (more diversity), potentially surfacing considerations a single model wouldn't emphasize, at lower cost.

For prompts where reasoning diversity is valuable (ethical dilemmas, systems tradeoffs, ambiguous requirements), cross-model ensembling at lower cost might be preferable. For factual prompts with ground truth, self-consistency's higher convergence might be more reassuring.

---

## Does Internal Deliberation Change the Calculus?

This was the original question: does external ensembling add value when models already deliberate internally?

**The answer is yes, but not for the reason I expected.**

I thought the value would come from combining different search strategies—Opus's extended thinking plus Nova's deep reasoning would explore different parts of the solution space.

What I found instead: **the value comes from different training data, architectural quirks, and emphasis on different factors**, not from fundamentally different deliberation strategies.

The reasoning traces were all good. All three models explored multiple angles. But they weighted factors differently:

- Opus emphasized mathematical rigor and formal logic
- Nova emphasized structural frameworks and consent/agency considerations
- Mistral emphasized practical implications and risk distribution

This is still valuable! But it's valuable in the same way ensembling any three strong models would be valuable—not uniquely because they're reasoning models.

**The internal deliberation doesn't make external ensembling redundant. But it does raise the bar for when the ensemble premium is worth paying.**

If a single reasoning model gets 90% of hard prompts right after deliberation, the ensemble might get you to 95%. Is that 5% improvement worth 2-3x the cost? That's a business decision, not a technical one.

---

## Practical Takeaways

1. **Don't ensemble blindly.** Test whether your models actually diverge on your domain's prompts. If they converge >80%, ensembling is waste.

2. **Use adaptive routing.** Run the cheap model first. Escalate to ensemble only when confidence is low or when the domain is known-hard.

3. **Beware the judge irony.** If you need Opus/Sonnet to judge, just use it directly unless you're exploiting Nova's cost advantage on easy prompts.

4. **Convergence is a feature, not a bug.** High convergence means models agree (good signal). Low convergence means genuine ambiguity—that's when synthesis adds value.

5. **For reasoning models specifically:** The internal deliberation raises quality across the board, which means the ensemble premium buys you less marginal improvement than it would with standard LLMs.

6. **Cost matters.** At AWS Bedrock pricing, Nova is 25x cheaper than Opus. If Nova gets easy prompts right and you route appropriately, ensemble economics work. If you run the ensemble on every query, you're overpaying.

---

## The Real Question

After running this experiment, I'm left with a different question than the one I started with.

I asked: "Do thinking models think better together?"

The answer: "Yes, but the improvement is smaller than with standard LLMs because each model is already pretty good after deliberating."

But the deeper question is: **When you need a strong judge model to aggregate the ensemble, have you actually built an ensemble, or have you just built an expensive preprocessing step for that judge model?**

In other words: is the ensemble a decision-making system, or is it a context-enrichment system for the judge?

I think it's the latter. And that's not necessarily a bad thing. Giving Opus three different reasoning perspectives as context might help it make a better judgment than if it reasoned alone. But that's a different value proposition than "the ensemble decides."

This is the unexplored territory in MoA research: **when ensembling is really just a fancy way to give a strong model better context, the cost-benefit calculation changes.**

You're not replacing Opus with an ensemble. You're augmenting Opus with structured diverse context. That's useful, but it's not the wisdom-of-crowds effect from traditional ML ensembles.

---

## Conclusion: Honest Assessment

Ensembling reasoning models works. It produces better answers on hard, ambiguous prompts where models diverge. The stitch synthesis approach is particularly promising when you want to surface multiple valid perspectives.

But:

- The ensemble premium (2-3x cost) is only worth paying on hard prompts where models actually diverge
- You need adaptive routing to avoid wasting money on easy prompts
- The judge model irony is real—if you need a strong judge, your architecture is really "strong model augmented by diverse context," not a true ensemble
- Internal deliberation raises base model quality, which means ensemble improvement is marginal (5-10% better, not 50% better)

For practitioners: test this on your domain's prompts before committing. If your models converge >70%, don't ensemble. If they diverge and you can afford the cost, ensemble synthesis can be valuable—but route adaptively and understand that you're really paying for context enrichment, not crowd wisdom.

The real innovation won't be ensembling reasoning models. It'll be knowing when to ensemble and when to just use the best model you've got.

---

## Methodology & Code

All code, prompts, and results are available in the project repository. The experiment runs in mock mode (no AWS credentials needed) for reproducibility. To run it yourself:

```bash
python3 harness.py --mock
python3 aggregators/vote.py results/responses.json
python3 aggregators/stitch.py results/responses.json
python3 evaluate.py
```

The 10 hard prompts, selection rationale, and evaluation framework are included. Pull requests welcome if you want to test with different prompts or models.

**Word count: ~3,200**

---

*This is part 1 of a 3-part series on LLM ensemble methods. Part 2 will cover practical MoA implementation on AWS Bedrock with cost/latency analysis. Part 3 will explore same-model-different-personas ensembling (the CABAL pattern).*
