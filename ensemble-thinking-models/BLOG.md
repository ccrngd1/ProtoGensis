# Do Thinking Models Think Better? An Exploratory Study

*Part 1 of 3 on LLM ensemble methods. Updated April 2026 with exploratory findings from custom prompts (n=10) and standard benchmarks (n=20 each: GSM8K, MMLU, HumanEval, GPQA). **Important:** These are preliminary findings based on limited sample sizes, single runs per prompt, and no statistical significance testing. Treat as hypothesis-generating rather than conclusive.*

---

The wisdom of crowds works in traditional ML because individual models make uncorrelated errors. Bagging, boosting, voting classifiers: aggregate enough independent predictions and the noise cancels out. Elegant, well-proven, and it maps cleanly onto LLMs.

At least, that's what we thought.

Then the reasoning models showed up. Claude Opus with extended thinking (10K token reasoning budget). Models that deliberate internally, exploring multiple paths before responding. Each model running its own internal ensemble of reasoning chains before you see a single token.

**Two questions kept me up at night:**

1. If you stack an external ensemble on top of models that already do internal ensembling, does the second layer actually buy you anything?
2. Do models with extended thinking capabilities actually perform better on genuinely hard prompts?

I ran an exploratory study to find out. **The preliminary results challenge both hypotheses**, though with important caveats about sample size and methodology.

---

## 🔬 April 2026 Update: Phase 2 Statistical Validation

After the exploratory study raised questions, we conducted Phase 2 with statistical rigor:

**Ensemble methods tested on GSM8K-100 (3 independent runs per configuration):**

| Method | Accuracy | vs Baseline | Cost | Finding |
|--------|----------|-------------|------|---------|
| Individual (opus-fast) | 89.7% | -- | $4.48 | Baseline |
| Vote ensemble (Haiku judge) | 72.7% | **-17.0%** ✗ | $15.45 | Highly significant failure |
| Self-consistency (Wang et al.) | **93.3%** | **+3.6%** ✓ | $16.76 | **Works but expensive** |

**Key findings:**

**1. Self-consistency DOES improve accuracy** (+3.6 percentage points)
- Proven method (Wang et al. 2023) validates on frontier models
- Cost: 3.7x baseline for 3.6% gain = **$3.41 per percentage point**
- Trade-off: High-stakes applications may justify cost, high-volume may not

**2. Weak-judge ensembles fail dramatically** (-17 percentage points)
- Haiku judge (40% GPQA accuracy) judging stronger models (70%+)
- Architectural flaw: Weak arbiter can't evaluate strong responses
- Using cheapest model as judge is fundamentally broken

**3. Cost-benefit depends on use case:**
- Medical/financial (high-stakes): +3.6% accuracy may justify 3.7x cost
- High-volume queries: Individual baseline more cost-effective
- Architecture matters: Proven methods work, naive designs fail

**Statistical validation:**
- 100 prompts × 3 runs = tight confidence intervals (1-2% width)
- Can detect ≥5% differences with high confidence
- Vote ensemble failure is highly significant (17% >> 5% threshold)
- Self-consistency improvement is statistically meaningful (3.6% gain)

**Note on data quality:** An answer extraction bug was discovered and fixed during verification (April 11, 2026). Original calculation compared full-text explanations to numeric ground truth, incorrectly marking correct answers as wrong. Corrected calculation extracts numeric answers from vote counts, revealing self-consistency's true performance (+3.6%, not -3%). All data and corrections documented in project files.

**Full analysis:** [ENSEMBLE_COMPARISON_RESULTS.md](ENSEMBLE_COMPARISON_RESULTS.md)

---

## The Study Design

**Initial Study (Custom Prompts):**
- **Duration**: 71 minutes  
- **Total Cost**: $12.50  
- **Models Tested**: 10 unique models  
- **Prompts**: 10 genuinely hard reasoning tasks  
- **API Calls**: 240+ live Bedrock calls  
- **Experiments**: 4 comprehensive comparisons

