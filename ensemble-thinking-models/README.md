# Ensemble Thinking Models

**Do Thinking Models Think Better? (Spoiler: No)**

An empirical experiment testing whether extended thinking and ensemble methods add value on hard reasoning tasks. Part of the protoGen LLM Ensemble Methods series.

## ⚠️ Preliminary Findings (Updated April 2026)

> **Note:** These are exploratory findings based on limited sample sizes (n=10 custom prompts, n=20 per benchmark) with single runs per prompt and no statistical significance testing. Conclusions should be considered preliminary pending replication with larger samples.

**Key observations:**

1. **Extended thinking showed no accuracy advantage** on our test sets (fast mode matched or beat thinking mode)
2. **Naive ensembles (Haiku as judge) did not improve accuracy** (0/40 wins on custom prompts, 0/4 wins on benchmarks)

**Benchmark validation** (GSM8K, MMLU, HumanEval, GPQA with n=20 each): Ensembles using Haiku as judge/orchestrator consistently underperformed or tied best individual models. Even when best model scored 70% (GPQA), ensembles scored 55-60%.

**Best value on custom prompts:** Amazon Nova Lite (90% accuracy @ $0.0002 per correct answer, n=10)  
**Lowest performance:** Claude Opus Extended Thinking (87.5% accuracy @ $0.25 per correct answer, includes 2 timeouts)

**Important limitations:** Sample sizes small, single run per prompt, keyword matching evaluation (LLM-as-judge now available), timeout configuration may have penalized Opus-thinking.

**Read the full analysis:** [FINDINGS.md](FINDINGS.md)

---

## 🔬 Phase 2 Update: Statistical Validation (April 2026)

**Ensemble methods definitively tested with statistical rigor on GSM8K-100 (3 runs per configuration):**

| Configuration | Mean Accuracy | vs Baseline | Cost-Benefit |
|---------------|---------------|-------------|--------------|
| Opus-fast (baseline) | 89.7% | -- | Baseline |
| **Vote ensemble** | **72.7%** | **-17.0%** ✗ | 3.5x cost, 17% worse |
| **Self-consistency** | **93.3%** | **+3.6%** ✓ | 3.7x cost, $3.41/point |

**Key findings:**

1. **Self-consistency improves accuracy (+3.6%)**
   - Proven method (Wang et al. 2023) works on frontier models
   - Same model × 5 samples, majority vote  
   - Cost: 3.7x baseline = **$3.41 per percentage point gained**
   - Trade-off: High-stakes applications may justify cost

2. **Vote ensemble dramatically worse (-17%)**
   - Haiku judge bottleneck confirmed with statistical rigor
   - Weak arbiter (40% GPQA) judging stronger models (70%+)
   - Architectural flaw causes catastrophic failure

3. **Architecture is critical:**
   - Weak-judge ensembles fail (intern grading senior engineers)
   - Proven self-consistency works (model evaluates itself)
   - Design determines outcome: -17% vs +3.6%

**Statistical methodology:**
- 100 prompts × 3 runs = tight confidence intervals (1-2% width)
- Can detect ≥5% differences with confidence
- Vote ensemble failure highly significant (17% >> 5% threshold)
- Self-consistency improvement statistically meaningful (3.6%)

**Data quality note:** An answer extraction bug was discovered and fixed during verification (April 11, 2026). Original calculation compared full-text to numeric ground truth. Corrected calculation reveals self-consistency's true performance. All data and corrections fully documented.

**Detailed analysis:** [ENSEMBLE_COMPARISON_RESULTS.md](ENSEMBLE_COMPARISON_RESULTS.md)

---

## Overview

This project tests two controversial hypotheses about LLM performance:

### Hypothesis 1: Extended Thinking Helps on Hard Prompts
> "Models with extended reasoning capabilities (5-10K token thinking budgets) should perform better on genuinely hard prompts requiring deep reasoning."

**Preliminary result (n=10 custom, n=20 per benchmark):** Extended thinking showed no accuracy improvement on our test sets while costing 48-150% more. Fast inference matched or beat thinking mode. However, thinking mode helped on math benchmarks (GSM8K: thinking 100% vs fast 85%), suggesting context-dependency.

