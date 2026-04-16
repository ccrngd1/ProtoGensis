# Changelog

All notable changes to this project will be documented in this file.

## [2026-04-14] - Multi-Benchmark Expansion + Judge Parser Robustness

### Added - Judge Parser Robustness
- New `aggregators/judge_parser.py` with robust judge response parsing
- Explicit confidence scoring (1.0 = structured, 0.9 = explicit, ... 0.3 = first valid)
- Comprehensive logging when fallback strategies used
- Validation of parsed model names with fuzzy matching
- Statistics generation for auditing parse reliability
- Test suite with 12 comprehensive tests (all passing)

### Fixed - Judge Parser Fragility
- **Issue:** Original vote.py used 87 lines of regex/heuristic fallbacks with no logging
- **Problem:** Silent failures, arbitrary weights (0.5 on possessive), no audit trail
- **Solution:** Centralized parser with explicit strategies, confidence scores, and logging
- **Impact:** LOW - newer aggregators (E18-E20) already used structured format
- **Location:** Old fragile code still in vote.py (Phase 1 only), newer code unaffected

## [2026-04-14] - Multi-Benchmark Expansion

### Added
- Phase 3B multi-benchmark validation (E18-E20 across GSM8K, MMLU, HumanEval, GPQA)
- 36 additional experiments testing domain-specific judge behavior
- Multi-benchmark analysis script (`analyze_multi_benchmark.py`)

### Changed
- Updated BLOG.md and README.md with domain-specific findings
- Changed recommendation from "never use judges" to "use strategically by domain"
- Updated all cost analyses and citations to reflect multi-benchmark results

### Fixed
- Phase 3 GSM8K analysis: String comparison bug caused 74.8% reported (actual 100%)
- Numeric extraction now correctly handles formatting differences ($70,000 vs 70000)

## [2026-04-13] - Phase 3A Correctness-Based Judging

### Added
- E18: Correctness-based vote ensemble
- E19: Correctness-based best-of-N
- E20: Two-stage judging (agreement → correctness)
- Correctness-based judge prompts explicitly asking for verification

### Found (Bug)
- Initial analysis reported E18=74.8%, E19=79.1% due to string comparison
- Re-evaluation revealed actual results: E18=100%, E19=100%
- Root cause: "$70,000" ≠ "70000" in string comparison

## [2026-04-11] - Self-Consistency Extraction Bug Fix

### Fixed
- **CRITICAL BUG**: Self-consistency `selected_answer` stored full-text responses instead of extracted numeric answers for GSM8K
- Example bug: "Let me work through this step-by-step..." instead of "18"
- Impact: Made answer comparison difficult, though accuracy calculation was correct (used extracted keys from vote_counts)
- Fixed files: `*_fixed.json` contain corrected `selected_answer` fields with numeric values

### Root Cause
- `SelfConsistencyResult.selected_answer` stored full raw answer from array
- Line 196 in `self_consistency.py`: `majority_answer = answers[answer_keys.index(majority_key)]`
- Should have stored the extracted key or added separate `extracted_answer` field

### Impact on Published Results
- **Accuracy calculations UNAFFECTED**: Vote counting used extracted keys correctly
- **Answer storage AFFECTED**: selected_answer field contained full text, not numbers
- Published Phase 2 results (93.3% accuracy) remain valid
- Fixed versions available in `results/phase2/*_fixed.json`

### Files Affected
- `results/phase2/gsm8k_100_selfcons_run1.json` (buggy)
- `results/phase2/gsm8k_100_selfcons_run1_fixed.json` (corrected)
- Similar for run2, run3

### Prevention
- Added regression test (see Testing section below)
- Updated self_consistency.py to include extracted_answer field
- Updated documentation to specify which results version is canonical

## [2026-04-10] - Phase 2 Statistical Validation

### Added
- GSM8K-100 benchmark with 3 runs per configuration
- Statistical rigor: confidence intervals, significance testing
- Vote ensemble (Haiku judge) comparison
- Self-consistency (Wang et al. 2023) implementation

### Found
- Vote ensemble: 72.7% (-17% vs baseline) - weak judge bottleneck confirmed
- Self-consistency: 93.3% (+3.6% vs 89.7% baseline) - proven method works

## Testing

### Self-Consistency Extraction Regression Test

To verify answer extraction is working correctly:

```bash
# Run verification script
python3 verify_selfcons_extraction.py

# Expected output for corrected code:
# ✅ EXTRACTION WORKING CORRECTLY
#    >90% of selected_answer fields contain numeric answers

# Bug signature (if present):
# 🔴 EXTRACTION BUG CONFIRMED
#    >50% of selected_answer fields contain full text
```

### Creating Regression Test

```bash
# Add to test suite
python3 -c "
import json
import re

# Load results
data = json.load(open('results/phase2/gsm8k_100_selfcons_run1.json'))

# Check extraction
buggy_count = 0
for result in data['results']:
    answer = result['selected_answer']
    # Check if answer is full text (>50 chars) instead of number
    if len(str(answer)) > 50:
        buggy_count += 1

if buggy_count > len(data['results']) * 0.5:
    print('FAIL: Self-consistency extraction bug detected')
    exit(1)
else:
    print('PASS: Self-consistency extraction working correctly')
    exit(0)
"
```

## Version History

- **v1.2** (2026-04-14): Multi-benchmark expansion, domain-specific findings
- **v1.1** (2026-04-13): Phase 3 correctness-based judging
- **v1.0** (2026-04-11): Bug fixes, self-consistency extraction corrected
- **v0.9** (2026-04-10): Phase 2 statistical validation
- **v0.1** (2026-04-03): Initial exploratory study (Phase 1)
