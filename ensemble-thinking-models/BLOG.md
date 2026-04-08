# Do Thinking Models Think Better? (Spoiler: No)

*Part 1 of 3 on LLM ensemble methods. Updated April 2026 with comprehensive live study results that challenge conventional wisdom about extended thinking and ensemble approaches.*

---

The wisdom of crowds works in traditional ML because individual models make uncorrelated errors. Bagging, boosting, voting classifiers: aggregate enough independent predictions and the noise cancels out. Elegant, well-proven, and it maps cleanly onto LLMs.

At least, that's what we thought.

Then the reasoning models showed up. Claude Opus with extended thinking (10K token reasoning budget). Models that deliberate internally, exploring multiple paths before responding. Each model running its own internal ensemble of reasoning chains before you see a single token.

**Two questions kept me up at night:**

1. If you stack an external ensemble on top of models that already do internal ensembling, does the second layer actually buy you anything?
2. Do models with extended thinking capabilities actually perform better on genuinely hard prompts?

I ran a comprehensive study to find out. **Both hypotheses failed spectacularly.**

---

## The Study Design

**Duration**: 71 minutes  
**Total Cost**: $12.50  
**Models Tested**: 10 unique models  
**Prompts**: 10 genuinely hard reasoning tasks  
**API Calls**: 240+ live Bedrock calls  
**Experiments**: 4 comprehensive comparisons

This was not a toy experiment. Every API call was live. Every cost number is real. Every timeout actually happened (looking at you, Opus-thinking).

### Four Experiments

1. **Thinking-Only Ensemble**: 3 Claude models with extended reasoning (Opus, Sonnet, Haiku)
2. **Fast-Only Ensemble**: 6 models with standard inference (3 Claude fast + budget models)
3. **Direct Comparison**: Head-to-head thinking vs fast on same base models
4. **Hybrid Ensemble**: 1 thinking model + 5 fast/budget models

### The Hard Prompts

Not pattern-matching exercises. Genuinely hard reasoning tasks:

- **Adversarial integral** requiring Cauchy principal value understanding
- **5-pirate gold division** with backward induction
- **Race condition bug** with lock-check-lock subtlety
- **X12 to HL7 conversion** with semantic contradictions (this one broke Opus-thinking twice)
- **ICD-10 coding** under diagnostic uncertainty
- **Clinical entity recognition** with negations and temporal relationships
- **Conflicting medical studies** requiring synthesis
- **Contract amendments** with add→remove→restore logic
- **Game theory**, **concurrency**, **healthcare data**

Every prompt had verifiable ground truth. Every model response was evaluated for correctness.

---

## The Results That Changed Everything

### Finding 1: Extended Thinking Provides ZERO Accuracy Benefit

**Hypothesis**: Extended thinking (5-10K token reasoning budgets) should improve accuracy on hard prompts.

**Result**: ❌ **REJECTED**

| Model | Thinking Mode | Fast Mode | Winner |
|-------|--------------|-----------|---------|
| Opus | 87.5% @ $2.21 | **90.0% @ $1.61** | 🏆 **FAST** |
| Sonnet | 90.0% @ $0.77 | **90.0% @ $0.40** | 🏆 **FAST** (tied accuracy, 48% cheaper) |
| Haiku | 90.0% @ $0.17 | **90.0% @ $0.08** | 🏆 **FAST** (tied accuracy, 53% cheaper) |

**Fast mode never worse, sometimes better, always cheaper.**

Not only did thinking mode fail to improve accuracy, **Opus-thinking actively performed WORSE** than Opus-fast while costing 37% more.

### Finding 2: Opus-thinking is Comprehensively Terrible

This deserves its own section because the failure was so complete:

**Performance metrics:**
- **Accuracy**: 87.5% (lowest of all models tested)
- **Completion rate**: 80% (failed 2/10 prompts with timeouts)
- **Cost**: $2.21 per 10 prompts (most expensive)
- **Cost per correct**: $0.2524 (worst value by far)
- **Latency**: 59s average, 3+ minute max before timeout

