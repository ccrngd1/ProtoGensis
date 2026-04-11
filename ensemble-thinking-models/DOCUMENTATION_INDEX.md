# Documentation Index - Quick Reference for Editors

**Purpose:** This index helps you quickly find specific information across all documentation files.

**Last updated:** April 10, 2026

---

## 🎯 Start Here

**New to the project?** Read these in order:
1. **README.md** (659 lines) - Overview, all findings, quick start
2. **BLOG.md** (670 lines) - Narrative form, suitable for publication
3. **ENSEMBLE_COMPARISON_RESULTS.md** (355 lines) - Deep dive Phase 2 analysis

**Writing/editing?** Start with:
- **RESEARCH_COMPENDIUM.md** (778 lines) - Complete reference, all details
- **DOCUMENTATION_INDEX.md** (this file) - What's where

---

## 📊 By Topic

### Executive Summaries

| File | Lines | Best For |
|------|-------|----------|
| **README.md** | 659 | Quick overview, key findings, recommendations |
| **BLOG.md** (intro) | First 100 | Narrative hook, storytelling version |
| **ENSEMBLE_COMPARISON_RESULTS.md** (exec summary) | Lines 11-22 | Phase 2 results table |
| **RESEARCH_COMPENDIUM.md** (key findings) | Lines 295-385 | Comprehensive findings summary |

### Statistical Methodology

| File | Lines | Content |
|------|-------|---------|
| **ENSEMBLE_COMPARISON_RESULTS.md** | 129-160 | Statistical significance, power analysis |
| **RESEARCH_COMPENDIUM.md** | 524-577 | Complete methodology, all tests |
| **VARIANCE_PILOT_RESULTS.md** | 267 | Why 3 runs is enough |
| **PHASE_2_PLAN.md** | 424 | Original statistical planning |

### Why Ensembles Fail

| File | Lines | Explanation Level |
|------|-------|-------------------|
| **README.md** | Lines 195-212 | Concise, bullet points |
| **BLOG.md** | Lines 270-296 | Narrative, accessible |
| **ENSEMBLE_COMPARISON_RESULTS.md** | Lines 163-193 | Technical, detailed |
| **RESEARCH_COMPENDIUM.md** | Lines 362-385 | Complete analysis |

### Cost Analysis

| File | Lines | What's Included |
|------|-------|-----------------|
| **ENSEMBLE_COMPARISON_RESULTS.md** | Lines 148-160 | Cost per correct, value analysis |
| **RESEARCH_COMPENDIUM.md** | Lines 406-450 | Complete Phase 1 & 2 breakdown |
| **README.md** | Lines 98-108 | Model cost/accuracy table |
| **FINDINGS.md** | Lines 200-280 | Phase 1 detailed costs |

### Phase 1 (Exploratory Study)

| File | Lines | Content |
|------|-------|---------|
| **FINDINGS.md** | 714 | Complete Phase 1 analysis |
| **HARD_PROMPTS_FINAL_ANALYSIS.md** | ~300 | Custom prompts deep dive |
| **README.md** | Lines 93-150 | Phase 1 summary tables |
| **BLOG.md** | Lines 100-400 | Phase 1 narrative |

### Phase 2 (Statistical Validation)

| File | Lines | Content |
|------|-------|---------|
| **ENSEMBLE_COMPARISON_RESULTS.md** | 355 | Complete Phase 2 analysis |
| **PHASE_2_RESULTS.md** | 334 | Execution summary |
| **README.md** | Lines 27-62 | Phase 2 update section |
| **BLOG.md** | Lines 22-55 | Phase 2 update section |

### Implementation Details

| File | Lines | What It Documents |
|------|-------|-------------------|
| **LLM_JUDGE_IMPLEMENTATION.md** | ~200 | How LLM-as-judge works |
| **SELF_CONSISTENCY_GUIDE.md** | 229 | Self-consistency method |
| **TIMEOUT_FIX.md** | 233 | Timeout configuration fixes |
| **IMPROVEMENTS_SUMMARY.md** | 283 | All fixes and enhancements |

### Known Issues and Fixes

| File | Lines | Issues Covered |
|------|-------|----------------|
| **RESEARCH_COMPENDIUM.md** | Lines 707-787 | All known issues, fixes |
| **REVIEW.md** | ~200 | Original methodology concerns |
| **IMPROVEMENTS_SUMMARY.md** | 283 | How concerns were addressed |
| **TIMEOUT_FIX.md** | 233 | Opus-thinking timeout issue |

