## All Experiments Ready to Run

**Date:** April 11, 2026  
**Status:** ✅ ALL CODE AND DATA READY

---

## Quick Start

Run all experiments (3 runs each, ~$200 total, ~24 hours):
```bash
bash run_all_experiments.sh
```

Run specific experiment:
```bash
# E1: Strong-judge vote
bash run_all_experiments.sh --experiments e1 --runs "1 2 3"

# E2: Best-of-N
bash run_all_experiments.sh --experiments e2 --runs "1 2 3"

# Just run 1 instead of 3
bash run_all_experiments.sh --runs 1
```

---

## Experiments Ready

### Priority 1: Critical Evidence Gaps (~$45, 6 hours)

**E1: Strong-Judge Vote Ensemble** ✅ READY
```bash
python3 run_e1_strong_judge_vote.py --run 1
python3 run_e1_strong_judge_vote.py --run 2
python3 run_e1_strong_judge_vote.py --run 3
```
- **Purpose:** Test if vote ensemble failure is architectural (weak Haiku judge) or fundamental
- **Config:** 6 proposers + Opus judge (strongest model)
- **Dataset:** GSM8K-100
- **Cost:** ~$7 per run × 3 = ~$20 total
- **Time:** ~2 hours
- **Key test:** If Opus judge works → architecture matters; if fails → ensembles fundamentally broken

---

**E2: Best-of-N with Opus Verifier** ✅ READY
```bash
python3 run_e2_best_of_n.py --run 1
python3 run_e2_best_of_n.py --run 2
python3 run_e2_best_of_n.py --run 3
```
- **Purpose:** Test strongest possible ensemble architecture
- **Config:** Opus-fast × 5 samples, Opus-fast judge picks best
- **Dataset:** GSM8K-100
- **Cost:** ~$8 per run × 3 = ~$25 total
- **Time:** ~3 hours
- **Key test:** If this fails, nothing will work

---

### Priority 2: Multi-Benchmark Validation (~$105, 10 hours)

**E6: MMLU-100 Full Ensemble** ✅ READY
```bash
# Run all 4 configs, 3 runs each
for run in 1 2 3; do
  python3 run_multi_benchmark.py --benchmark mmlu --config opus-fast --run $run
  python3 run_multi_benchmark.py --benchmark mmlu --config opus-thinking --run $run
  python3 run_multi_benchmark.py --benchmark mmlu --config vote --run $run
  python3 run_multi_benchmark.py --benchmark mmlu --config self-consistency --run $run
done
```
- **Purpose:** Test if findings generalize to knowledge tasks
- **Dataset:** MMLU-100 (57 subjects, multiple choice)
- **Cost:** ~$15 per full cycle × 3 = ~$45 total
- **Time:** ~4 hours

---

**E7: GPQA-50 Full Ensemble** ✅ READY
```bash
# Run all 4 configs, 3 runs each
for run in 1 2 3; do
  python3 run_multi_benchmark.py --benchmark gpqa --config opus-fast --run $run
  python3 run_multi_benchmark.py --benchmark gpqa --config opus-thinking --run $run
  python3 run_multi_benchmark.py --benchmark gpqa --config vote --run $run
  python3 run_multi_benchmark.py --benchmark gpqa --config self-consistency --run $run
done
```
- **Purpose:** Test at ~70% baseline (below capability limit)
- **Dataset:** GPQA-50 (PhD-level science)
- **Cost:** ~$10 per full cycle × 3 = ~$30 total
- **Time:** ~3 hours
- **Key test:** Does self-consistency help below capability limit?

---

**E8: HumanEval-50 Full Ensemble** ✅ READY
```bash
# Run all 4 configs, 3 runs each
for run in 1 2 3; do
  python3 run_multi_benchmark.py --benchmark humaneval --config opus-fast --run $run
  python3 run_multi_benchmark.py --benchmark humaneval --config opus-thinking --run $run
  python3 run_multi_benchmark.py --benchmark humaneval --config vote --run $run
  python3 run_multi_benchmark.py --benchmark humaneval --config self-consistency --run $run
done
```
- **Purpose:** Test at very low baseline (~30%)
- **Dataset:** HumanEval-50 (code generation)
- **Cost:** ~$10 per full cycle × 3 = ~$30 total
- **Time:** ~3 hours
- **Key test:** Extreme capability limit test

---

### Priority 3: Theory Testing (~$11, 3 hours)

**E14: Budget Model Baselines** ✅ READY
```bash
# Haiku baseline
python3 run_theory_tests.py --experiment e14 --model haiku-fast --run 1
python3 run_theory_tests.py --experiment e14 --model haiku-fast --run 2
python3 run_theory_tests.py --experiment e14 --model haiku-fast --run 3

# Sonnet baseline
python3 run_theory_tests.py --experiment e14 --model sonnet-fast --run 1
python3 run_theory_tests.py --experiment e14 --model sonnet-fast --run 2
python3 run_theory_tests.py --experiment e14 --model sonnet-fast --run 3
```
- **Purpose:** Map capability spectrum
- **Dataset:** GSM8K-100
- **Cost:** ~$1 per model × 2 models × 3 runs = ~$2 total
- **Time:** ~1 hour

---