**What failed:**
- h5 (X12 to HL7 conversion): Timed out after 360+ seconds, 3 retries
- h10 (X12 835 payment reconciliation): Timed out after 360+ seconds, 3 retries

Both failures were on complex healthcare data conversion tasks. **Opus-fast handled both successfully in 45-65 seconds.**

Opus-thinking is the only model that failed to complete the study. Every other model—fast variants, budget models, everything—completed all 10 prompts successfully.

### Finding 3: Nova-lite Wins Everything

The dark horse. Amazon Nova Lite. A budget model priced at $0.002 per 10 prompts.

**Performance:**
- **Accuracy**: 90% (9/10 correct)
- **Cost**: $0.0002 per correct answer
- **Speed**: 4.6 seconds average
- **Reliability**: 100% completion rate

**Value comparison:**
- **1100x cheaper** than Opus-thinking (same or better accuracy)
- **808x cheaper** than Opus-fast (equal accuracy)
- **383x cheaper** than Sonnet-thinking (equal accuracy)
- **87x cheaper** than Haiku-thinking (equal accuracy)

For 1 million prompts:
- Nova-lite: $200
- Opus-thinking: $220,900
- **Savings: $220,700 (99.9% cost reduction)**

This wasn't supposed to happen. Nova-lite isn't marketed as a reasoning model. It doesn't have extended thinking. It's just fast, cheap inference. And it matched or beat every premium model tested.

### Finding 4: Ensembles Beat Best Individual 0/40 Times

**Hypothesis**: When models diverge on hard prompts, ensemble aggregation should produce better answers.

**Result**: ❌ **REJECTED**

| Experiment | Prompts | Ensemble Beat Best | Win Rate |
|-----------|---------|-------------------|----------|
| Exp 1: Thinking-only | 10 | 0 | 0% |
| Exp 2: Fast-only | 10 | 0 | 0% |
| Exp 3: Comparison | 10 | 0 | 0% |
| Exp 4: Hybrid | 10 | 0 | 0% |
| **TOTAL** | **40** | **0** | **0%** |

Not once. Not on easy prompts where models converged. Not on hard prompts where models diverged (0% convergence in fast-only experiment). Not with vote aggregation. Not with stitch synthesis.

**Ensembles just pick one of the existing answers.** They don't synthesize anything better. They add cost (6-45% overhead) without adding value.

---

## Why These Results Matter

### The Cost of Being Wrong About Thinking

If you deployed Opus-thinking for production reasoning tasks based on the hypothesis that extended thinking helps:

**Monthly cost for 10M prompts:**
- Opus-thinking: $2,209,000
- Nova-lite: $2,000
- **Wasted budget: $2,207,000**

That's not a rounding error. That's the cost of an entire engineering team.

And you'd get **lower accuracy** (87.5% vs 90%) with **20% failure rate** as a bonus.

### The Judge Model Irony (Resolved)

Original hypothesis: "If you need a strong judge model to select the best ensemble answer, why not just use the judge directly?"

**Turns out the premise was wrong.** You don't need a judge at all. You don't need an ensemble. Just use the cheapest model that meets your accuracy threshold.

For most tasks, that's Nova-lite at $0.0002 per correct answer.

### When Fast Mode > Thinking Mode

Every single tier:
- Opus-fast beat Opus-thinking (90% vs 87.5%, 27% cheaper)
- Sonnet-fast tied Sonnet-thinking (90% vs 90%, 48% cheaper)
- Haiku-fast tied Haiku-thinking (90% vs 90%, 53% cheaper)

**Thinking mode added 48-150% cost premium for 0% accuracy gain.**

The 2-3x increase in output tokens from thinking mode (2K-10K token reasoning traces) didn't translate to better answers. It just burned money.

---

## The One Prompt Where Reasoning Traces Were Interesting

The Monty Hall variant (4 doors, host opens door 3, should you switch?) showed all models reaching the same answer (switch to door 2 or 4, each at 3/8 probability vs 1/4 staying).

