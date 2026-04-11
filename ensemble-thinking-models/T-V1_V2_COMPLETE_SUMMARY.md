# T-V1 & T-V2 Verification Complete - Self-Consistency Extraction Bug

**Date:** April 11, 2026  
**Tasks:** T-V1 (Answer Extraction) + T-V2 (Sample Counts)  
**Status:** ✅ COMPLETE  
**Finding:** 🔴 **CRITICAL BUG CONFIRMED - 100% of answers use full text instead of numbers**

---

## Executive Summary

**The self-consistency implementation does NOT extract numeric answers from GSM8K responses.**

- **100% of selected_answer fields contain full text explanations** (not numbers)
- **Expected:** `"18"` or `"18.0"`
- **Actual:** `"Let me work through this step-by-step... **$18**"`

**This invalidates all Phase 2 self-consistency claims** about proving that "even proven methods fail."

---

## What Was Checked (T-V1)

### Files Analyzed
- `results/phase2/gsm8k_100_selfcons_run1.json` (100 prompts)
- `results/phase2/gsm8k_100_selfcons_run2.json` (100 prompts)
- `results/phase2/gsm8k_100_selfcons_run3.json` (100 prompts)

### Extraction Analysis
```
Total prompts: 300
Numeric answers:    0 (0.0%)  ❌
Full-text answers:  300 (100.0%)  ❌
```

**Every single selected_answer contains full explanation text, not extracted numbers.**

---

## Examples of the Bug

### Prompt 0 (Egg Problem)

**Expected answer:** `"18"`

**Actual selected_answer:**
```
Let me work through this step-by-step.

**Eggs laid per day:** 16

**Eggs used:**
- Breakfast: 3
- Muffins: 4
- Total used: 3 + 4 = 7

**Eggs remaining to sell:** 16 - 7 = 9

**Daily earnings:** 9 × $2 = **$18**
```

**Problem:** Voting algorithm should compare numeric answers (`"18"`, `"18.0"`, `"$18"`), not full text paragraphs.

### Prompt 1 (Fiber Problem)

**Expected answer:** `"3"`

**Actual selected_answer:**
```
To find the total bolts of fiber needed:

- **Blue fiber:** 2 bolts
- **White fiber:** Half of 2 bolts = 1 bolt

**Total:** 2 + 1 = **3 bolts**
```

**Problem:** Different phrasing of the same explanation would count as different "answers" in voting.

---

## Why This Is Critical

### Self-Consistency Voting Requires Extracted Answers

**The algorithm:**
1. Generate 5 responses for each prompt
2. Extract final numeric answer from each response
3. Vote on most common numeric answer
4. Report selected answer and agreement rate

**What's happening:**
1. Generate 5 responses ✅
2. Extract answer? ❌ **SKIPPED - storing full text**
3. Vote on... full text paragraphs? ❌ **BROKEN**
4. Report full text as "selected answer" ❌ **USELESS**

### Agreement Rates Are Meaningless

If the code is comparing full text strings:
- **Different phrasing = different "answers"** even if numeric answer is same
- **Agreement rates likely artificially low**
- **Cannot determine actual numeric consensus**

Example:
- Response 1: "The answer is $18"
- Response 2: "Therefore: 18 dollars"
- Response 3: "Final result: 18"

**Same numeric answer (18), different text → algorithm sees 3 different answers → 20% agreement**

---

## Impact on Published Claims

### BLOG.md Claims (Phase 2)

**Claim 1:** "Self-consistency (proven method) failed to improve results"
- **Status:** ❌ UNVERIFIED
- **Reason:** Cannot determine if self-consistency worked without proper answer extraction

**Claim 2:** "Agreement rates showed X% consistency"
- **Status:** ❌ INVALID
- **Reason:** Comparing full text, not numeric answers

**Claim 3:** "Accuracy on GSM8K: X%"
- **Status:** ❌ UNCLEAR
- **Reason:** How was accuracy calculated if answers aren't numbers?

### What We DON'T Know

- ❓ Did self-consistency actually improve accuracy?
- ❓ What were the real agreement rates?
- ❓ How did it compare to baseline Opus-fast?
- ❓ Did it beat 89.7% baseline (GSM8K-20)?

**Bottom line:** Phase 2 results are unreliable until bug is fixed and experiment re-run.

---

## Sample Count Verification (T-V2) ✅

### What Was Checked

Verified that correct number of API calls were made for self-consistency:
- 5 samples per prompt
- 100 prompts per run
- 3 runs total
- **Expected:** 5 × 100 × 3 = 1,500 API calls
- **Actual:** 1,500 samples generated, aggregated to 300 results (100 per run)

**Verdict:** ✅ Sample counts are correct. The experiment was executed properly, just with buggy extraction logic.

---

## Root Cause Analysis

### Where Is The Bug?

Need to check `aggregators/self_consistency.py` or similar extraction code.

**Expected logic:**
```python
def extract_numeric_answer(response):
    """Extract final numeric answer from GSM8K response."""
    # Look for patterns like:
    # - "**$18**"
    # - "Final answer: 18"
    # - "Therefore, 18 dollars"
    
    # Extract just the number: "18"
    pass
```

