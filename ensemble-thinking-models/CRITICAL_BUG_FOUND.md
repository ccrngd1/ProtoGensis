# 🚨 CRITICAL BUG: Self-Consistency Answer Extraction

> **⚠️ HISTORICAL DOCUMENT**  
> This file documents the bug discovery process (April 11, 2026).  
> **Status:** ✅ RESOLVED (see BUGFIX_SUMMARY.md)  
> References to 86.7% are initial buggy reports. **Corrected result: 93.3%**  
> For current documentation, see BLOG.md, README.md, and CHANGELOG.md

**Discovered:** April 11, 2026  
**Severity:** CRITICAL - Invalidates Phase 2 self-consistency findings  
**Source:** DEVILS_ADVOCATE_REVIEW_2.md Issue #1 prediction confirmed  
**Resolution:** Fixed April 11, 2026 - accuracy calculations were correct (93.3%), only storage was buggy

---

## The Bug

**File:** `aggregators/self_consistency.py` line 69

**Code:**
```python
def _extract_answer_key(self, answer: str) -> str:
    # Try to extract multiple choice letter FIRST (for MMLU, GPQA)
    mc_match = re.search(r'\b([A-D])\b', answer.upper())
    if mc_match:
        return mc_match.group(1)  # ← BUG: Returns letter
    
    # Try to extract number (for GSM8K, numeric answers)
    numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', answer)
    if numbers:
        return numbers[-1].replace(',', '')
```

**Problem:** On GSM8K (numeric math benchmark), the regex `\b([A-D])\b` matches:
- The article "**a**" in common phrases like "a week", "a total", "a day"
- Letter identifiers in reasoning: "Method A", "Step B", "Formula C"
- Any standalone A-D letter in the reasoning text

When uppercased, these become 'A', 'B', 'C', 'D' and get extracted **instead of** the numeric answer.

---

## Evidence

**Tested on actual Phase 2 data:**

```bash
$ grep vote_counts results/phase2/gsm8k_100_selfcons_run1.json | grep '"[A-D]"' | wc -l
16  # out of 100 prompts
```

**Impact by run:**
- Run 1: **16/100 prompts (16%)** extracted letters instead of numbers
- Run 2: **15/100 prompts (15%)** extracted letters instead of numbers  
- Run 3: **15/100 prompts (15%)** extracted letters instead of numbers

**Example from gsm8k_004:**
```
Question: "James runs 3 sprints 3 times a week. He runs 60 meters each sprint. How many meters does he run a week?"
Correct answer: 540

Model response: "3 sprints × 60 meters × 3 times a week = **540 meters**"
                                              ↑
Regex matched: 'A' from "a week"
Extracted key: 'A' (WRONG - should be '540')
Vote counts: {'A': 5}  (all 5 samples extracted 'A')
```

---

## Impact on Phase 2 Findings

### Self-Consistency Results (Current, Potentially Invalid)

| Run | Accuracy | Status |
|-----|----------|--------|
| Run 1 | 87/100 = 87% | 16 prompts affected |
| Run 2 | 87/100 = 87% | 15 prompts affected |
| Run 3 | 86/100 = 86% | 15 prompts affected |
| **Mean** | **86.7%** | **15-16% affected** |

**vs Baseline:** 86.7% vs 89.7% = **-3.0% difference**

### Potential Impact

**Reviewer's prediction:**
> "If even 3-4 out of 100 prompts had miskeyed answers, that accounts for the entire 3% self-consistency penalty."

**Actual:** 15-16 prompts affected per run (15-16%)

**Worst case:** If all 15-16 mis-extracted answers were actually correct, the true accuracy could be:
- Run 1: 87 + 16 = 103/100 → obviously impossible, so some were legitimately wrong
- But if even 3-4 were actually correct, that's 90-91% → **ties or beats baseline**

**Best case:** All 15-16 letter extractions were from genuinely wrong answers → 86.7% is accurate

**Unknown:** How many of the letter-extracted answers were actually correct vs wrong?

---

## Affected Prompts (Consistent Across Runs)

Prompts that extracted letters in multiple runs:
- gsm8k_004 (3/3 runs) - "a week" → 'A'
- gsm8k_014 (3/3 runs)
- gsm8k_022 (3/3 runs)
- gsm8k_025 (3/3 runs)
- gsm8k_034 (3/3 runs)
- gsm8k_037 (3/3 runs)
- gsm8k_047 (3/3 runs)
- gsm8k_053 (3/3 runs)
- gsm8k_064 (3/3 runs)

At least 9 prompts consistently trigger the bug across all runs.

---

## Root Cause Analysis

### Why This Happened

**Design decision:** Check MC letters before numbers to handle MMLU/GPQA (multiple choice)

**Assumption:** GSM8K responses wouldn't contain standalone A-D letters

**Reality:** Math reasoning frequently uses:
- Articles: "a week", "a day", "a total"
- Method labels: "Method A", "Formula B"
- Step labels: "Step C", "Part D"
- Variables: "Let a be..."

### Why It Wasn't Caught

1. **No unit tests** for GSM8K-specific extraction
2. **Spot checks** likely missed it (only 9-16% of prompts affected)
3. **Plausible results** - 86.7% vs 89.7% seemed reasonable, not obviously buggy
4. **No manual audit** of extracted vote_counts keys

---

## Fix Options

### Option 1: Benchmark-Aware Extraction (Recommended)