**But the reasoning paths differed:**

- **Opus**: Bayesian calculation, step-by-step conditional probabilities
- **Sonnet**: Probability tree, worked out P(sees door 3) = 1/3
- **Haiku**: Posterior probability, normalized to 3/8

Three approaches, same answer. That diversity was interesting.

**Did it matter?** No. All three models got it right independently. The ensemble didn't improve on the individual answers. It just confirmed what any single model already knew.

And Nova-lite got it right too, without any extended reasoning, at 1/1000th the cost.

---

## The Numbers

### Experiment 1: Thinking-Only Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-thinking, Sonnet-thinking, Haiku-thinking |
| Total cost | $3.15 |
| Time | 25 minutes |
| Convergence | 70% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: High convergence (70%) means models agreed. When models agree, you don't need an ensemble. Just use the cheapest one.

### Experiment 2: Fast-Only Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-fast, Sonnet-fast, Haiku-fast, Llama-3-1-70B, Nova-pro, Nova-lite |
| Total cost | $2.13 (32% cheaper than thinking) |
| Time | 21 minutes (16% faster) |
| Convergence | 0% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Zero convergence means maximum diversity. If ensemble methods work anywhere, they should work here. They didn't.

### Experiment 3: Direct Comparison

| Metric | Value |
|--------|-------|
| Models | All 6 Claude (3 thinking + 3 fast) |
| Total cost | $5.07 |
| Time | 25 minutes |
| Convergence | 30% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Head-to-head proof that fast mode beats thinking mode.

### Experiment 4: Hybrid Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-thinking + 5 fast/budget models |
| Total cost | $2.18 |
| Time | 20 minutes |
| Convergence | 0% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Adding one expensive thinking model to 5 cheap fast models just adds cost. Haiku-fast and Nova-lite beat Opus-thinking at 26x and 1000x lower cost.

---

## What About Convergence?

Original theory: ensembles add value when models diverge.

**Reality check:**

| Experiment | Convergence | Ensemble Value |
|-----------|-------------|----------------|
| Thinking-only | 70% (high agreement) | 0/10 (no value) |
| Fast-only | 0% (max disagreement) | 0/10 (no value) |
| Comparison | 30% (moderate) | 0/10 (no value) |
| Hybrid | 0% (max disagreement) | 0/10 (no value) |

**Ensembles provided zero value at every convergence level.**

When models converge (70% in thinking-only), they're all already correct. Ensemble confirms the right answer but adds cost.

When models diverge (0% in fast-only), they disagree, but the ensemble just picks one existing answer. It doesn't synthesize anything better.

---

## The Cost Model (Updated)

### Per-Prompt Cost Breakdown

| Model | Input | Output | Total | Accuracy | Cost/Correct |
|-------|-------|--------|-------|----------|--------------|
| Nova-lite | $0.0001 | $0.0001 | $0.0002 | 90% | $0.0002 |
| Llama-3-1-70B | $0.0005 | $0.0005 | $0.0010 | 80% | $0.0013 |
| Nova-pro | $0.0013 | $0.0013 | $0.0026 | 90% | $0.0029 |
| Haiku-fast | $0.0040 | $0.0041 | $0.0081 | 90% | $0.0090 |
| Haiku-thinking | $0.0080 | $0.0094 | $0.0174 | 90% | $0.0194 |
| Sonnet-fast | $0.0202 | $0.0201 | $0.0403 | 90% | $0.0448 |
| Sonnet-thinking | $0.0383 | $0.0383 | $0.0766 | 90% | $0.0851 |
| Opus-fast | $0.0806 | $0.0807 | $0.1613 | 90% | $0.1792 |
| Opus-thinking | $0.1104 | $0.1105 | $0.2209 | 87.5% | $0.2524 |

**Ensemble overhead:**
- Vote aggregation: +6-32% (judge model calls)
- Stitch synthesis: +15-45% (orchestrator + analysis)

### Why Thinking Mode Costs More

