# E18-E20: Correctness-Based Judging Experiments

**Status:** ✅ Implemented, ready to run  
**Date Created:** 2026-04-13  
**Hypothesis:** "Is the judge doing the wrong task?"

---

## Motivation

E1-E2 results showed that even with a strong Opus judge, ensemble performance was disappointing:
- **E1 (Vote + Opus judge):** 79.7% (-5% vs baseline)
- **E2 (Best-of-N + Opus judge):** 78.1% (-6.6% vs baseline)
- **Opus baseline:** 84.7%
- **Self-consistency:** 93.3%

**Critical discovery:** The judge prompt in E1/E2 asks for **AGREEMENT**, not **CORRECTNESS**.

```python
# E1 prompt (WRONG?)
"Identify which answers AGREE with each other"
"Group responses that reach the SAME conclusion"
"Determine the weighted majority"
```

This makes the judge a **semantic grouping tool**, not a **correctness evaluator**.

**Key insight from user:** The judge should reason through available answers to determine which is MOST LIKELY CORRECT, using only the proposers' answers as context (no external knowledge).

---

## Experiments

### E18: Correctness-Based Vote

**Question:** Does correctness-based judging fix the vote ensemble?

**Configuration:**
- Proposers: Opus, Sonnet, Haiku (all fast mode)
- Judge: Opus
- **Judge task:** Evaluate which answer is MOST LIKELY CORRECT
- Benchmark: GSM8K-100
- Runs: 3

**Judge prompt (NEW):**
```
You are evaluating multiple mathematical solutions to determine which is 
MOST LIKELY CORRECT.

Evaluation criteria:
1. Mathematical accuracy - Are the calculations correct?
2. Logical reasoning - Is the approach sound?
3. Completeness - Does it address all parts?
4. Final answer - Is the number reasonable?

Important:
- Focus ONLY on correctness, not style
- Verify calculations step-by-step
- The models may disagree - pick the RIGHT one, not the majority
```

**Expected outcome:**
- If E18 >> E1 (79.7%), confirms judge was doing the wrong task
- If E18 ≈ E1, confirms evaluation is inherently hard

**Cost:** ~$18 (3 runs × $6)

---

### E19: Correctness-Based Best-of-N

**Question:** Does correctness-based judging fix best-of-N?

**Configuration:**
- Candidate model: Opus-fast (5 samples, temp=0.7)
- Judge: Opus-fast
- **Judge task:** Evaluate which answer is MOST LIKELY CORRECT
- Benchmark: GSM8K-100
- Runs: 3

**Difference from E2:**
```
E2:  Judge picks "best quality" (clarity, completeness, explanation)
E19: Judge picks "most likely correct" (mathematical accuracy, verification)
```

**Judge prompt (NEW):**
```
You are evaluating solutions to select the one most likely to be CORRECT.

Evaluation process:
1. Extract final numerical answer from each candidate
2. Verify calculations step-by-step
3. Check if reasoning is sound
4. Select the candidate with the CORRECT answer

Important:
- Don't assume detailed explanation = correct
- Verify calculations independently
- The candidates may all agree but still be wrong
```

**Expected outcome:**
- If E19 >> E2 (78.1%), confirms judge prompt was the issue
- If E19 ≈ E2, confirms best-of-N is fundamentally flawed

**Cost:** ~$24 (3 runs × $8)

---

### E20: Two-Stage Judging

**Question:** Does combining both approaches work better?

**Configuration:**
- Proposers: Opus, Sonnet, Haiku (all fast mode)
- Judge: Opus (used for both stages)
- **Stage 1:** Group by agreement (filter outliers)
- **Stage 2:** Evaluate correctness within majority
- Benchmark: GSM8K-100
- Runs: 3

**Two-stage process:**
```
Stage 1: "Which models AGREE with each other?"
  → Groups: {A: [opus, sonnet], B: [haiku]}
  → Majority: Group A

Stage 2: "Within Group A, which answer is MOST LIKELY CORRECT?"
  → Evaluates: opus vs sonnet
  → Selects: opus (after verification)
```

**Hypothesis:**
- Stage 1 filters out wrong outliers via consensus
- Stage 2 picks the correct answer within the consensus group
- Best of both worlds?

**Expected outcome:**
- If E20 >> E18 > E1, confirms two-stage is optimal
- If E20 ≈ E18, Stage 1 filtering doesn't help
- If E20 < E18, Stage 1 filtering hurts (removes correct minority answers)

**Cost:** ~$24 (3 runs × $8, 2× judge calls per prompt)

---

## Comparison Matrix