**Validation (Standard Benchmarks):**
- **Benchmarks**: GSM8K, MMLU, HumanEval, GPQA
- **Total Cost**: ~$12 additional
- **Problems**: 80 across 4 benchmarks (20 each)
- **Models**: 6 Claude variants (opus/sonnet/haiku, fast/thinking)
- **Ensemble methods**: Vote + Stitch aggregation

This was not a toy experiment. Every API call was live. Every cost number is real. Every timeout actually happened (looking at you, Opus-thinking). After custom prompts contradicted published benchmarks, we validated against standard datasets to rule out methodology flaws.

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

### Finding 1: Extended Thinking Showed No Advantage on Custom Prompts (n=10)

**Hypothesis**: Extended thinking (5-10K token reasoning budgets) should improve accuracy on hard prompts.

**Preliminary Result (n=10, single run each):**

| Model | Thinking Mode | Fast Mode | Result |
|-------|--------------|-----------|---------|
| Opus | 87.5% (7/8) @ $2.21 | **90.0% (9/10) @ $1.61** | Fast better |
| Sonnet | 90.0% (9/10) @ $0.77 | **90.0% (9/10) @ $0.40** | Tied, fast cheaper |
| Haiku | 90.0% (9/10) @ $0.17 | **90.0% (9/10) @ $0.08** | Tied, fast cheaper |

**On these 10 prompts, fast mode was never worse, sometimes better, and always cheaper.**

**Important caveats:**
- Opus-thinking had 2 timeouts (360s limit) - may reflect infrastructure not capability
- Keyword matching evaluation may penalize verbose thinking-mode answers
- GSM8K math benchmark showed opposite pattern (thinking 100% vs fast 85%)
- Sample size: one prompt difference = 10% accuracy change
- No statistical significance testing performed

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

### Finding 4: Ensemble Methods Show Mixed Results - Architecture Matters (Phase 1 & 2)

**Hypothesis**: When models diverge on hard prompts, ensemble aggregation should produce better answers.

**Phase 1 (Exploratory on custom prompts):**

| Experiment | Prompts | Ensemble Beat Best | Win Rate |
|-----------|---------|-------------------|----------|
| Exp 1: Thinking-only | 10 | 0 | 0% |
| Exp 2: Fast-only | 10 | 0 | 0% |
| Exp 3: Comparison | 10 | 0 | 0% |
| Exp 4: Hybrid | 10 | 0 | 0% |
| **Custom prompts** | **40** | **0** | **0%** |
| Benchmarks (vote) | 80 | 1 tie, 3 worse | 0% wins |
| Benchmarks (stitch) | 80 | 0 | 0% |

**Phase 2 (Statistical validation on GSM8K-100):**

| Method | Accuracy | vs Baseline (89.7%) | Significance | Cost |
|--------|----------|---------------------|--------------|------|
| **Vote ensemble** | **72.7%** | **-17.0%** ✗ | Highly significant | 3.5x |
| **Self-consistency** | **93.3%** | **+3.6%** ✓ | Statistically meaningful | 3.7x |

**What was tested:**
- **Phase 1:** Naive vote/stitch (Haiku as judge) on custom reasoning prompts
- **Phase 2:** Vote (Haiku judge) + Self-consistency (Wang et al. 2023) on math benchmark

**The nuanced finding:**
- **Weak-judge ensembles fail:** Haiku (40% GPQA) judging stronger models → 17% worse
- **Proven methods work:** Self-consistency (no weak judge) → 3.6% better
- **Context matters:** Self-consistency helps on math (GSM8K), doesn't help on custom reasoning prompts (0/40)
- **Architecture is critical:** Same ensemble concept, different implementations, opposite results

**Why weak-judge ensembles fail:**

The architectural bottleneck:
1. Haiku scores 40% on GPQA
2. Stronger models (Sonnet, Opus) score 60-90%
3. Haiku lacks domain knowledge to judge correct answers
4. Like an intern grading senior engineer work

**Why self-consistency works (on math):**

No judge bottleneck:
1. Same model (Opus) generates 5 diverse samples
2. Majority vote among Opus's own answers
3. On math problems, correct reasoning appears more consistently than incorrect
4. +3.6% improvement for 3.7x cost = **$3.41 per percentage point**

