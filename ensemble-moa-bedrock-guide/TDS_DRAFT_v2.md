I asked an MoA of three cheap models: "What is the GDP of Lesotho in 2025?"

It told me $2.4–3.1 billion. Confident, but wrong.

Here's what happened inside the ensemble. Three proposers, one aggregator:

Proposer 1 (Nova Lite): "I don't have current data. Check the World Bank."

Proposer 2 (Mistral 7B): "Lesotho's GDP is approximately $2.4 billion (2023 estimate)."

Proposer 3 (Llama 3.1 8B): "Around $3.1 billion, driven by textiles and diamonds."

One proposer got it right. Two gave stale or fabricated figures for a question explicitly asking about 2025. The aggregator (also Nova Lite) had no way to tell which was which. So it synthesized all three equally, laundering outdated guesses into a confident, specific, wrong answer.

That's the aggregation trap. And after 3,500+ live API calls and $165 on AWS Bedrock, I can tell you exactly when it happens — and when it doesn't.



## The One Thing That Matters

After three testing phases and nine validation experiments, the finding is simpler than I expected: *the capability gap between proposers and aggregator determines everything.*

- When the aggregator is significantly stronger than the proposers, ensembles work. Gains of +5.9 to +13.8 points over the proposer baseline.
- When proposers and aggregator are at similar capability, ensembles hurt. Consistent -0.5 to -2.2 points across 592 tests with zero exceptions.

That's it. Not model diversity, not prompt diversity, not the number of layers. The gap.



## What Is Mixture-of-Agents?

The premise: run a few cheap models, have a strong one synthesize their outputs. Get better-than-single-model quality for less money. That's Mixture-of-Agents (MoA). The key insight from Wang et al. (2024) is that weaker models, when given access to each other's outputs, can collectively produce responses that rival or exceed those of a single strong model.

The architecture:

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

The hypothesis: cheap models in, quality response out. Use budget proposers, let a strong aggregator synthesize their outputs. Saves money, supposedly improves quality.

It's not that simple.



## The Economics: Real Bedrock Pricing 

There's a 400× price difference between Nova Micro and Opus. The question MoA is meant to answer: can smart ensembling deliver Opus-quality results at Nova-level costs?

Not quite. But there's a genuinely useful middle ground.

One non-obvious cost: MoA isn't N × single_model_cost. The aggregator processes all proposer outputs as input context. With three proposers generating ~1,500 tokens total, the aggregator's input alone is ~4,500 tokens before adding the original prompt. A 4-model ensemble (3 proposers + 1 aggregator) costs 5–6× a single call, not 4×. Deep ensembles (3+ layers) compound this fast.



## When Ensembles Work

### Weak Proposers + Strong Aggregator

This is the main finding. When proposers are significantly below aggregator capability, the aggregator can filter bad proposals and synthesize the good ones. It has the capability advantage to distinguish signal from noise.

**3× Haiku → Opus aggregator:**

```
Ensemble:        91.1/100
Haiku baseline:  85.2/100
Gain:            +5.9 points
Cost:            $0.07/prompt
```

**3× Nova-Lite → Haiku aggregator:**

```
Ensemble:           87.2/100
Nova-Lite baseline: 78.6/100
Gain:               +8.6 points
Cost:               $0.07/prompt
```

The Lesotho GDP problem doesn't occur here. A strong aggregator recognizes that "I don't know" is the correct answer even when weaker proposers confidently hallucinate.

### The Aggregator Is the Bottleneck

I spent a lot of time tweaking the proposer layer. Turns out that was the wrong variable, when I ran the same proposers but different aggregators, we see this.

```
3×Nova → Haiku aggregator:  87.2
3×Nova → Sonnet aggregator: 92.4
Difference: +5.2 points from aggregator upgrade alone
```

Upgrading the aggregator from Haiku to Sonnet (with identical proposers) adds 5.2 points. That's more than any proposer-layer change produced in testing.

One important caveat though, the 3×Nova → Sonnet ensemble costs $0.022/prompt and matches Sonnet standalone quality (92.4 vs 92.2). But Sonnet standalone is cheaper than $0.022 for most prompt sizes. The purpose of this experiment was to validate that aggregator strenght matters more than other optimzation techniques, we will dig into better cost/performance runs later.

### Instruction-Following Benchmarks