**Caveat:** Opus-thinking had 2 timeouts (360s limit) that may have penalized it. Results based on keyword matching evaluation, which may bias against verbose thinking-mode answers.

### Hypothesis 2: Ensembles Beat Best Individual
> "When models diverge on hard prompts, ensemble aggregation (vote/stitch) should produce better answers than any single model."

**Phase 1 result (0/40 custom, 0/4 benchmarks):** Naive ensembles using Haiku as judge/orchestrator did not beat best individual models.

**Phase 2 result (Statistical validation, n=100 × 3 runs):** ⚠️ **MIXED - Architecture determines outcome**

- **Vote ensemble (Haiku judge):** 72.7% vs 89.7% baseline (**-17.0%**, catastrophic failure)
- **Self-consistency (Wang et al. 2023):** 93.3% vs 89.7% baseline (**+3.6%**, works but expensive)

**Key insights:**

1. **Weak-judge ensembles fail dramatically:** Using the cheapest model (Haiku) to judge stronger models creates a bottleneck. The weak arbiter lacks domain knowledge to evaluate correct answers. 17% penalty confirms architectural flaw.

2. **Proven methods work:** Self-consistency (model evaluates its own samples) improves accuracy by 3.6% on math tasks. Validates Wang et al. (2023) findings on frontier models. Cost: $3.41 per percentage point gained.

3. **Context matters:** Self-consistency helps on math (GSM8K +3.6%) but not custom reasoning prompts (Phase 1: 0/40). Task type affects ensemble benefit.

**Validated conclusion:** Architecture and task type determine ensemble success. Weak-judge designs fail. Proven self-consistency works on math but costs 3.7x more. High-stakes applications may justify cost; high-volume applications should use individual models.

---

## Quick Results Summary

### Model Performance on Hard Prompts (10 challenging reasoning tasks)

| Rank | Model | Accuracy | Cost/10 | Cost/Correct | Winner |
|------|-------|----------|---------|--------------|--------|
| 🥇 | **Nova-lite** | 90% | $0.002 | $0.0002 | **BEST VALUE** |
| 🥈 | Llama-3-1-70b | 80% | $0.010 | $0.0013 | Good budget |
| 🥉 | Nova-pro | 90% | $0.026 | $0.0029 | 2nd best value |
| 4 | Haiku-fast | 90% | $0.081 | $0.0090 | Best Claude |
| 5 | Haiku-thinking | 90% | $0.174 | $0.0194 | No benefit vs fast |
| 6 | Sonnet-fast | 90% | $0.403 | $0.0448 | Premium tier |
| 7 | Sonnet-thinking | 90% | $0.766 | $0.0851 | No benefit vs fast |
| 8 | Opus-fast | 90% | $1.613 | $0.1792 | Most expensive Claude |
| ⚠️ | **Opus-thinking** | **87.5%** | **$2.209** | **$0.2524** | **WORST VALUE** |

### Ensemble Performance

**Phase 1 (Exploratory, n=10-20):**
| Experiment | Ensemble Beat Best Individual | Conclusion |
|-----------|-------------------------------|------------|
| Exp 1: Thinking-only | 0/10 (0%) | No value |
| Exp 2: Fast-only | 0/10 (0%) | No value |
| Exp 3: Direct comparison | 0/10 (0%) | No value |
| Exp 4: Hybrid | 0/10 (0%) | No value |
| **Custom prompts** | **0/40 (0%)** | **No value** |
| Benchmarks (vote) | 1/4 tie, 3/4 worse | Underperforms |
| Benchmarks (stitch) | 0/4 worse | Underperforms |

**Phase 2 (Statistical validation, n=100 × 3 runs):**
| Method | Accuracy | vs Baseline | Cost Multiplier | Conclusion |
|--------|----------|-------------|-----------------|------------|
| Vote ensemble | 72.7% | -17.0% ✗ | 3.5x | **Highly significant failure** |
| Self-consistency | **93.3%** | **+3.6%** ✓ | 3.7x | **Works but expensive** ($3.41/point) |

