# M-V2 Verification Complete - T-Test Type Check

**Date:** April 11, 2026  
**Task:** M-V2 - Confirm Paired vs Unpaired T-Tests  
**Status:** ✅ COMPLETE  
**Finding:** 🟡 **Existing script uses WRONG test type (independent instead of paired)**

---

## What Was Checked

Reviewed `/benchmark/analyze_diversity.py` for statistical test implementation.

**Line 83:**
```python
t_stat, p_value = stats.ttest_ind(diverse_scores, same_scores)
```

---

## Finding

**The existing script uses `ttest_ind` (independent/unpaired t-test).**

This is **methodologically incorrect** for this experimental design.

---

## Why This Is Wrong

### Experimental Design

- Same 54 prompts tested across all configurations
- Each prompt has paired observations: (baseline_score, ensemble_score)
- Prompts are matched across configurations

### Correct Test Type

**Should use:** `ttest_rel` (paired/related samples t-test)

**Reason:** Pairing accounts for prompt-level variance and provides more statistical power. Some prompts are intrinsically harder than others, and pairing controls for this.

### Statistical Impact

Paired tests are generally MORE powerful (detect smaller effects) than unpaired tests when observations are truly paired. Using unpaired tests when data is paired:
- Wastes statistical power
- Inflates variance estimates
- Makes it HARDER to find significance (conservative error)

---

## Implications for Published Results

### Good News

Using unpaired tests is a **conservative error** — it makes it HARDER to find significance, not easier.

Since we found **0 of 6 significant with CORRECT (paired) tests**, the original results would have been even LESS significant if they had used incorrect (unpaired) tests.

This means:
- ✅ The finding that "0 of 6 significant" is robust
- ✅ Using correct method (paired) doesn't inflate p-values
- ✅ No need to worry about false positives from wrong test type

### Context

However, the original BLOG.md claim of "5 of 6 significant" doesn't match ANY analysis we can find:
- Wrong baseline (82.7 instead of 94.48/91.43)
- Wrong scores (all ~10-15 points too low)
- Likely from a different scoring run entirely

So while the `analyze_diversity.py` script uses the wrong test type, **it's unclear if this script was even used** to generate the published claims.

---

## Corrected Implementation

`recalculate_statistics.py` (created during M-V1) uses the CORRECT test type:

```python
# Line 42-43 in recalculate_statistics.py
# Paired t-test (same prompts for baseline and ensemble)
t_stat, p_value = stats.ttest_rel(baseline_scores, ensemble_scores)
```

**This is correct because:**
- Same prompts evaluated across configurations
- Observations are naturally paired
- Controls for prompt difficulty variance

---

## Statistical Results with Correct Method

Using **paired t-tests** with **correct baselines**:

### Phase 1
- High-End Reasoning: t = +0.817, p = 0.418 ❌ not significant
- Mixed-Capability: t = +0.761, p = 0.450 ❌ not significant
- Same-Model-Premium: t = +1.794, p = 0.078 ❌ not significant (close)

### Phase 3
- Persona-Diverse: t = +1.892, p = 0.064 ❌ not significant (close)
- Reasoning Cross-Vendor: t = +1.293, p = 0.202 ❌ not significant
- Reasoning + Personas: t = +0.471, p = 0.639 ❌ not significant

**Total: 0 of 6 comparisons statistically significant (p < 0.05)**

---

## Recommendation

### For Documentation Updates

When updating BLOG.md:
- ✅ Use results from `recalculate_statistics.py` (paired tests, correct baselines)
- ✅ Note that paired tests were used (methodologically appropriate)
- ❌ Do NOT use results from `analyze_diversity.py` (wrong test type)

### For analyze_diversity.py Script

**Option 1:** Fix the script (change `ttest_ind` to `ttest_rel`)

```python
# Line 83 - BEFORE (wrong)
t_stat, p_value = stats.ttest_ind(diverse_scores, same_scores)

# Line 83 - AFTER (correct)
t_stat, p_value = stats.ttest_rel(diverse_scores, same_scores)
```

Also update line 85 comment:
```python
# BEFORE
print(f"\nStatistical Test (Independent t-test):")

# AFTER  
print(f"\nStatistical Test (Paired t-test):")
```

**Option 2:** Deprecate the script and use `recalculate_statistics.py` instead

---

## M-V2 Completion Checklist

- ✅ Found existing analysis script
- ✅ Confirmed test type (independent, wrong)
- ✅ Explained why it's wrong (data is paired)
- ✅ Verified corrected script uses right test (paired)
- ✅ Confirmed impact is conservative (wrong test makes significance harder, not easier)
- ✅ Documented recommendation (use paired tests going forward)

---

## Impact on Publication

**Status:** ✅ **Not a publication blocker**

**Reason:**
- The wrong test type (if it was used) would have made it HARDER to find significance
- Our corrected analysis uses the RIGHT test type
- Results still show 0 of 6 significant
- No false positives from methodology issue

**Action Required:**
- Fix `analyze_diversity.py` if it will be used in future
- Use `recalculate_statistics.py` for all published results
- Note in methodology that paired tests were used (adds credibility)

---

## Next Phase 0 Tasks

- ✅ M-V1: Baseline reconciliation (COMPLETE)
- ✅ M-V2: T-test type check (COMPLETE)
- ⬜ M-V3: Verify Phase 3 diversity measurement
- ⬜ M-V4: Results with/without adversarial prompts
- ⬜ M-V5: Category-weighted averages

---

*M-V2 completed April 11, 2026*  
*Estimated time: 30 minutes*
