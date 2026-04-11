# Devil's Advocate Review #2: Pre-Publication Gap Analysis

**Reviewer:** CABAL (Main)
**Date:** April 10, 2026
**Scope:** Both ensemble projects (thinking-models + MOA bedrock guide)
**Purpose:** Identify critical gaps before full editorial review

---

## 🔴 Critical Issues

### 1. Self-Consistency Answer Extraction Has a Potential Systematic Bug

In `aggregators/self_consistency.py`, the `_extract_answer_key()` method checks for multiple-choice letters (A-D) **before** checking for numbers:

```python
def _extract_answer_key(self, answer: str) -> str:
    mc_match = re.search(r'\b([A-D])\b', answer.upper())
    if mc_match:
        return mc_match.group(1)
    # THEN try numbers...
```

**For GSM8K (numeric math), this is wrong.** If a model's reasoning mentions "Method A", "Using formula B", "Step C", or any incidental A-D letter — extremely common in math explanations — the answer key becomes that letter instead of the actual numeric answer.

Five samples might all compute "72" but get keyed as `"A"`, `"B"`, `"A"`, `"C"`, `"A"` based on reasoning artifacts. The majority vote then picks whichever reasoning *phrasing* was most common, not which *answer* was most common.

**Impact:** If even 3-4 out of 100 prompts had miskeyed answers, that accounts for the entire 3% self-consistency penalty. This could mean the only novel Phase 2 finding is an artifact.

**Verification needed:** Check `results/phase2/gsm8k_100_selfcons_run*.json` — do `selected_answer` fields contain numbers or letters for GSM8K prompts?

**Fix:** For GSM8K/numeric benchmarks, extract numbers first, fall back to letters only for MMLU/GPQA.

---

### 2. Phase 2 Statistical Rigor Covers ONE Benchmark

The "HIGH CONFIDENCE" label on ensemble failure rests entirely on GSM8K-100. One task type (grade school math). One model family (Claude).

| What was claimed | What was tested |
|---|---|
| "Ensembles fail at capability limits" | Ensembles fail on GSM8K math for Claude Opus |
| "Even proven methods fail" | Self-consistency fails on GSM8K (with potential extraction bug) |
| "HIGH CONFIDENCE" | 1 benchmark, 3 runs, 1 model family |

Phase 2 ran MMLU (57 prompts, 3 runs) but only tested opus-fast individually — no ensemble comparison on MMLU. No Phase 2 ensemble test on code, reasoning, science, or any other domain.

The conclusion should be scoped to "GSM8K math" until validated across task types.

---

### 3. The Vote Ensemble Test Reuses the Known-Broken Architecture

Phase 1's own review identified "Haiku judging stronger models" as an architectural flaw — "the intern grading senior engineers." This was the single biggest criticism.

Phase 2 then tested... the exact same Haiku-judge vote ensemble. The 17% penalty is presented as evidence that "ensembles fail," but it actually proves "a known-broken design is still broken."

**What should have been tested in Phase 2:**
- Opus as judge (strongest available model)
- Best-of-N with Opus as verifier
- Weighted voting by historical model accuracy

The only genuinely novel Phase 2 ensemble method was self-consistency — which carries the entire "even proven methods fail" argument solo, with the extraction bug concern from Issue #1.

---

### 4. The Thinking Mode Finding Contradicts Itself — Unexplored

| Phase | Dataset | Opus-thinking | Opus-fast | Winner |
|---|---|---|---|---|
| Phase 1 | GSM8K-20 | **100%** | 85% | **Thinking (+15%)** |
| Phase 2 | GSM8K-100 | 89.7% | 89.7% | **Tie** |

This is a 15-point discrepancy. Phase 1's single strongest evidence FOR thinking mode vanished at scale. The BLOG gives this one line ("context-dependent").

**Possible explanations (none investigated):**
- The 20-prompt subset happened to favor thinking mode (sampling luck)
- The 100-prompt set includes easier problems where thinking doesn't help (dilution)
- Phase 1's keyword evaluator scored differently than Phase 2's evaluator
- Phase 1 was a fluke and thinking never actually helped

**If Phase 1's strongest finding didn't replicate, what else from Phase 1 didn't replicate?** This should shake confidence in all unreplicated Phase 1 claims (Nova-lite, custom prompt results, 0/40 ensemble stat).

---

## 🟡 Significant Concerns

### 5. The "Systematic Error" Theory Is Post-Hoc and Untested

The narrative: "At capability limits, models make systematic errors, so ensembles amplify rather than correct them."

