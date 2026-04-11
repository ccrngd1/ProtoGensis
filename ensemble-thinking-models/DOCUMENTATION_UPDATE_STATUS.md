# Documentation Update Status - April 11, 2026

**Task:** Update all documentation with corrected Phase 2 self-consistency results  
**Trigger:** Extraction bug fix revealed SC improves by +3.6%, not -3%

---

## ✅ COMPLETED (Committed)

### Primary Publication Files

1. **BLOG.md** ✅
   - Updated Phase 2 section with corrected results (93.3%)
   - Rewrote Finding 4: "Mixed Results - Architecture Matters"
   - Changed "Ensemble Failure Is Fundamental" → "Architecture Matters"
   - Added cost-benefit analysis ($3.41/point)
   - Added data quality note about extraction bug fix

2. **README.md** ✅
   - Updated Phase 2 Update section with new table
   - Revised Hypothesis 2 from "REJECTED" to "MIXED"
   - Updated Ensemble Performance table (Phase 2)
   - Changed conclusions to reflect architecture importance

3. **ENSEMBLE_COMPARISON_RESULTS.md** ✅
   - Updated Executive Summary table (93.3%)
   - Rewrote Configuration 4 section completely
   - Changed "Why it fails" → "Why it works"
   - Added cost-benefit analysis
   - Added data quality note with reference to CRITICAL_FINDING_SELFCONS.md

4. **EXECUTIVE_SUMMARY.md** ✅
   - Changed top-level answer from "No" to "Depends on architecture"
   - Updated Key Finding 1: "Architecture Determines Success"
   - Revised Key Finding 2: "Proven Methods DO Work"
   - Updated all statistics (86.7% → 93.3%)

---

## ⏳ IN PROGRESS / REMAINING

### Additional Documentation Files

5. **RESEARCH_COMPENDIUM.md** ⬜
   - Lines 451-468: Key findings summary needs update
   - Self-consistency section needs revision
   - Cost summary needs updating

6. **DOCUMENTATION_INDEX.md** ⬜
   - Quick lookups table has wrong SC accuracy (86.7%)
   - Key quotes section needs updating
   - References to "ensembles fail" need revision

7. **PHASE_2_RESULTS.md** ⬜
   - Self-consistency section needs complete rewrite
   - Conclusions need updating

---

## Key Narrative Changes Made

### OLD Narrative (WRONG)
- "Ensemble methods consistently underperform"
- "Even proven methods fail at capability limits"
- "Self-consistency: 86.7% (-3% penalty)"
- "Systematic errors amplified by majority vote"

### NEW Narrative (CORRECT)
- "Architecture determines ensemble success"
- "Proven methods work: Self-consistency improves by +3.6%"
- "Self-consistency: 93.3% (+3.6% improvement)"
- "Weak-judge ensembles fail, proven methods work"

---

## Numbers Updated

| Metric | Old (Wrong) | New (Correct) |
|--------|-------------|---------------|
| SC Accuracy | 86.7% | **93.3%** |
| SC vs Baseline | -3.0% ✗ | **+3.6%** ✓ |
| SC Run 1 | 87/100 | **93/100** |
| SC Run 2 | 87/100 | **94/100** |
| SC Run 3 | 86/100 | **93/100** |
| Verdict | "Underperforms" | **"Works but expensive"** |

---

## What Stays Unchanged

✅ **Vote ensemble:** Still 72.7% (-17%)  
✅ **Opus-thinking:** Still 89.7% (= baseline)  
✅ **Cost analysis:** All cost numbers accurate  
✅ **Statistical methodology:** Still valid  
✅ **Haiku judge bottleneck:** Still confirmed

---

## Impact Assessment

### High-Priority Claims Updated

1. ✅ "Self-consistency improves accuracy" (was "fails")
2. ✅ "Architecture matters" (was "failure is fundamental")
3. ✅ "Proven methods work on frontier models" (was "fail at limits")
4. ✅ Cost-benefit framing ($3.41/point) added

### Claims That Can NO LONGER Be Made

❌ "Even proven methods fail at capability limits"  
❌ "Self-consistency underperforms individual"  
❌ "Ensemble methods consistently worse"  
❌ "Systematic errors amplified by ensembles"

### Claims That Remain Valid

✅ "Weak-judge ensembles fail dramatically"  
✅ "Haiku bottleneck confirmed"  
✅ "Extended thinking provides no advantage on GSM8K"  
✅ "Self-consistency is expensive (3.7x cost)"

---

## Remaining Work Estimate

### Quick Updates (1-2 hours)

**RESEARCH_COMPENDIUM.md:**
- Update key findings summary (30 min)
- Update self-consistency section (30 min)
- Update cost summary (15 min)

**DOCUMENTATION_INDEX.md:**
- Update quick lookups table (15 min)
- Update key quotes (15 min)
- Update common questions (15 min)

**PHASE_2_RESULTS.md:**
- Rewrite self-consistency section (30 min)
- Update conclusions (15 min)

**Total:** ~2-3 hours

### Optional Deep Verification (2-3 hours)

- Read through all 30+ MD files for consistency
- Update any remaining references to old SC results
- Verify all cross-references are accurate
- Update any charts/diagrams if they exist

---

## Files That DON'T Need Updates

✅ **CRITICAL_BUG_FOUND.md** - Already documents the bug  
✅ **CRITICAL_FINDING_SELFCONS.md** - Already has correct results  
✅ **PHASE0_COMPLETE_SUMMARY.md** - Already discusses extraction fix  
✅ **EXTRACTION_SUMMARY.md** - Already has corrected accuracies  
✅ **T-V1_V2_COMPLETE_SUMMARY.md** - Verification findings  
✅ **T-V3_COMPLETE_SUMMARY.md** - Verification findings  
✅ **T-V4_COMPLETE_SUMMARY.md** - Verification findings

---

## Git Status

**Commits made:**
1. `bb33302` - CRITICAL FIX: Self-consistency extraction bug (code fix)
2. `b8ef52c` - MAJOR UPDATE: Correct Phase 2 findings (docs update)

**Branch:** main  
**Ahead of origin:** 4 commits (needs push)

---

## Next Steps

### Immediate (If Time)
1. Update RESEARCH_COMPENDIUM.md (~30-45 min)
2. Update DOCUMENTATION_INDEX.md (~30-45 min)
3. Update PHASE_2_RESULTS.md (~30 min)

### Final
4. Commit remaining updates
5. Push all commits to GitHub
6. Mark documentation update complete

---

## Quality Check

### Before/After Comparison

**Before extraction fix:**
- Vote: 72.7% (-17%) ✗
- SC: 86.7% (-3%) ✗
- **Conclusion:** All ensembles fail

**After extraction fix:**
- Vote: 72.7% (-17%) ✗ (unchanged, correctly bad)
- SC: 93.3% (+3.6%) ✓ (corrected, actually good)
- **Conclusion:** Architecture matters, proven methods work

**The reversal is complete and correct.**

---

**Status:** Major files updated and committed ✅  
**Remaining:** Minor files (2-3 hours)  
**Ready for publication after minor updates**
