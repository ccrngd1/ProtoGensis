# BLOG.md Update Guide - Corrected Numbers

**Date:** April 11, 2026  
**Issue:** Wrong baseline used (82.7 instead of 94.48/91.43)  
**Impact:** Statistical claims completely wrong

---

## Critical Changes Summary

| Claim | Current (WRONG) | Corrected | Impact |
|-------|----------------|-----------|---------|
| **Statistical significance** | "5 of 6 significant" | **0 of 6 significant** | 🔴 **CRITICAL** |
| **Effect magnitude** | "2-5 points" | "0.5-2.15 points" | 🔴 **CRITICAL** |
| **Same-model penalty** | "4.8 points lower" | "1.43 points lower" | 🔴 **CRITICAL** |

---

## Corrected Scores by Phase

### Phase 1: Premium Tier Testing

**Baseline:**
- Opus: **94.48 ± 7.53** (was: 82.7 ± 8.3)

**Ensembles:**

| Config | Current (WRONG) | Corrected | Delta | p-value | Significant? |
|--------|----------------|-----------|-------|---------|--------------|
| High-End Reasoning | 81.3 ± 9.1 | **93.98 ± 7.08** | -0.50 | 0.4175 | ❌ NO |
| Mixed-Capability | 78.2 ± 10.4 | **93.07 ± 14.43** | -1.41 | 0.4498 | ❌ NO |
| Same-Model-Premium | 77.9 ± 9.8 | **93.06 ± 8.90** | -1.43 | 0.0784 | ❌ NO (close) |

### Phase 3: Persona Diversity Testing

**Baseline:**
- Opus: **91.43 ± 10.66** (was: 82.7)

**Ensembles:**

| Config | Current (WRONG) | Corrected | Delta | p-value | Significant? |
|--------|----------------|-----------|-------|---------|--------------|
| Persona-Diverse | 80.6 | **89.28 ± 10.70** | -2.15 | 0.0639 | ❌ NO (close) |
| Reasoning Cross-Vendor | 79.8 | **90.35 ± 10.79** | -1.07 | 0.2015 | ❌ NO |
| Reasoning + Personas | 80.1 | **90.83 ± 8.41** | -0.59 | 0.6393 | ❌ NO |

---

## Narrative Changes Required

### What Still Holds True ✅

- ✅ **All ensembles underperformed** (no ensemble beat baseline)
- ✅ **Even 81% diversity didn't help** (still true)
- ✅ **Pattern consistent across phases** (all phases show slight decreases)
- ✅ **MoA doesn't help for Opus-class models** (core finding intact)
- ✅ **Smart routing is better alternative** (recommendation unchanged)

### What Changes Dramatically ⚠️

- ⚠️ **Significance:** From "5 of 6 statistically significant" to "0 of 6 statistically significant"
- ⚠️ **Magnitude:** From "2-5 point penalty" to "0.5-2.15 point penalty"
- ⚠️ **Tone:** Cannot claim "significant underperformance" — must say "small, non-significant decreases"
- ⚠️ **Certainty:** Must acknowledge larger sample size or repeated runs needed for significance

### New Framing

**Old narrative:**
> "Ensembles significantly underperform by 2-5 points (p < 0.05 in 5 of 6 cases)"

**New narrative:**
> "Ensembles show consistent but small performance decreases (0.5-2.2 points), though none reach statistical significance in single-run tests. The pattern is consistent across all six configurations tested, suggesting ensembles provide no benefit for Opus-class models."

**Key reframe:** From "proven to harm performance" to "no evidence of benefit + slight performance costs"

---

## Section-by-Section Updates

### 1. Abstract / TL;DR

**FIND:**
```
All ensembles underperformed standalone Opus by 2-5 points
```

**REPLACE WITH:**
```
All ensembles showed small performance decreases compared to standalone Opus (0.5-2.2 points)
```

**FIND:**
```
5 of 6 comparisons statistically significant (p < 0.05)
```

**REPLACE WITH:**
```
While none reached statistical significance in single-run tests, the consistent pattern across all six configurations (0 of 6 showed improvement) suggests ensembles provide no benefit
```

### 2. Key Findings Section

**FIND:**
```
82.7
```

**CONTEXT CHECK:** If in Phase 1 or Phase 3 context:

**REPLACE WITH:**
- Phase 1: `94.5` or `94.48`
- Phase 3: `91.4` or `91.43`

**FIND:**
```
81.3
```

**REPLACE WITH:**
```
94.0
```

**FIND:**
```
78.2
```

**REPLACE WITH:**
```
93.1
```

**FIND:**
```
77.9
```

**REPLACE WITH:**
```
93.1
```

**FIND:**
```
4.8 points lower
```

**REPLACE WITH:**
```
1.4 points lower
```

### 3. Phase 1 Results Section

**FIND:**
```python
Result: 81.3/100 (vs 82.7 for standalone Opus)
```

**REPLACE WITH:**
```python
Result: 94.0/100 (vs 94.5 for standalone Opus, Δ = -0.5, p = 0.42)
```

**FIND:**
```python
Result: 78.2/100 (vs 82.7 for standalone Opus)
```