### Data Files and Locations

| File | Lines | What It Lists |
|------|-------|---------------|
| **RESEARCH_COMPENDIUM.md** | Lines 234-336 | Complete file inventory |
| **README.md** | Bottom | Where to find results |
| **ENSEMBLE_COMPARISON_RESULTS.md** | Lines 303-314 | Phase 2 result files |

### How to Replicate

| File | Lines | Instructions For |
|------|-------|------------------|
| **RESEARCH_COMPENDIUM.md** | Lines 805-907 | Complete Phase 2 replication |
| **PHASE_2_PLAN.md** | 424 | Original experimental design |
| **README.md** | Bottom | Quick start commands |

---

## 🎨 By Use Case

### For a Blog Post

**Read these:**
1. **BLOG.md** (670 lines) - Already in blog format
2. **RESEARCH_COMPENDIUM.md** (778 lines) - Reference for details
3. **ENSEMBLE_COMPARISON_RESULTS.md** (355 lines) - Phase 2 deep dive

**Key quotes/findings:**
- Line 12-16 (BLOG.md): Opening hook
- Lines 167-213 (BLOG.md): Finding 4 (ensemble failure)
- Lines 270-296 (BLOG.md): Why ensembles fail (accessible)

**Data to cite:**
- Vote ensemble: -17% (highly significant failure due to weak judge)
- Self-consistency: +3.6% (works but 3.7x more expensive)
- Cost-benefit: $3.41 per percentage point for self-consistency

### For a Research Paper

**Read these:**
1. **ENSEMBLE_COMPARISON_RESULTS.md** (355 lines) - Results section
2. **RESEARCH_COMPENDIUM.md** (778 lines) - Methods, all details
3. **VARIANCE_PILOT_RESULTS.md** (267 lines) - Sample size justification
4. **PHASE_2_PLAN.md** (424 lines) - Experimental design

**Section mapping:**
- **Abstract:** README.md lines 1-20
- **Introduction:** BLOG.md lines 1-100
- **Methods:** RESEARCH_COMPENDIUM.md lines 524-577
- **Results:** ENSEMBLE_COMPARISON_RESULTS.md lines 24-127
- **Discussion:** ENSEMBLE_COMPARISON_RESULTS.md lines 163-299
- **Conclusion:** ENSEMBLE_COMPARISON_RESULTS.md lines 331-355

### For Technical Documentation

**Read these:**
1. **RESEARCH_COMPENDIUM.md** (778 lines) - Master reference
2. **LLM_JUDGE_IMPLEMENTATION.md** (~200 lines) - Evaluation details
3. **SELF_CONSISTENCY_GUIDE.md** (229 lines) - SC implementation

**Code references:**
- Evaluation: `benchmarks/evaluators.py`
- Self-consistency: `aggregators/self_consistency.py`
- Vote ensemble: `aggregators/vote.py`
- Statistical tests: `benchmarks/statistical_analysis.py`

### For a Presentation

**Key slides:**

**Slide 1 - Title:**
- "Do Ensemble Methods Help Thinking Models?"
- "Spoiler: No"

**Slide 2 - Research Question:**
- Phase 1: Exploratory (n=10 custom, n=20 benchmarks)
- Phase 2: Statistical validation (n=100 × 3 runs)

**Slide 3 - Main Results Table:**
- From ENSEMBLE_COMPARISON_RESULTS.md lines 14-19
- Or README.md lines 31-36

**Slide 4 - Why Ensembles Fail:**
- Systematic errors at capability limits
- Diagram: README.md lines 195-212

**Slide 5 - Cost Analysis:**
- ENSEMBLE_COMPARISON_RESULTS.md lines 148-160
- Cost multipliers: 3.5x, 3.7x for worse accuracy

**Slide 6 - Recommendations:**
- Use individual models
- Skip ensembles
- README.md lines 276-298

### For Fact-Checking

**Primary sources (raw data):**
- Phase 2 results: `results/phase2/*.json`
- Aggregated: `results/phase2/ensemble_comparison_results.json`
- Phase 1 results: `results/*.json`

**Analysis scripts:**
- `benchmarks/evaluate_ensemble_comparison.py`
- `benchmarks/statistical_analysis.py`

