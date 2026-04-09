# Phase 2: Statistical Rigor Plan

**Date:** April 9, 2026  
**Status:** Planning  
**Estimated Cost:** $250-300  
**Estimated Time:** 30-40 hours (API time, not wall clock)

---

## Context from Phase 1

Phase 1 (Quick Wins) achieved:
- ✅ LLM-as-judge evaluation (replaces keyword matching)
- ✅ Documentation improvements (honest framing)
- ✅ Timeout fixes (120s → 600s)
- ✅ Self-consistency testing (validated: ensembles hurt at capability limits)

**Key finding:** Self-consistency (proven method) performed worse than individual (50% vs 80% on GPQA). Ensembles amplify systematic errors when models operate at capability limits.

**Phase 2 goal:** Add statistical rigor to validate findings with proper sample sizes, multiple runs, and significance testing.

---

## Current State

### Datasets Available

| Benchmark | Current Size | Target Size | Status |
|-----------|-------------|-------------|--------|
| GSM8K | 100 problems | 100 | ✅ Ready |
| MMLU | 20 problems | 100 | ❌ Need to generate |
| GPQA | 20 problems | 50 (PhD-level, smaller OK) | ❌ Need to generate |
| HumanEval | 20 problems | 164 (full dataset) | ❌ Need to generate |

### Pilot Results (n=20, single run)

| Benchmark | Best Individual | Ensemble (vote) | Ensemble (stitch) |
|-----------|----------------|----------------|------------------|
| GSM8K | 100% (Opus-thinking) | 90% | 90% |
| MMLU | 85% (Sonnet-fast) | 70% | 70% |
| GPQA | 70% (Sonnet-fast) | 55% | 55% |
| HumanEval | 30% (all models) | 25% | 20% |

**Pattern:** Ensembles consistently underperform best individual (except GSM8K where thinking helped).

---

## Phase 2 Components

### 1. Dataset Expansion

#### 1a. Generate MMLU-100 ✅ Easy (5 min, $0)
```bash
python3 benchmarks/mmlu_loader.py --output prompts/mmlu_100.json --count 100
```

**Why 100?** Minimum for statistical power. MMLU has 14,000+ questions so plenty available.

**Categories:** Mix of STEM, humanities, social sciences (balanced sampling).

#### 1b. Generate GPQA-50 (10 min, $0)
```bash
python3 benchmarks/gpqa_loader.py --output prompts/gpqa_50.json --count 50
```

**Why 50 not 100?** GPQA is PhD-level and expensive to run. 50 provides reasonable power.

**Note:** GPQA dataset has ~450 questions total, so 50 is ~11% sample.

#### 1c. Generate HumanEval-164 (5 min, $0)
```bash
python3 benchmarks/humaneval_loader.py --output prompts/humaneval_164.json --count 164
```

**Why 164?** That's the full HumanEval dataset. Use it all.

**Note:** Current 30% accuracy suggests evaluation issues (expected 70-80%). May need to debug before expansion.

---

### 2. Multiple Runs per Prompt

**Goal:** Run each prompt 3 times to estimate variance and detect statistical significance.

**Why 3 runs?** Minimum for variance estimate. 5 runs would be better but costs 5x.

**Models to test:**
- Individual baselines: opus-fast, opus-thinking, sonnet-fast, sonnet-thinking
- Ensembles: vote (6 models), stitch (6 models)
- Self-consistency: sonnet-fast (N=5 samples per run)

**Total configurations:** 7 (4 individual + 2 ensemble + 1 self-consistency)

---

### 3. Statistical Testing

Create `benchmarks/statistical_analysis.py`:

```python
#!/usr/bin/env python3
"""
Statistical significance testing for benchmark results.
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Tuple

def bootstrap_confidence_interval(
    accuracies: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for accuracy.
    
    Args:
        accuracies: List of accuracy values (0-1) from multiple runs
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (default 0.95 for 95% CI)
    
    Returns:
        (lower_bound, upper_bound) of confidence interval
    """
    bootstrap_means = []
    n = len(accuracies)
    
    for _ in range(n_bootstrap):
        sample = np.random.choice(accuracies, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))
    
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_means, alpha/2 * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha/2) * 100)
    
    return (lower, upper)


def paired_t_test(
    baseline_accuracies: List[float],
    treatment_accuracies: List[float]
) -> Tuple[float, float]:
    """
    Paired t-test comparing baseline vs treatment.
    
    Args:
        baseline_accuracies: Accuracies from baseline approach
        treatment_accuracies: Accuracies from treatment approach
    
    Returns:
        (t_statistic, p_value)
    """
    assert len(baseline_accuracies) == len(treatment_accuracies)
    
    t_stat, p_value = stats.ttest_rel(baseline_accuracies, treatment_accuracies)
    return (t_stat, p_value)


def mcnemar_test(
    baseline_correct: List[bool],
    treatment_correct: List[bool]
) -> Tuple[float, float]:
    """
    McNemar's test for paired nominal data.
    
    More appropriate than t-test for binary outcomes (correct/incorrect).
    
    Args:
        baseline_correct: Binary list of correct/incorrect for baseline
        treatment_correct: Binary list of correct/incorrect for treatment
    
    Returns:
        (chi2_statistic, p_value)
    """
    # Count discordant pairs
    b_yes_t_no = sum(1 for b, t in zip(baseline_correct, treatment_correct) if b and not t)
    b_no_t_yes = sum(1 for b, t in zip(baseline_correct, treatment_correct) if not b and t)
    
    # McNemar's test statistic
    chi2 = (abs(b_yes_t_no - b_no_t_yes) - 1)**2 / (b_yes_t_no + b_no_t_yes)
    p_value = 1 - stats.chi2.cdf(chi2, df=1)
    
    return (chi2, p_value)


def analyze_benchmark_results(results_file: str):
    """
    Analyze benchmark results with statistical tests.
    
    Generates:
    1. Bootstrap 95% CIs for each approach
    2. Paired t-tests comparing approaches
    3. McNemar's test for ensemble vs individual
    4. Effect sizes (Cohen's d)
    """
    # Load results, compute statistics, generate report
    pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('results_file', help='Results JSON with multiple runs')
    args = parser.parse_args()
    
    analyze_benchmark_results(args.results_file)
```

---

### 4. Execution Plan

#### Step 1: Generate Datasets (20 min, $0)
```bash
python3 benchmarks/mmlu_loader.py --output prompts/mmlu_100.json --count 100
python3 benchmarks/gpqa_loader.py --output prompts/gpqa_50.json --count 50
python3 benchmarks/humaneval_loader.py --output prompts/humaneval_164.json --count 164
```

#### Step 2: Run GSM8K-100 (3 runs per config)

**Cost per run:**
- Individual models: ~$15 per run × 4 models = $60
- Vote ensemble: ~$80 per run
- Stitch ensemble: ~$80 per run
- Self-consistency: ~$75 per run

**Total for 3 runs:** ($60 + $80 + $80 + $75) × 3 = $885 😱

**Problem:** Way over budget!

**Solution:** Subset approach
- Run 3x on 50-prompt subset (not full 100)
- Cost: $885 ÷ 2 = $442 (still over budget)

**Better solution:** Prioritize configurations
- Individual (opus-fast, opus-thinking): 2 × $7.50 × 3 = $45
- Vote ensemble: $40 × 3 = $120
- Self-consistency: $37.50 × 3 = $112
- **Total:** $277 (within budget)

**Command:**
```bash
# Run 1
python3 harness.py \
  --prompts prompts/gsm8k_100.json \
  --models opus-fast opus-thinking \
  --output results/gsm8k_100_run1.json

python3 aggregators/vote.py \
  results/gsm8k_100_run1.json \
  --output results/gsm8k_100_run1_vote.json

python3 aggregators/self_consistency.py \
  prompts/gsm8k_100.json \
  --model opus-fast --samples 5 \
  --output results/gsm8k_100_run1_selfcons.json

# Repeat for run2, run3
```

#### Step 3: Run MMLU-100 (3 runs)

**Cost estimate:** Similar to GSM8K, ~$280

**Command:**
```bash
python3 harness.py \
  --prompts prompts/mmlu_100.json \
  --models opus-fast opus-thinking \
  --output results/mmlu_100_run1.json
# ... (same pattern)
```

#### Step 4: Statistical Analysis

```bash
python3 benchmarks/statistical_analysis.py \
  results/gsm8k_100_run*.json \
  --output results/gsm8k_statistical_report.json

python3 benchmarks/statistical_analysis.py \
  results/mmlu_100_run*.json \
  --output results/mmlu_statistical_report.json
```

