# E18-E20 Multi-Benchmark Expansion

**Status:** 🚧 Implementation complete, ready to run  
**Date:** 2026-04-13

---

## Motivation

### The Problem with Current Evidence

Phase 2-3 research (E6-E20) generated **strong evidence that judge-based ensembles fail**:

- E18 (correctness vote): 74.8% vs 84.7% baseline (-9.8%)
- E19 (correctness best-of-N): 79.1% vs 84.7% baseline (-5.6%)
- E20 (two-stage): 68.0% vs 84.7% baseline (-16.7%)

**Conclusion drawn:** "NEVER use judge-based ensembles"

### The Scope Limitation

**Critical issue:** All Phase 2-3 evidence comes from **GSM8K math problems only**.

| Phase | Benchmarks Tested | Depth |
|-------|-------------------|-------|
| **Phase 1** | GSM8K, MMLU, HumanEval, GPQA | Shallow (1-3 runs) |
| **Phase 2-3** | **GSM8K ONLY** | Deep (55 experiments) |

**Result:** 15 experiments across domains, 50 experiments on math alone.

### Why This Matters

Math has **unique properties** that may make it especially hard for judges:

1. **Objective verification:** 16 - 3 - 4 = 9 is provably correct
2. **Step-by-step reasoning:** One error breaks the chain
3. **Numeric precision:** No room for "close enough"
4. **Verifiable ground truth:** Can check every calculation

**Other domains might be different:**

| Domain | Properties | Why Judges Might Work Better |
|--------|-----------|------------------------------|
| **Code (HumanEval)** | Executable, testable | Spotting bugs easier than writing bug-free code |
| **Knowledge (MMLU)** | Multiple choice, categorical | Pattern matching easier than generation |
| **Science (GPQA)** | Conceptual, explanatory | Evaluation different from generation |
| **Creative writing** | Subjective, aesthetic | Judging quality easier than producing quality |

### The Overclaim Risk

Current docs state **universally**: "NEVER use judge-based ensembles"

But evidence is **narrow**: Only proven for math problems.

**This violates scientific integrity:**
- Can't generalize math findings to code, knowledge, or subjective tasks
- May miss domains where judge-based ensembles actually work
- Overclaims can mislead users

---

## Research Questions

### Primary Question

**Do judge failures generalize beyond math?**

**Three possible outcomes:**

1. **Universal failure:** Judges fail on all benchmarks
   - → Problem is architectural (evaluation fundamentally harder than generation)
   - → "Never use judge-based ensembles" is valid

2. **Math-specific failure:** Judges only fail on GSM8K
   - → Problem is domain-specific (math has unique properties)
   - → Recommendation should be: "Don't use judges for math, but consider for other domains"

3. **Task-specific variation:** Judges fail on some, succeed on others
   - → Need nuanced recommendations per task type
   - → Some domains benefit, others don't

### Secondary Questions

1. **Is math uniquely hard for judges?**
   - Compare GSM8K performance deltas vs other benchmarks
   - Measure if math has larger negative deltas

2. **Does correctness-based prompting help anywhere?**
   - E18 vs E1 across all benchmarks
   - Test if prompt engineering works on non-math tasks

3. **Which benchmark types favor judges?**
   - Code: Bug-spotting vs generation
   - Knowledge: Pattern matching vs reasoning
   - Science: Conceptual evaluation vs creation

---

## Experimental Design

### Benchmarks (4 total)

| Benchmark | Size | Type | Ground Truth | Why Include |
|-----------|------|------|--------------|-------------|
| **GSM8K** | 100 | Math problems | Numeric | Baseline (known to fail) |
| **MMLU** | 100 | Multiple choice | Categorical (A/B/C/D) | Test knowledge/pattern matching |
| **HumanEval** | 50 | Code generation | Executable tests | Test bug-spotting vs writing |
| **GPQA** | 50 | Graduate science | Conceptual | Test hard reasoning |

**Total prompts:** 300 across 4 benchmarks

### Experiments (3 methods)

| Experiment | Method | Config | Tests |
|------------|--------|--------|-------|
| **E18** | Correctness vote | 3 proposers + correctness judge | Does explicit correctness help vote? |
| **E19** | Correctness best-of-N | 5 samples + correctness judge | Does it help sample selection? |
| **E20** | Two-stage | Agreement → correctness | Does hybrid approach work? |

**Same as Phase 3, but across all 4 benchmarks.**

### Runs & Statistical Validity

- **3 runs per experiment × benchmark**
- **Total experiments:** 3 methods × 4 benchmarks × 3 runs = **36 experiments**
- Same as Phase 2-3 methodology (enables statistical comparison)

### Evaluation

Each benchmark uses **domain-specific evaluators** (already implemented in `benchmarks/evaluators.py`):

```python
# GSM8K: Numeric extraction + comparison
evaluate_gsm8k(model_answer, ground_truth)

# MMLU: Letter extraction (A/B/C/D) + match
evaluate_mmlu(model_answer, ground_truth, choices)

# HumanEval: Code extraction + test execution
evaluate_humaneval(model_answer, test_cases)

# GPQA: Concept matching (need to implement)
evaluate_gpqa(model_answer, correct_answer)
```

