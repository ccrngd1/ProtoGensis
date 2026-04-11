# BLOG.md Recalculation Plan

**Date:** April 11, 2026  
**Issue:** BLOG.md uses MT-Bench baseline (82.7) for ALL phases. Should use different baselines for Phase 1 (94.48) and Phase 3 (91.43).  
**Status:** Ready to execute

---

## Current (Wrong) vs Correct Scores

### Phase 1: Premium Tier Testing

#### Opus Baseline
- **Current (WRONG):** 82.7 ± 8.3
- **Correct:** 94.48 ± 7.53
- **Source:** `results/premium_tier.json` → `.baselines.opus[]`

#### Ensemble Configurations

| Configuration | Current (WRONG) | Correct | Delta (Current) | Delta (Correct) | Delta Change |
|--------------|-----------------|---------|-----------------|-----------------|--------------|
| High-End Reasoning | 81.3 ± 9.1 | 93.98 ± 7.08 | -1.4 | -0.50 | **3x smaller** |
| Mixed-Capability | 78.2 ± 10.4 | 93.07 ± 14.43 | -4.5 | -1.41 | **3x smaller** |
| Same-Model-Premium | 77.9 ± 9.8 | 93.06 ± 8.90 | -4.8 | -1.42 | **3x smaller** |

**Impact:** The "2-5 point penalty" claim should be "0.5-1.4 point penalty"

---

### Phase 2: MT-Bench Multi-Turn

#### Opus Baseline
- **Current:** 82.6 ± 20.3
- **Status:** ✅ **CORRECT** (this is the MT-Bench score)

**No changes needed for Phase 2.**

---

### Phase 3: Persona Diversity Testing

#### Opus Baseline
- **Current (WRONG):** 82.7
- **Correct:** 91.43 ± 10.66
- **Source:** `results/persona_experiment.json` → `.baseline.opus[]`

#### Ensemble Configurations

| Configuration | Current (WRONG) | Correct | Delta (Current) | Delta (Correct) | Delta Change |
|--------------|-----------------|---------|-----------------|-----------------|--------------|
| Persona-Diverse | 80.6 | 89.28 ± 10.70 | -2.1 | -2.15 | ~same |
| Reasoning Cross-Vendor | 79.8 | 90.35 ± 10.79 | -2.9 | -1.08 | **3x smaller** |
| Reasoning + Personas | 80.1 | 90.83 ± 8.41 | -2.6 | -0.60 | **4x smaller** |

**Impact:** Phase 3 shows MUCH smaller penalties than reported, especially for reasoning-with-personas

---

## Statistical Analysis Re-calculation Needed

### Current Statistical Claims (Based on Wrong Baseline)

From BLOG.md:
- "5 of 6 comparisons statistically significant (p < 0.05)"
- "Same-model-premium scored 4.8 points lower"
- "Even premium ensembles underperform by 2-5 points"

### What Needs Recalculation

1. **T-tests:** Re-run paired t-tests with correct baseline scores
2. **P-values:** All p-values need recalculation
3. **Effect sizes:** Cohen's d calculations with correct deltas
4. **Confidence intervals:** If using normal approximation, recalculate with correct means

### Expected Statistical Impact

**Phase 1 (with correct baseline 94.48):**
- High-end reasoning: delta = -0.50 (very small)
  - Expected p-value: p > 0.05 (NOT significant)
- Mixed-capability: delta = -1.41  
  - Expected p-value: p > 0.05 (likely not significant, given large std = 14.43)
- Same-model-premium: delta = -1.42
  - Expected p-value: p > 0.05 (likely not significant)

**Preliminary assessment:** Phase 1 may have **0 of 3 significant comparisons** (not 3 of 3)

**Phase 3 (with correct baseline 91.43):**
- Persona-diverse: delta = -2.15
  - Expected p-value: Needs calculation (moderate effect)
- Reasoning cross-vendor: delta = -1.08
  - Expected p-value: p > 0.05 (likely not significant)
- Reasoning-with-personas: delta = -0.60
  - Expected p-value: p > 0.05 (NOT significant, very small)

**Preliminary assessment:** Phase 3 may have **0-1 of 3 significant comparisons** (not 3 of 3)

---

## Files That Need Updates

### Priority 1: Core Results Documents