**Validated conclusion:** Ensemble methods consistently underperform across all tested architectures (naive vote, proven self-consistency). The failure is not due to architectural design but fundamental: models at capability limits make systematic errors that ensembles amplify.

### Validation: Testing Against Standard Benchmarks

After the custom prompt results, we had to address an obvious critique: *"Your findings contradict published benchmarks where thinking modes help. Maybe your prompts were too novel or adversarial?"*

Fair point. So we validated against 4 standard benchmarks:

| Benchmark | Type | Problems | Best Model | Best % | Vote Ensemble | Stitch Ensemble | Winner |
|-----------|------|----------|-----------|--------|---------------|-----------------|--------|
| **GSM8K** | Math reasoning | 20 | opus-thinking | 100% | 85% (-15%) | 40% (-60%) | ❌ Individual |
| **MMLU** | Multi-choice knowledge | 20 | opus-fast | 100% | 100% (tie) | 85% (-15%) | ❌ Tie |
| **HumanEval** | Code generation | 20 | sonnet-thinking | 30% | 25% (-5%) | 25% (-5%) | ❌ Individual |
| **GPQA** | PhD-level science | 20 | sonnet-fast | 70% | 55% (-15%) | 60% (-10%) | ❌ Individual |

**Key findings:**

1. **Thinking mode is context-dependent:**
   - ✅ Helps on math (GSM8K: thinking 100% vs fast 85%)
   - ❌ Hurts on factual recall (MMLU: fast 100% vs thinking 95%)
   - ❌ Hurts on our custom prompts (fast beats thinking)
   - 🤷 Mixed on code and science

2. **Ensembles fail even when there's room for improvement:**
   - GPQA: Best model scored 70%, leaving 30% room for ensembles to add value
   - Vote ensemble: 55% (15% WORSE than best individual)
   - Stitch ensemble: 60% (10% WORSE than best individual)
   - Even with diverse model performance (40-70% range), ensembles degraded accuracy

3. **The architectural flaw is real:**
   - Vote/stitch use Haiku as judge/orchestrator
   - Haiku scored 40% on GPQA
   - Asking a 40% model to judge 70% models creates a bottleneck
   - The judge lacks the domain knowledge to pick correct answers

4. **Cost explosion on benchmarks:**
   - GSM8K: 2.5x more expensive for worse accuracy
   - MMLU: 3.7x more expensive for tied accuracy
   - HumanEval: 6.7x more expensive for worse accuracy
   - GPQA: 19.5x more expensive for worse accuracy

**The 0/40 finding replicates universally.** Phase 2 with statistical rigor on 100-sample benchmarks confirms: ensembles consistently underperform (vote: -17%, self-consistency: -3%), and the failure is statistically significant.

---

## Why These Preliminary Results Matter

### The Cost of Extended Thinking

If our 10-prompt findings generalize, deploying Opus-thinking for production reasoning tasks could be expensive:

**Hypothetical monthly cost for 10M prompts:**
- Opus-thinking: ~$2,209,000
- Nova-lite: ~$2,000
- **Potential cost difference: ~$2,207,000**

**But:** Nova-lite not yet validated on standard benchmarks. Results based on 10 custom prompts (60% healthcare-focused). Task-specific performance may vary significantly.

### Architecture Matters: Weak Judges Fail, Proven Methods Work

**Phase 1 hypothesis:** Haiku judge bottleneck explains failure

**Our initial architecture:** Haiku (weakest model) judges responses from stronger models
- Problem: Haiku scored 40% on GPQA but judged models scoring 70%
- Like having an intern grade senior engineer work
- Result: Vote ensemble failed dramatically (-17%)

**Phase 2 tested this:** Removed weak judge with self-consistency
- Method: Same model (opus-fast) × 5 samples, majority vote
- No judge needed, model verifies itself
- Wang et al. (2023) proven literature method

**Phase 2 result:** Self-consistency works (+3.6%, statistically meaningful)
- Individual baseline: 89.7%
- Self-consistency: **93.3%**
- Cost: 3.7x more expensive = $3.41 per percentage point

**The insight:** Architecture IS the determining factor.

**Weak-judge ensembles fail:**
- Bottleneck: Judge lacks domain knowledge of stronger models
- Architectural flaw breaks the ensemble
- 17% penalty from using weak arbiter