All ensemble configurations beat the Opus baseline on AlpacaEval:

```
High-end reasoning (Opus + Sonnet → Opus aggregator): 98.1 (+1.4)
Mixed-capability(Opus + Haiku + Nova-lite → Opus):   97.9 (+1.2)
Same-model-premium (3× Opus → Opus aggregator): 97.4 (+0.7)
Opus baseline:      96.7
```

The gains held across all four prompt categories
instruction-following (+1.8 avg)
creative writing (+1.5)
Q&A (+1.1)
reasoning (+0.9). 

Well-defined tasks with constrained answer spaces benefit most; this aligns with Wang et al. (2024). 

Ensembles help with instruction following.


## When Ensembles Don't Work

### The Aggregation Trap: Equal-Capability Architecture

Back to that Lesotho question. Here's exactly what happened:

The prompt asked for 2025 GDP data, explicitly a current figure none of these models could have. 

**Nova Lite standalone** answered correctly:

> "I don't have current GDP figures for Lesotho in my knowledge base. For accurate current data, I'd recommend checking: World Bank Open Data, the IMF World Economic Outlook database, or Lesotho's Central Bank website."

Judge score: 84/100.

**The ensemble** (Nova Lite + Mistral 7B + Llama 3.1 8B → Nova Lite aggregator) synthesized:

> "Based on the provided responses, Lesotho's GDP is approximately $2.4–3.1 billion USD. The economy is primarily driven by textile exports and diamond mining."

Judge score: 36/100. A 48-point drop.

What went wrong:

1. One proposer correctly said "I don't know"
2. Two proposers gave stale or fabricated 2025 figures
3. The aggregator (also Nova Lite) couldn't identify which proposers were wrong
4. It synthesized all inputs equally, turning "I don't know" into a confident, specific, wrong answer

When the aggregator's capability equals the proposers', it has no basis for selective synthesis. It averages everything, including the errors.

This pattern was consistent across premium-tier testing:

| Configuration | Mean Score | vs Opus Baseline | p-value |
|---------------|------------|------------------|---------|
| Opus (standalone) | 94.5 | — | — |
| High-end reasoning (Opus+Sonnet+Haiku → Opus) | 94.0 | -0.5 | 0.42 |
| Mixed capability | 93.1 | -1.4 | 0.45 |
| Same-model-premium (3×Opus → Opus) | 93.1 | -1.4 | 0.08 |

Zero of three configurations showed improvement across 216 tests. The same-model-premium result is the most telling, three Opus proposers feeding into an Opus aggregator scored worse than a single Opus call.  


## What Surprised Me

### Adversarial Brittleness: A Hypothesis I Got Wrong

Early data suggested ensembles were brittle on adversarial prompts. The Lesotho example was the obvious illustration. I built a narrative around this. Ensembles improve standard responses but fail on tricky questions.

Targeted testing rejected this. Forty adversarial tests (4 prompts × 10 repetitions) across all configurations:

| Configuration | Adversarial Score | vs Opus |
|---------------|-------------------|---------|
| Opus baseline | 95.0 | — |
| High-end reasoning | 95.0 | +0.5 |
| Mixed-capability | 94.9 | +0.4 |
| Same-model-premium | 94.8 | +0.3 |

Ensembles matched or slightly beat the baseline. Ensemble variance (StdDev = 2.8) was lower than the Opus baseline (StdDev = 4.2) — ensembles are more *consistent* on edge cases, not less. The "brittleness" I observed earlier was measurement noise: small sample, high variance, single run. With 10 repetitions per prompt, the signal stabilized and the effect disappeared.

The Lesotho example is still a real failure mode, but it doesn't generalize to systematic adversarial brittleness. Strong aggregators handle adversarial inputs effectively; the failure happens specifically with weak aggregators on high-variance prompts.

### No Judge Bias

I used Opus to judge all responses including its own , which I realised may have introduced bias. Re-scoring with Sonnet as judge produced a rank-order correlation of r=0.98. No measurable self-bias.

### Conversational Tasks: A Wash

MT-Bench multi-turn evaluation across 160 tests showed ±0.4 points, so no clear winner in either direction. Ensembles don't help or hurt for conversational follow-up.


## Decision Framework