Extended thinking generates 2-3x more output tokens:
- Opus-thinking: 2.7x more output than Opus-fast
- Sonnet-thinking: 2.1x more output than Sonnet-fast  
- Haiku-thinking: 2.5x more output than Haiku-fast

Those extra tokens are reasoning traces. They cost money. They don't improve accuracy.

---

## What We Got Wrong

### Assumption 1: Expensive Models Are Better
**Reality**: Nova-lite (cheapest) matched Opus-fast (most expensive) at 808x lower cost.

### Assumption 2: Extended Thinking Helps on Hard Prompts
**Reality**: Thinking mode provided zero accuracy improvement and introduced failures.

### Assumption 3: Ensembles Add Value When Models Diverge
**Reality**: 0/40 win rate even at 0% convergence (maximum divergence).

### Assumption 4: Reasoning Traces Indicate Quality
**Reality**: Opus-thinking generated longest reasoning traces (2-10K tokens) but had worst accuracy (87.5%).

### Assumption 5: You Need Claude for Quality
**Reality**: Nova-lite matched Claude Opus/Sonnet/Haiku on accuracy for 1/1000th the cost.

---

## Practical Recommendations

### ✅ DO Use These Models

1. **Nova-lite** (production default)
   - 90% accuracy on hard reasoning prompts
   - $0.0002 per correct answer
   - 4.6s average latency
   - Use unless you have specific reason not to

2. **Haiku-fast** (Claude requirement)
   - 90% accuracy
   - $0.009 per correct answer
   - If you need Claude specifically (brand, compliance, features)
   - Still 25x cheaper than Opus-fast

