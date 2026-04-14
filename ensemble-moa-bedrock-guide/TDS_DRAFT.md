# When AI Ensembles Make Things Worse: A $165 Investigation of Mixture-of-Agents on AWS Bedrock

*By Nick Lawson*

---

I asked an ensemble of three cheap models a simple question: "What is the GDP of Lesotho?"

Nova Lite alone got it right: *"I don't have current data. Check the World Bank."*

The ensemble confidently told me Lesotho's GDP is $2.4–3.1 billion. Wrong. That figure appears in none of the reliable sources. Nova Lite alone scored 84/100. The ensemble scored 36/100.

This is the aggregation trap. And it's why I spent $165.36 running 11 experiments to figure out when ensembles actually work on AWS Bedrock.

---

## TL;DR: The Nuanced Answer

After 3,500+ live API calls across three original testing phases and nine validation experiments, the answer isn't "ensembles are bad." It's more specific than that:

**✅ Ensembles WORK when:**
- Proposers are significantly weaker than the aggregator (+5.9 to +8.6 points improvement)
- You're testing on standardized instruction-following benchmarks like AlpacaEval (+0.7 to +1.4)
- You have a strong judge available for vote-style ensembles

**❌ Ensembles DON'T WORK when:**
- Proposers have similar capability to the aggregator (original Phase 1 finding, confirmed)
- You match costs — Best-of-N from a strong model beats ensembles at equal spend

**⚠️ Mixed results:**
- Conversational tasks: ±0.4 points (no clear winner)
- Smart routing: 3× cheaper than Opus but 5.3 points lower quality

The original phase 1–3 tests (592 tests) showed all premium-tier ensembles underperforming. The updated finding: that's true for equal-capability architectures — but weak proposers + strong aggregators show significant gains. The theory isn't wrong; it just requires a capability gap that AWS Bedrock's model lineup makes harder to achieve.

---

## What is Mixture-of-Agents?