**Accuracy numbers:**
| Configuration | Source File | Lines |
|---------------|-------------|-------|
| Opus-fast | ENSEMBLE_COMPARISON_RESULTS.md | 32-43 |
| Opus-thinking | ENSEMBLE_COMPARISON_RESULTS.md | 46-67 |
| Vote ensemble | ENSEMBLE_COMPARISON_RESULTS.md | 70-96 |
| Self-consistency | ENSEMBLE_COMPARISON_RESULTS.md | 99-126 |

**Cost numbers:**
- Complete breakdown: RESEARCH_COMPENDIUM.md lines 406-450
- Per-run: ENSEMBLE_COMPARISON_RESULTS.md lines 317-326

---

## 📈 Charts and Tables

### Ready-to-Use Tables

**Main Results Table:**
- **ENSEMBLE_COMPARISON_RESULTS.md** line 14
- 4 configurations, mean accuracy, vs baseline, cost

**Cost-Benefit Analysis:**
- **ENSEMBLE_COMPARISON_RESULTS.md** line 149
- Accuracy, cost, cost/correct, value

**Phase 1 Performance Table:**
- **README.md** line 97
- 8 models ranked by value

**Benchmark Results:**
- **README.md** line 134
- 4 benchmarks, best model, ensemble comparison

**Statistical Significance:**
- **ENSEMBLE_COMPARISON_RESULTS.md** line 132
- Observed differences, threshold, verdict

### Data for Visualizations

**Line chart - Accuracy by configuration:**
- Data: ENSEMBLE_COMPARISON_RESULTS.md lines 32-43, 46-67, 70-96, 99-126
- X-axis: Configuration
- Y-axis: Accuracy (%)
- Error bars: 95% CI width 1-2%

**Bar chart - Cost multipliers:**
- Data: RESEARCH_COMPENDIUM.md lines 445-448
- Baseline: 1.0x
- Opus-thinking: 1.4x
- Vote: 3.5x
- Self-consistency: 3.7x

**Scatter plot - Cost vs Accuracy:**
- Data: ENSEMBLE_COMPARISON_RESULTS.md line 149
- X-axis: Total cost ($)
- Y-axis: Accuracy (%)
- Best: Top-left (low cost, high accuracy) = Opus-fast

**Flow diagram - Why ensembles fail:**
- Concept: README.md lines 195-212
- Text: BLOG.md lines 202-212

---

## 🔍 Quick Lookups

### Key Numbers

| Metric | Value | Source |
|--------|-------|--------|
| **Vote ensemble accuracy** | 72.7% | ENSEMBLE_COMPARISON_RESULTS.md:18 |
| **Self-consistency accuracy** | **93.3%** | ENSEMBLE_COMPARISON_RESULTS.md:108 |
| **Baseline accuracy** | 89.7% | ENSEMBLE_COMPARISON_RESULTS.md:16 |
| **Vote ensemble failure** | -17.0% | ENSEMBLE_COMPARISON_RESULTS.md:18 |
| **SC improvement** | **+3.6%** | ENSEMBLE_COMPARISON_RESULTS.md:19 |
| **SC cost per point** | **$3.41** | ENSEMBLE_COMPARISON_RESULTS.md:126 |
| **Phase 1 cost** | $12.00 | RESEARCH_COMPENDIUM.md:243 |
| **Phase 2 cost** | $42.77 | RESEARCH_COMPENDIUM.md:257 |
| **Total cost** | $54.77 | RESEARCH_COMPENDIUM.md:272 |
| **Statistical threshold** | ≥5% | ENSEMBLE_COMPARISON_RESULTS.md:135 |

### Key Quotes

**Opening hook (blog):**
> "The wisdom of crowds works in traditional ML because individual models make uncorrelated errors. Bagging, boosting, voting classifiers: aggregate enough independent predictions and the noise cancels out. Elegant, well-proven, and it maps cleanly onto LLMs. At least, that's what we thought."
- **BLOG.md lines 7-9**

**Main finding:**
> "Ensemble architecture determines outcome - weak judges fail, proven methods work."
- **ENSEMBLE_COMPARISON_RESULTS.md line 12**

**Self-consistency works:**
> "Self-consistency (Wang et al. 2023) improves accuracy by 3.6% on math. Cost: 3.7x baseline = $3.41 per percentage point gained."
- **ENSEMBLE_COMPARISON_RESULTS.md lines 125-127**