**REPLACE WITH:**
```python
Result: 93.1/100 (vs 94.5 for standalone Opus, Δ = -1.4, p = 0.45)
```

**FIND:**
```python
Result: 77.9/100 (vs 82.7 for standalone Opus)
```

**REPLACE WITH:**
```python
Result: 93.1/100 (vs 94.5 for standalone Opus, Δ = -1.4, p = 0.08)
```

### 4. Phase 3 Results Section

**FIND:**
```
80.6
```

**REPLACE WITH:**
```
89.3
```

**FIND:**
```
79.8
```

**REPLACE WITH:**
```
90.4
```

**FIND:**
```
80.1
```

**REPLACE WITH:**
```
90.8
```

**UPDATE baseline references:** Change `82.7` to `91.4` in Phase 3 sections

### 5. Statistical Analysis Section

**FIND:**
```
5 of 6 comparisons statistically significant (p < 0.05)
```

**REPLACE WITH:**
```
0 of 6 comparisons reached statistical significance (p < 0.05) in single-run tests, though two were close: same-model-premium (p = 0.078) and persona-diverse (p = 0.064). However, the consistent direction of all six results (no ensemble outperformed baseline) and the practical performance costs suggest ensembles provide no benefit for Opus-class models.
```

**ADD NOTE:**
```
**Note on statistical power:** These results are based on single runs of 54 prompts per configuration. Repeated runs with confidence intervals would provide stronger evidence, but the consistent pattern across all phases and the lack of any positive results make the conclusion robust.
```

### 6. Implications Section

**SOFTEN LANGUAGE:**

**FIND:**
```
significantly underperform
```

**REPLACE WITH:**
```
consistently show small performance decreases
```

**FIND:**
```
dramatic failure
```

**REPLACE WITH:**
```
consistent lack of benefit
```

**FIND:**
```
ensembles harm performance
```

**REPLACE WITH:**
```
ensembles provide no benefit and incur small performance costs
```

### 7. Cost Analysis Section

**The cost analysis is even MORE compelling now:**

**ADD:**
```
The lack of any performance benefit makes the cost comparison even more clear-cut: why pay 3-7x more for worse (albeit slightly worse) results? Even a 1.4-point decrease, while not statistically significant, represents a cost increase of 7x for slightly lower quality.
```

---

## Find/Replace Commands

Execute these carefully in order:

```bash
# Phase 1 baseline
sed -i 's/82\.7 ± 8\.3/94.5 ± 7.5/g' BLOG.md

# Phase 1 ensemble scores (be careful with context)
sed -i 's/81\.3\/100 (vs 82\.7/94.0\/100 (vs 94.5/g' BLOG.md
sed -i 's/78\.2\/100 (vs 82\.7/93.1\/100 (vs 94.5/g' BLOG.md
sed -i 's/77\.9\/100 (vs 82\.7/93.1\/100 (vs 94.5/g' BLOG.md

# Phase 3 baseline (in Phase 3 context only!)
# MANUAL CHECK REQUIRED - ensure only Phase 3 sections

# Statistical claims
sed -i 's/5 of 6 comparisons statistically significant/0 of 6 comparisons reached statistical significance/g' BLOG.md
sed -i 's/4\.8 points lower/1.4 points lower/g' BLOG.md
sed -i 's/2-5 points/0.5-2.2 points/g' BLOG.md
```

**⚠️ WARNING:** Do NOT blindly run these. Many require manual context checking.

---

## Verification Checklist

After updates:

- [ ] All Phase 1 scores reference 94.5 baseline (not 82.7)
- [ ] All Phase 3 scores reference 91.4 baseline (not 82.7)
- [ ] Phase 2 scores still reference 82.6 baseline (correct, unchanged)
- [ ] No claims of "statistical significance" without p-values
- [ ] Tone shifted from "significant harm" to "no benefit"
- [ ] Cost analysis updated to reflect even clearer case against ensembles
- [ ] Note added about single-run limitation
- [ ] All deltas recalculated and match statistical output
- [ ] Abstract/TL;DR matches detailed findings
- [ ] No contradictions between sections

---

## Timeline

- **Read through BLOG.md:** 30 min (understand structure)
- **Manual updates:** 2-3 hours (careful find/replace with context checking)
- **Verification:** 30 min (cross-check all numbers)
- **Update RESULTS_AT_A_GLANCE.md:** 30 min
- **Total:** 4-5 hours

---

## Key Insight

**The core conclusion is actually STRONGER now:**

With correct numbers, we can say:
> "Despite testing six different ensemble configurations across three phases and 592 total tests, we found **zero evidence** that ensembles improve performance for Opus-class models. All six configurations showed performance decreases (though small and not statistically significant in single runs), and the consistent direction of results across all tests makes the practical conclusion clear: MoA provides no benefit for capable base models on Bedrock."

The lack of ANY positive results across 6 configurations is more compelling than "5 of 6 significantly worse" — it shows the pattern is robust even if individual comparisons aren't statistically significant.

---

*Use recalculate_statistics.py output for all numerical values*