```python
def _extract_answer_key(self, answer: str, benchmark: str = "numeric") -> str:
    """
    Extract answer key for voting.
    
    Args:
        answer: Model response text
        benchmark: "numeric" (GSM8K), "mc" (MMLU/GPQA), or "auto"
    """
    if benchmark == "numeric":
        # For GSM8K: extract numbers ONLY
        numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', answer)
        if numbers:
            return numbers[-1].replace(',', '')
    
    elif benchmark == "mc":
        # For MMLU/GPQA: extract MC letters
        mc_match = re.search(r'\b([A-D])\b', answer.upper())
        if mc_match:
            return mc_match.group(1)
    
    # Fallback
    return answer[:50]
```

### Option 2: Context-Aware MC Extraction

Only match letters that appear in answer-like contexts:

```python
# Look for "Answer: A", "The answer is B", etc.
mc_match = re.search(r'(?:answer|choice|option)[\s:]*\(?([A-D])\)?', answer, re.IGNORECASE)
```

**Problem:** Might miss valid MC answers that don't use these phrases

### Option 3: Stricter Letter Matching

Require uppercase only, or specific formatting:

```python
# Only match if uppercase and preceded/followed by specific chars
mc_match = re.search(r'(?:^|\s)([A-D])(?:\.|:|$|\s)', answer)
```

**Problem:** Still brittle, might miss valid answers or match reasoning

---

## Recommended Action

### Immediate (P0 - Blocking)

1. ✅ **Document the bug** (this file)
2. **Implement Fix Option 1** (benchmark-aware extraction)
3. **Re-run self-consistency** (3 runs × 100 prompts, ~$17)
4. **Compare results:**
   - If fixed SC > baseline: Self-consistency helps (reverses finding)
   - If fixed SC = baseline: No difference (weakens "ensembles hurt" claim)
   - If fixed SC < baseline but closer: Still hurts but less (modifies magnitude)
   - If fixed SC still ~86.7%: Bug wasn't the cause, finding stands

### Documentation Updates (P0)

**Until re-run completes, add to all docs:**

> ⚠️ **CRITICAL BUG DISCOVERED (April 11, 2026):** Self-consistency answer extraction on GSM8K affected 15-16% of prompts (extracted article "a" as letter 'A' instead of numeric answer). The reported 86.7% accuracy and "-3% vs baseline" finding may be invalid. Re-run in progress with fixed extraction. All Phase 2 self-consistency conclusions are preliminary pending verification.

**Files to update:**
- README.md (Phase 2 section)
- BLOG.md (self-consistency section)
- ENSEMBLE_COMPARISON_RESULTS.md (SC results)
- EXECUTIVE_SUMMARY.md (key findings)
- RESEARCH_COMPENDIUM.md (known issues)

### Investigation (P1 - High Priority)

Audit the 15-16 affected prompts manually:
- How many letter-extracted answers were actually correct?
- How many were legitimately wrong?
- This determines if 86.7% is close to truth or way off

---

## Impact on Published Claims

### Claims That MAY Be Invalid

**"Even proven methods fail"**
- Depends entirely on self-consistency result
- If bug caused the failure, claim is FALSE

**"Self-consistency: 86.7% (-3.0%)"**
- Number is suspect
- Re-run required

**"Ensembles amplify systematic errors"**
- Theory built on SC result
- If SC didn't actually fail, theory unsupported

### Claims That Remain Valid

**"Vote ensemble fails (-17%)"**
- Vote ensemble uses different extraction (Haiku judge selects full answer)
- Not affected by this bug

**"Opus-thinking = Opus-fast (89.7%)"**
- Individual model results use LLM-as-judge evaluation
- Not affected by this bug

---

## Reviewer Credit

**Predicted by:** DEVILS_ADVOCATE_REVIEW_2.md Issue #1

**Exact quote:**
> "If a model's reasoning mentions 'Method A', 'Using formula B', 'Step C', or any incidental A-D letter — extremely common in math explanations — the answer key becomes that letter instead of the actual numeric answer."

**Prediction accuracy:** 100% correct

**Recommended verification method:** Check `selected_answer` fields in result files

**Follow-up:** This review saved the project from publishing an invalid finding

---

## Timeline

| Date | Event |
|------|-------|
| April 9 | Self-consistency runs complete, reported 86.7% |
| April 10 | DEVILS_ADVOCATE_REVIEW_2.md predicts extraction bug |
| April 11 | Bug confirmed in production data (15-16% affected) |
| April 11 | Fix implemented, re-run scheduled |
| TBD | Re-run complete, findings updated |

---

## Cost to Fix

**Re-run self-consistency (3 runs):** ~$17  
**Time:** ~30 minutes compute  
**Value:** Validates or invalidates key Phase 2 finding  
**ROI:** CRITICAL - cannot publish without this

---

## Lessons Learned

1. **Unit test extraction logic** on diverse real-world examples
2. **Manual audit** of extracted keys (spot check vote_counts)
3. **Benchmark-specific** extraction strategies, not one-size-fits-all
4. **Devil's advocate reviews** catch bugs that automated tests miss
5. **Audit before publication** - this would have been embarrassing post-publication

---

**Status:** BUG CONFIRMED, FIX PENDING, RE-RUN REQUIRED  
**Blocker:** YES - self-consistency findings cannot be trusted until re-run  
**ETA:** 2-3 hours (fix + re-run + analysis)