This was constructed after seeing results. It's a plausible story, but it has a testable prediction that was never tested: **ensembles should help on tasks where the model is below capability limits (60-70% baseline).**

HumanEval Phase 1 data exists: best model scored 30%. Did ensembles help there? GPQA Phase 1: best model scored 70%. Did ensembles help there? This data exists and is not analyzed through the systematic-vs-random lens.

Without testing the counterfactual, the explanation is unfalsifiable — a story that fits the data, not a tested mechanism.

---

### 6. Nova-Lite Claims Were Never Validated

Phase 1 headline: "Nova-lite matches Opus at 1/1000th the cost." The BLOG projects $220,700/month savings.

**Evidence base:** 10 custom prompts (60% healthcare), single run, no error bars. Nova-lite was never tested on GSM8K-100, MMLU-57, or any Phase 2 benchmark.

The cost projection that anchors the entire value narrative has zero statistical validation.

---

### 7. MMLU Loader Bug — Acknowledged, Ignored

"MMLU loader generated 57 prompts instead of expected 100." Noted as known issue, never investigated. Were they the easy 57? Hard 57? Random 57? If the loader has unexplained bugs, it erodes confidence in the entire evaluation pipeline. This also means MMLU confidence intervals are wider than they need to be.

---

### 8. N=3 Runs When Pilot Recommended 5

The variance pilot concluded "MODERATE" variance and explicitly said 5 runs would be better. Proceeded with 3 for cost. Valid trade-off, but then don't stamp "HIGH CONFIDENCE" on borderline findings. The self-consistency result (-3%) is explicitly called "borderline significant" — with 5 runs the verdict might change.

---

### 9. Self-Consistency Cost Numbers Don't Add Up

Self-consistency cost: $16.76 for 3 runs (5 samples × 100 prompts × 3 runs = 1500 Opus calls).

Baseline: $4.48 for 3 runs (100 prompts × 3 runs = 300 calls) → ~$0.0149/call.

Expected self-consistency: 1500 × $0.0149 = ~$22.35. Actual: $16.76.

Either the per-call cost is lower for self-consistency (different token lengths?), or it didn't actually run 5 samples per prompt on every run. Worth sanity-checking.

---

### 10. No Baseline Degradation Check for Self-Consistency

Self-consistency uses temperature=0.7 for diversity. The individual baseline likely used a different temperature (default/0). If each sample at temp=0.7 is individually worse than a single shot at temp=0, you're not testing "does majority vote help" — you're testing "does majority vote on degraded samples help."

Wang et al. addressed this explicitly. It's not clear if this study did.

---

## 🟠 Moderate Issues

### 11. Two Projects Tell Overlapping But Inconsistent Stories

The MOA project (592 tests, quality-scored by Opus judge) and thinking-models project (Phase 1+2, accuracy-scored by evaluators) share conclusions but use different methodologies, benchmarks, and evaluation methods. Cross-references are weak. A reader of one BLOG doesn't know about the other's data.

### 12. Phase 1 "0/40" Still Gets Prominent Billing Alongside Phase 2

Phase 2 was explicitly done because Phase 1 methodology was weak. But the BLOG still features "0/40" from Phase 1 prominently next to Phase 2 data, lending Phase 1 findings more authority than the methodology earned.

### 13. Levenshtein Distance ≠ Meaningful Diversity (MOA Project)

81% diversity via character-level edit distance doesn't measure semantic diversity. Two responses can say the same thing in different words (high Levenshtein, low actual diversity) or different things in similar words (low Levenshtein, high actual diversity). The "even 81% diversity didn't help" claim may be measuring the wrong thing.

---

## Required Experiment Matrix

The table below lists every experiment combination needed to close the gaps identified above. Organized by priority.

### Priority 1: Verify/Fix Existing Results (No New Runs Needed)

