# E18-E20 Implementation Summary

**Date:** 2026-04-13  
**Status:** ✅ Fully implemented, ready to run (NOT YET EXECUTED)

---

## What Was Implemented

### The Core Hypothesis
**"Is the judge doing the wrong task?"**

Analysis of E1-E2 revealed that the judge prompt asks for **AGREEMENT**, not **CORRECTNESS**:
- E1 prompt: "Identify which answers AGREE with each other"
- Should be: "Identify which answer is MOST LIKELY CORRECT"

### Three New Experiments

#### **E18: Correctness-Based Vote**
- Vote ensemble (Opus/Sonnet/Haiku proposers + Opus judge)
- Judge evaluates CORRECTNESS instead of agreement
- Tests: "Does fixing the prompt fix the performance?"
- Compare to: E1 (79.7% with agreement-based judging)

#### **E19: Correctness-Based Best-of-N**
- Best-of-N (5 Opus samples + Opus judge)
- Judge evaluates CORRECTNESS instead of "quality"
- Tests: "Does best-of-N work with correct evaluation?"
- Compare to: E2 (78.1% with quality-based judging)

#### **E20: Two-Stage Judging**
- Stage 1: Group by agreement (filter outliers)
- Stage 2: Evaluate correctness within majority
- Tests: "Does combining both approaches work better?"
- Compare to: E18 (single-stage correctness)

---

## Files Created

### Aggregators (3 new classes)
```
aggregators/vote_correctness.py         (267 lines)
  └─ CorrectnessVoteAggregator
     └─ Judge evaluates correctness, not agreement

aggregators/best_of_n_correctness.py    (345 lines)
  └─ CorrectnessBasedBestOfN
     └─ Judge evaluates correctness, not quality

aggregators/two_stage.py                (388 lines)
  └─ TwoStageAggregator
     └─ Stage 1: Agreement grouping
     └─ Stage 2: Correctness evaluation
```

### Runners (3 experiment scripts)
```
run_e18_correctness_vote.py             (145 lines)
  └─ E18: 3 proposers + correctness judge
  └─ 3 runs × 100 prompts each

run_e19_correctness_best_of_n.py        (140 lines)
  └─ E19: 5 samples + correctness judge
  └─ 3 runs × 100 prompts each

run_e20_two_stage.py                    (160 lines)
  └─ E20: 3 proposers + 2-stage judge
  └─ 3 runs × 100 prompts each
```

### Master Script
```
run_e18_e20_all.sh                      (executable)
  └─ Runs all 9 experiments (E18-E20, 3 runs each)
  └─ Total: ~$66, ~10.5 hours
```

### Documentation
```
EXPERIMENTS_E18_E20.md                  (comprehensive spec)
  └─ Hypothesis, design, success criteria
  └─ Detailed analysis plan
  └─ Cost/time estimates

E18_E20_IMPLEMENTATION_SUMMARY.md       (this file)
  └─ Quick reference for what was built
```

---

## Key Prompt Differences

### E1 (Agreement-Based) - CURRENT
```python
"""You are analyzing responses to identify which answers AGREE.

Your task:
1. Identify the CORE CONCLUSION of each response
2. Group responses that reach the SAME conclusion
3. Apply CONFIDENCE WEIGHTING
4. Determine the weighted majority

Focus on CONCLUSIONS, not wording.
Two responses AGREE if they reach the same final answer."""
```

### E18 (Correctness-Based) - NEW
```python
"""You are evaluating solutions to determine which is MOST LIKELY CORRECT.

Evaluation criteria:
1. Mathematical accuracy - Are calculations correct?
2. Logical reasoning - Is the approach sound?
3. Completeness - Does it address all parts?
4. Final answer - Is the numerical answer reasonable?

Important:
- Focus ONLY on correctness of the final answer
- VERIFY calculations step-by-step when possible
- The models may disagree - your job is to determine which is RIGHT"""
```

**Critical difference:** E18 asks judge to VERIFY correctness, not just identify consensus.

---

## Cost & Time Estimates

| Experiment | Config | Runs | Cost/Run | Total Cost | Time/Run | Total Time |
|------------|--------|------|----------|------------|----------|------------|
| **E18** | Vote + Correctness | 3 | $6 | $18 | 1h | 3h |
| **E19** | Best-of-N + Correctness | 3 | $8 | $24 | 1h | 3h |
| **E20** | Two-Stage | 3 | $8 | $24 | 1.5h | 4.5h |
| **TOTAL** | - | **9** | - | **~$66** | - | **~10.5h** |