**What's likely happening:**
```python
selected_answer = most_common_response  # Bug: storing full response text
```

### Why Did This Happen?

**Hypothesis:** The self-consistency implementation was copied from a different benchmark where full-text voting makes sense (e.g., multiple-choice where answers are letters A/B/C/D).

For GSM8K (math word problems), numeric extraction is REQUIRED but was likely missed.

---

## Impact Assessment

### Priority: 🔴 CRITICAL

**Blocks publication?** YES, if claiming "self-consistency fails" based on these results

**Affects:** Phase 2 headline finding ("even proven methods fail")

**Cost to fix:** ~$17 to re-run (5 samples × 100 prompts × 3 runs × $0.0001/call)

### What Needs To Happen

1. **Fix extraction logic** (1-2 hours development)
   - Add numeric answer extraction
   - Test on sample responses
   - Verify extraction works correctly

2. **Re-run experiments** (~$17, 2-3 hours)
   - 3 runs × 100 prompts × 5 samples = 1,500 API calls
   - Same config as original

3. **Update documentation** (1-2 hours)
   - Recalculate accuracy
   - Recalculate agreement rates
   - Update BLOG.md Phase 2 section
   - Update PHASE2_RESULTS.md

**Total: ~5-7 hours + $17**

---

## Options for Response

### Option 1: Fix & Re-Run (Recommended)

**Action:**
1. Fix `aggregators/self_consistency.py` to extract numeric answers
2. Re-run 3 × GSM8K-100 self-consistency experiments
3. Recalculate all metrics
4. Update documentation with correct results

**Pros:**
- Validates or refutes "self-consistency fails" claim
- Proper implementation of proven method
- Relatively cheap ($17)

**Cons:**
- ~5-7 hours of work
- Might show self-consistency DOES work (contradicts current narrative)

### Option 2: Remove Self-Consistency Claims

**Action:**
1. Remove Phase 2 self-consistency section from BLOG.md
2. Acknowledge extraction bug in limitations
3. Focus on vote-based ensemble results (Phase 1)

**Pros:**
- No API costs
- Fast (1-2 hours documentation update)

**Cons:**
- Weakens Phase 2 findings
- Loses "even proven methods fail" angle
- Leaves question unanswered

### Option 3: Disclose Bug, Report As-Is

**Action:**
1. Add note in BLOG.md about extraction bug
2. Report results with caveat
3. Recommend future work to re-run properly

**Pros:**
- Transparent
- Fast (30 min documentation update)

**Cons:**
- Results are unreliable
- Undermines credibility
- Not publication-quality

---

## Recommended Action

**Implement Option 1: Fix & Re-Run**

**Rationale:**
- Self-consistency is a proven baseline method (Wei et al., 2022)
- Properly testing it is important for validity
- $17 is cheap for validation
- Could discover self-consistency DOES work → more interesting story
- Even if it fails (properly implemented), claim is much stronger

**Timeline:**
- Fix extraction: 1-2 hours (today)
- Re-run experiments: 2-3 hours runtime (today/tomorrow)
- Analyze results: 1 hour (tomorrow)
- Update docs: 1-2 hours (tomorrow)

**Total: 2-3 days** (can overlap with MOA documentation updates)

---

## Verification Checklist

### T-V1: Answer Extraction ✅

- ✅ Located Phase 2 self-consistency result files
- ✅ Checked `selected_answer` field format
- ✅ Analyzed 300 results across 3 runs
- ✅ Confirmed 100% use full text (not numbers)
- ✅ Created verification script: `verify_selfcons_extraction.py`
- ✅ Documented impact on claims

### T-V2: Sample Counts ✅

- ✅ Verified 5 samples per prompt (correct)
- ✅ Verified 100 prompts per run (correct)
- ✅ Verified 3 runs total (correct)
- ✅ Confirmed 1,500 total API calls (correct)
- ✅ Results properly aggregated (100 per run)

---

## Next Phase 0 Tasks

- ✅ T-V1: Answer extraction audit (COMPLETE - BUG CONFIRMED)
- ✅ T-V2: Sample count verification (COMPLETE - CORRECT)
- ⬜ T-V3: Compare GSM8K-20 vs GSM8K-100 prompt IDs
- ⬜ T-V4: Check temperature settings

---

## Deliverables

- ✅ `verify_selfcons_extraction.py` - Automated bug verification
- ✅ `T-V1_V2_COMPLETE_SUMMARY.md` - This document

**Next:** Fix extraction bug or move to T-V3/T-V4 verification tasks

---

## Key Quote for BLOG.md (If Fixing)

**Before fix:**
> "We tested self-consistency (5 samples per prompt, vote on most common answer) and found it failed to improve over baseline."

**After proper fix & re-run:**
> "We tested self-consistency (5 samples per prompt, vote on most common numeric answer) and found [RESULTS TBD - could show improvement, no change, or degradation]."

---

*T-V1 & T-V2 completed April 11, 2026*  
*Estimated time: 1 hour*  
*Verification script: `verify_selfcons_extraction.py`*  
*Recommendation: Fix extraction bug and re-run ($17, 5-7 hours total)*