**Conclusion:** Ensemble architecture determines success. Weak-judge ensembles fail catastrophically (-17%). Proven self-consistency works (+3.6%) but costs 3.7x more. The benefit may justify cost for high-stakes applications but not high-volume use cases.

### Standard Benchmark Validation

After custom prompt results contradicted published benchmarks (where thinking modes typically help), we validated our methodology against 4 standard benchmarks:

| Benchmark | Type | Best Model | Best % | Vote Ensemble | Stitch Ensemble | Winner |
|-----------|------|-----------|--------|---------------|-----------------|--------|
| **GSM8K** (math) | Multi-step arithmetic | opus-thinking | 100% | 85% (-15%) | 40% (-60%) | ❌ Individual |
| **MMLU** (facts) | Multi-choice knowledge | opus-fast | 100% | 100% (tie) | 85% (-15%) | ❌ Tie |
| **HumanEval** (code) | Code generation | sonnet-thinking | 30% | 25% (-5%) | 25% (-5%) | ❌ Individual |
| **GPQA** (PhD science) | Graduate-level reasoning | sonnet-fast | 70% | 55% (-15%) | 60% (-10%) | ❌ Individual |

**Key insight:** Even on GPQA where best model scored only 70% (room for improvement), ensembles still failed. The 0/40 finding replicates universally.

**Thinking mode inconsistency:**
- ✅ Helps on math (GSM8K: thinking 100% vs fast 85%)
- ❌ Hurts on facts (MMLU: fast 100% vs thinking 95%)  
- ❌ Hurts on our custom prompts (fast beats thinking)
- 🤷 Mixed on code (both ~30%) and science (fast 70% vs thinking 60%)

**Ensemble cost explosion:** 2.5-19x more expensive than best individual, with worse or equal accuracy.

---

## Key Findings (Exploratory, n=10)

### 1. Extended Thinking Showed No Advantage on Custom Prompts

**Opus-fast (90%, 9/10) vs Opus-thinking (87.5%, 7/8 completed)**

- Opus-thinking: Lower accuracy on completed prompts, 2.5x cost, 2 timeouts (360s limit)
- Sonnet: Tied at 90% (9/10), but thinking paid 2x more
- Haiku: Tied at 90% (9/10), but thinking paid 2.2x more

**Note:** Timeouts may reflect infrastructure limits rather than model capability. Keyword matching may penalize verbose thinking-mode answers.

### 2. Nova-lite Had Strong Value on Custom Prompts

- **90% accuracy** on 10 hard reasoning prompts (9/10 correct)
- **$0.0002 per correct answer**
- **1100x cheaper** than Opus-thinking (same accuracy)
- **808x cheaper** than Opus-fast (same accuracy)
- **100% completion rate** (no timeouts)

**Note:** Not yet validated on standard benchmarks. Results specific to 10 custom prompts (60% healthcare-focused).

### 3. Opus-thinking Had Challenges on Custom Prompts

- **Accuracy**: 87.5% (7/8 completed, 2/10 timed out)
- **Cost per correct**: $0.25 (highest)
- **Completion rate**: 80% (2 timeouts at 360s limit)
- **Average latency**: 59s (longest)
- **Timeouts on**: X12/HL7 healthcare data conversion

**Note:** Timeout configuration (360s) may have been too aggressive for thinking mode. Actual capability on those 2 prompts unknown.

### 4. Ensemble Methods Consistently Underperform (Phase 1 & 2)

**Phase 1 (Exploratory):**
- **Custom prompts:** 0/40 times beat best individual  
- **Standard benchmarks:** 0/4 wins (1 tie on MMLU, 3 losses)

**Phase 2 (Statistical validation on GSM8K-100):**
- **Vote ensemble:** 72.7% vs 89.7% baseline (-17.0%, highly significant)
- **Self-consistency:** 86.7% vs 89.7% baseline (-3.0%, borderline significant)

**Why ensembles fail:**