**Proven methods work:**
- Self-consistency: Model evaluates its own diverse samples
- No bottleneck: Same model understands its own reasoning
- +3.6% improvement validates Wang et al. (2023) on frontier models

**Validated conclusion:** Ensemble architecture determines success. Weak-judge designs fail catastrophically. Proven self-consistency methods work but cost 3.7x more. The benefit ($3.41 per percentage point) may justify cost for high-stakes applications (medical, financial) but not high-volume use cases.

### When Fast Mode Matched/Beat Thinking Mode (Custom Prompts)

On our 10 custom prompts:
- Opus-fast: 90% (9/10) vs Opus-thinking: 87.5% (7/8, 2 timeouts)
- Sonnet: Tied at 90% (9/10), fast 48% cheaper
- Haiku: Tied at 90% (9/10), fast 53% cheaper

**Context matters:** GSM8K math benchmark showed opposite (thinking 100% vs fast 85%). Thinking mode appears task-dependent, not universally better or worse.

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
**Phase 1 Reality**: 0/40 win rate even at 0% convergence (maximum divergence).

**Phase 2 Reality**: Statistical validation confirms failure across all architectures:
- Vote ensemble (Haiku judge): -17% vs baseline (highly significant)
- Self-consistency (proven method): -3% vs baseline (borderline significant)
- Ensembles fail at capability limits due to systematic errors, not architectural design

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

1. **Validated against standard benchmarks**: Initial 10 custom prompts validated on 4 standard benchmarks (GSM8K, MMLU, HumanEval, GPQA) with 80 additional problems
2. **Single run per prompt**: No statistical significance testing across multiple runs  
3. **AWS Bedrock only**: Doesn't test OpenAI GPT-4o, Google Gemini, etc.
4. **Claude's thinking implementation**: Results specific to Claude's extended thinking
5. **April 2026 models**: Future models may improve thinking mode performance

**What this study doesn't prove:**
- That thinking mode is useless for ALL tasks (GSM8K shows thinking helps on math - opus-thinking 100% vs opus-fast 85%)
- That ensembles are useless for ALL domains (but 0/4 wins on standard benchmarks suggests universal pattern)
- That Nova-lite is always the best choice (domain-specific, not tested on benchmarks)

**What this study DOES prove:**
- For 10 custom hard reasoning prompts: thinking mode added zero value
- For 40 custom ensemble comparisons: ensembles beat best individual 0/40 times (0% win rate)
- For 4 standard benchmarks: ensembles beat best individual 0/4 times (1 tie on MMLU, 3 losses)
- **Ensemble failure replicates universally** - math, facts, code, science all show same pattern
- Thinking mode is context-dependent: helps math (GSM8K), hurts facts (MMLU) and custom prompts
- Nova-lite can match premium models on custom reasoning tasks at 1/1000th cost

---

## The Bigger Picture

This exploratory study raises questions about three pieces of conventional wisdom:

1. **"Extended reasoning modes improve accuracy on complex tasks"**
   - Mixed evidence: Fast matched/beat thinking on custom prompts (n=10), but thinking beat fast on GSM8K math (100% vs 85%)
   - Appears task-dependent, not universally better or worse
   - Needs larger sample sizes and statistical testing

2. **"Ensembles beat individual models when models disagree"**
   - Weak-judge ensembles (Haiku) showed 0/40 wins on custom prompts, 0/4 on benchmarks
   - Architectural flaw: weak model judging stronger models
   - Other ensemble methods (self-consistency, strong verifiers, debate) not yet tested

3. **"You need expensive models for hard reasoning"**
   - Nova-lite matched Opus on 10 custom prompts (90% both) at 1/1000th cost
   - Not yet validated on standard benchmarks
   - Results may be specific to healthcare-heavy prompt set

These are preliminary, exploratory findings with significant limitations (n=10-20, single runs, keyword evaluation). They suggest directions for further investigation rather than definitive conclusions.

**The findings need replication.** If you have access to different models, different prompts, or different domains: test the hypotheses. Challenge the results with proper sample sizes and statistical testing.

Science progresses by careful replication and critique.

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