**Weak-judge failure:**
> "Using Haiku (40% GPQA) to judge stronger models → -17% penalty. Architectural flaw: Weak arbiter can't evaluate strong responses."
- **ENSEMBLE_COMPARISON_RESULTS.md lines 15-16**

**Cost-benefit trade-off:**
> "Whether the 3.7x cost justifies 3.6% gain depends on use case: High-stakes applications (medical, financial) may justify cost; high-volume queries should use individual baseline."
- **ENSEMBLE_COMPARISON_RESULTS.md lines 134-137**

### Common Questions and Where to Find Answers

**Q: How many runs did you do?**
- A: 3 runs per configuration, 12 total runs
- **ENSEMBLE_COMPARISON_RESULTS.md line 6**

**Q: Why 3 runs?**
- A: Variance pilot showed 3 runs gives tight CI (1-2% width)
- **VARIANCE_PILOT_RESULTS.md** (complete analysis)
- **RESEARCH_COMPENDIUM.md lines 524-540**

**Q: What dataset?**
- A: GSM8K-100 (grade school math, 100 problems)
- **ENSEMBLE_COMPARISON_RESULTS.md line 4**

**Q: What evaluation method?**
- A: LLM-as-judge (GPT-4 equivalent)
- **LLM_JUDGE_IMPLEMENTATION.md** (complete guide)
- **RESEARCH_COMPENDIUM.md lines 655-675**

**Q: Do ensemble methods help?**
- A: Depends on architecture - weak judges fail (-17%), self-consistency works (+3.6%)
- **README.md lines 79-92** (overview)
- **BLOG.md lines 279-304** (detailed)
- **ENSEMBLE_COMPARISON_RESULTS.md lines 12-21** (summary)

**Q: Did you test proven methods?**
- A: Yes, self-consistency (Wang et al. 2023) improves accuracy by 3.6%
- **ENSEMBLE_COMPARISON_RESULTS.md lines 99-137**
- **SELF_CONSISTENCY_GUIDE.md** (implementation)

**Q: What about GPT-3 results showing ensembles help?**
- A: Our findings validate Wang et al. - self-consistency works on both GPT-3 and Opus 4.6
- **ENSEMBLE_COMPARISON_RESULTS.md lines 99-137**

**Q: Why did vote ensemble fail?**
- A: Haiku judge (40% GPQA) judging stronger models (70%+) - architectural bottleneck
- **README.md lines 39-42**
- **BLOG.md lines 279-290**

**Q: Can I replicate this?**
- A: Yes, full instructions in RESEARCH_COMPENDIUM.md lines 805-907

**Q: Where's the raw data?**
- A: `results/phase2/*.json`
- **RESEARCH_COMPENDIUM.md lines 204-237** (inventory)

**Q: What models did you test?**
- A: Opus, Sonnet, Haiku (fast & thinking)
- **RESEARCH_COMPENDIUM.md lines 394-416** (complete configs)

**Q: What about extended thinking?**
- A: Opus-thinking = Opus-fast on GSM8K-100 (89.7% both)
- **ENSEMBLE_COMPARISON_RESULTS.md lines 46-67**

**Q: Should I use ensembles in production?**
- A: Self-consistency for high-stakes applications if +3.6% justifies 3.7x cost; otherwise use individual
- **README.md lines 82-92** (recommendations)

---

## 📂 File Organization

### Top-Level Documentation (For Publication)

```
README.md                          - Main project overview
BLOG.md                           - Blog post format
ENSEMBLE_COMPARISON_RESULTS.md     - Phase 2 deep dive
RESEARCH_COMPENDIUM.md            - Master reference
DOCUMENTATION_INDEX.md            - This file
```

### Phase-Specific Documentation

```
FINDINGS.md                       - Phase 1 complete analysis
HARD_PROMPTS_FINAL_ANALYSIS.md    - Phase 1 custom prompts
PHASE_2_PLAN.md                   - Phase 2 design
PHASE_2_RESULTS.md                - Phase 2 execution
VARIANCE_PILOT_RESULTS.md         - Sample size study
```

### Implementation Guides

