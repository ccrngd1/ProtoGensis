# T-V3 Verification Complete - Thinking Mode Discrepancy Analysis

**Date:** April 11, 2026  
**Task:** T-V3 - Compare GSM8K-20 vs GSM8K-100 Prompt IDs  
**Status:** ✅ COMPLETE  
**Finding:** 🔴 **GSM8K-20 accuracy claims (100% thinking, 85% fast) are UNVERIFIED due to extraction bug**

---

## Executive Summary

**BLOG.md claims:**
- GSM8K-20: opus-thinking = 100%, opus-fast = 85%
- GSM8K-100: opus-fast = 89.7%

**What we found:**
1. ✅ GSM8K-20 is EXACTLY the first 20 prompts of GSM8K-100
2. ❌ GSM8K-20 pilot results have same extraction bug (full text, not numbers)
3. ❌ Accuracy calculations for 100% and 85% are UNVERIFIED
4. ❓ Claimed thinking mode superiority on math is UNSUPPORTED by data

**This is the SAME extraction bug as Phase 2 self-consistency (T-V1).**

---

## Prompt ID Verification ✅

### GSM8K-20 Pilot
- **File:** `prompts/gsm8k_pilot_20.json`
- **Prompt IDs:** gsm8k_001 through gsm8k_020
- **Count:** 20 prompts

### GSM8K-100 Phase 2
- **File:** `results/phase2/gsm8k_100_selfcons_run1.json`
- **Prompt IDs:** gsm8k_001 through gsm8k_100
- **Count:** 100 prompts

### Relationship
✅ **GSM8K-20 is EXACTLY the first 20 prompts of GSM8K-100** (sequential subset)

**Implication:** Any accuracy difference between the two is NOT due to different prompt selection. They're comparable datasets (subset vs full set).

---

## Extraction Bug in GSM8K-20 Pilot ❌

### Pilot Response File
**File:** `results/benchmarks/gsm8k/pilot_responses.json`

Contains responses for:
- opus-fast
- opus-thinking

### Example Response

**Ground truth:** `"18"` (numeric)

**Opus-fast answer field:**
```
"Janet's ducks lay 16 eggs per day. She eats 3 for breakfast and 
uses 4 for baking muffins, so she uses 3 + 4 = 7 eggs per day. 
The remainder is 16 - 7 = 9 eggs. She sells these at $2 per egg, 
so she makes 9 × $2 = $18 per day at the farmers' market."
```

**Problem:** Answer contains full explanation, not extracted number `"18"`

### Accuracy Calculation Impact

**Attempted calculation with buggy data:**
```python
answer = "Janet's ducks lay... $18 per day"  # Full text
truth = "18"                                   # Number only
if answer == truth:  # FALSE
    correct += 1
```

**Result:** 0% accuracy (both models) → Simple string comparison fails

**Reality:** Either:
1. Accuracies were calculated MANUALLY (reviewing 20 responses by hand)
2. Accuracies were calculated with DIFFERENT extraction logic (not in repo)
3. Accuracies are WRONG and need recalculation

---

## Impact on BLOG.md Claims

### Claim 1: "GSM8K shows thinking helps on math"

**BLOG.md line 222:**
> GSM8K | Math reasoning | 20 | opus-thinking | 100% | 85% (-15%) | 40% (-60%) | ❌ Individual

**Status:** ❌ UNVERIFIED

**Reason:**
- Pilot results have extraction bug (full text, not numbers)
- Cannot calculate 100% and 85% from data in repo
- Either manually scored or calculation logic missing
- Needs verification

### Claim 2: "Thinking mode is context-dependent"

**BLOG.md line 230:**
> ✅ Helps on math (GSM8K: thinking 100% vs fast 85%)

**Status:** ❌ UNSUPPORTED

**Reason:** Based on unverified 100% claim

### Claim 3: "What this study doesn't prove"

**BLOG.md line 571:**
> That thinking mode is useless for ALL tasks (GSM8K shows thinking helps on math - opus-thinking 100% vs opus-fast 85%)

**Status:** ❌ UNSUBSTANTIATED

**Reason:** Cannot prove thinking helps on math with unverified data

---

## Why The Discrepancy Doesn't Matter (Yet)

The original question was: **Why does opus-fast score 85% on GSM8K-20 but 89.7% on GSM8K-100?**

**Answer:** We can't answer this because the 85% is unverified.

**What we DO know:**
1. GSM8K-20 is the first 20 of GSM8K-100 (same prompts)
2. Both have extraction bugs (full text answers)
3. GSM8K-100 Phase 2 reports 89.7% (but may also be wrong if calculated from buggy data)
4. GSM8K-20 reports 85% and 100% (unverifiable from current data)

**Until extraction is fixed, all GSM8K accuracy claims are suspect.**

---

## Root Cause Analysis

### The Pattern Across Both Tests

