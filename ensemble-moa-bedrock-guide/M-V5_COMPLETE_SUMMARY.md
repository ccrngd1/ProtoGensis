# M-V5 Verification Complete - Category-Weighted Averages

**Date:** April 11, 2026  
**Task:** M-V5 - Calculate Category-Weighted Averages  
**Status:** ✅ COMPLETE  
**Finding:** 🟡 **Moderate impact - Mixed-capability changes by 1.02 points; deltas shift up to 0.77 points**

---

## Executive Summary

**Category weighting has minimal impact (< 0.5 points) for 7 of 8 configurations, but LARGE impact (1.02 points) for mixed-capability.**

- **Average impact:** 0.29 points across all configs
- **Maximum impact:** 1.02 points (mixed-capability)
- **Delta changes:** Up to 0.77 points (mixed-capability penalty worsens)

**Recommendation:** Report both methods, or justify equal prompt weighting (current method).

---

## Methodology Comparison

### Current Method (Used in BLOG.md)
- All 54 prompts weighted equally
- Natural representation of actual prompt distribution
- Simple, intuitive

### Category-Weighted Method
- Each of 8 categories weighted equally
- Balances uneven category representation
- Treats "adversarial" (5 prompts) same as "reasoning" (7 prompts)

---

## Results: Current vs Category-Weighted

### Phase 1: Premium Tier Testing

| Configuration | Current | Weighted | Difference | Impact |
|---------------|---------|----------|------------|--------|
| Opus Baseline | 94.48 | 94.22 | -0.26 | Minimal |
| High-End Reasoning | 93.98 | 93.99 | +0.00 | Minimal |
| **Mixed-Capability** | **93.07** | **92.05** | **-1.02** | **Large** |
| Same-Model-Premium | 93.06 | 92.64 | -0.41 | Minimal |

### Phase 3: Persona Diversity Testing

| Configuration | Current | Weighted | Difference | Impact |
|---------------|---------|----------|------------|--------|
| Opus Baseline | 91.43 | 91.25 | -0.18 | Minimal |
| Persona-Diverse | 89.28 | 89.52 | +0.24 | Minimal |
| Reasoning Cross-Vendor | 90.35 | 90.29 | -0.06 | Minimal |
| Reasoning + Personas | 90.83 | 90.71 | -0.12 | Minimal |

---

## Delta Changes

**How do ensemble vs baseline deltas change with category weighting?**

### Phase 1

| Configuration | Current Delta | Weighted Delta | Change |
|---------------|--------------|----------------|---------|
| High-End Reasoning | -0.50 | -0.24 | +0.26 (improves) |
| **Mixed-Capability** | **-1.41** | **-2.17** | **-0.77 (worsens)** |
| Same-Model-Premium | -1.43 | -1.58 | -0.15 (worsens) |

### Phase 3

| Configuration | Current Delta | Weighted Delta | Change |
|---------------|--------------|----------------|---------|
| Persona-Diverse | -2.15 | -1.73 | +0.42 (improves) |
| Reasoning Cross-Vendor | -1.07 | -0.96 | +0.12 (improves) |
| Reasoning + Personas | -0.59 | -0.54 | +0.06 (improves) |

**Pattern:** Category weighting makes Phase 1 look slightly worse, Phase 3 look slightly better.

---

## Why Mixed-Capability Is Sensitive to Weighting

### Category-Level Performance

Mixed-capability (Nova-lite, Haiku, Llama-8B aggregated by Opus):

| Category | Score | Note |
|----------|-------|------|
| **Adversarial** | **72.00** | **Very low - cheap models fail** |
| Analysis | 98.75 | Excellent |
| Code | 95.88 | Good |
| Creative | 92.00 | OK |
| Edge-cases | 95.00 | Good |
| Factual | 98.62 | Excellent |
| Multistep | 85.00 | Moderate |
| Reasoning | 99.14 | Excellent |

**Interpretation:**
- Mixed-capability does VERY WELL on most categories (95-99 points)
- But FAILS HARD on adversarial (72 points)
- Current method (all prompts equal): Adversarial is 5 of 54 prompts (9.3%)
- Category weighting: Adversarial is 1 of 8 categories (12.5%)

**Effect:** Category weighting gives MORE weight to adversarial category, pulling mixed-capability score down more.

---

## Which Method Is "Right"?

### Argument for Current Method (All Prompts Equal)