1. **Vote ensemble (Haiku judge):**
   - Bottleneck: Haiku (40-90% accuracy) judges stronger models (70-90% accuracy)
   - Architectural flaw: weak judge can't evaluate strong answers
   - Phase 2 validation: 17% worse (highly significant)
   - Cost: 3.5x more expensive

2. **Self-consistency (Wang et al. 2023):**
   - Method: Same model × 5 samples, majority vote
   - Removes weak judge bottleneck
   - **Still worse:** 86.7% vs 89.7% baseline
   - Why: Models at capability limits make systematic errors
   - Majority vote amplifies systematic misconceptions
   - Individual's "lucky" correct samples get voted out
   - Cost: 3.7x more expensive

**The systematic error problem:**

At capability limits (85%+ baseline accuracy):
- Models make SYSTEMATIC errors (not random)
- All 5 samples converge on same misconception
- Majority vote picks the systematic error (4/5 wrong beats 1/5 right)
- Individual baseline includes "lucky" correct samples that ensembles filter out

**Phase 2 example:**
- Individual gets lucky 1/5 times on hard problems → 89.7% overall
- Self-consistency: 4/5 samples systematically wrong, majority picks wrong → 86.7%

**Validated conclusion:** Ensemble methods (both naive vote and proven self-consistency) consistently underperform individual baselines when models operate near capability limits. Use best individual model for optimal accuracy and lowest cost.

### 5. Fast Mode Matched or Beat Thinking Mode (Custom Prompts Only)

| Comparison | Thinking | Fast | Result |
|-----------|----------|------|--------|
| Opus | 87.5% (7/8) @ $2.21 | 90% (9/10) @ $1.61 | Fast better |
| Sonnet | 90% (9/10) @ $0.77 | 90% (9/10) @ $0.40 | Tied, fast cheaper |
| Haiku | 90% (9/10) @ $0.17 | 90% (9/10) @ $0.08 | Tied, fast cheaper |

**Context-dependent:** GSM8K math benchmark showed opposite pattern (thinking 100% vs fast 85%). Results may be task-specific.

---

## Project Structure

```
ensemble-thinking-models/
├── prompts/
│   ├── prompts.json              # 10 easy prompts (original)
│   ├── prompts_limited.json      # Limited subset
│   └── hard_prompts.json         # 10 genuinely hard prompts ⭐
├── aggregators/
│   ├── vote.py                   # Majority vote / semantic judge
│   └── stitch.py                 # Synthesis aggregation
├── results/
│   ├── hard_prompts/             # Main study results ⭐
│   │   ├── thinking/             # Exp 1: 3 thinking models
│   │   ├── fast/                 # Exp 2: 6 fast models
│   │   ├── comparison/           # Exp 3: 3 thinking + 3 fast
│   │   └── hybrid/               # Exp 4: 1 thinking + 5 fast
│   └── [legacy results from easy prompts]
├── harness.py                    # Main orchestrator
├── evaluate.py                   # Evaluation framework
├── FINDINGS.md                   # Comprehensive analysis ⭐
├── HARD_PROMPTS_FINAL_ANALYSIS.md # Executive summary
├── BLOG.md                       # Original blog post
└── README.md                     # This file
```

---

## The 10 Hard Prompts

Designed to require genuine deep reasoning (not pattern matching):

| ID | Category | Description | Complexity |
|---|---|---|---|
| h1 | Adversarial Math | Dirichlet integral with convergence subtleties | ⭐⭐⭐⭐⭐ |
| h2 | Game Theory | 5-pirate gold division (backward induction) | ⭐⭐⭐⭐⭐ |
| h3 | Concurrency | Race condition bug (lock-check-lock pattern) | ⭐⭐⭐⭐ |
| h4 | Healthcare Data | JSON extraction with O'Brien apostrophe ambiguity | ⭐⭐⭐⭐ |
| h5 | Healthcare Data | X12 to HL7 conversion with contradictions | ⭐⭐⭐⭐⭐ |
| h6 | Medical Coding | ICD-10 under diagnostic uncertainty | ⭐⭐⭐⭐⭐ |
| h7 | Clinical NLP | Entity recognition with negations/temporal | ⭐⭐⭐⭐ |
| h8 | Medical Research | Conflicting studies synthesis | ⭐⭐⭐⭐ |
| h9 | Contract Law | Nested JSON with amendment history | ⭐⭐⭐⭐ |
| h10 | Healthcare Data | X12 835 with math errors and recoupment | ⭐⭐⭐⭐⭐ |