```
LLM_JUDGE_GUIDE.md                - Evaluation method overview
LLM_JUDGE_IMPLEMENTATION.md       - Implementation details
SELF_CONSISTENCY_GUIDE.md         - Self-consistency method
SELF_CONSISTENCY_RESULTS.md       - SC-specific findings
TIMEOUT_FIX.md                    - Timeout issue resolution
```

### Planning and Process

```
BENCHMARK_INTEGRATION_PLAN.md     - Benchmark validation plan
IMPROVEMENTS_SUMMARY.md           - All fixes/enhancements
DOCUMENTATION_UPDATES.md          - Doc change log
REVIEW.md                         - Methodology critique
```

### Internal (.claude/docs/)

```
HARD_PROMPTS_EXPERIMENT_PLAN.md   - Original study design
REQUIREMENTS.md                   - Technical requirements
PRE_RUN_CHECKLIST.md              - Pre-flight checklist
VOTE_MECHANISM_COMPARISON.md      - Vote vs stitch
PARALLELIZATION_*.md              - Parallel execution
RESEARCH.md                       - Literature review
```

---

## 🏷️ Tags for Quick Filtering

Use grep to find content by tag:

```bash
# Find all cost discussions
grep -r "cost" *.md | grep -i "dollar\|\\$"

# Find all statistical significance mentions
grep -r "statistical\|significance\|p-value\|confidence" *.md

# Find all accuracy numbers
grep -r "accuracy\|89\.7%\|72\.7%\|86\.7%" *.md

# Find all ensemble failure explanations
grep -r "systematic error\|capability limit" *.md

# Find all recommendations
grep -r "recommendation\|should\|avoid" *.md
```

---

## 📋 Checklist for Editors

### Before Publishing Blog Post

- [ ] Verify all accuracy numbers against ENSEMBLE_COMPARISON_RESULTS.md
- [ ] Check cost calculations in RESEARCH_COMPENDIUM.md
- [ ] Confirm statistical claims with VARIANCE_PILOT_RESULTS.md
- [ ] Validate ensemble failure explanation (README.md lines 195-212)
- [ ] Cross-check Phase 1 findings with FINDINGS.md
- [ ] Ensure Nova-lite claims marked as "Phase 1 only, not validated Phase 2"
- [ ] Verify extended thinking results context-dependent caveat included

### Before Citing in Paper

- [ ] Raw data location verified: `results/phase2/*.json`
- [ ] Evaluation method documented: LLM_JUDGE_IMPLEMENTATION.md
- [ ] Statistical methodology complete: RESEARCH_COMPENDIUM.md lines 524-577
- [ ] Sample size justified: VARIANCE_PILOT_RESULTS.md
- [ ] All model IDs correct: RESEARCH_COMPENDIUM.md lines 579-607
- [ ] Limitations section includes: single dataset, LLM-as-judge validation
- [ ] Literature comparison accurate: Wang et al. (2023) reference

### Before Technical Talk

- [ ] Results table ready: ENSEMBLE_COMPARISON_RESULTS.md line 14
- [ ] Why ensembles fail diagram: README.md lines 195-212
- [ ] Cost-benefit analysis: ENSEMBLE_COMPARISON_RESULTS.md line 149
- [ ] Replication instructions: RESEARCH_COMPENDIUM.md lines 805-907
- [ ] Code available: All scripts in benchmarks/, aggregators/, runners/
- [ ] Known issues documented: RESEARCH_COMPENDIUM.md lines 707-787

---

## 🔗 Cross-References

When editing one file, check these related files for consistency:

**Editing README.md?** Also check:
- BLOG.md (matching findings)
- ENSEMBLE_COMPARISON_RESULTS.md (matching numbers)

**Editing BLOG.md?** Also check:
- README.md (consistency)
- RESEARCH_COMPENDIUM.md (fact-check details)

**Editing statistical claims?** Also check:
- VARIANCE_PILOT_RESULTS.md (sample size)
- PHASE_2_PLAN.md (original design)
- ENSEMBLE_COMPARISON_RESULTS.md (results)

**Editing cost numbers?** Also check:
- RESEARCH_COMPENDIUM.md lines 406-450 (complete breakdown)
- ENSEMBLE_COMPARISON_RESULTS.md lines 317-326 (per-run)
- Raw JSON files for token counts

---

**Last updated:** April 10, 2026  
**Maintained by:** ccrngd1  
**Questions?** Check RESEARCH_COMPENDIUM.md first, then README.md