| Test | File | Models | Extraction Bug? |
|------|------|--------|-----------------|
| GSM8K-20 pilot | `results/benchmarks/gsm8k/pilot_responses.json` | opus-fast, opus-thinking | ✅ YES (full text) |
| GSM8K-100 Phase 2 | `results/phase2/gsm8k_100_selfcons_run*.json` | self-consistency | ✅ YES (full text) |

**Same bug in both places.**

### Why This Happened

**Hypothesis:** The codebase was built for multi-choice benchmarks (MMLU) where answers are letters (A, B, C, D), then adapted for math benchmarks (GSM8K) but numeric extraction was never implemented.

**Evidence:**
- MMLU responses likely work fine (comparing letters)
- GSM8K responses fail (need number extraction)
- Code stores full response text as "answer"

---

## What Needs To Happen

### Priority 1: Fix Extraction (Blocks All Math Benchmarks)

**Affected:**
- GSM8K-20 pilot (100% and 85% claims)
- GSM8K-100 Phase 2 (89.7% baseline, self-consistency results)
- Any other math benchmarks

**Action:**
1. Implement numeric answer extraction
2. Re-calculate accuracies from existing response data
3. OR re-run experiments with fixed extraction

### Priority 2: Verify GSM8K-20 Accuracies

**Options:**

**Option A: Manual Review**
- Review 20 × 2 = 40 responses by hand
- Extract numeric answers manually
- Calculate actual accuracies
- **Time:** 1-2 hours
- **Cost:** $0

**Option B: Fix + Auto-Extract**
- Fix extraction logic
- Re-run extraction on pilot_responses.json
- Calculate accuracies automatically
- **Time:** 1-2 hours (coding)
- **Cost:** $0 (using existing data)

**Option C: Re-run Pilot**
- Re-run GSM8K-20 with fixed extraction
- Get clean results
- **Time:** 1 hour runtime
- **Cost:** ~$5 (20 prompts × 2 models × 2 runs)

### Priority 3: Update BLOG.md

**If 100% thinking claim is WRONG:**
- Remove "thinking helps on math" claim
- Remove GSM8K from benchmark table
- Revise "context-dependent" finding
- Add limitation: "Math benchmarks need re-verification"

**If 100% thinking claim is CORRECT:**
- Keep claims as-is
- Add note about manual verification
- Document extraction bug and fix

---

## Recommended Action

**Implement Option B: Fix extraction, re-calculate from existing data**

**Rationale:**
- Fastest path to verification ($0, 1-2 hours)
- Uses existing response data
- Can validate both GSM8K-20 and GSM8K-100 at once
- If correct, no BLOG changes needed
- If wrong, clear path to fix

**Implementation:**
1. Write numeric extraction function
2. Load pilot_responses.json and phase2 results
3. Extract numeric answers from all responses
4. Compare with ground truth
5. Report actual accuracies
6. Document findings

**Deliverable:** 
- `extract_gsm8k_accuracy.py` script
- Verified accuracies for all GSM8K tests
- Updated claims in BLOG.md (if needed)

---

## T-V3 Completion Checklist

- ✅ Loaded GSM8K-20 pilot prompts
- ✅ Loaded GSM8K-100 Phase 2 results
- ✅ Compared prompt IDs
- ✅ Confirmed GSM8K-20 is first 20 of GSM8K-100
- ✅ Checked pilot response data
- ✅ Identified extraction bug in pilot
- ✅ Attempted accuracy calculation (failed due to bug)
- ✅ Documented impact on BLOG claims
- ✅ Recommended fix approach

---

## Next Phase 0 Task

- ✅ T-V1: Self-consistency extraction (COMPLETE - BUG CONFIRMED)
- ✅ T-V2: Sample counts (COMPLETE - CORRECT)
- ✅ T-V3: GSM8K-20 vs GSM8K-100 (COMPLETE - UNVERIFIED ACCURACIES)
- ⬜ T-V4: Temperature settings

---

## Key Insight

**The extraction bug affects ALL GSM8K claims in this project:**
- Phase 1 pilot (100% thinking, 85% fast)
- Phase 2 baseline (89.7% fast)
- Phase 2 self-consistency (all results)

**Until extraction is fixed and re-calculated, NO GSM8K accuracy claims are reliable.**

This is even more critical than initially thought (T-V1). It's not just self-consistency that's broken — it's the entire GSM8K benchmark validation.

---

## Bottom Line

**You claimed thinking mode helps on math (100% vs 85% on GSM8K).**

**But:** The data has an extraction bug. The 100% and 85% accuracies cannot be verified from current data.

**Action:** Fix extraction, recalculate, verify the claim is true before publishing.

**Impact:** If claim is wrong, loses "thinking is context-dependent" finding.

---

*T-V3 completed April 11, 2026*  
*Estimated time: 30 minutes*  
*Verification script: `verify_thinking_mode_discrepancy.py`*  
*Recommendation: Fix extraction and recalculate all GSM8K accuracies*