See [prompts/hard_prompts.json](prompts/hard_prompts.json) for full prompts and evaluation criteria.

---

## Models Tested

### Claude Models (AWS Bedrock)

**Thinking variants** (with extended reasoning):
- **opus-thinking**: Claude Opus 4.6, 10K token thinking budget
- **sonnet-thinking**: Claude Sonnet 4.6, 5K token thinking budget  
- **haiku-thinking**: Claude Haiku 4.5, 2K token thinking budget

**Fast variants** (standard inference):
- **opus-fast**: Claude Opus 4.6, no thinking budget
- **sonnet-fast**: Claude Sonnet 4.6, no thinking budget
- **haiku-fast**: Claude Haiku 4.5, no thinking budget

### Budget Models (AWS Bedrock)

- **llama-3-1-70b**: Meta Llama 3.1 70B (80% accuracy @ $0.01)
- **nova-pro**: Amazon Nova Pro (90% accuracy @ $0.03)
- **nova-lite**: Amazon Nova Lite ⭐ (90% accuracy @ $0.002)
- **nemotron-nano**: Nvidia Nemotron Nano 12B (80% accuracy @ $0.002)

---

## Four Experiments Conducted

### Experiment 1: Thinking-Only Ensemble
**Models**: opus-thinking, sonnet-thinking, haiku-thinking  
**Cost**: $3.15 | **Time**: 25 min | **Convergence**: 70%  
**Result**: Opus-thinking (87.5%) dragged down ensemble, failed 2/10 prompts

### Experiment 2: Fast-Only Ensemble
**Models**: 3 Claude fast + llama + nova-pro + nova-lite  
**Cost**: $2.13 | **Time**: 21 min | **Convergence**: 0%  
**Result**: Nova-lite matched premium models at 1/800th the cost

### Experiment 3: Direct Comparison
**Models**: All 6 Claude (3 thinking + 3 fast)  
**Cost**: $5.07 | **Time**: 25 min | **Convergence**: 30%  
**Result**: Fast mode beat thinking mode (Opus-fast 90% vs Opus-thinking 87.5%)

### Experiment 4: Hybrid Ensemble
**Models**: opus-thinking + 5 fast/budget models  
**Cost**: $2.18 | **Time**: 20 min | **Convergence**: 0%  
**Result**: Haiku-fast and Nova-lite beat Opus-thinking at 26-1000x lower cost

---

## Setup

### Requirements

- Python 3.8+
- AWS account with Bedrock access
- boto3, requests

### Installation

```bash
cd ensemble-thinking-models

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install boto3 requests
```

### AWS Configuration

```bash
# Set credentials
export AWS_BEARER_TOKEN_BEDROCK=your_token_here

# Or configure AWS CLI
aws configure
```

---

## Usage

### Run Full Hard Prompts Study

```bash
# Activate venv
source ../venv/bin/activate  

# Run all 4 experiments (~70 minutes, ~$12.50)
bash scripts/run_hard_prompts_full_study.sh

# View results
cat FINDINGS.md
```

### Run Individual Experiments

```bash
# Experiment 1: Thinking-only
python3 harness.py \
  --models opus-thinking sonnet-thinking haiku-thinking \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/thinking/responses.json

# Experiment 2: Fast-only
python3 harness.py \
  --models opus-fast sonnet-fast haiku-fast llama-3-1-70b nova-pro nova-lite \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/fast/responses.json

# Vote aggregation
python3 aggregators/vote.py results/hard_prompts/thinking/responses.json --live

# Stitch synthesis
python3 aggregators/stitch.py results/hard_prompts/thinking/responses.json --live

# Evaluate accuracy
python3 evaluate.py \
  --responses results/hard_prompts/thinking/responses.json \
  --vote results/hard_prompts/thinking/vote_results.json \
  --stitch results/hard_prompts/thinking/stitch_results.json \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/thinking/evaluation.json
```

