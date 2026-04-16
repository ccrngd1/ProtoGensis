# Results Version Notes

This document clarifies which version of experimental results is canonical and what corrections have been applied.

## Phase 2: Self-Consistency Results (GSM8K-100)

### Canonical Results

**Published accuracy: 93.3%** (correct)

The published accuracy is CORRECT. The bug only affected the `selected_answer` field storage, not the accuracy calculation.

### Files

**Original files (buggy `selected_answer` field):**
- `results/phase2/gsm8k_100_selfcons_run1.json`
- `results/phase2/gsm8k_100_selfcons_run2.json`
- `results/phase2/gsm8k_100_selfcons_run3.json`

**Fixed files (corrected `selected_answer` field):**
- `results/phase2/gsm8k_100_selfcons_run1_fixed.json`
- `results/phase2/gsm8k_100_selfcons_run2_fixed.json`
- `results/phase2/gsm8k_100_selfcons_run3_fixed.json`

### The Bug

**Problem:** `selected_answer` field stored full-text responses instead of extracted numeric answers.

**Example:**
- **Buggy:** `"selected_answer": "Let me work through this step-by-step.\n\n**Eggs laid per day:** 16..."`
- **Fixed:** `"selected_answer": "18"`

**Root cause:** Line 196 in `self_consistency.py` retrieved full answer from array:
```python
majority_answer = answers[answer_keys.index(majority_key)]
```

Should have been:
```python
extracted_majority = majority_key  # Use extracted key, not full answer
```

### Why Accuracy Was Correct

The vote counting used extracted keys:
```python
answer_keys = [self._extract_answer_key(ans, benchmark="numeric") for ans in answers]
vote_counts = Counter(answer_keys)
```

So the **voting logic** was correct (extracted "18", "18", "18", "18", "18" → majority "18").

Only the **storage** was wrong (stored full text instead of extracted key in `selected_answer`).

### Impact

**NO IMPACT on published results:**
- ✅ Accuracy: 93.3% (CORRECT)
- ✅ Vote counts: Correct
- ✅ Agreement rates: Correct
- ✅ Cost calculations: Correct

**ONLY AFFECTED:**
- ❌ `selected_answer` field contained full text (hard to read/compare)
- ❌ Manual inspection of results files difficult

### Fix Applied

**Date:** 2026-04-11

**Changes:**
1. Added `extracted_answer` field to `SelfConsistencyResult` dataclass
2. Store both full answer AND extracted key
3. Updated code to populate `extracted_answer` with numeric/MC key
4. Fixed files manually corrected to have numeric `selected_answer`

**For future experiments:** ALWAYS use `extracted_answer` for GSM8K evaluation, not `selected_answer`.

## Phase 3: Correctness-Based Judging (GSM8K-100)

### Canonical Results

**Published accuracy (corrected): E18=100%, E19=100%, E20=76.3%**

The initial analysis (April 13) incorrectly reported E18=74.8%, E19=79.1% due to string comparison bug.

### Files

**Published results (correct):**
- `results/phase3_multi/e18_gsm8k_run[1-3].json`
- `results/phase3_multi/e19_gsm8k_run[1-3].json`
- `results/phase3_multi/e20_gsm8k_run[1-3].json`

### The Bug

**Problem:** Analysis script used string comparison instead of numeric evaluation.

**Example:**
- Ground truth: `"70000"`
- Judge extracted: `"$70,000"`
- String comparison: `"70000" != "$70,000"` → ❌ WRONG
- Numeric comparison: `70000 == 70000` → ✅ CORRECT

**Root cause:** Initial analysis used:
```python
if vote_result.final_answer_extracted == prompt['ground_truth']:
    is_correct = True
```

Should have used:
```python
is_correct = evaluate_gsm8k(prompt, vote_result.final_answer_extracted)
```

### Impact

**INCORRECT initial report (April 13):**
- E18: 74.8% (25% underestimate)
- E19: 79.1% (21% underestimate)

**CORRECTED report (April 13, same day):**
- E18: 100% (CORRECT)
- E19: 100% (CORRECT)

**Published results (April 14, multi-benchmark expansion):**
- Use corrected 100% for GSM8K math results
- All BLOG.md and README.md references updated

### Fix Applied

**Date:** 2026-04-13 (same day as initial analysis)

**Changes:**
1. Re-ran evaluation using numeric extraction (`evaluate_gsm8k()`)
2. Updated all documentation with corrected 100% accuracy
3. Changed conclusion from "judges fail" to "judges excel at math"
4. Expanded to multi-benchmark to test generalization

## Phase 3B: Multi-Benchmark Results

### Canonical Results

**Published results (correct):**
- GSM8K: E18=100%, E19=100%, E20=76.3%
- MMLU: E18=87.1%, E19=87.7%, E20=73.1%
- HumanEval: E18=50%, E19=50%, E20=50%
- GPQA: E18=57.3%, E19=60.0%, E20=53.3%

### Files

**All correct from first run:**
- `results/phase3_multi/e18_[benchmark]_run[1-3].json`
- `results/phase3_multi/e19_[benchmark]_run[1-3].json`
- `results/phase3_multi/e20_[benchmark]_run[1-3].json`

**Baseline measurements:**
- `results/baselines/baseline_[benchmark]_run[1-3].json`

**No bugs in multi-benchmark results.** All experiments used correct evaluation from the start.

## Summary: Which Files to Use

### For Accuracy Calculations

**Phase 2 (Self-consistency):**
- Use: Original `gsm8k_100_selfcons_run[1-3].json`
- Accuracy: 93.3% (CORRECT in original files)
- Note: `selected_answer` field is buggy but vote_counts are correct

**Phase 3A (GSM8K correctness-based):**
- Use: `results/phase3_multi/e[18-20]_gsm8k_run[1-3].json`
- Re-evaluate with: `evaluate_gsm8k()` numeric extraction
- Accuracy: E18=100%, E19=100%, E20=76.3%

**Phase 3B (Multi-benchmark):**
- Use: `results/phase3_multi/` all files
- Use: `results/baselines/` for baseline comparisons
- All correct from first run

### For Answer Inspection

**Phase 2 (Self-consistency):**
- Use: Fixed `gsm8k_100_selfcons_run[1-3]_fixed.json`
- Has numeric `selected_answer` field for easy reading

**Phase 3+:**
- Use: Original files (no fixes needed)

## Verification

Run regression tests to verify bug fixes:

```bash
# Test self-consistency extraction
python3 tests/test_selfcons_extraction.py

# Expected output:
# ✅ ALL REGRESSION TESTS PASSED
```

Verify Phase 2 results haven't been corrupted:

```bash
# Check original files have correct accuracy (despite buggy selected_answer)
python3 -c "
import json

for run in [1, 2, 3]:
    data = json.load(open(f'results/phase2/gsm8k_100_selfcons_run{run}.json'))
    # Note: original files don't have 'accuracy' field, calculate from vote_counts
    print(f'Run {run}: Use vote_counts to verify correctness')
    print(f'  First result vote_counts: {data[\"results\"][0][\"vote_counts\"]}')
"
```

## Questions?

See `CHANGELOG.md` for full bug history and fixes.

For Phase 3 multi-benchmark methodology, see `analyze_multi_benchmark.py`.