---

## Expected Results

### Scenario A: Hypothesis CONFIRMED (prompt was the problem)
```
E18: >84% accuracy (beats baseline)
E19: >84% accuracy (beats baseline)
E20: >E18 (two-stage wins)

Conclusion: Judge-based ensembles CAN work with correct prompting
```

### Scenario B: Hypothesis REJECTED (evaluation is fundamentally hard)
```
E18: ~79.7% (+2% or less vs E1)
E19: ~78.1% (+2% or less vs E2)
E20: ~E18 (two-stage doesn't help)

Conclusion: Evaluation is harder than generation, even with optimal prompts
             Self-consistency wins for fundamental reasons
```

---

## How to Run

### Option 1: Run all at once (recommended)
```bash
export AWS_BEARER_TOKEN_BEDROCK="your_token_here"
bash run_e18_e20_all.sh
```

### Option 2: Run individually
```bash
# E18 only
python3 run_e18_correctness_vote.py --run 1
python3 run_e18_correctness_vote.py --run 2
python3 run_e18_correctness_vote.py --run 3

# E19 only
python3 run_e19_correctness_best_of_n.py --run 1
python3 run_e19_correctness_best_of_n.py --run 2
python3 run_e19_correctness_best_of_n.py --run 3

# E20 only
python3 run_e20_two_stage.py --run 1
python3 run_e20_two_stage.py --run 2
python3 run_e20_two_stage.py --run 3
```

### Results will be saved to:
```
results/phase2/
  e18_correctness_vote_run1.json
  e18_correctness_vote_run2.json
  e18_correctness_vote_run3.json
  e19_correctness_best_of_n_run1.json
  e19_correctness_best_of_n_run2.json
  e19_correctness_best_of_n_run3.json
  e20_two_stage_run1.json
  e20_two_stage_run2.json
  e20_two_stage_run3.json
```

---

## Analysis After Completion

Once experiments finish, update `analyze_architecture.py` to include:

1. **Add E18-E20 to analysis:**
   ```python
   experiments = {
       'E1: Vote + Opus (agreement)': ...,
       'E18: Vote + Opus (correctness)': ...,
       'E2: Best-of-N (quality)': ...,
       'E19: Best-of-N (correctness)': ...,
       'E20: Two-Stage': ...
   }
   ```

2. **Compare prompt impact:**
   - E1 vs E18 delta
   - E2 vs E19 delta

3. **Compare architectures:**
   - E18 vs E19 (vote vs best-of-N)
   - E18 vs E20 (single vs two-stage)

4. **Error analysis:**
   - When does correctness judging work?
   - When does it still fail?

---

## What Changed from E1/E2

| Aspect | E1/E2 (Original) | E18-E20 (New) |
|--------|------------------|---------------|
| **Judge task** | Identify agreement | Evaluate correctness |
| **Judge prompt** | "Which answers AGREE?" | "Which answer is CORRECT?" |
| **Evaluation focus** | Semantic similarity | Mathematical accuracy |
| **Verification** | No calculation checking | Explicit verification |
| **Majority rule** | Weighted by confidence | Based on correctness |

**Key innovation:** Judge now acts as a VERIFIER, not just a GROUPER.

---

## Success Metrics

| Metric | Target | Interpretation |
|--------|--------|----------------|
| **E18 accuracy** | >82% | Correctness prompt helps vote |
| **E19 accuracy** | >82% | Correctness prompt helps best-of-N |
| **E20 accuracy** | >E18 | Two-stage adds value |
| **Any > baseline** | >84.7% | Judge ensembles can work |
| **Any > self-cons** | >93.3% | Judge beats crowd wisdom (unlikely) |

---

## Next Steps

1. **Run experiments:** `bash run_e18_e20_all.sh`
2. **Analyze results:** Extend `analyze_architecture.py`
3. **Update docs:** Add findings to BLOG.md, README.md
4. **Write insights:** Judge prompt engineering lessons
5. **Decide:** Should we continue with judge-based ensembles?

---

*Implementation complete: 2026-04-13*  
*Ready to execute: ✅*  
*Awaiting user approval to run*