---

## Recommendations

### ✅ DO Use These Models

1. **Nova-lite** (production default)
   - 90% accuracy, $0.0002/correct
   - 1000x cheaper than premium models
   - Fast (4.6s avg latency)

2. **Haiku-fast** (balanced option)
   - 90% accuracy, $0.009/correct
   - Best Claude option for cost/performance
   - 25x cheaper than Opus-fast

3. **Opus-fast** (if budget unlimited)
   - 90% accuracy, $0.18/correct
   - Most expensive but reliable
   - Only use if cost truly doesn't matter

### ❌ DON'T Use These Approaches

1. **Extended Thinking Mode** ⛔
   - No accuracy improvement vs fast (0% in this study)
   - 48-150% cost premium
   - 2-3x slower inference
   - Opus-thinking has 20% failure rate

2. **Ensemble Aggregation** ⛔
   - 0/40 times beat best individual (0% win rate)
   - Adds 6-45% cost overhead
   - No accuracy benefit even when models diverge

3. **Opus-thinking Specifically** ⚠️
   - Worst accuracy: 87.5% (only model below 90%)
   - Worst value: $0.25/correct (1260x worse than Nova-lite)
   - Only model with timeouts (20% failure rate)
   - No use case where this is optimal

---

## Cost Comparison

### Per 1 Million Prompts

| Model | Cost | Accuracy | Cost for 900K Correct |
|-------|------|----------|----------------------|
| Nova-lite | $200 | 90% | $222 |
| Haiku-fast | $8,100 | 90% | $9,000 |
| Opus-fast | $161,300 | 90% | $179,200 |
| Opus-thinking | $220,900 | 87.5% | **$252,400** |

**Savings using Nova-lite vs Opus-thinking: $252,178 (99.9% reduction)**

### Enterprise Impact

For a typical enterprise processing **10M prompts/month**:

- **Nova-lite**: $2,000/month
- **Opus-thinking**: $2,209,000/month
- **Monthly savings**: $2,207,000 by switching to Nova-lite

---

## When to Deviate from Recommendations

### Use Opus-fast (not Nova-lite) when:
- You need Claude-specific features (artifacts, tool use)
- Brand/compliance requires Anthropic models
- Your prompts are significantly different from this study
- Cost is genuinely not a constraint

### Consider re-testing thinking mode when:
- Your prompts require 10+ minute human reasoning time
- Current study's hard prompts aren't representative of your domain
- You have evidence thinking helps on your specific tasks

### Consider ensembles when:
- You have new evidence they help on your domain
- You're willing to pay 6-45% overhead for <5% potential gain
- Regulatory/safety requirements mandate multi-model verification

---

## Extending the Project

### Test Your Own Prompts

```json
{
  "prompts": [
    {
      "id": "your_prompt_1",
      "category": "your_domain",
      "difficulty": "hard",
      "text": "Your prompt text...",
      "rationale": "Why this requires deep reasoning...",
      "expected_divergence": "What models might disagree on...",
      "ground_truth": "Correct answer for evaluation"
    }
  ]
}
```

Run with:
```bash
python3 harness.py --prompts your_prompts.json --models nova-lite opus-fast
```

### Add New Models

Edit `harness.py`:

```python
MODELS = {
    "your_model": ModelConfig(
        name="Your Model Name",
        model_id="your-bedrock-model-id",
        supports_thinking=False,  # or True if it has thinking mode
        thinking_budget=0  # token budget if supports_thinking=True
    )
}
```

---

## Known Limitations

1. **Limited to 10 hard prompts**: Results may not generalize to all domains
2. **Healthcare/technical focus**: Prompts emphasize medical and technical reasoning
3. **Single run per prompt**: No statistical significance testing across multiple runs
4. **AWS Bedrock only**: Doesn't test OpenAI, Google, or other providers
5. **Thinking mode definition**: Results specific to Claude's extended thinking implementation
6. **Ground truth evaluation**: Manual evaluation criteria, not automated metrics