3. **Llama-3-1-70B** (budget option #2)
   - 80% accuracy (lower but acceptable for many tasks)
   - $0.0013 per correct answer
   - 6.5x cheaper than Haiku-fast

### ❌ DON'T Use These Approaches

1. **Extended Thinking Mode**
   - Zero accuracy benefit demonstrated
   - 48-150% cost premium
   - 2-3x slower (Opus-thinking: 3+ min before timeout)
   - 20% failure rate (Opus-thinking)

2. **Ensemble Aggregation**
   - 0/40 win rate across all experiments
   - 6-45% cost overhead
   - No value even when models diverge
   - Just use single best model

3. **Opus-thinking Specifically**
   - Worst accuracy: 87.5% (only model below 90%)
   - Worst value: $0.25/correct (1260x worse than Nova-lite)
   - Only model with failures (20% timeout rate)
   - No use case where this is optimal

---

## When You Might Deviate

### Consider Opus-fast (not Nova-lite) if:
- You need Claude-specific features (artifacts, tool use)
- Brand/compliance requires Anthropic models
- Your prompts are vastly different from this study
- Cost genuinely doesn't matter (rare)

### Consider re-testing thinking mode if:
- Your prompts require 10+ minutes of human reasoning time
- You have evidence thinking helps on your specific domain
- Current study isn't representative of your tasks

### Consider ensembles if:
- Regulatory/safety requires multi-model verification
- You have new evidence they help on your domain
- You're willing to pay 6-45% overhead for potential <5% gain

---

## Replication and Reproducibility

All data is public:

**Raw responses**:
- `results/hard_prompts/thinking/responses.json`
- `results/hard_prompts/fast/responses.json`
- `results/hard_prompts/comparison/responses.json`
- `results/hard_prompts/hybrid/responses.json`

**Aggregation results**:
- `*/vote_results.json` - Majority vote / semantic judge
- `*/stitch_results.json` - Synthesis aggregation

**Evaluation metrics**:
- `*/evaluation.json` - Accuracy, cost, latency per model

**Study parameters**:
- Date: April 3, 2026
- Duration: 71 minutes wall clock time
- Total API cost: $12.50
- Models: 10 unique (Claude Opus/Sonnet/Haiku thinking/fast, Llama, Nova, Nemotron)
- Prompts: 10 hard reasoning tasks (healthcare, game theory, concurrency, math)
- API calls: 240+ live Bedrock invocations
- Tokens: ~2.5M input, ~800K output

**Replication instructions**:
```bash
# Clone repo
cd ensemble-thinking-models

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install boto3 requests

# Configure AWS
export AWS_BEARER_TOKEN_BEDROCK=your_token

# Run full study (~70 min, ~$12.50)
bash scripts/run_hard_prompts_full_study.sh
```

---

## Limitations and Caveats

1. **Limited to 10 prompts**: Results may not generalize to all reasoning tasks
2. **Healthcare/technical focus**: Prompts emphasize medical and technical domains
3. **Single run per prompt**: No statistical significance testing across multiple runs
4. **AWS Bedrock only**: Doesn't test OpenAI GPT-4o, Google Gemini, etc.
5. **Claude's thinking implementation**: Results specific to Claude's extended thinking
6. **April 2026 models**: Future models may improve thinking mode performance

**What this study doesn't prove:**
- That thinking mode is useless for ALL tasks (only tested these 10)
- That ensembles are useless for ALL domains (only tested reasoning)
- That Nova-lite is always the best choice (domain-specific)

**What this study DOES prove:**
- For these 10 hard reasoning prompts, thinking mode added zero value
- For these 40 ensemble comparisons, ensembles added zero value
- Nova-lite can match premium models on some reasoning tasks

---

## The Bigger Picture

This study challenges three pieces of conventional wisdom:

1. **"Extended reasoning modes improve accuracy on complex tasks"**
   - Not demonstrated. Fast mode matched or beat thinking mode.

2. **"Ensembles beat individual models when models disagree"**
   - Not demonstrated. 0/40 win rate at all convergence levels.

3. **"You need expensive models for hard reasoning"**
   - Not demonstrated. Nova-lite matched Opus at 1/1000th cost.

These aren't small claims. They contradict marketing materials, pricing strategies, and common assumptions about LLM capabilities.

**The findings demand replication.** If you have access to different models, different prompts, or different domains: test the hypotheses. Challenge the results. Open source your data.

Science progresses by proving each other wrong.

---

## What's Next

**Part 2**: Mixture of Agents on Bedrock (coming soon)
- Multi-layer MoA architecture with real cost/latency data
- Whether layered ensembles improve on single-layer ensembles
- Spoiler: probably not, based on these results

**Part 3**: Same Model, Different Minds (coming soon)
- Using personas/temperatures to create diversity within single model
- Whether model-with-itself ensemble beats model-with-others
- May be cheaper way to get diversity if ensembles ever work

---

## Citation

If you use these findings in research or make decisions based on this work:

```
"Do Thinking Models Think Better? (No)"
Ensemble Thinking Models Experiment
April 2026

Key Findings:
• Extended thinking provided zero accuracy improvement (48-150% cost premium)
• Ensembles beat best individual 0/40 times (0% win rate)
• Nova-lite matched premium models at 1/1000th cost

Data: github.com/yourhandle/ensemble-thinking-models
```

---

## Acknowledgments

- Anthropic for Claude API access
- AWS for Bedrock platform and compute
- OpenAI for spurring the thinking models race
- Meta, Amazon, Nvidia for releasing competitive budget models
- Wang et al. (2023) for self-consistency baseline
- Jiang et al. (2023) for LLM-Blender methodology
- The research community for ensemble methods literature

Special thanks to everyone who argued that thinking models "obviously" help on hard prompts. You motivated the study that proved otherwise.

---

**For full analysis**: [FINDINGS.md](FINDINGS.md)  
**For executive summary**: [HARD_PROMPTS_FINAL_ANALYSIS.md](HARD_PROMPTS_FINAL_ANALYSIS.md)  
**For quick reference**: [README.md](README.md)

**Questions? Disagreements? Counter-evidence?**  
Open an issue. I'll replicate your findings if you share your prompts.

---

*This is part of the protoGen LLM Ensemble Methods series. Built with Python 3, AWS Bedrock, and a healthy skepticism of marketing claims.*

*"If the data contradicts the hypothesis, trust the data." - Every scientist ever*