| Experiment | Judge Task | Architecture | Expected Accuracy | Cost |
|------------|-----------|--------------|-------------------|------|
| **E1** | Agreement | Vote (3 proposers) | 79.7% (baseline) | $6 |
| **E18** | Correctness | Vote (3 proposers) | **>79.7%?** | $6 |
| **E2** | Quality | Best-of-N (5 samples) | 78.1% (baseline) | $8 |
| **E19** | Correctness | Best-of-N (5 samples) | **>78.1%?** | $8 |
| **E20** | Both (2 stages) | Vote + Correctness | **>79.7%?** | $8 |

**Reference points:**
- Opus baseline: 84.7%
- Self-consistency: 93.3%

---

## Success Criteria

### Hypothesis Confirmed: "Judge was doing the wrong task"
If we see significant improvements:
- E18 > 84% (beats baseline)
- E19 > 84% (beats baseline)
- E20 > E18 (two-stage wins)

**Conclusion:** Judge-based ensembles CAN work with correct prompting.

### Hypothesis Rejected: "Evaluation is fundamentally hard"
If we see minimal improvements:
- E18 ≈ 79.7% (+2% or less vs E1)
- E19 ≈ 78.1% (+2% or less vs E2)
- E20 ≈ E18 (two-stage doesn't help)

**Conclusion:** Even optimal prompting can't fix judge-based ensembles. Self-consistency wins for fundamental reasons (wisdom of crowds > single evaluator).

---

## Detailed Analysis Plan

After running E18-E20, analyze:

1. **Prompt impact:**
   - E18 vs E1 delta
   - E19 vs E2 delta
   - Does correctness prompt help consistently?

2. **Architecture comparison:**
   - E18 vs E19 (vote vs best-of-N with same prompt)
   - E20 vs E18 (two-stage vs single-stage)

3. **Error analysis:**
   - When judge picks correct answer: What patterns?
   - When judge picks wrong answer: What went wrong?
   - Does judge verify calculations or just trust reasoning?

4. **Cost-benefit:**
   - If E18 works, is it worth 4× baseline cost?
   - Does it beat self-consistency (93.3% at 3.7× cost)?

5. **Qualitative review:**
   - Read 10 judge reasoning examples
   - Does judge actually verify calculations?
   - Or does it still group by consensus?

---

## Files Created

### Aggregators:
- `aggregators/vote_correctness.py` - Correctness-based vote
- `aggregators/best_of_n_correctness.py` - Correctness-based best-of-N
- `aggregators/two_stage.py` - Two-stage judging

### Runners:
- `run_e18_correctness_vote.py` - E18 runner
- `run_e19_correctness_best_of_n.py` - E19 runner
- `run_e20_two_stage.py` - E20 runner
- `run_e18_e20_all.sh` - Master script (all 9 runs)

### Documentation:
- `EXPERIMENTS_E18_E20.md` (this file)

---

## Running the Experiments

### Run all at once (recommended):
```bash
export AWS_BEARER_TOKEN_BEDROCK="your_token_here"
bash run_e18_e20_all.sh
```

### Run individually:
```bash
# E18 (3 runs)
python3 run_e18_correctness_vote.py --run 1
python3 run_e18_correctness_vote.py --run 2
python3 run_e18_correctness_vote.py --run 3

# E19 (3 runs)
python3 run_e19_correctness_best_of_n.py --run 1
python3 run_e19_correctness_best_of_n.py --run 2
python3 run_e19_correctness_best_of_n.py --run 3

# E20 (3 runs)
python3 run_e20_two_stage.py --run 1
python3 run_e20_two_stage.py --run 2
python3 run_e20_two_stage.py --run 3
```

### Results location:
```
results/phase2/
  e18_correctness_vote_run{1,2,3}.json
  e19_correctness_best_of_n_run{1,2,3}.json
  e20_two_stage_run{1,2,3}.json
```

---

## Cost & Time Estimates

| Experiment | Runs | Cost/Run | Total Cost | Time/Run | Total Time |
|------------|------|----------|------------|----------|------------|
| E18 | 3 | $6 | $18 | ~1h | ~3h |
| E19 | 3 | $8 | $24 | ~1h | ~3h |
| E20 | 3 | $8 | $24 | ~1.5h | ~4.5h |
| **Total** | **9** | - | **~$66** | - | **~10.5h** |

---

## Next Steps After Results

1. **Extend analyze_architecture.py** to include E18-E20
2. **Create comparison report:**
   - E1 vs E18 (agreement vs correctness)
   - E2 vs E19 (quality vs correctness)
   - E18 vs E20 (single vs two-stage)
3. **Update BLOG.md** and **README.md** with findings
4. **Write up judge prompt engineering lessons**

---

*Experiments designed: 2026-04-13*  
*Ready to run: ✅*
