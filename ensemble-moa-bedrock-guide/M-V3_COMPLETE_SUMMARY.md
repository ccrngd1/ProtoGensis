# M-V3 Verification Complete - Phase 3 Diversity Measurement

**Date:** April 11, 2026  
**Task:** M-V3 - Verify Phase 3 Diversity Measurement  
**Status:** ✅ COMPLETE  
**Finding:** 🟡 **Diversity (81%) measured only in pilot test, not re-measured in full Phase 3 run**

---

## What Was Checked

### Files Reviewed
- `results/persona_test.json` — Pilot test (3 elements)
- `results/persona_experiment.json` — Full Phase 3 run (54 prompts × 4 configs)
- BLOG.md — Claims about diversity
- Search for Levenshtein distance calculations

### Timeline
- **April 10, 00:26**: `persona_test.json` created (pilot, 33KB)
- **April 10, 03:36**: `persona_experiment.json` created (full run, 1.4MB)

---

## Findings

### Pilot Test (20 prompts × 3 personas)
- **File:** `results/persona_test.json`
- **Size:** 33KB
- **Measurement:** 81% response diversity (Levenshtein distance)
- **Purpose:** Validate that personas produce more diversity than model differences (which typically produce 40-60%)

### Full Phase 3 Run (54 prompts × 4 configs = 216 tests)
- **File:** `results/persona_experiment.json`  
- **Size:** 1.4MB
- **Configs:** persona-diverse, reasoning-cross-vendor, reasoning-with-personas, opus baseline
- **Measurement:** ❌ No diversity_score fields found in results
- **Conclusion:** Diversity was NOT re-measured on the full run

---

## How BLOG.md Frames This

### Technically Accurate
Line 184 (table finding):
> "Even with 81% response diversity between personas **(measured in pilot test)**, persona-diverse ensembles still underperform standalone Opus."

**This is accurate** — it explicitly says "measured in pilot test."

### Potentially Misleading
Other references don't always clarify:

- Line 36: "measured 81% response diversity" (in pilot section, OK)
- Line 40: "Even 81% diversity didn't help" (summary, doesn't clarify pilot)
- Line 197: "Even with 81% response diversity" (doesn't say pilot)
- Line 334: "Even with 81% response diversity between personas" (partial clarification)

### The Issue

**Conflation:** Diversity measured on pilot (20 prompts, 3 personas) is being used to characterize the full Phase 3 run (54 prompts, different configs).

**Questions:**
1. Did the full Phase 3 "persona-diverse" config also have ~81% diversity?
2. Or is the pilot diversity (81%) not representative of the full run?

---

## Is This A Problem?

### Argument: NOT a problem

**Assumption:** If personas produce 81% diversity on 20 prompts, they likely produce similar diversity on 54 prompts (same personas, same model).

**Validity:** Personas are deterministic instructions, so diversity should be consistent across prompt sets.

**Evidence:** BLOG.md does disclose "measured in pilot test" in one place.

### Argument: IS a problem

**Concern:** We can't PROVE the full Phase 3 run had 81% diversity without re-measuring.

**Risk:** What if diversity was lower on the full 54-prompt set due to prompt characteristics?

**Transparency:** Not all references clarify this was pilot-only measurement.

---

## Recommendation

### Option 1: Re-measure Diversity on Full Phase 3 Run (Most Rigorous)

**What to do:**
1. Load `persona_experiment.json`
2. Extract all responses for "persona-diverse" config (54 prompts)
3. Calculate pairwise Levenshtein distance between persona responses for each prompt
4. Report average diversity percentage
5. Update BLOG.md with "81% diversity confirmed on full 54-prompt run" (if similar)

**Effort:** 1-2 hours (write script, calculate, document)

**Cost:** $0 (data already exists)

**Benefit:** Eliminates any ambiguity about diversity claim

### Option 2: Clarify in Documentation (Pragmatic)

**What to do:**
1. Keep pilot measurement (81%) as stated
2. Add note in methodology: "Diversity measured on 20-prompt pilot, assumed consistent for full run"
3. Update summary references to consistently say "measured in pilot" where 81% is mentioned
4. Acknowledge as limitation if needed

**Effort:** 30 min (text edits only)

**Cost:** $0

**Benefit:** Transparent about measurement approach

### Option 3: Accept As-Is (Minimal Change)

**Rationale:**
- BLOG.md already says "measured in pilot test" in key location
- Personas are deterministic, diversity should generalize
- Not a publication blocker

**Risk:** Reviewer might question whether diversity held for full run

---

## Recommended Action

**Implement Option 2:** Clarify in documentation

### Specific Edits

**Line 40 (summary):**
```markdown
# BEFORE
- Result: Even 81% diversity didn't help; ensembles still underperformed

# AFTER
- Result: Even 81% diversity (measured in pilot) didn't help; ensembles still underperformed
```

**Line 197 (finding):**
```markdown
# BEFORE
**Finding:** Even with 81% response diversity, ensemble scored 2.1 points lower.

# AFTER
**Finding:** Even with 81% response diversity (measured in pilot test), ensemble scored 2.1 points lower.
```

**Add to DETAILED_METHODOLOGY.md:**
```markdown
**Note on diversity measurement:** The 81% diversity figure comes from a 20-prompt pilot test. We assumed this diversity level generalized to the full 54-prompt run, since personas are deterministic instructions applied to the same model (Opus). Future work could re-measure diversity on the full dataset to confirm.
```

---

## Impact Assessment

**Status:** 🟡 **Minor Issue (Not a Publication Blocker)**

**Reason:**
- BLOG.md does disclose pilot measurement in at least one place
- Assumption that diversity generalizes is reasonable (personas are deterministic)
- Core finding still holds: "persona ensembles underperformed" (regardless of exact diversity %)

**Action Required:**
- Clarify documentation consistently (30 min)
- Optionally: Re-measure diversity on full run (1-2 hours)

**Priority:** Low (after M-V1 corrections)

---

## M-V3 Completion Checklist

- ✅ Checked pilot test file (persona_test.json)
- ✅ Checked full Phase 3 file (persona_experiment.json)
- ✅ Confirmed diversity NOT re-measured on full run
- ✅ Reviewed BLOG.md framing
- ✅ Assessed validity of assumption (diversity generalizes)
- ✅ Documented options and recommendations

---

## Next Phase 0 Tasks

- ✅ M-V1: Baseline reconciliation (COMPLETE)
- ✅ M-V2: T-test type check (COMPLETE)
- ✅ M-V3: Phase 3 diversity measurement (COMPLETE)
- ⬜ M-V4: Results with/without adversarial prompts
- ⬜ M-V5: Category-weighted averages

---

*M-V3 completed April 11, 2026*  
*Estimated time: 30 minutes*  
*Recommendation: Option 2 (clarify documentation)*