**E15: Self-Consistency Low Baseline (Haiku)** ✅ READY
```bash
python3 run_theory_tests.py --experiment e15 --model haiku-fast --run 1
python3 run_theory_tests.py --experiment e15 --model haiku-fast --run 2
python3 run_theory_tests.py --experiment e15 --model haiku-fast --run 3
```
- **Purpose:** Test if SC helps at ~60-70% baseline
- **Dataset:** GSM8K-100
- **Cost:** ~$1 per run × 3 = ~$3 total
- **Time:** ~1 hour
- **Key test:** Systematic error theory - does SC help below capability?

---

**E17: Self-Consistency Mid Baseline (Sonnet)** ✅ READY
```bash
python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run 1
python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run 2
python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run 3
```
- **Purpose:** Find help→hurt threshold (~80% baseline)
- **Dataset:** GSM8K-100
- **Cost:** ~$2 per run × 3 = ~$6 total
- **Time:** ~1 hour

---

## Total Summary

| Priority | Experiments | Cost | Time | Purpose |
|----------|-------------|------|------|---------|
| **P1 Critical** | E1, E2 | ~$45 | ~6h | Architecture vs fundamental |
| **P2 Validation** | E6, E7, E8 | ~$105 | ~10h | Multi-benchmark generalization |
| **P3 Theory** | E14, E15, E17 | ~$11 | ~3h | Systematic error theory |
| **TOTAL** | **9 experiments** | **~$161** | **~19h** | **Complete gap closure** |

---

## Code Changes Made

### 1. ✅ Made vote.py support configurable judge
- Added `judge_model` parameter to `VoteAggregator.__init__()`
- Maps judge_model key to Bedrock model ID
- Supports: haiku-fast, sonnet-fast, opus-fast

### 2. ✅ Created best_of_n.py aggregator
- New file: `aggregators/best_of_n.py`
- Generates N samples from same model
- Uses judge to pick best (no voting)
- CLI interface included

### 3. ✅ Generated missing datasets
- `prompts/mmlu_100_full.json` - 100 prompts (was 57)
- `prompts/gpqa_50.json` - 50 prompts (was 20)
- `prompts/humaneval_50.json` - 50 prompts (was 20)

### 4. ✅ Created runner scripts
- `run_e1_strong_judge_vote.py` - E1 runner
- `run_e2_best_of_n.py` - E2 runner
- `run_multi_benchmark.py` - E6-E8 runner (all benchmarks)
- `run_theory_tests.py` - E14-E17 runner
- `run_all_experiments.sh` - Master script

---

## Files Created/Modified

**Code:**
- `aggregators/vote.py` - Modified (added judge_model parameter)
- `aggregators/best_of_n.py` - NEW (225 lines)
- `run_e1_strong_judge_vote.py` - NEW (200 lines)
- `run_e2_best_of_n.py` - NEW (150 lines)
- `run_multi_benchmark.py` - NEW (300 lines)
- `run_theory_tests.py` - NEW (200 lines)
- `run_all_experiments.sh` - NEW (master script)

**Data:**
- `prompts/mmlu_100_full.json` - NEW (100 prompts)
- `prompts/gpqa_50.json` - NEW (50 prompts)
- `prompts/humaneval_50.json` - NEW (50 prompts)

---

## What Each Experiment Tests

### E1: Architecture Matters
**Current claim:** "Vote ensemble fails by -17%"  
**Limitation:** Only tested with Haiku judge (weakest model)  
**Test:** If Opus judge (strongest) works → claim becomes "weak judges fail"  
**Impact:** Changes headline from "ensembles fail" to "architecture matters"

### E2: Strongest Possible Architecture
**Test:** Best ensemble design: same strong model + same strong judge  
**If succeeds:** Ensembles CAN work with right architecture  
**If fails:** Even optimal design doesn't help

### E6-E8: Task Generalization
**Current limitation:** All Phase 2 findings are GSM8K-only (math)  
**Test:** Do findings hold on knowledge (MMLU), science (GPQA), code (HumanEval)?  
**Impact:** Shows if findings are task-specific or general

### E14-E17: Systematic Error Theory
**Theory:** Self-consistency helps below capability limit (random errors), hurts at limit (systematic errors)  
**Test:** Run SC on Haiku (~60%), Sonnet (~80%), already have Opus (~90%)  
**Impact:** Validates or refutes theoretical explanation

---

## Cost Efficiency

**Original devils-advocate plan:** $399 for everything  
**This plan:** $161 (60% reduction)

**Savings from:**
- Using existing GSM8K-100 (don't need to regenerate)
- 50 prompts instead of 100 for GPQA/HumanEval
- Strategic experiment selection (9 experiments vs 17)

---

## Ready to Run

Everything is prepped. To start:

```bash
# Run everything
bash run_all_experiments.sh

# Or run in parallel (if you have enough Bedrock quota)
bash run_all_experiments.sh --experiments e1 --runs "1 2 3" &
bash run_all_experiments.sh --experiments e2 --runs "1 2 3" &
bash run_all_experiments.sh --experiments e14 --runs "1 2 3" &
```

Monitor progress: Results will be saved to `results/phase2/` as they complete.

---

**Status:** ✅ READY TO LAUNCH  
**Total setup time:** 4 hours (code + data generation)  
**Next:** Run experiments and analyze results