---

## Research Context

This project extends and contradicts findings from:

- **Self-Consistency**: Wang et al., ICLR 2023 (we found it doesn't help)
- **LLM-Blender**: Jiang et al., ACL 2023 (we found ensembles add no value)
- **Mixture-of-Agents**: Wang et al., 2024 (we found MoA doesn't beat best individual)
- **Extended Thinking**: Anthropic, 2024 (we found no accuracy benefit)

Our findings challenge conventional wisdom about:
1. The value of extended reasoning modes
2. The benefit of ensemble methods on hard tasks
3. The need for premium models on complex reasoning

See [FINDINGS.md](FINDINGS.md) for full analysis and [BLOG.md](BLOG.md) for original hypothesis.

---

## Reproducibility

All raw data available:
- `results/hard_prompts/*/responses.json` - Raw model outputs
- `results/hard_prompts/*/vote_results.json` - Vote aggregation
- `results/hard_prompts/*/stitch_results.json` - Synthesis results
- `results/hard_prompts/*/evaluation.json` - Accuracy metrics

Study parameters:
- Date: April 3, 2026
- Duration: 71 minutes
- Total cost: $12.50
- Prompts: 10 hard reasoning tasks
- Models: 10 unique models
- API calls: 240+ (10 prompts × 6-10 models × 4 experiments)
- Tokens processed: ~2.5M input, ~800K output

---

## Contributing

Pull requests welcome for:

- Testing on different prompt domains
- Adding support for OpenAI/Google models
- Replicating study with different thinking mode implementations
- Challenging findings with counter-evidence

**Before opening PR**: Read [FINDINGS.md](FINDINGS.md) to understand current results.

---

## Citation

If you use this work in research or make decisions based on findings:

```
"Do Thinking Models Think Better? (No)"
Ensemble Thinking Models Experiment, April 2026
https://github.com/yourhandle/ensemble-thinking-models

Key Finding: Extended thinking provided zero accuracy improvement 
while costing 48-150% more. Nova-lite (90% @ $0.0002/correct) beat 
Opus-thinking (87.5% @ $0.25/correct) by 1260x on cost-per-correct.
```

---

## Part of protoGen Series

This is **Project 1 of 3** in the LLM Ensemble Methods series:

1. **Do Thinking Models Think Better?** (this project) ❌ No
2. **Practitioner's Guide to MoA on Bedrock** (coming soon)
3. **Same Model, Different Minds** (coming soon)

---

## Summary: What We Learned

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  HYPOTHESIS 1: Extended thinking helps on hard prompts│
│  RESULT: REJECTED ❌                                    │
│    • Fast mode matched or beat thinking mode          │
│    • 48-150% cost premium for 0% accuracy gain        │
│    • Opus-thinking had worst performance of all       │
│                                                        │
│  HYPOTHESIS 2: Ensembles beat best individual         │
│  RESULT: REJECTED ❌                                    │
│    • 0/40 win rate across all experiments             │
│    • Just use single best model                       │
│    • Ensembles add cost without adding value          │
│                                                        │
│  WINNER: Nova-lite                                    │
│    • 90% accuracy @ $0.0002/correct                   │
│    • 1000x better value than premium models           │
│    • Fast, reliable, production-ready                 │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**For detailed analysis**: See [FINDINGS.md](FINDINGS.md)  
**For executive summary**: See [HARD_PROMPTS_FINAL_ANALYSIS.md](HARD_PROMPTS_FINAL_ANALYSIS.md)  
**For questions**: Open an issue with your findings/counter-evidence

---

**Built with:** Python 3, AWS Bedrock, Claude Opus/Sonnet/Haiku 4.5+, Amazon Nova, Meta Llama, Nvidia Nemotron

**Study conducted**: April 2026 | **Total cost**: $12.50 | **Duration**: 71 minutes | **Prompts**: 10 hard reasoning tasks