---

## Cost & Time Estimates

### Per-Benchmark Costs

| Experiment | Prompts | Cost/Run | Runs | Total |
|------------|---------|----------|------|-------|
| **GSM8K-100** | 100 | $6 (E18), $8 (E19/E20) | 3 | $18-24 |
| **MMLU-100** | 100 | $6 (E18), $8 (E19/E20) | 3 | $18-24 |
| **HumanEval-50** | 50 | $3 (E18), $4 (E19/E20) | 3 | $9-12 |
| **GPQA-50** | 50 | $3 (E18), $4 (E19/E20) | 3 | $9-12 |

### Total Costs

| Experiment | Total Cost (4 benchmarks × 3 runs) |
|------------|-------------------------------------|
| **E18** | ~$72 |
| **E19** | ~$96 |
| **E20** | ~$96 |
| **TOTAL** | **~$264** |

### Time Estimates

| Benchmark | E18 | E19 | E20 | Total/Benchmark |
|-----------|-----|-----|-----|-----------------|
| **GSM8K-100** | 3h | 3h | 4.5h | 10.5h |
| **MMLU-100** | 3h | 3h | 4.5h | 10.5h |
| **HumanEval-50** | 1.5h | 1.5h | 2h | 5h |
| **GPQA-50** | 1.5h | 1.5h | 2h | 5h |

**Total time:** ~31h (but benchmarks can run sequentially, not in parallel due to rate limits)

**Wall-clock time with sequential execution:** ~40-45 hours (~2 days)

---

## Success Criteria

### Scenario A: Universal Failure (Architectural Problem)

**Evidence:**
- All benchmarks show judges worse than baseline (>2% degradation)
- GSM8K and other benchmarks have similar negative deltas
- No task type shows improvement

**Conclusion:**
- Problem is **architectural**: Evaluation is fundamentally harder than generation
- Hypothesis 2 remains **DEFINITIVELY REJECTED**
- Recommendation: "Never use judge-based ensembles" is **valid universally**

**Why:**
- Same model performing worse as judge across ALL domains
- Consistent 10-15% performance penalty regardless of task type
- No amount of prompt engineering helps

### Scenario B: Math-Specific Failure (Domain Problem)

**Evidence:**
- GSM8K shows large negative delta (>10%)
- MMLU/HumanEval/GPQA show neutral or positive deltas
- Judge performance better on non-math tasks

**Conclusion:**
- Problem is **math-specific**: Verification harder than other domains
- Hypothesis 2 is **PARTIALLY REJECTED** (fails on math, not elsewhere)
- Recommendation: "Don't use judges for math, consider for code/knowledge/subjective"

**Why:**
- Math requires precise step-by-step verification
- Other tasks allow pattern matching, heuristic evaluation
- Different cognitive skills for generation vs evaluation by domain

### Scenario C: Task-Specific Variation (Nuanced)

**Evidence:**
- Mixed results across benchmarks
- Some show improvement (code, knowledge), some fail (math, science)
- Pattern depends on task properties

**Conclusion:**
- Need **nuanced recommendations** per task type
- Some domains benefit from judges, others don't
- Consider: Is evaluation easier than generation for this specific task?

**Factors:**
- Bug-spotting (code) vs writing bug-free code
- Multiple choice pattern matching vs reasoning
- Subjective quality evaluation vs creative production

---

## Implementation

### Files Created

```
run_e18_multi_benchmark.py       (210 lines)
  └─ E18 across 4 benchmarks
  └─ Uses evaluate_benchmark() for domain-specific eval

run_e19_multi_benchmark.py       (210 lines)
  └─ E19 across 4 benchmarks
  └─ Same evaluation logic

run_e20_multi_benchmark.py       (210 lines)
  └─ E20 across 4 benchmarks
  └─ Same evaluation logic

run_e18_e20_multi_all.sh         (executable)
  └─ Master script: 36 experiments
  └─ Sequential execution with progress tracking

analyze_multi_benchmark.py       (300 lines)
  └─ Cross-benchmark comparison
  └─ Tests 3 research questions
  └─ Generates findings report
```

### How to Run

```bash
# Set AWS credentials
export AWS_BEARER_TOKEN_BEDROCK="your_token"

# Run all experiments (~40h, ~$264)
bash run_e18_e20_multi_all.sh

# Or run individual benchmarks
python3 run_e18_multi_benchmark.py --benchmark gsm8k --run 1
python3 run_e18_multi_benchmark.py --benchmark mmlu --run 1
# ... etc

# Analyze results
python3 analyze_multi_benchmark.py
```

### Results Location

```
results/phase3_multi/
  e18_gsm8k_run1.json
  e18_gsm8k_run2.json
  e18_gsm8k_run3.json
  e18_mmlu_run1.json
  ...
  e20_gpqa_run3.json
  analysis_summary.json
```

---

## Analysis Plan

### Step 1: Per-Benchmark Analysis

For each benchmark (GSM8K, MMLU, HumanEval, GPQA):

1. Load E18-E20 results (3 runs each)
2. Calculate mean ± std accuracy
3. Compare to baseline (Opus solo)
4. Determine: Better / Same / Worse

