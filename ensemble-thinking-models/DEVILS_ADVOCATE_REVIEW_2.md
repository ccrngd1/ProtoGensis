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

## 🟠 Moderate Issues (Thinking Models)

### 11. Two Projects Tell Overlapping But Inconsistent Stories

The MOA project (592 tests, quality-scored by Opus judge) and thinking-models project (Phase 1+2, accuracy-scored by evaluators) share conclusions but use different methodologies, benchmarks, and evaluation methods. Cross-references are weak. A reader of one BLOG doesn't know about the other's data.

### 12. Phase 1 "0/40" Still Gets Prominent Billing Alongside Phase 2

Phase 2 was explicitly done because Phase 1 methodology was weak. But the BLOG still features "0/40" from Phase 1 prominently next to Phase 2 data, lending Phase 1 findings more authority than the methodology earned.

### 13. Levenshtein Distance ≠ Meaningful Diversity (MOA Project)

81% diversity via character-level edit distance doesn't measure semantic diversity. Two responses can say the same thing in different words (high Levenshtein, low actual diversity) or different things in similar words (low Levenshtein, high actual diversity). The "even 81% diversity didn't help" claim may be measuring the wrong thing.

---

---

# Part 2: MOA Bedrock Guide — Dedicated Review

The thinking-models project got the deep treatment in Part 1. The MOA project has its own distinct methodology, data, and gaps that deserve equal scrutiny. This section covers them.

---

## 🔴 Critical Issues (MOA)

### M1. Opus Baseline Score Is Inconsistent Across Documents (94.4 vs 82.7)

This is the most concerning data integrity issue in the project.

| Document | Opus Baseline Score | Source |
|---|---|---|
| PREMIUM_TIER_RESULTS.md | **94.4 ± 7.6** | Phase 1 single models table |
| RESULTS_AT_A_GLANCE.md | **82.7** | "Complete Results Table" |
| BLOG.md | **82.7** | Used throughout as baseline for all deltas |
| MTBENCH_RESULTS.md | **82.6 ± 20.3** | Phase 2 MT-Bench |

The BLOG and RESULTS_AT_A_GLANCE report 82.7 as the universal Opus baseline. But PREMIUM_TIER_RESULTS reports Opus at 94.4 on the same Phase 1 data. The MT-Bench score is 82.6.

**One of these is wrong, or they're from different scoring runs/methodologies.** If the BLOG's deltas ("-1.4", "-4.5", "-4.8") are computed against 82.7 but Phase 1's raw data shows Opus at 94.4, then:
- The actual deltas are much larger (e.g., Same-Model-Premium at 92.4 vs 94.4 = -2.0, not vs 82.7 = +9.7)
- Or the ensemble scores in the BLOG are also from a different scoring run than PREMIUM_TIER_RESULTS

**This needs to be traced to the raw JSON files and reconciled before any publication.** Every delta, p-value, and effect size depends on the baseline number being correct.

### M2. The Judge (Opus) Is Scoring Its Own Responses

Opus is both the baseline model AND the judge evaluating all responses. The BLOG acknowledges this: "We used Opus to judge its own responses." The mitigation cited: "same-model-premium scored worse than standalone Opus, suggesting Opus doesn't favor more Opus."

But that's not a controlled test of judge bias. Same-model-premium sends Opus 3 other Opus responses as context, fundamentally changing the task from "answer this question" to "synthesize these 3 answers." The lower score could be aggregation overhead, not evidence of fair judging.