---

## Revised Budget

### Conservative Approach (Stay under $300)

**Test only GSM8K-100:**
- 3 runs × (2 individual + 1 ensemble + 1 self-consistency)
- Cost: ~$280
- Provides: Statistical significance for math/reasoning domain

**Rationale:**
- GSM8K showed interesting pattern (thinking helped, 100% accuracy)
- Most relevant for validating thinking vs ensemble findings
- Can expand to MMLU later if needed

### Aggressive Approach (Accept $500-600 cost)

**Test both GSM8K-100 and MMLU-100:**
- Cost: ~$560
- Provides: Two domains with statistical power
- Risk: May not find significant differences (wasted cost)

---

## Expected Outcomes

### What Statistical Testing Will Show

#### Scenario 1: Original findings hold (most likely)
- Individual > Ensemble (statistically significant)
- Thinking helps on GSM8K (p < 0.05)
- Self-consistency ≈ Individual or worse
- **Conclusion:** Original study validated with rigor

#### Scenario 2: Results were lucky (unlikely given self-consistency)
- No significant difference between approaches
- High variance across runs
- **Conclusion:** Need even larger sample sizes

#### Scenario 3: Ensembles actually help (very unlikely)
- Ensemble > Individual (p < 0.05)
- **Conclusion:** Pilot results were misleading

---

## Implementation Schedule

### Week 1: Infrastructure (Days 1-2)
- Generate datasets (MMLU-100, GPQA-50)
- Implement `statistical_analysis.py`
- Test on pilot data to validate

### Week 2: Data Collection (Days 3-7)
- Run GSM8K-100 (3 runs × 4 configs)
- Run MMLU-100 (3 runs × 4 configs) - if budget allows
- Total runtime: ~40 hours (can run overnight)

### Week 3: Analysis (Day 8)
- Run statistical tests
- Generate report with CI, p-values, effect sizes
- Update README/BLOG with validated findings

---

## Success Criteria

**Minimum viable:**
- ✅ GSM8K-100 with 3 runs per config
- ✅ Bootstrap 95% CI for each approach
- ✅ Paired t-tests comparing approaches
- ✅ Effect sizes (Cohen's d)

**Nice to have:**
- MMLU-100 with statistical testing
- McNemar's test for binary outcomes
- Power analysis for future sample size

**Documentation:**
- Statistical report (confidence intervals, p-values)
- Updated findings in README/BLOG with "p < 0.05" citations
- Methodology section explaining statistical approach

---

## Risks and Mitigation

### Risk 1: Cost overrun
**Mitigation:** Start with GSM8K-100 only. Evaluate cost/benefit before MMLU.

### Risk 2: High variance across runs
**Mitigation:** If variance is high (CI > 10%), need more runs or larger sample.

### Risk 3: API rate limits
**Mitigation:** Use `time.sleep()` between requests. Split across multiple days.

### Risk 4: HumanEval evaluation broken
**Mitigation:** Fix evaluation first (separate mini-project). Don't include in Phase 2.

---

## Next Steps

**Immediate:**
1. Generate MMLU-100 dataset
2. Implement `statistical_analysis.py`
3. Validate statistical tests on pilot data (20 prompts × 3 mock runs)

**After validation:**
1. Run GSM8K-100 (3 runs, ~$280, 20 hours)
2. Analyze results
3. Decide if MMLU-100 is worth the cost

**Final:**
1. Update documentation with statistical findings
2. Commit results with proper CI and p-values
3. Declare Phase 2 complete

---

## Files to Create

1. `prompts/mmlu_100.json` - 100 MMLU problems
2. `prompts/gpqa_50.json` - 50 GPQA problems (optional)
3. `benchmarks/statistical_analysis.py` - Statistical testing
4. `results/gsm8k_100_run{1,2,3}.json` - Multiple run results
5. `results/gsm8k_statistical_report.json` - Analysis output
6. `PHASE_2_RESULTS.md` - Summary of statistical findings

---

**Decision point:** Do you want to:
- **Option A:** Conservative ($280) - GSM8K-100 only, validate key findings
- **Option B:** Aggressive ($560) - GSM8K + MMLU, comprehensive validation
- **Option C:** Pilot first ($30) - Run 3x on 20-prompt subset to validate variance

Recommend **Option C** (pilot first) to check variance before committing to full runs.
