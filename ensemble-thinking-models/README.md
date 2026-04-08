# Ensemble Thinking Models

**Do Thinking Models Think Better? (Spoiler: No)**

An empirical experiment testing whether extended thinking and ensemble methods add value on hard reasoning tasks. Part of the protoGen LLM Ensemble Methods series.

## ⚠️ Major Findings (Updated April 2026)

**Both hypotheses REJECTED:**

1. ❌ **Extended thinking does NOT improve accuracy** on hard prompts (fast mode matched or beat thinking mode)
2. ❌ **Ensembles provide ZERO value** (0/40 times beat best individual model)

**Winner:** Amazon Nova Lite (90% accuracy @ $0.0002 per correct answer)  
**Loser:** Claude Opus Extended Thinking (87.5% accuracy @ $0.25 per correct answer, 1260x worse value)

**Read the full analysis:** [FINDINGS.md](FINDINGS.md)

---

## Overview

This project tests two controversial hypotheses about LLM performance:

### Hypothesis 1: Extended Thinking Helps on Hard Prompts ❌ REJECTED
> "Models with extended reasoning capabilities (5-10K token thinking budgets) should perform better on genuinely hard prompts requiring deep reasoning."

**Result:** Extended thinking provided **ZERO accuracy improvement** while costing 48-150% more. Fast inference matched or beat thinking mode on all models tested.

### Hypothesis 2: Ensembles Beat Best Individual ❌ REJECTED
> "When models diverge on hard prompts, ensemble aggregation (vote/stitch) should produce better answers than any single model."

**Result:** Ensembles beat best individual **0/40 times (0% win rate)**. Ensembles just add cost without adding accuracy.

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

| Experiment | Ensemble Beat Best Individual | Conclusion |
|-----------|-------------------------------|------------|
| Exp 1: Thinking-only | 0/10 (0%) | No value |
| Exp 2: Fast-only | 0/10 (0%) | No value |
| Exp 3: Direct comparison | 0/10 (0%) | No value |
| Exp 4: Hybrid | 0/10 (0%) | No value |
| **TOTAL** | **0/40 (0%)** | **Don't use ensembles** |

---

## Key Findings

### 1. Extended Thinking Failed Its Test

**Opus-fast (90%) BEAT Opus-thinking (87.5%)**

- Opus-thinking: Lower accuracy, 2.5x cost, 20% failure rate (timeouts)
- Sonnet: Tied at 90%, but thinking paid 2x more
- Haiku: Tied at 90%, but thinking paid 2.2x more

**Cost premium for thinking mode: 48-150% with ZERO accuracy gain**

### 2. Nova-lite is the Value Champion

- **90% accuracy** on hard reasoning prompts
- **$0.0002 per correct answer**
- **1100x cheaper** than Opus-thinking
- **808x cheaper** than Opus-fast (same accuracy)
- **100% completion rate** (no timeouts)

### 3. Opus-thinking is the Worst Option

- **Worst accuracy**: 87.5% (only model below 90%)
- **Worst value**: $0.25 per correct answer
- **Only model with failures**: 20% timeout rate (2/10 prompts)
- **Slowest**: 59s average, 3+ minute max before timeout
- **Failed on**: Complex X12/HL7 healthcare data conversion tasks

### 4. Ensembles Remain Useless

- **0/40 times** beat best individual across all experiments
- **Added cost**: 6-45% overhead for vote/stitch aggregation
- **No accuracy benefit**: Even when models diverge (0% convergence)
- **Recommendation**: Don't use ensembles, just pick single best model

### 5. Fast Mode > Thinking Mode

| Comparison | Thinking | Fast | Winner |
|-----------|----------|------|--------|
| Opus | 87.5% @ $2.21 | 90% @ $1.61 | **Fast** |
| Sonnet | 90% @ $0.77 | 90% @ $0.40 | **Fast** |
| Haiku | 90% @ $0.17 | 90% @ $0.08 | **Fast** |

**Fast mode never worse, sometimes better, always cheaper.**

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
