# CRITICAL FINDING: Self-Consistency Actually IMPROVES Performance

**Date:** April 11, 2026  
**Status:** 🔴 **PUBLICATION BLOCKER** - Narrative reversal required

---

## The Discrepancy

### Original Claim (ENSEMBLE_COMPARISON_RESULTS.md, BLOG.md)
- Self-consistency: **86.7%** mean accuracy
- Baseline (opus-fast): **89.7%** mean accuracy  
- **Difference: -3.0%** ✗ WORSE
- **Narrative**: "Even proven ensemble methods (Wang et al. 2023) fail at capability limits"

### Corrected Calculation (After Extraction Fix)
- Self-consistency: **93.3%** mean accuracy (93%, 94%, 93%)
- Baseline (opus-fast): **89.7%** mean accuracy (89%, 89%, 91%)
- **Difference: +3.6%** ✓ BETTER
- **New Narrative**: "Self-consistency improves accuracy by 3.6 percentage points"

**Magnitude**: 6.6 percentage point swing (+3.0% → -3.6%)

---

## Root Cause

**The extraction bug:**
1. Self-consistency stored full-text explanations in `selected_answer` field
2. Original accuracy calculation compared full-text to numeric ground truth
3. String comparison failed: "Let me work through... **$18**" ≠ "18"
4. Marked many CORRECT answers as WRONG

**The fix:**
1. Extracted numeric answers from `vote_counts` field (which had correct numbers)
2. Compared numeric to numeric: "18" == "18" ✓
3. Revealed true accuracy: 93.3% (not 86.7%)

---

## Evidence

### Original Results (ensemble_comparison_results.json)
```json
"self_consistency": {
  "runs": [
    {"correct": 87, "total": 100, "accuracy": 0.87},
    {"correct": 87, "total": 100, "accuracy": 0.87},
    {"correct": 86, "total": 100, "accuracy": 0.86}
  ],
  "mean_accuracy": 0.8666666666666667
}
```

### Corrected Results (recalculate_gsm8k_accuracies.py output)
```
Run 1: gsm8k_100_selfcons_run1_fixed.json
  Correct: 93/100
  Accuracy: 93.0%

Run 2: gsm8k_100_selfcons_run2_fixed.json
  Correct: 94/100
  Accuracy: 94.0%

Run 3: gsm8k_100_selfcons_run3_fixed.json
  Correct: 93/100
  Accuracy: 93.0%

SELF-CONSISTENCY MEAN ACCURACY: 93.3%
```

**Verification**: Extracted answers from `vote_counts` field and compared to ground truth from `prompts/gsm8k_100.json`.

---

## Impact Assessment

### What This Means

**Phase 2 headline finding is WRONG:**
- ❌ "Self-consistency underperforms individual by 3%"
- ✅ "Self-consistency outperforms individual by 3.6%"

**Narrative changes:**
- From: "Even proven methods fail at capability limits"
- To: "Proven methods (self-consistency) DO improve performance, but costs 3.7x more for 3.6% gain"

### What Stays the Same

- Vote ensemble still fails dramatically: 72.7% (still 17% worse than baseline)
- Haiku judge bottleneck still valid
- Cost analysis still valid (self-consistency costs 3.7x baseline)

### New Cost-Benefit Analysis

| Method | Accuracy | vs Baseline | Cost | Cost per % gain |
|--------|----------|-------------|------|-----------------|
| Opus-fast (baseline) | 89.7% | -- | $4.48 | -- |
| Self-consistency | 93.3% | **+3.6%** ✓ | $16.76 | **$3.41 per point** |
| Vote ensemble | 72.7% | -17.0% ✗ | $15.45 | N/A (worse) |

**New interpretation**: Self-consistency provides a small but real accuracy boost at 3.7x cost. Whether this is worth it depends on use case:
- High-stakes applications (medical, financial): +3.6% may justify 3.7x cost
- High-volume applications: baseline is more cost-effective

---

## What Needs to Change

### Documentation Updates Required

1. **BLOG.md**:
   - Update Phase 2 section with corrected self-consistency accuracy (86.7% → 93.3%)
   - Change narrative from "fails" to "helps but expensive"
   - Update cost-benefit analysis
   - Add note about extraction bug and correction

2. **ENSEMBLE_COMPARISON_RESULTS.md**:
   - Update Configuration 4 section
   - Change verdict from "underperforms" to "outperforms by 3.6%"
   - Update "Why it fails" section (remove or revise)

3. **PHASE0_COMPLETE_SUMMARY.md**:
   - Update T-V1 finding to reflect that extraction bug DID invalidate Phase 2
   - Document the narrative reversal

4. **EXECUTIVE_SUMMARY.md**:
   - Update Phase 2 findings
   - Revise key takeaways

### What Can Still Be Claimed

✅ Vote ensemble dramatically underperforms (72.7% vs 89.7%, -17%)  
✅ Haiku judge bottleneck is a real architectural flaw  
✅ Extended thinking mode provides no advantage on GSM8K (89.7% both)  
✅ Self-consistency is expensive (3.7x cost)

**CANNOT claim anymore:**
❌ "Even proven methods fail at capability limits"  
❌ "Self-consistency underperforms individual"  
❌ "Ensemble methods consistently worse across all tested architectures"

**CAN claim instead:**
✅ "Self-consistency improves accuracy by 3.6% but costs 3.7x more"  
✅ "Weak-judge ensembles fail, but proven self-consistency works"  
✅ "Ensemble benefit exists but may not justify cost for all use cases"

---

## Timeline Impact

**Original plan**: Fix extraction → validate existing claims  
**Actual result**: Fix extraction → **discovered claims were WRONG**

**Additional work required**:
- Revise all Phase 2 documentation (4-6 hours)
- Rewrite narrative sections (2-3 hours)
- Update cost-benefit analysis (1 hour)
- Cross-verify all claims (1-2 hours)

**Total**: +8-12 hours beyond original Week 2 estimate

---

## Lessons Learned

1. **Data validation is critical**: The extraction bug silently inverted a key finding
2. **Always verify intermediate results**: Original accuracy numbers should have been spot-checked
3. **String comparison is fragile**: Comparing full-text to numeric ground truth failed silently
4. **Phase 0 verification caught this in time**: Would have been embarrassing after publication

---

## Next Steps

1. ✅ Document this finding (this file)
2. ⬜ Update BLOG.md with corrected self-consistency results
3. ⬜ Update ENSEMBLE_COMPARISON_RESULTS.md
4. ⬜ Revise narrative from "ensembles always fail" to "self-consistency works, weak-judge fails"
5. ⬜ Update PHASE2_RESULTS.md
6. ⬜ Verify no other claims affected by extraction bug

---

**Bottom Line**: The extraction bug didn't just create wrong numbers—it inverted a major finding. Self-consistency DOES improve performance on GSM8K-100, contrary to the published claim. This is why Phase 0 verification exists.

---

*Discovered during Week 2: Thinking-Models extraction fix*  
*Part of Phase 0 verification findings*