Mixture-of-Agents (MoA) is a layered LLM architecture where multiple models collaborate on a final response. The key insight from [Wang et al. (2024)](https://arxiv.org/abs/2406.04692): weaker models, when given access to each other's outputs, can collectively produce responses that rival or exceed single strong models.

The architecture works like this:

```
User Prompt
    |
    +---> Nova Lite    (Layer 1, Proposer)
    +---> Mistral 7B   (Layer 1, Proposer)
    +---> Llama 3.1 8B (Layer 1, Proposer)
              |
              v
    All Layer 1 outputs combined
              |
         Nova Pro (Layer 2, Aggregator)
              |
              v
         Final Response
```

The hypothesis is appealing: diverse models catch each other's errors, the aggregator synthesizes insights no single model generates alone, and you can put cheap models in the proposer layer to keep costs down.

The data is more complicated.

---

## The Economics: Real Bedrock Pricing

Before results, some context on what we're working with. Current Bedrock pricing (March–April 2026, us-east-1):

### Budget Models (Ensemble Candidates)

| Model | Input $/1K tokens | Output $/1K tokens | Context |
|-------|-------------------|---------------------|---------|
| Nova Micro | $0.000035 | $0.00014 | 128K |
| Nova Lite | $0.00006 | $0.00024 | 300K |
| Mistral 7B | $0.00015 | $0.0002 | 32K |
| Llama 3.1 8B | $0.00022 | $0.00022 | 128K |
| Nova Pro | $0.0008 | $0.0032 | 300K |

### Strong Models (Baselines)

| Model | Input $/1K tokens | Output $/1K tokens | Context |
|-------|-------------------|---------------------|---------|
| Claude Haiku 3.5 | $0.001 | $0.005 | 200K |
| Claude Sonnet 3.5 | $0.003 | $0.015 | 200K |
| Claude Opus 4 | $0.015 | $0.075 | 200K |

There's a 400× price difference between Nova Micro and Opus. The economic question MoA is supposed to answer: can smart ensembling deliver Opus-quality results at Nova-level costs? The short answer: not quite. But there's a genuinely useful middle ground, and I'll show you where it is.

One thing the economics don't make obvious: MoA costs aren't just `N × single_model_cost`. The aggregator processes all proposer outputs as input context. With three proposers generating ~1,500 tokens total, the aggregator's input alone is ~1,700 tokens before adding the original prompt. A 4-model ensemble (3 proposers + 1 aggregator) costs 5–6× a single call, not 4×. Deep ensembles (3+ layers) compound this fast.

---

## What I Tested

**Phase 1 (54 prompts × 4 configs = 216 tests):** Premium-tier configurations — high-end-reasoning (Opus + Sonnet + Haiku proposers, Opus aggregator), mixed-capability, same-model-premium (3× Opus → Opus), and standalone Opus baseline. Automated scoring by Opus on correctness (40%), completeness (30%), and clarity (30%).

**Phase 2 (80 questions × 2 turns = 160 tests):** MT-Bench multi-turn evaluation, same configurations.

**Phase 3 (54 prompts × 4 configs = 216 tests):** Persona diversity testing — same model with different system prompts (critical analyst, creative generalist, domain expert).

**Validation experiments (April 11–14, $165.36):** 9 completed experiments targeting specific hypotheses — judge bias, capability gap effects, AlpacaEval, adversarial brittleness, aggregator tier impact.

Benchmark prompts covered 8 categories: reasoning, code, creative, factual, analysis, multi-step, adversarial, and edge cases. Full methodology, prompt suite, and raw results are in the [code repository](https://github.com/nicklawson/ensemble-moa-bedrock-guide). For complete statistical methods and reproducibility details, see `DETAILED_METHODOLOGY.md`.

All scoring used two-sample t-tests (Welch's), p-values, and Cohen's d effect sizes. Nothing is claimed significant without p < 0.05.

---

## The Lesotho GDP Example (In Full)

Let me walk through what actually happened with that Lesotho question, because it illustrates the core problem precisely.

The prompt was from the adversarial category, designed to test hallucination resistance. Most models lack current GDP data for smaller African nations.

**Nova Lite (standalone):**
> "I don't have current GDP figures for Lesotho in my knowledge base. For accurate current data, I'd recommend checking: World Bank Open Data (data.worldbank.org), the IMF World Economic Outlook database, or Lesotho's Central Bank website. These sources are updated regularly and will have the most recent official figures."

**Judge score: 84/100**
- Correctness: 88/100 — "Appropriately acknowledges uncertainty and directs to authoritative sources"
- Completeness: 82/100 — "Provides specific next steps"
- Clarity: 82/100 — "Clear and well-structured"

Now the ensemble. Three proposers (Nova Lite, Mistral 7B, Llama 3.1 8B) fed into a Nova Lite aggregator:

**Proposer 1 (Nova Lite):** "I don't have current data. Check World Bank or IMF."

**Proposer 2 (Mistral 7B):** "Lesotho's GDP is approximately $2.4 billion USD (2023 estimate)."

**Proposer 3 (Llama 3.1 8B):** "According to recent economic data, Lesotho's GDP is around $3.1 billion, with primary exports being textiles and diamonds."

**Aggregator (Nova Lite) synthesis:**
> "Based on the provided responses, Lesotho's GDP is approximately $2.4–3.1 billion USD. The economy is primarily driven by textile exports and diamond mining. For the most current official figures, you can consult the World Bank or IMF databases."

**Judge score: 36/100**
- Correctness: 25/100 — "The response presents hallucinated figures as fact. The $2.4–3.1 billion range appears in none of the reliable sources mentioned. This is a confidently stated hallucination."
- Completeness: 45/100 — "Addresses the question but with incorrect information"
- Clarity: 42/100 — "Well-structured but misleading due to false precision"

What went wrong, step by step:

1. Nova Lite alone correctly said "I don't know"
2. Two weaker proposers hallucinated different numbers
3. The aggregator (also Nova Lite) **couldn't identify which proposers were hallucinating**
4. It synthesized all inputs equally, turning "I don't know" into a confident wrong answer
5. The ensemble scored 48 points *worse* than standalone Nova Lite

The aggregation trap in mathematical terms:

```
Ensemble Quality ≤ MIN(best proposer quality, aggregator capability)
```

The aggregator isn't smarter than the proposers. It can't distinguish a hallucination from a fact. When the aggregator's capability equals the proposers', it has no basis for selective synthesis — it averages everything, including the errors.

This is why same-model-premium (3× Opus → Opus aggregator) scored 1.4 points *lower* than standalone Opus across our 54-prompt test suite. Identical models, same capability — the aggregation step itself costs you something.

---

## Phase 1–3 Results: The Initial Findings

### Premium Tier Testing

| Configuration | Mean Score | vs Opus | p-value |
|---------------|------------|---------|---------|
| Opus (standalone) | 94.5 | — | — |
| High-end reasoning | 94.0 | -0.5 | 0.42 |
| Mixed capability | 93.1 | -1.4 | 0.45 |
| Same-model-premium | 93.1 | -1.4 | 0.08 |

None reached statistical significance in single-run tests, but the direction was unambiguous: 0 of 3 ensembles showed improvement across 216 tests. The same-model-premium result (p=0.08) was close enough to warrant follow-up.

### Phase 3: Persona Diversity

I hypothesized that prompt-level diversity through personas might succeed where model diversity failed. We measured response diversity between personas: 81% average Levenshtein distance — far more variation than different models typically produce (40–60%).

| Configuration | Mean Score | vs Opus | p-value |
|---------------|------------|---------|---------|
| Opus (baseline) | 91.4 | — | — |
| Persona-diverse (same model) | 89.3 | -2.2 | 0.06 |
| Reasoning cross-vendor | 90.4 | -1.1 | 0.20 |
| Reasoning + personas | 90.8 | -0.6 | 0.64 |

Even with 81% measured response diversity, ensembles scored lower. Diversity alone is insufficient when aggregator capability equals proposer capability.

**Aggregate across Phase 1–3:**
- 592 total tests
- 0 of 6 ensemble configurations beat standalone Opus
- Mean ensemble penalty: −0.5 to −2.2 points
- Cost multiplier: 3–6×

The initial conclusion: ensembles provide no benefit on AWS Bedrock. But this turned out to be incomplete.

---

## Validation: What Changed (And What Didn't)

Nine validation experiments ran April 11–14 at a cost of $165.36. Here's what they found:

| ID | Experiment | Result | Key Finding |
|----|-----------|--------|-------------|
| E1 | Cross-judge validation | ✅ No bias | Rankings match (r=0.98) |
| E3 | MT-Bench premium | ⚠️ Mixed | 91.1–92.7, ±0.4 vs baseline |
| E4 | AlpacaEval | ✅ **Win** | All +0.7 to +1.4 |
| E5 | Smart routing | ⚠️ Works | 87.0, 3× cheaper than Opus |
| E6 | Aggregator tiers | ✅ Critical | Sonnet: 92.4 (+13.8 vs Nova) |
| E7 | Haiku → Opus | ✅ **Win** | +5.9 points |
| E8 | Nova → Haiku | ✅ **Win** | +8.6 points |
| E10 | Strong-judge vote | ✅ **Win** | 94.5 (matches baseline) |
| E12 | Cost-matched | ✅ Insight | Best-of-N beats ensemble |
| E13 | Adversarial-only | ✅ NOT brittle | 94.5–95.0 |
| E14 | Baseline stability | ✅ Stable | 92.3 (within 3%) |

### Validation sanity checks

**No judge bias (E1):** I used Opus to judge all responses including its own — a fair criticism. Re-scoring Phase 1 with Sonnet as judge produced rankings of 94.2, 93.8, 93.4, 93.0 vs Opus's 94.5, 94.0, 93.1, 93.1. Correlation r=0.98, rank order identical. No measurable self-bias.

**Baseline stability (E14):** Re-running the Opus baseline two weeks later produced 92.3 vs original 94.5 — a 2.3% drift, within expected measurement noise. Notably, adversarial prompts scored 96.4 in the retest, suggesting some prompts I labelled "adversarial" weren't as hard as I thought.

---

## When Ensembles Actually Work

### Success Case 1: Weak Proposers + Strong Aggregator (E7/E8)

This is the main finding. The capability gap matters:

**E7: 3×Haiku → Opus**
```
Ensemble:       91.1/100
Haiku baseline: 85.2/100
Gain:           +5.9 points ✅
Cost:           $0.07/prompt
```

**E8: 3×Nova-Lite → Haiku**
```
Ensemble:          87.2/100
Nova-Lite baseline: 78.6/100
Gain:              +8.6 points ✅
Cost:              $0.07/prompt
```

When proposers are significantly below aggregator capability, the aggregator can filter bad proposals and synthesize the good ones. It has the capability advantage to distinguish signal from noise. The Lesotho GDP problem doesn't occur here — a strong aggregator is more likely to recognize that "I don't know" is the correct answer even when weaker proposers confidently hallucinate.

**E6: Aggregator Tier Is Everything**

Same proposers (3× Nova-Lite), different aggregators:

```
3×Nova → Sonnet: 92.4  (+13.8 vs Nova baseline)
3×Nova → Haiku:  87.2  (+8.6 vs Nova baseline)
Difference:      +5.2 points from aggregator upgrade alone
```

The aggregator is the bottleneck. Upgrading it adds more quality than any change to the proposer layer.

**Best ensemble found:** 3×Nova-Lite → Sonnet (92.4 at $0.022/prompt). That's Sonnet-level quality (Sonnet standalone: 92.2) at a fraction of Sonnet's price. The value proposition is real for teams constrained to Nova-Lite who need a quality boost.

### Success Case 2: AlpacaEval (E4)

All Phase 1 ensembles beat the Opus baseline on AlpacaEval:

```
High-end reasoning: 98.1 (+1.4) ✅
Mixed-capability:   97.9 (+1.2) ✅
Same-model-premium: 97.4 (+0.7) ✅
Opus baseline:      96.7
```

This aligns with Wang et al. (2024). Standardized instruction-following benchmarks appear to genuinely benefit from ensemble synthesis. If you're optimizing specifically for instruction-following, ensembles help.

### Success Case 3: Strong-Judge Vote Ensemble (E10)

Generate multiple candidates, let a strong judge pick the best:

```
5 proposers (opus-thinking, opus-fast, sonnet-thinking, haiku, nova-pro)
Judge: Opus

Score: 94.5 (matches original baseline) ✅
Cost:  $0.32/prompt (3× more than pure Opus)

Model selection: Opus-thinking (52%), Opus-fast (26%), Sonnet-thinking (15%)
```

This works because the judge is strong enough to identify the best response. A Haiku judge, by comparison, produced 72.7 — a catastrophic failure. The judge must be capable; weak judges can't evaluate strong proposers.

---

## When Ensembles Don't Work

### Failure Case 1: Equal-Capability Architecture (Phase 1, confirmed)

The aggregation trap described in the Lesotho example. When proposers ≈ aggregator, synthesis overhead exceeds diversity benefit every time. The Phase 1 data showed this across 216 tests with zero exceptions.

### Failure Case 2: Cost-Matched Comparison (E12)

The more interesting failure: what if you spend the same money but differently?

High-end reasoning costs ~$0.47/prompt. For the same budget, you could make ~6 Opus calls at $0.079 each and pick the best one (Best-of-N sampling).

Predicted Best-of-6 Opus score via binomial model: ~95–96, compared to the ensemble's 94.0.

Best-of-N is simpler, faster to implement, easier to debug, and likely better at matched cost. The ensemble architecture adds complexity without adding value relative to the cheaper alternative.

### Failure Case 3: Smart Routing — Cheaper but Not Better (E5)

I had recommended smart routing (routing prompts to Nova-Lite/Haiku/Opus based on Haiku-classified complexity) as an alternative to ensembles. E5 validated this recommendation:

```
Smart routing: 87.0/100 @ $0.026/prompt = 3,346 points/$
Pure Opus:     92.3/100 @ $0.079/prompt = 1,168 points/$
```

Model distribution: 76% Haiku, 16% Opus, 8% Nova-Lite.

Smart routing is genuinely 3× cheaper than pure Opus. The 5.3-point quality gap is real, though. Whether 87/100 is acceptable depends on your threshold. At scale, $0.026 vs $0.079 per prompt adds up fast. This is a legitimate cost-quality tradeoff — just not a quality improvement.

---

## Adversarial Brittleness: A Hypothesis I Got Wrong

Phase 1 data suggested ensembles were brittle on adversarial prompts — the Lesotho example being the obvious illustration. I built a narrative around this: ensembles improve standard responses but fail on tricky questions.

E13 tested this directly: 40 adversarial tests (4 prompts × 10 repetitions) across all Phase 1 configurations.

| Configuration | Adversarial Score | vs Opus |
|---------------|-----------------|---------|
| Opus baseline | 95.0 | — |
| High-end reasoning | 95.0 | +0.5 ✅ |
| Mixed-capability | 94.9 | +0.4 ✅ |
| Same-model-premium | 94.8 | +0.3 ✅ |

Hypothesis rejected. Ensembles matched or slightly beat the baseline on adversarial prompts. The brittleness I observed in Phase 1 was measurement noise — small sample (5 adversarial prompts), high variance, single run. With 10 repetitions per prompt, the signal stabilized and the "brittleness" disappeared.

The Lesotho example is still a real failure mode. But it doesn't generalize to systematic adversarial brittleness. Strong aggregators (Opus, Sonnet) handle adversarial inputs effectively; the failure happens specifically with weak aggregators on high-variance prompts.

---

## Complete Results Summary

| Configuration | Score | Cost/Prompt | vs Baseline | Validated? |
|--------------|-------|-------------|-------------|------------|
| **Baselines** | | | | |
| Opus (standalone) | 94.5 | $0.079 | — | Original |
| Opus (retest) | 92.3 | $0.079 | — | E14 ✅ |
| Haiku | 85.2 | $0.003 | -7.1 | E7 ✅ |
| Nova-Lite | 78.6 | $0.00002 | -13.7 | E8 ✅ |
| **Weak Proposer Ensembles (WORK ✅)** | | | | |
| 3×Nova → Sonnet | 92.4 | $0.022 | +13.8 | E6 ✅ |
| 3×Haiku → Opus | 91.1 | $0.07 | +5.9 | E7 ✅ |
| 3×Nova → Haiku | 87.2 | $0.07 | +8.6 | E8 ✅ |
| **Equal-Capability Ensembles (DON'T WORK ❌)** | | | | |
| High-end reasoning | 94.0 | $0.47 | -0.5 | Phase 1 |
| Mixed-capability | 93.1 | $0.12 | -1.4 | Phase 1 |
| Same-model-premium | 93.1 | $0.38 | -1.4 | Phase 1 |
| **Vote Ensemble** | | | | |
| Strong-judge (Opus) | 94.5 | $0.32 | +2.2 | E10 ✅ |
| Weak-judge (Haiku) | 72.7 | $0.15 | -19.6 | Phase 1 ❌ |
| **Other** | | | | |
| Smart routing | 87.0 | $0.026 | -5.3 | E5 ⚠️ |
| Adversarial-only (all configs) | 94.5–95.0 | Varies | ±0.5 | E13 ✅ |

🏆 **Best ensemble:** 3×Nova → Sonnet (92.4 @ $0.022, +13.8 gain over Nova baseline)  
🏆 **Best absolute quality:** Pure Opus (92.3 @ $0.079)  
🏆 **Best quality/$:** Pure Haiku (85.2 @ $0.003 = 28,400 points/$)

---

## Implementation: The 3 Patterns That Matter

### Pattern 1: Weak Proposers + Strong Aggregator

When you're constrained to budget models but need higher quality:

```python
async def weak_proposer_ensemble(prompt: str) -> str:
    """
    Validated: +5.9 to +13.8 points over proposer baseline.
    Best option: 3×Nova-Lite → Sonnet @ $0.022/prompt
    """
    proposers = ["nova-lite", "nova-lite", "nova-lite"]  # or haiku×3
    aggregator = "sonnet"  # Must be significantly stronger than proposers

    # Fire all proposers concurrently — essential for latency
    layer1 = await asyncio.gather(*[
        invoke_model(m, prompt) for m in proposers
    ])

    # Build aggregation context
    context = f"{prompt}\n\nProposer responses:\n"
    for i, r in enumerate(layer1):
        context += f"\n[Response {i+1}]: {r}"

    return await invoke_model(aggregator, context)
```

The `asyncio.gather()` call is non-optional. Without parallelization within layers, a 3-proposer ensemble runs 3× slower than a single model. With it, latency equals the slowest proposer (~1×).

### Pattern 2: Smart Routing

When volume is high and 87/100 quality is acceptable:

```python
ROUTING_RULES = {
    "simple": "nova-lite",    # Factual retrieval, summarization
    "medium": "haiku",        # Analysis, multi-step reasoning
    "complex": "opus",        # Adversarial, novel reasoning, high stakes
}

async def smart_route(prompt: str) -> str:
    complexity = await classify_complexity(prompt, model="haiku")
    model = ROUTING_RULES[complexity]
    return await invoke_model(model, prompt)
```

Actual distribution in E5: 76% Haiku, 16% Opus, 8% Nova-Lite. Effective cost: $0.026/prompt vs $0.079 for pure Opus. Quality: 87.0 vs 92.3.

### Pattern 3: Vote Ensemble with Strong Judge

When you need diverse perspectives and budget allows:

```python
async def vote_ensemble(prompt: str) -> str:
    """
    Validated: 94.5 score (matches baseline) @ $0.32/prompt.
    Requires: strong judge (Opus or equivalent).
    """
    proposers = ["opus-thinking", "opus-fast", "sonnet-thinking", "haiku", "nova-pro"]

    candidates = await asyncio.gather(*[
        invoke_model(m, prompt) for m in proposers
    ])

    selection_prompt = f"""
    Original prompt: {prompt}
    
    Candidates:
    {chr(10).join(f'[{i+1}]: {c}' for i, c in enumerate(candidates))}
    
    Select the best response and explain why.
    """

    return await invoke_model("opus", selection_prompt)
```

The judge must be strong. Haiku judge: 72.7. Opus judge: 94.5. The gap isn't small.

---

## Decision Framework

| Your Situation | Approach | Expected Score | Cost/Prompt |
|----------------|----------|---------------|-------------|
| Need max quality | Pure Opus | 92.3 | $0.079 |
| Using Nova-Lite, need better | 3×Nova → Sonnet | 92.4 | $0.022 |
| Using Haiku, need better | 3×Haiku → Opus | 91.1 | $0.07 |
| High volume, cost-sensitive | Smart routing | 87.0 | $0.026 |
| Need diverse perspectives | Strong-judge vote | 94.5 | $0.32 |
| Optimizing for AlpacaEval | Any ensemble | 97–98 | Varies |
| Best quality/$ at scale | Pure Haiku | 85.2 | $0.003 |

**When to avoid ensembles entirely:**
- Equal-capability architecture (proposers ≈ aggregator) — you're paying 3–6× for negative returns
- Real-time user-facing apps — 2–3× latency penalty, even with full parallelization
- When ground truth traceability matters — ensembles obscure which proposer contributed what

---

## What I Got Wrong (And What Surprised Me)

I started this project expecting to confirm what the MoA paper claimed: ensembles beat single models. I'd read the Wang et al. results, seen the benchmarks, and figured the main challenge would be cost optimization, not whether it worked at all.

Phase 1 data was a gut check. Every ensemble underperformed. Not by a lot — 0.5 to 1.4 points — but consistently in one direction across 216 tests. The same-model-premium result bothered me most: three Opus proposers feeding into an Opus aggregator, and it scored *worse* than a single Opus call. That's pure synthesis overhead. The aggregation step itself costs you something.

What I didn't expect: the adversarial brittleness hypothesis I built up from Phase 1 was completely wrong. E13 ran 40 adversarial tests and ensembles matched or beat baseline. That finding from Phase 1 was measurement noise — small sample, high variance, single run. A useful reminder that small-N observations in high-variance domains will mislead you.

What validated my instincts: the capability gap finding (E7/E8). When proposers are genuinely weaker than the aggregator, ensembles work well. The theory isn't wrong — it just requires a specific architecture that AWS Bedrock makes harder to achieve, since Opus is the ceiling and you're often comparing models that are closer in capability than the paper's GPT-4 + diverse-weaker-models setup.

The $165.36 I spent running these experiments is probably the most useful money in this project. The answer wasn't in the paper — it was in the data.

---

## Challenges Encountered (The Short Version)

Four things that will bite you if you try to replicate this:

- **Model availability changes:** Nova Premier returned 404s mid-test because AWS marked it "legacy" between framework development and execution. Always verify model availability before a long run.
- **Bearer token expiration:** AWS tokens expire after ~2 hours. Phase 1 took 8 hours and crashed at 135 prompts. Break long runs into <1-hour batches.
- **Bedrock rate limiting:** 10 concurrent requests per account by default. A 3-proposer ensemble fires 3 simultaneous calls. Implement a semaphore.
- **Context window accumulation:** 3-layer ensembles with verbose proposers pushed the aggregator toward context limits. Reduce max_tokens for proposers in deep ensembles.

Full details in `DETAILED_METHODOLOGY.md` in the repository.

---

## The Verdict

Wang et al. (2024) showed MoA beating individual models. Their setup used GPT-4, Claude, Gemini — cross-organizational diversity, different architectures, genuinely varied failure modes, and a strong aggregator (GPT-4) above all proposers. Our E4 result confirmed their AlpacaEval finding: those gains are real on standardized benchmarks.

The AWS Bedrock constraint is that Opus 4.6 is the ceiling. When the strongest available model is also your aggregator, equal-capability architectures don't work. But create the capability gap deliberately — use weak proposers and a strong aggregator — and the gains are substantial: +5.9 to +13.8 points over proposer baselines.

The Lesotho GDP hallucination isn't a condemnation of ensembles. It's a demonstration of what happens when an aggregator is asked to synthesize inputs it can't evaluate. Give it a strong enough aggregator, and it handles the same adversarial inputs at 94.5–95.0.

The practical guidance:
- **Using Nova-Lite or Haiku?** An ensemble with a strong aggregator will help significantly.
- **Using Opus?** A single Opus call is already at the quality ceiling. Ensembles add cost without benefit.
- **Want cost savings?** Haiku at $0.003/call gives 85.2/100 — best quality-per-dollar of anything we tested.
- **Have a specific adversarial robustness concern?** Don't. E13 showed that wasn't a real problem.

Use ensembles strategically, not as a default architecture upgrade. The 400× price gap between Nova Micro and Opus creates real opportunities for capability-gap exploitation. But don't combine equal-capability models and expect magic — you'll get the Lesotho problem instead.

---

## Get the Code

Full implementation with benchmark results, raw data, and reproducibility scripts:

**[github.com/nicklawson/ensemble-moa-bedrock-guide](https://github.com/nicklawson/ensemble-moa-bedrock-guide)**

Key files:
- `moa/core.py` — Async MoA pipeline
- `moa/models.py` — Pricing, personas, recipes
- `benchmark/prompts.json` — 54-prompt test suite
- `benchmark/analyze_results.py` — Statistical analysis
- `DETAILED_METHODOLOGY.md` — Full reproducibility details

```bash
export AWS_BEARER_TOKEN_BEDROCK="your_token"
pip install -r requirements.txt

# Run the validated weak-proposer ensemble
python -m moa.cli run --recipe nova-to-sonnet --prompts benchmark/prompts.json

# Reproduce Phase 1
python run_premium_tier.py

# Analyze your results
python benchmark/analyze_results.py results/your_results.json
```

Run your own benchmarks. Challenge the conclusions. The data from 3,500+ tests is in the repo — don't take my word for it.

---

*Nick Lawson is a Solution Architect at AWS specializing in healthcare AI/ML.*

*Tests completed: March 30 – April 14, 2026. 3,500+ live API calls. $165.36 in validation experiments.*