1. **BLOG.md** — MAJOR REWRITE NEEDED
   - Replace all Phase 1 scores (lines ~120-180)
   - Replace all Phase 3 scores (lines ~220-280)
   - Update narrative: "0.5-1.4 points" not "2-5 points"
   - Revise statistical claims after re-analysis
   - Update abstract/executive summary

2. **RESULTS_AT_A_GLANCE.md** — TABLE UPDATES
   - Update Phase 1 comparison table
   - Update Phase 3 comparison table
   - Keep Phase 2 table as-is (correct)

3. **EDITORIAL_REFERENCE.md** — EXAMPLE UPDATES
   - Update any example calculations using wrong baselines
   - Check all numerical examples

### Priority 2: Technical Documentation

4. **DETAILED_METHODOLOGY.md**
   - Check if it references specific scores
   - Update if needed

5. **PREMIUM_TIER_RESULTS.md**
   - Currently reports 94.4 ± 7.6 ✅ **CORRECT**
   - No changes needed (already matches JSON)

### Priority 3: Analysis Scripts

6. **benchmark/analyze_results.py**
   - Re-run to regenerate all statistics
   - Confirm it's reading from correct JSON paths
   - Generate new p-values, effect sizes

---

## Execution Steps

### Step 1: Generate Correct Statistics (30 min)

Run statistical analysis script on correct data:

```bash
cd /home/ubuntu/Desktop/ProtoGensis/ensemble-moa-bedrock-guide
python3 benchmark/analyze_results.py --phase 1 --output analysis/phase1_corrected.txt
python3 benchmark/analyze_results.py --phase 3 --output analysis/phase3_corrected.txt
```

**Outputs needed:**
- Means, standard deviations (confirm match JSON)
- Paired t-test results (p-values)
- Cohen's d effect sizes
- Confidence intervals

### Step 2: Create Corrected Scores Table (15 min)

Create a reference table with all corrected scores for easy copy-paste:

```markdown
## Phase 1 Corrected Scores

| Configuration | Score | Std Dev | n | Delta | p-value | Significant? |
|---------------|-------|---------|---|-------|---------|--------------|
| Opus Baseline | 94.48 | 7.53 | 54 | — | — | — |
| High-End Reasoning | 93.98 | 7.08 | 54 | -0.50 | [RECALC] | [RECALC] |
| Mixed-Capability | 93.07 | 14.43 | 54 | -1.41 | [RECALC] | [RECALC] |
| Same-Model-Premium | 93.06 | 8.90 | 54 | -1.42 | [RECALC] | [RECALC] |

## Phase 3 Corrected Scores

| Configuration | Score | Std Dev | n | Delta | p-value | Significant? |
|---------------|-------|---------|---|---|---------|--------------|
| Opus Baseline | 91.43 | 10.66 | 54 | — | — | — |
| Persona-Diverse | 89.28 | 10.70 | 54 | -2.15 | [RECALC] | [RECALC] |
| Reasoning Cross-Vendor | 90.35 | 10.79 | 54 | -1.08 | [RECALC] | [RECALC] |
| Reasoning + Personas | 90.83 | 8.41 | 54 | -0.60 | [RECALC] | [RECALC] |
```

### Step 3: Update BLOG.md (2-3 hours)

**Section-by-section edits:**

1. **Abstract** — Update key findings
   - Change: "2-5 point penalty" → "0.5-2.2 point penalty"
   - Change: "statistically significant" → recalculate which are significant

2. **TL;DR** — Update headline numbers
   - Update Opus baseline references
   - Update delta claims

3. **Phase 1 Section** — Replace all scores
   - Update baseline: 82.7 → 94.48
   - Update high-end-reasoning: 81.3 → 93.98
   - Update mixed-capability: 78.2 → 93.07
   - Update same-model-premium: 77.9 → 93.06
   - Update all delta calculations

4. **Phase 2 Section** — NO CHANGES (already correct)

5. **Phase 3 Section** — Replace all scores
   - Update baseline: 82.7 → 91.43
   - Update persona-diverse: 80.6 → 89.28
   - Update reasoning-cross-vendor: 79.8 → 90.35
   - Update reasoning-with-personas: 80.1 → 90.83
   - Update all delta calculations