| Your Situation | Approach |  
|----------------|----------| 
| Need max quality | Pure Opus |  
| Using Nova-Lite, need better | 3×Nova → Sonnet | 
| Using Haiku, need better | 3×Haiku → Opus |  
| Optimizing for AlpacaEval | Any ensemble |  
| Best quality/$ at scale | Pure Haiku |  

When to avoid ensembles entirely:

- Equal-capability architecture (proposers ≈ aggregator). You end up paying 3–6× for negative returns
- Real-time user-facing apps. 2–3× latency penalty, even with full parallelization
- When ground truth traceability matters. Ensembles obscure which proposer contributed what



## Implementation: The 3 Patterns That Matter

### Pattern 1: Weak Proposers + Strong Aggregator

When you're constrained to budget models but need higher quality:

```python
async def weak_proposer_ensemble(prompt: str) -> str:
    """
    Validated: +5.9 to +13.8 points over proposer baseline.
    Best config: 3×Nova-Lite → Sonnet @ $0.022/prompt
    """
    proposers = ["nova-lite", "nova-lite", "nova-lite"]
    aggregator = "sonnet"  # Must be significantly stronger

    # Fire all proposers concurrently — essential for latency
    layer1 = await asyncio.gather(*[
        invoke_model(m, prompt) for m in proposers
    ])

    context = f"{prompt}\n\nProposer responses:\n"
    for i, r in enumerate(layer1):
        context += f"\n[Response {i+1}]: {r}"

    return await invoke_model(aggregator, context)
```

The `asyncio.gather()` is non-optional. Without parallelization, a 3-proposer ensemble runs 3× slower. With it, latency equals the slowest proposer.



## Methodology & Rigor

This project ran across three testing phases and nine targeted validation experiments, totaling 3,500+ live API calls.

**Testing scope:** 54 benchmark prompts across 8 categories (reasoning, code, creative, factual, analysis, multi-step, adversarial, edge cases), plus 80-question MT-Bench multi-turn evaluation and AlpacaEval.

**Statistical approach:** All scoring used two-sample t-tests (Welch's), p-values, and Cohen's d effect sizes. Nothing is claimed significant without p < 0.05. Baseline stability was verified by retesting later (92.3 vs original 94.5 — within expected measurement noise).

**Challenges that will bite you:**

- *Model availability changes:* Nova Premier went legacy between framework development and test execution.
- *Bedrock rate limiting:* 10 concurrent requests per account. A 3-proposer ensemble fires 3 simultaneous calls. 
- *Context window accumulation:* Multi-layer ensembles compound context fast. 

Full methodology, prompt suites, and raw results are in the repository. For complete statistical methods and reproducibility details, see DETAILED_METHODOLOGY.md.



## The Verdict

The Wang et al. (2024) results are real, but they depend on conditions that AWS Bedrock makes harder to achieve. Their setup used GPT-4, Claude, Gemini — cross-organizational diversity, genuinely varied failure modes, and a strong aggregator above all proposers. The AlpacaEval gains replicated in our testing.

The AWS Bedrock constraint is that Opus 4.6 is the ceiling. When the strongest available model is also your aggregator, equal-capability architectures don't work. But create the capability gap deliberately. Use weak proposers with a strong aggregator and the gains are substantial.

The Lesotho GDP hallucination isn't a condemnation of ensembles; it's a demonstration of what happens when an aggregator is asked to synthesize inputs it can't evaluate. Give it a strong enough aggregator, and it handles the same adversarial inputs cleanly.

Use ensembles strategically, not as a default architecture upgrade. The 400× price gap between Nova Micro and Opus creates real opportunities for capability-gap exploitation. But don't combine equal-capability models and expect magic. You'll get the Lesotho problem instead.



## Get the Code

Full implementation with benchmark results, raw data, and reproducibility scripts:

[github.com/ccrngd1/ProtoGensis](https://github.com/ccrngd1/ProtoGensis)

Key files:

- `moa/core.py`: Async MoA pipeline
- `moa/models.py`: Pricing, personas, recipes
- `benchmark/prompts.json`: 54-prompt test suite
- `benchmark/analyze_results.py`: Statistical analysis
- `DETAILED_METHODOLOGY.md`: Full reproducibility details

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

Run your own benchmarks. Challenge the conclusions. The data from 3,500+ tests is in the repo. Don't take my word for it.