**Output:** Table per benchmark showing deltas

### Step 2: Cross-Benchmark Comparison

1. **Question 1:** Do judges fail on ALL benchmarks?
   - If yes → Universal failure (architectural)
   - If no → Domain-specific

2. **Question 2:** Is math uniquely hard?
   - Compare GSM8K deltas vs others
   - Test if math shows larger negative deltas

3. **Question 3:** Does correctness prompting help?
   - E18 vs E1 comparison
   - Test across all benchmarks

**Output:** Answers to 3 research questions

### Step 3: Pattern Identification

Look for patterns:
- Which benchmarks favor judges?
- Which task properties correlate with success/failure?
- Can we predict when judges will work?

**Properties to consider:**
- Objective vs subjective
- Verifiable ground truth vs judgment call
- Step-by-step reasoning vs holistic evaluation
- Numeric precision vs categorical/qualitative

### Step 4: Recommendation Update

Based on findings, update recommendations:

**If universal failure:**
- Keep "Never use judge-based ensembles"

**If math-specific:**
- "Avoid judges for math, consider for code/knowledge/creative"

**If task-specific:**
- Nuanced guidelines per domain
- Decision tree: When to use judges?

---

## Expected Insights

### Insight 1: Evaluation Difficulty by Domain

**Hypothesis:** Evaluation difficulty varies by domain.

**Test:**
- Math: Verification requires recalculating (hard)
- Code: Bug-spotting pattern matching (easier?)
- Knowledge: Multiple choice comparison (easier?)
- Science: Conceptual evaluation (hard)

**Measure:** Compare judge performance deltas across domains.

### Insight 2: Ground Truth Types Matter

**Hypothesis:** Ground truth type affects judge performance.

| Type | Examples | Judge Difficulty |
|------|----------|------------------|
| **Numeric** | GSM8K (72 vs 73) | High (requires calculation) |
| **Categorical** | MMLU (A vs B vs C) | Medium (pattern matching) |
| **Executable** | HumanEval (tests pass/fail) | Low? (clear criteria) |
| **Conceptual** | GPQA (explanation quality) | High (requires understanding) |

**Measure:** Correlate ground truth type with judge success.

### Insight 3: When Evaluation ≠ Generation

**Key question:** When is judging a different skill than generating?

**Examples where they might differ:**
- **Code review:** Spotting bugs ≠ writing bug-free code
- **Essay grading:** Judging quality ≠ writing quality essays
- **Safety filtering:** Detecting harm ≠ generating harmful content

**Measure:** Which benchmarks show this property? Do judges work better there?

---

## Next Steps After Results

### 1. Update Documentation

Based on findings, update:
- **BLOG.md:** Add multi-benchmark findings section
- **README.md:** Revise recommendations with domain nuance
- **E18_E20_CRITICAL_FINDINGS.md:** Add cross-domain analysis

### 2. Revise Recommendations

Create domain-specific guidelines:

```markdown
## When to Use Judge-Based Ensembles

### ✗ Don't Use For:
- Math problems (verification as hard as generation)
- [Other domains found to fail]

### ✓ Consider For:
- Code review (if bug-spotting easier than writing)
- [Other domains found to succeed]

### ⚠️ Test First For:
- [Domains with mixed results]
```

### 3. Additional Research (Optional)

If patterns unclear:
- Test creative/subjective tasks (essay writing, story generation)
- Test safety/content moderation (easier evaluation?)
- Test more benchmarks to build decision tree

---

## Risk Mitigation

### What if baselines are wrong?

**Problem:** Assumed baselines (MMLU: 75%, HumanEval: 65%, GPQA: 55%) may be incorrect.

**Solution:**
1. Run Opus solo baseline on all benchmarks first (low cost)
2. Use actual baselines for comparison
3. Add baseline measurement to master script

### What if results are noisy?

**Problem:** 3 runs may show high variance on smaller benchmarks.

**Solution:**
- Use statistical tests (t-tests) to determine significance
- Flag high-variance results as "unclear"
- Consider 5 runs if needed (but costly)

### What if code execution fails (HumanEval)?

**Problem:** `evaluate_humaneval()` executes untrusted code.

**Solution:**
- Already has timeout (5 seconds)
- Already has restricted namespace
- Runs in isolated process
- If still risky, consider containerization

---

## Summary

| Aspect | Value |
|--------|-------|
| **Motivation** | Test if judge failures generalize beyond math |
| **Scope** | 4 benchmarks (GSM8K, MMLU, HumanEval, GPQA) |
| **Experiments** | E18-E20 × 4 benchmarks × 3 runs = 36 total |
| **Cost** | ~$264 |
| **Time** | ~40-45 hours |
| **Key Question** | Universal failure or domain-specific? |
| **Impact** | Determines validity of "never use judges" recommendation |

**Status:** ✅ Implementation complete, ready to run

**Command to execute:**
```bash
export AWS_BEARER_TOKEN_BEDROCK="your_token"
bash run_e18_e20_multi_all.sh
```

---

*Created: 2026-04-13*  
*Ready for execution upon user approval*