6. **Statistical Analysis Section** — Update all claims
   - Update p-values
   - Update "5 of 6 significant" claim
   - Update effect size interpretations

7. **Implications Section** — Revise narrative
   - Smaller effects still support "ensembles don't help" but less dramatically
   - May need to soften language about "significant underperformance"

### Step 4: Update RESULTS_AT_A_GLANCE.md (30 min)

Find/replace all Phase 1 and Phase 3 scores in tables.

### Step 5: Update EDITORIAL_REFERENCE.md (20 min)

Check all numerical examples, update any using wrong baselines.

### Step 6: Verify Consistency (30 min)

```bash
# Check all references to "82.7" in non-Phase-2 contexts
grep -n "82\.7" BLOG.md RESULTS_AT_A_GLANCE.md EDITORIAL_REFERENCE.md

# Check all references to "94" or "91" to confirm updated
grep -n "94\." BLOG.md RESULTS_AT_A_GLANCE.md

# Verify no contradictions remain
diff <(grep -o "[0-9][0-9]\.[0-9]" BLOG.md | sort | uniq) \
     <(grep -o "[0-9][0-9]\.[0-9]" RESULTS_AT_A_GLANCE.md | sort | uniq)
```

### Step 7: Document Correction (15 min)

Add a note to VERIFICATION_REPORT.md documenting:
- What was corrected
- Why the error occurred (MT-Bench baseline used for all phases)
- Confirmation that JSON files are authoritative
- Date of correction

---

## Narrative Impact Assessment

### What Still Holds True

✅ "All ensembles underperformed standalone Opus" — STILL TRUE  
✅ "Even 81% diversity didn't help" — STILL TRUE  
✅ "Pattern consistent across phases" — STILL TRUE  
✅ "MoA underperforms on Bedrock for capable models" — STILL TRUE

### What Changes

⚠️ **Effect magnitude:** "2-5 points" → "0.5-2.2 points" (smaller)  
⚠️ **Statistical significance:** "5 of 6 significant" → likely "0-2 of 6 significant"  
⚠️ **Same-model ablation:** "4.8 points worse" → "1.4 points worse" (3x smaller)  
⚠️ **Tone:** May need to soften "dramatic failure" language

### Core Conclusion Remains Valid

The finding that "MoA doesn't help for Opus-class models on Bedrock" is still supported, but the effect is more subtle than reported. The recommendation to use smart routing instead of MoA remains sound.

---

## Quality Checks After Update

- [ ] All Phase 1 scores reference 94.48 baseline
- [ ] All Phase 3 scores reference 91.43 baseline
- [ ] Phase 2 scores still reference 82.62 baseline (unchanged)
- [ ] All deltas recalculated correctly
- [ ] All p-values come from new statistical analysis
- [ ] No references to "2-5 points" in Phase 1 context
- [ ] Abstract/TL;DR match detailed results
- [ ] RESULTS_AT_A_GLANCE tables match BLOG
- [ ] PREMIUM_TIER_RESULTS.md (already correct) cited as supporting evidence

---

## Timeline Estimate

- Statistical re-analysis: 30 min
- BLOG.md updates: 2-3 hours  
- RESULTS_AT_A_GLANCE.md: 30 min
- EDITORIAL_REFERENCE.md: 20 min
- Verification: 30 min
- **Total: 4-5 hours**

---

## Risk Assessment

**Low risk of further errors because:**
- JSON files are authoritative source (result of actual API calls)
- PREMIUM_TIER_RESULTS.md already uses correct scores (validates JSON)
- Multiple JSON files (premium_tier, persona_experiment) internally consistent
- Only BLOG.md and derivative docs have wrong numbers

**High confidence that JSON files are correct.**

---

## Next Steps

1. ✅ Verification complete (M-V1 done)
2. ⬜ Run statistical re-analysis script
3. ⬜ Update BLOG.md with correct scores
4. ⬜ Update RESULTS_AT_A_GLANCE.md
5. ⬜ Update EDITORIAL_REFERENCE.md if needed
6. ⬜ Verify consistency across all docs
7. ⬜ Proceed with other Phase 0 verification tasks (M-V2 through M-V5)
8. ⬜ Consider Phase 1 critical experiments (M-E1, M-E2) after docs corrected

---

*This recalculation plan addresses the M-V1 publication blocker identified in the Phase 0 verification.*