| # | Action | Purpose | Estimated Effort |
|---|---|---|---|
| V1 | Audit `selected_answer` fields in `gsm8k_100_selfcons_run*.json` | Verify self-consistency isn't miskeying numeric answers as letters (Issue #1) | 30 min |
| V2 | Audit self-consistency sample counts per prompt | Confirm 5 samples actually ran per prompt per run (Issue #9) | 15 min |
| V3 | Compare GSM8K-20 prompt IDs to GSM8K-100 prompt IDs | Determine if Phase 1's 20 prompts are a subset of Phase 2's 100 (Issue #4) | 15 min |
| V4 | Check temperature settings: baseline vs self-consistency | Confirm what temp was used for individual runs vs self-consistency samples (Issue #10) | 10 min |
| V5 | Fix MMLU loader to generate 100 prompts | Investigate and fix the 57-prompt bug (Issue #7) | 1-2 hr |

### Priority 2: Close Critical Evidence Gaps (New Runs Required)

These experiments directly address the critical issues. Without them, the core claims remain under-supported.

| # | Experiment | Model(s) | Benchmark | N Prompts | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E1 | Strong-judge vote ensemble | Opus (judge) + Sonnet + Haiku + Nova-pro + Llama-70B + Nova-lite (proposers) | GSM8K-100 | 100 | 3 | Vote with Opus as judge | Test whether ensemble failure is architectural (Haiku judge) or fundamental (Issue #3) | ~$20 |
| E2 | Best-of-N with Opus verifier | Opus (verifier) × 5 candidates from Opus-fast | GSM8K-100 | 100 | 3 | Generate 5 responses, Opus picks best | Strongest ensemble architecture available on Bedrock (Issue #3) | ~$25 |
| E3 | Self-consistency (bug-fixed) | Opus-fast | GSM8K-100 | 100 | 3 | Same as before but with number-first extraction for GSM8K | Verify self-consistency finding isn't an extraction artifact (Issue #1) | ~$17 |
| E4 | Nova-lite individual | Nova-lite | GSM8K-100 | 100 | 3 | Individual baseline | Validate the headline cost claim with statistical rigor (Issue #6) | ~$0.10 |
| E5 | Nova-lite individual | Nova-lite | MMLU-100 | 100 | 3 | Individual baseline | Cross-benchmark Nova-lite validation (Issue #6) | ~$0.10 |

### Priority 3: Broaden the Evidence Base

These experiments generalize the findings beyond GSM8K math. Needed to support the broad claims in the papers.

| # | Experiment | Model(s) | Benchmark | N Prompts | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E6 | Ensemble comparison (full suite) | Opus-fast, Opus-thinking, Vote (Opus judge), Self-consistency | MMLU-100 | 100 | 3 | All 4 configs | Validate ensemble findings on knowledge tasks (Issue #2) | ~$45 |
| E7 | Ensemble comparison (full suite) | Opus-fast, Opus-thinking, Vote (Opus judge), Self-consistency | GPQA-50+ | 50+ | 3 | All 4 configs | Test "below capability limit" prediction — Opus ~70% on GPQA (Issue #5) | ~$30 |
| E8 | Ensemble comparison (full suite) | Opus-fast, Opus-thinking, Vote (Opus judge), Self-consistency | HumanEval-50+ | 50+ | 3 | All 4 configs | Test at very low baseline (~30%) where ensembles "should" help (Issue #5) | ~$30 |
| E9 | Opus-fast individual | Opus-fast | GPQA-50+ | 50+ | 3 | Individual baseline | Establish baseline for GPQA ensemble comparison | ~$3 |
| E10 | Opus-fast individual | Opus-fast | HumanEval-50+ | 50+ | 3 | Individual baseline | Establish baseline for HumanEval ensemble comparison | ~$3 |

### Priority 4: Strengthen Thinking Mode Claims

| # | Experiment | Model(s) | Benchmark | N Prompts | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E11 | Thinking vs fast comparison | Opus-thinking | MMLU-100 | 100 | 3 | Individual (thinking) | Does thinking help on knowledge tasks? | ~$6 |
| E12 | Thinking vs fast comparison | Opus-thinking | GPQA-50+ | 50+ | 3 | Individual (thinking) | Does thinking help on hard science? | ~$4 |
| E13 | Thinking vs fast comparison | Opus-thinking | HumanEval-50+ | 50+ | 3 | Individual (thinking) | Does thinking help on code? | ~$4 |
| E14 | Budget model baselines | Nova-lite, Haiku-fast, Sonnet-fast | GSM8K-100 | 100 | 3 | Individual baselines | Establish capability spectrum for "systematic error threshold" theory | ~$2 |

### Priority 5: Test the Systematic Error Theory (Issue #5)

| # | Experiment | Model(s) | Benchmark | N Prompts | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E15 | Self-consistency at LOW baseline | Haiku-fast (expected ~60-70%) | GSM8K-100 | 100 | 3 | Self-consistency (5 samples) | If systematic error theory is right, self-consistency should HELP here | ~$3 |
| E16 | Self-consistency at LOW baseline | Nova-lite | GPQA-50+ | 50+ | 3 | Self-consistency (5 samples) | Test on hard domain where budget models struggle | ~$0.50 |
| E17 | Self-consistency at MID baseline | Sonnet-fast | GSM8K-100 | 100 | 3 | Self-consistency (5 samples) | Map the threshold where ensembles flip from helping to hurting | ~$6 |

---

## Consolidated Cost Summary

| Priority | Experiments | Purpose | Total Est. Cost |
|---|---|---|---|
| P1 (Verify) | V1-V5 | Audit existing results, fix bugs | $0 (time only) |
| P2 (Critical) | E1-E5 | Close critical evidence gaps | ~$62 |
| P3 (Broaden) | E6-E10 | Multi-benchmark validation | ~$111 |
| P4 (Thinking) | E11-E14 | Thinking mode claims | ~$16 |
| P5 (Theory) | E15-E17 | Systematic error threshold | ~$10 |
| **Total** | **V1-V5 + E1-E17** | **Complete gap closure** | **~$199** |

### Recommended Minimum (Closes Critical Issues Only)

| Experiments | Purpose | Cost |
|---|---|---|
| V1-V4 | Audit existing data for bugs | $0 |
| E3 | Bug-fixed self-consistency | ~$17 |
| E1 | Strong-judge ensemble (Opus) | ~$20 |
| E4 | Nova-lite on GSM8K-100 | ~$0.10 |
| **Minimum total** | **Closes Issues #1, #3, #6** | **~$37** |

If the bug-fixed self-consistency (E3) still shows -3%, and the Opus-judge ensemble (E1) still underperforms, the "ensembles fail" conclusion becomes much more defensible. If Nova-lite validates at 85%+ on GSM8K-100, the cost narrative holds.

If either E1 or E3 *reverses* the finding, the papers need significant revision before publication.

---

## Model Reference

Models available on AWS Bedrock for experiments:

| Model | Key | Tier | Input $/1K | Output $/1K | Notes |
|---|---|---|---|---|---|
| Claude Opus 4.6 (fast) | opus-fast | Premium | $0.015 | $0.075 | Primary baseline |
| Claude Opus 4.6 (thinking) | opus-thinking | Premium | $0.015 | $0.075 + thinking tokens | 10K thinking budget |
| Claude Sonnet 4.6 (fast) | sonnet-fast | Mid | $0.003 | $0.015 | |
| Claude Sonnet 4.6 (thinking) | sonnet-thinking | Mid | $0.003 | $0.015 + thinking | 5K thinking budget |
| Claude Haiku 4.5 (fast) | haiku-fast | Budget-Claude | $0.001 | $0.005 | |
| Claude Haiku 4.5 (thinking) | haiku-thinking | Budget-Claude | $0.001 | $0.005 + thinking | 2K thinking budget |
| Amazon Nova Pro | nova-pro | Mid-budget | $0.0008 | $0.0032 | |
| Amazon Nova Lite | nova-lite | Ultra-budget | $0.00006 | $0.00024 | Headline cost claim |
| Meta Llama 3.1 70B | llama-70b | Budget | $0.00072 | $0.00072 | |

---

## Benchmark Reference

| Benchmark | Type | Available N | Evaluation Method | Baseline Range (Opus-fast) |
|---|---|---|---|---|
| GSM8K | Grade school math | 100 (validated) | Numeric extraction + comparison | ~89-91% |
| MMLU | Multi-choice knowledge | 57 (bugged) / 100 (target) | Letter extraction + comparison | ~89-93% |
| GPQA | PhD-level science | 50+ (needs validation) | Letter extraction + comparison | ~60-70% (Phase 1) |
| HumanEval | Code generation | 50+ (needs validation) | Code execution + test cases | ~25-30% (Phase 1) |

---

## Decision Points

After running the minimum experiments (V1-V4, E1, E3, E4):

**If self-consistency extraction was bugged (V1 confirms):**
→ Re-run E3 with fix. If finding reverses, revise all "proven methods fail" claims.

**If Opus-judge ensemble (E1) outperforms baseline:**
→ The "ensembles fail" conclusion is wrong. The finding is "weak-judge ensembles fail." Major paper revision needed.

**If Opus-judge ensemble (E1) still underperforms:**
→ Strong evidence for fundamental failure. Paper claims become defensible.

**If Nova-lite (E4) scores <80% on GSM8K-100:**
→ Remove or heavily caveat all cost projections. The value narrative collapses.

**If Nova-lite (E4) scores >85% on GSM8K-100:**
→ Cost narrative validated. Can make projections with confidence intervals.

---

*Review completed: April 10, 2026*
*Previous review: REVIEW.md (April 9, 2026) — methodology critique that prompted Phase 2*
*This review: Post-Phase 2 gap analysis with specific experiment prescriptions*