**Proper mitigation would include:**
- Using a different judge model (Sonnet, or cross-provider like GPT-4)
- Blind evaluation (judge doesn't know which response came from which config)
- Inter-rater reliability (two judges, measure agreement)

The 20-judgment manual validation (18/20 agreement) is a start but statistically thin for 592 judgments. That's a 3.5% sample.

### M3. MT-Bench Phase 2 Only Tested ONE Ensemble Configuration

MT-Bench (160 tests) only compared Opus vs ultra-cheap ensemble. That's the weakest possible ensemble (cheapest models as proposers). The interesting comparisons — premium ensembles, persona-diverse, cross-vendor — were never tested on MT-Bench.

The 13.1-point gap (82.6 vs 69.6) is real but uninteresting. Of course the cheapest models lose to the most expensive model. The meaningful question — do premium/diverse ensembles beat standalone Opus on multi-turn? — is unanswered.

**Phase 2 was 160 tests but tested only the least interesting comparison.**

### M4. No Repeated Runs in the Entire MOA Project

The thinking-models project ran Phase 2 with 3 independent runs per configuration. The MOA project ran every test exactly once. Zero variance estimates. Zero confidence intervals on the actual scores.

The p-values reported (0.001 to 0.730) come from within-run variance across the 54 prompts — treating each prompt as an independent sample. This is a reasonable approach, but it conflates prompt difficulty variation with configuration quality difference. A harder prompt will score lower for ALL configurations, creating correlated errors.

**Paired analysis** (comparing ensemble vs baseline on the same prompt) would be more appropriate and is the standard approach in ML evaluation. It's unclear whether the reported p-values use paired or unpaired tests.

---

## 🟡 Significant Concerns (MOA)

### M5. "592 Tests" Overstates the Evidence Breadth

592 sounds like a large study. But:
- Phase 1: 54 prompts × 4 configs = 216 datapoints... but only 54 unique prompts
- Phase 2: 80 questions × 2 turns = 160... but only 80 unique questions, tested on 2 configs
- Phase 3: 54 prompts × 4 configs = 216... but the SAME 54 prompts as Phase 1

The actual unique prompt count is ~134 (54 + 80). And only 54 of those were tested across multiple ensemble configurations. "592 test cases" is technically accurate but creates an impression of more evidence diversity than exists.

### M6. Phase 3 Persona Diversity — Only the Pilot Measured Diversity

The "81% diversity" finding comes from a pilot test (20 prompts × 3 personas). The full Phase 3 test used different configurations (4 configs, not 3 personas). Was diversity actually measured on the full test, or is the 81% figure from the pilot being applied to a different setup?

If only the pilot measured diversity, the claim "even 81% diversity didn't help" is conflating pilot diversity measurements with full-test quality measurements from a different configuration.

### M7. Ensemble Configurations Don't Match Wang et al.'s Architecture

The paper positions itself against Wang et al. (2024), but the tested architectures differ significantly:

| Factor | Wang et al. | This Study |
|---|---|---|
| Proposers | GPT-4, Claude, Gemini (cross-provider) | Bedrock-only models |
| Aggregator | GPT-4 Turbo (stronger than proposers) | Opus (equal to best proposer) |
| Benchmark | AlpacaEval, MT-Bench | Custom 54 prompts + partial MT-Bench |
| Layers | Up to 3 | 2-3 |

The study correctly identifies these differences as reasons for divergent results. But the BLOG title "Ensembles Don't Work on Bedrock" could be read as "MoA doesn't work" rather than "MoA doesn't work when your aggregator isn't stronger than your proposers." The latter is a platform constraint, not a method failure.

**The actual finding is: "MoA requires a stronger aggregator than your best proposer, and Bedrock doesn't have one."** That's a useful finding but narrower than "ensembles don't work."

### M8. Smart Routing Recommendation Is Untested

The BLOG recommends "smart routing" (classify complexity → route to appropriate model tier) as a superior alternative. This recommendation includes code examples and cost projections.

But smart routing was never tested. The quality claims ("Better than any ensemble") and cost projections ($0.00056/query blended) are hypothetical. Given how thoroughly the ensembles were tested, presenting an untested alternative as the recommended approach is inconsistent methodology.

### M9. No Cross-Validation of Judge Scores

The judge scored 592 responses with ~1% parse failure rate. But were the scores calibrated? Does Opus-as-judge give consistent scores when evaluating the same response twice? Is there score drift across a multi-hour judging session?

Without intra-rater reliability testing (score the same 20 responses at the beginning and end of the session), we don't know if the judge was consistent. The 20-response manual validation checks accuracy but not consistency.

---

## 🟠 Moderate Issues (MOA)

### M10. "3-6x" Cost Multiplier Range Is Imprecise

EDITORIAL_REFERENCE.md flags this: "Blog says '3-6x' but minimum we tested was 4x." Minor but sloppy for a data-driven piece.

### M11. Nova Premier Substitution May Have Changed Results

High-end-reasoning was supposed to use Nova Premier (a strong proposer). When it went 404, Haiku was substituted. The substitution weakened the proposer tier, potentially changing the result. The original design — Opus + Sonnet + Nova Premier → Opus aggregator — was the closest match to Wang et al.'s architecture. We never saw those results.

### M12. Adversarial Prompts Were Designed to Make Ensembles Fail

5 of 54 prompts (9%) are explicitly adversarial — "designed to trigger hallucinations or expose model limitations." These prompts are specifically crafted for ensemble failure (hallucination amplification). While important to test, including them in the overall average skews the "2-5 point" penalty figure. The analysis should report results with and without adversarial prompts.

### M13. Category Imbalance May Distort Averages

The 54 prompts range from 4 (edge-cases) to 8 (code, creative, factual, analysis) per category. Categories with more prompts have more weight in the overall average. If ensembles happen to perform worse on the larger categories, the penalty is amplified. Weighted-by-category averages should be reported alongside raw averages.

---

## Combined Experiment Matrix: MOA + Thinking Models

### All Verification Tasks (No New Runs)

| # | Project | Action | Purpose | Effort |
|---|---|---|---|---|
| V1 | Thinking | Audit `selected_answer` in `gsm8k_100_selfcons_run*.json` | Self-consistency extraction bug check | 30 min |
| V2 | Thinking | Audit self-consistency sample counts | Confirm 5 samples per prompt per run | 15 min |
| V3 | Thinking | Compare GSM8K-20 vs GSM8K-100 prompt IDs | Explain Phase 1→2 thinking mode discrepancy | 15 min |
| V4 | Thinking | Check temperature: baseline vs self-consistency | Confirm fair comparison | 10 min |
| V5 | Thinking | Fix MMLU loader (57→100 prompts) | Pipeline bug | 1-2 hr |
| V6 | **MOA** | **Reconcile Opus baseline: 94.4 vs 82.7** | **Data integrity — all deltas depend on this** | **1 hr** |
| V7 | **MOA** | **Confirm paired vs unpaired t-tests** | **Statistical validity of all p-values** | **30 min** |
| V8 | **MOA** | **Verify Phase 3 diversity was measured on full run (not just pilot)** | **"81% diversity" claim accuracy** | **30 min** |
| V9 | **MOA** | **Report results with/without adversarial prompts** | **Check if adversarial skews average** | **1 hr** |

### Priority 1: Critical Evidence Gaps (New Runs)

#### Thinking Models

| # | Experiment | Model(s) | Benchmark | N | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E1 | Strong-judge vote | Opus (judge) + Sonnet + Haiku + Nova-pro + Llama-70B + Nova-lite | GSM8K-100 | 100 | 3 | Vote, Opus judge | Is failure architectural (Haiku judge) or fundamental? | ~$20 |
| E2 | Best-of-N + Opus verifier | Opus-fast × 5 candidates, Opus picks best | GSM8K-100 | 100 | 3 | Best-of-N | Strongest ensemble available on Bedrock | ~$25 |
| E3 | Self-consistency (bug-fixed) | Opus-fast | GSM8K-100 | 100 | 3 | Number-first extraction | Verify finding isn't extraction artifact | ~$17 |
| E4 | Nova-lite baseline | Nova-lite | GSM8K-100 | 100 | 3 | Individual | Validate headline cost claim | ~$0.10 |
| E5 | Nova-lite baseline | Nova-lite | MMLU-100 | 100 | 3 | Individual | Cross-benchmark Nova-lite validation | ~$0.10 |

#### MOA Bedrock Guide

| # | Experiment | Model(s) | Benchmark | N | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| M-E1 | **Repeat Phase 1 with 3 runs** | All Phase 1 configs (4) | Custom-54 | 54 | 3 | Full Phase 1 rerun | Add variance estimates + CIs to MOA claims | ~$135 |
| M-E2 | **Cross-judge validation** | Use Sonnet as judge (instead of Opus) on Phase 1 results | Custom-54 | 54 | 1 | Re-score existing responses | Test judge bias (Opus judging itself) | ~$5 |
| M-E3 | **Premium ensembles on MT-Bench** | Mixed-capability, same-model-premium, persona-diverse, Opus baseline | MT-Bench-80 | 80 | 1 | Full ensemble comparison | Close the MT-Bench single-config gap | ~$25 |
| M-E4 | **Smart routing validation** | Nova-lite + Haiku + Opus with classifier | Custom-54 | 54 | 3 | Route by complexity | Validate the recommended alternative | ~$15 |

### Priority 2: Broaden Evidence Base (New Runs)

#### Thinking Models

| # | Experiment | Model(s) | Benchmark | N | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E6 | Full ensemble comparison | Opus-fast, Opus-thinking, Vote (Opus judge), Self-consistency | MMLU-100 | 100 | 3 | All 4 configs | Knowledge task validation | ~$45 |
| E7 | Full ensemble comparison | Same as E6 | GPQA-50+ | 50+ | 3 | All 4 configs | Below-capability test (~70% baseline) | ~$30 |
| E8 | Full ensemble comparison | Same as E6 | HumanEval-50+ | 50+ | 3 | All 4 configs | Very low baseline (~30%) | ~$30 |
| E9 | Opus-fast baseline | Opus-fast | GPQA-50+ | 50+ | 3 | Individual | GPQA baseline for comparison | ~$3 |
| E10 | Opus-fast baseline | Opus-fast | HumanEval-50+ | 50+ | 3 | Individual | HumanEval baseline for comparison | ~$3 |

#### MOA Bedrock Guide

| # | Experiment | Model(s) | Benchmark | N | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| M-E5 | **Test with external benchmark** | All Phase 1 configs | AlpacaEval subset (50 prompts) | 50 | 1 | Match Wang et al. benchmark | Directly comparable to Wang et al. | ~$20 |

### Priority 3: Thinking Mode + Theory Testing

| # | Experiment | Model(s) | Benchmark | N | Runs | Method | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E11 | Thinking vs fast | Opus-thinking | MMLU-100 | 100 | 3 | Individual | Thinking on knowledge tasks | ~$6 |
| E12 | Thinking vs fast | Opus-thinking | GPQA-50+ | 50+ | 3 | Individual | Thinking on hard science | ~$4 |
| E13 | Thinking vs fast | Opus-thinking | HumanEval-50+ | 50+ | 3 | Individual | Thinking on code | ~$4 |
| E14 | Budget baselines | Nova-lite, Haiku-fast, Sonnet-fast | GSM8K-100 | 100 | 3 | Individual | Capability spectrum mapping | ~$2 |
| E15 | Self-consistency LOW baseline | Haiku-fast (~60-70%) | GSM8K-100 | 100 | 3 | Self-consistency (5 samples) | Test if ensembles help below capability limit | ~$3 |
| E16 | Self-consistency LOW baseline | Nova-lite | GPQA-50+ | 50+ | 3 | Self-consistency (5 samples) | Budget model on hard domain | ~$0.50 |
| E17 | Self-consistency MID baseline | Sonnet-fast | GSM8K-100 | 100 | 3 | Self-consistency (5 samples) | Map the help→hurt threshold | ~$6 |

---

## Consolidated Cost Summary

| Priority | Experiments | Purpose | Est. Cost |
|---|---|---|---|
| Verify (P0) | V1-V9 | Audit existing data, reconcile inconsistencies | $0 (time) |
| P1 Critical — Thinking | E1-E5 | Close thinking-models critical gaps | ~$62 |
| P1 Critical — MOA | M-E1 to M-E4 | Close MOA critical gaps | ~$180 |
| P2 Broaden — Thinking | E6-E10 | Multi-benchmark validation | ~$111 |
| P2 Broaden — MOA | M-E5 | Direct Wang et al. comparison | ~$20 |
| P3 Theory | E11-E17 | Thinking mode + systematic error theory | ~$26 |
| **Total** | **All** | **Complete gap closure** | **~$399** |

### Recommended Minimum — Both Projects

| Experiments | Purpose | Cost |
|---|---|---|
| **V1-V4, V6-V8** | Audit existing data for bugs + score reconciliation | $0 |
| **E3** | Bug-fixed self-consistency | ~$17 |
| **E1** | Strong-judge ensemble (Opus as judge) | ~$20 |
| **E4** | Nova-lite on GSM8K-100 | ~$0.10 |
| **M-E2** | Cross-judge validation (Sonnet judges MOA Phase 1) | ~$5 |
| **M-E1** | Phase 1 rerun with 3 runs (variance estimates) | ~$135 |
| **Minimum total** | **Closes critical issues both projects** | **~$177** |

If budget is tight, **V6 (score reconciliation) and M-E2 (cross-judge) are the highest-value MOA items at near-zero cost** — V6 is just tracing numbers, and M-E2 re-scores existing responses with a different judge.

---

## Decision Points

### Thinking Models (unchanged from Part 1)

- **If self-consistency extraction was bugged (V1):** Re-run E3. If finding reverses, revise "proven methods fail" claims.
- **If Opus-judge ensemble (E1) outperforms baseline:** Finding becomes "weak-judge ensembles fail," not "ensembles fail." Major revision.
- **If Nova-lite (E4) scores <80% on GSM8K-100:** Remove or heavily caveat all cost projections.

### MOA Bedrock Guide (new)

- **If V6 shows 94.4 is the correct Opus baseline (not 82.7):** All deltas in BLOG and RESULTS_AT_A_GLANCE are wrong. Every comparison needs recalculation. Publication blocker.
- **If M-E2 (Sonnet judge) produces significantly different rankings:** Opus judge bias is real. All 592 judgments are suspect. Need independent judge for key comparisons.
- **If M-E1 (repeated runs) shows high variance:** The single-run p-values are unreliable. Reported significance levels may not hold.
- **If adversarial prompts (V9) are driving the penalty:** Report with/without. The "2-5 point penalty" headline may become "0-3 points without adversarial prompts."

---

## Model Reference

| Model | Key | Tier | Input $/1K | Output $/1K | Notes |
|---|---|---|---|---|---|
| Claude Opus 4.6 (fast) | opus-fast | Premium | $0.015 | $0.075 | Primary baseline |
| Claude Opus 4.6 (thinking) | opus-thinking | Premium | $0.015 | $0.075 + thinking | 10K thinking budget |
| Claude Sonnet 4.6 (fast) | sonnet-fast | Mid | $0.003 | $0.015 | |
| Claude Sonnet 4.6 (thinking) | sonnet-thinking | Mid | $0.003 | $0.015 + thinking | 5K thinking budget |
| Claude Haiku 4.5 (fast) | haiku-fast | Budget-Claude | $0.001 | $0.005 | |
| Claude Haiku 4.5 (thinking) | haiku-thinking | Budget-Claude | $0.001 | $0.005 + thinking | 2K thinking budget |
| Amazon Nova Pro | nova-pro | Mid-budget | $0.0008 | $0.0032 | |
| Amazon Nova Lite | nova-lite | Ultra-budget | $0.00006 | $0.00024 | Headline cost claim |
| Meta Llama 3.1 70B | llama-70b | Budget | $0.00072 | $0.00072 | |

## Benchmark Reference

| Benchmark | Type | Available N | Evaluation | Baseline (Opus-fast) |
|---|---|---|---|---|
| GSM8K | Grade school math | 100 (validated) | Numeric extraction | ~89-91% |
| MMLU | Multi-choice knowledge | 57 (bugged) / 100 target | Letter extraction | ~89-93% |
| GPQA | PhD-level science | 50+ (needs validation) | Letter extraction | ~60-70% |
| HumanEval | Code generation | 50+ (needs validation) | Code execution | ~25-30% |
| Custom-54 | Mixed (8 categories) | 54 (validated) | Opus judge (100-pt) | 82.7 or 94.4 ⚠️ |
| MT-Bench | Multi-turn dialogue | 80 (validated) | Opus judge (100-pt) | 82.6 |
| AlpacaEval | Instruction following | 50+ (not yet used) | TBD | Not tested |

---

*Review completed: April 10, 2026*
*Previous review: REVIEW.md (April 9, 2026) — methodology critique that prompted Phase 2*
*This review: Post-Phase 2 gap analysis with specific experiment prescriptions across both projects*