**Pros:**
- Natural representation of actual workload
- If 5 adversarial prompts in 54 total, that's the real distribution
- Simple, intuitive
- Matches real-world use case (9% adversarial inputs)

**Cons:**
- Overrepresented categories (reasoning: 7 prompts) have more influence
- Underrepresented categories (adversarial: 5 prompts) have less influence
- Arbitrary prompt selection affects results

### Argument for Category-Weighted Method

**Pros:**
- Balances uneven category representation
- Each task type (adversarial, reasoning, code, etc.) weighted equally
- More robust to arbitrary prompt selection within categories
- Better for comparing across categories

**Cons:**
- Gives equal weight to small categories (5 prompts) and large categories (7 prompts)
- May not reflect real-world usage (is adversarial really 12.5% of workload?)
- More complex, less intuitive

---

## Recommendation

### Option 1: Report Both Methods (Most Transparent)

**In BLOG.md:**
```markdown
### Averaging Method

All results use per-prompt averaging (each of 54 prompts weighted equally). We also calculated category-weighted averages (each of 8 categories weighted equally) to check for category imbalance effects:

- **Average difference:** 0.29 points
- **Maximum difference:** 1.02 points (mixed-capability)

The current method is appropriate for representing actual workload distribution. Category weighting would slightly penalize configurations that struggle with underrepresented categories (adversarial prompts).
```

### Option 2: Use Current Method, Justify (Pragmatic)

**Add note in DETAILED_METHODOLOGY.md:**
```markdown
**Averaging Method:** All 54 prompts are weighted equally in calculating means. This reflects the natural distribution of our benchmark. Category-weighted averages (treating each of 8 categories equally regardless of prompt count) show similar results (average difference: 0.29 points, maximum: 1.02 points for mixed-capability).
```

### Option 3: Switch to Category-Weighted (Conservative)

**Recalculate all scores using category-weighted method.**

**Pros:** More robust to category imbalance  
**Cons:** Complicates already complex recalculation; not standard practice

---

## Impact Assessment

**Status:** 🟡 **Minor Issue (Not a Publication Blocker)**

**Reason:**
- Average impact is small (0.29 points)
- Only 1 of 8 configs affected significantly (mixed-capability: 1.02 points)
- Does NOT change core finding (ensembles still underperform overall)
- Does NOT flip any comparisons (no config goes from underperform to outperform)

**Action Required:**
- Document the averaging method used
- Optionally: Report category-weighted results as sensitivity check
- Justify choice of equal prompt weighting

**Priority:** Low (after M-V1, M-V4 corrections)

---

## Detailed Category Breakdown

### Categories in Benchmark

| Category | Count | % of Total |
|----------|-------|------------|
| Adversarial | 5 | 9.3% |
| Analysis | 8 | 14.8% |
| Code | 8 | 14.8% |
| Creative | 8 | 14.8% |
| Edge-cases | 4 | 7.4% |
| Factual | 8 | 14.8% |
| Multistep | 6 | 11.1% |
| Reasoning | 7 | 13.0% |

**Distribution is relatively balanced** (7-15% per category, except edge-cases at 7%).

**Implication:** Category imbalance is NOT severe. Current method (equal prompt weighting) is reasonable.

---

## Statistical Note

The category-weighted deltas are still **not statistically significant** (we're only changing averaging method, not sample size or variance).

So even with category weighting:
- **0 of 6 comparisons significant** (p < 0.05)

This doesn't change the statistical picture.

---

## M-V5 Completion Checklist

- ✅ Calculated category-weighted averages for all configs
- ✅ Compared to current method (all prompts equal)
- ✅ Identified maximum impact (1.02 points, mixed-capability)
- ✅ Analyzed delta changes with category weighting
- ✅ Assessed pros/cons of each method
- ✅ Documented category breakdown

---

## Next Steps

- ✅ All Phase 0 verification tasks complete (M-V1 through M-V5)
- ⬜ Consolidate findings into master verification report
- ⬜ Prioritize documentation updates based on all findings
- ⬜ Execute BLOG.md corrections

---

## Bottom Line

**Category weighting has minimal impact on most configurations (< 0.5 points).**

Mixed-capability is sensitive to weighting method because it fails hard on adversarial prompts (72/100) but excels on most other categories (95-99).

**Recommendation:** Use current method (equal prompt weighting), document it clearly, optionally report category-weighted as sensitivity check.

---

*M-V5 completed April 11, 2026*  
*Estimated time: 30 minutes*  
*Script: `analyze_category_weighted.py`*
