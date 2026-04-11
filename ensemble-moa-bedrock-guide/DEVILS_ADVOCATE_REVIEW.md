# Devil's Advocate Review: MOA Bedrock Guide

**Reviewer:** CABAL (Main)
**Date:** April 11, 2026
**Scope:** ensemble-moa-bedrock-guide — all phases, methodology, claims, and evidence gaps
**Purpose:** Hypercritical pre-publication gap analysis

---

## Summary

The MOA project has real strengths: 592 live API tests, automated judge scoring, statistical significance testing, transparent methodology documentation, and an editorial reference mapping claims to evidence. The directional finding — ensembles don't beat standalone Opus on Bedrock — is probably correct.

But the evidence has gaps that an informed reviewer would catch, and some data inconsistencies that could undermine credibility if discovered post-publication.

---

## 🔴 Critical Issues

### 1. Opus Baseline Score Is Inconsistent: 94.4 vs 82.7

This is the most serious data integrity issue in the project.

| Document | Opus Baseline Score | Context |
|---|---|---|
| PREMIUM_TIER_RESULTS.md | **94.4 ± 7.6** | Phase 1 single-model table |
| RESULTS_AT_A_GLANCE.md | **82.7** | "Complete Results Table," used for all deltas |
| BLOG.md | **82.7** | Used throughout as baseline for all ensemble comparisons |
| MTBENCH_RESULTS.md | **82.6 ± 20.3** | Phase 2 MT-Bench (different benchmark, expected to differ) |

PREMIUM_TIER_RESULTS reports Opus at 94.4 on Phase 1's 54 custom prompts. The BLOG and RESULTS_AT_A_GLANCE report 82.7 as the universal baseline — and compute all deltas against it.

**If both come from the same Phase 1 data, one is wrong.** If they come from different scoring runs, neither document explains the discrepancy. Every delta, p-value, and effect size in the BLOG depends on the baseline being correct.

**Example impact:** Same-Model-Premium is reported at 77.9 in the BLOG (vs 82.7 baseline = -4.8 delta). PREMIUM_TIER_RESULTS reports it at 92.4 (vs 94.4 baseline = -2.0 delta). These tell very different stories — a 4.8-point penalty vs a 2.0-point penalty.

**Action required:** Trace both numbers to raw JSON files. Determine which is correct. Recalculate all deltas and p-values against the verified baseline. This is a publication blocker.

---

### 2. Opus Is Judging Its Own Responses

Opus is both the baseline model (generating responses scored against) AND the judge evaluating all 592 responses. The BLOG acknowledges this and cites mitigations:

- "Same judge for all configurations, so relative comparisons are consistent"
- "Same-model-premium scored worse than standalone Opus, suggesting no self-bias"
- "Validated 20 random judgments manually (18/20 agreement)"

**Why these mitigations are insufficient:**

**Relative consistency ≠ no bias.** If Opus systematically scores its own response style 3 points higher across all configs, relative deltas are preserved but absolute scores are inflated. This matters when making claims like "Opus scores 94.4/100" — is that Opus quality or Opus self-assessment?

**Same-model-premium is not a bias control.** That config sends Opus 3 responses as context, fundamentally changing the task. The lower score could be aggregation overhead, not evidence of fair judging. A real bias control would have a different judge score the same responses.

**20 manual validations = 3.4% sample.** For a 592-judgment study, 20 spot-checks is thin. The 90% agreement rate (18/20) means 2 judgments diverged — a 10% human-judge disagreement rate, which would be worth reporting.

**Recommended fix:** Re-score a subset (50-100 responses) using Sonnet as judge. If rankings shift meaningfully, the Opus-as-judge methodology has a problem. Cost: ~$3-5. This is the cheapest high-value verification available.

---

### 3. MT-Bench (Phase 2) Only Tested the Weakest Ensemble

MT-Bench is the strongest validation benchmark in the study — 80 multi-turn questions from the LM-Sys team, directly comparable to Wang et al. But Phase 2 only tested two configurations:

| Config | Score | Notes |
|---|---|---|
| Opus standalone | 82.6 | Baseline |
| Ultra-cheap ensemble | 69.6 | Cheapest possible ensemble |

The 13.1-point gap is real but uninteresting. Of course the cheapest models lose to the most expensive one.

**The comparisons that matter — and are missing:**

| Missing Config | Why It Matters |
|---|---|
| Mixed-capability (cheap proposers + Opus aggregator) | Closest to Wang et al.'s architecture |
| Same-model-premium (3×Opus → Opus) | Isolates aggregation overhead |
| Persona-diverse (Opus with personas) | Tests if diversity helps in multi-turn |
| High-end reasoning (3-layer) | Tests deep ensemble on conversations |

Phase 2 was 160 tests but answered only the least interesting question.

---

### 4. Zero Repeated Runs — No Variance Estimates

The thinking-models project ran Phase 2 with 3 independent runs per configuration, producing confidence intervals and variance estimates. The MOA project ran every single test exactly once. There are no variance estimates anywhere in the 592-test study.

The p-values reported (0.001 to 0.730) come from treating each of the 54 prompts as an independent sample within a single run. This approach has two problems:

**Prompt difficulty is a confounding variable.** A hard prompt scores low for ALL configurations. This creates correlated errors across configs, violating the independence assumption of unpaired t-tests.

**Paired tests should be used.** Since every config was tested on the same prompts, paired t-tests (comparing ensemble vs baseline on each prompt) are the standard approach. It's unclear whether the reported p-values are paired or unpaired — the documentation doesn't specify.

**Without repeated runs, we don't know:**
- Whether scores are stable (would Opus score 94.4 again, or was that a lucky run?)
- Whether the "5 of 6 significant" finding would replicate
- What the confidence intervals on the delta are

---

## 🟡 Significant Concerns

### 5. "592 Tests" Overstates the Evidence Breadth

592 is technically accurate but creates an impression of more evidence than exists.

| Phase | Tests | Unique Prompts | Unique Configs | Unique Prompt×Config Combinations |
|---|---|---|---|---|
| Phase 1 | 216 | 54 | 4 | 216 |
| Phase 2 | 160 | 80 | 2 | 160 |
| Phase 3 | 216 | 54 (same as Phase 1) | 4 | 216 |
| **Total** | **592** | **134** | **~10** | **592** |

Phase 3 reuses the same 54 prompts as Phase 1. Only 134 unique prompts were tested. And only 54 of those were tested across multiple ensemble configurations.

A more honest framing: "134 unique prompts across 10 configurations, totaling 592 evaluations."

---

### 6. Persona Diversity Measurement Doesn't Match the Full Test

The "81% diversity" finding comes from a pilot test: 20 prompts × 3 personas, measured via Levenshtein distance. The full Phase 3 test used 4 different configurations (persona-diverse, reasoning-cross-vendor, reasoning-with-personas, opus baseline).

**Was diversity measured on the full Phase 3 run?** If only the pilot measured diversity, the claim "even 81% diversity didn't help" is conflating pilot diversity measurements with full-test quality measurements from a different configuration.

Additionally, **Levenshtein distance measures character-level edit distance, not semantic diversity.** Two responses can say the same thing in different words (high Levenshtein, low actual diversity) or say meaningfully different things in similar phrasing (low Levenshtein, high actual diversity). Semantic similarity (embedding cosine distance) would be more appropriate.

---

### 7. Tested Architectures Don't Match Wang et al.

The paper positions itself against Wang et al. (2024), but the architectures differ in ways that explain the divergent results:

| Factor | Wang et al. | This Study |
|---|---|---|
| Proposers | GPT-4, Claude, Gemini (cross-provider, truly diverse) | All from AWS Bedrock |
| Aggregator | GPT-4 Turbo (stronger than proposers) | Opus (equal to best proposer) |
| Benchmark | AlpacaEval, MT-Bench (instruction-following) | Custom 54 prompts (mixed) + partial MT-Bench |
| Error correlation | Low (different training, different companies) | Potentially high (same platform) |

The study correctly identifies these as reasons for divergent results. But the finding is more precisely: **"MoA requires a stronger aggregator than your best proposer, and Bedrock doesn't provide one"** — a platform constraint, not evidence that the method is flawed.

The BLOG title "Ensembles Don't Work on Bedrock" is defensible but could be read as "MoA doesn't work" broadly. The narrower claim is more accurate and more useful.

---

### 8. Smart Routing Recommendation Is Untested

The BLOG recommends "smart routing" as the superior alternative to ensembles, complete with code examples and cost projections ($0.00056/query blended cost). But smart routing was never tested.

Given how rigorously the ensembles were tested (592 evaluations, statistical significance, multiple phases), presenting an untested alternative as the recommended approach is an inconsistency. If a reviewer asks "did you test the alternative you recommend?" the answer is no.

---

### 9. No Judge Consistency Check

The Opus judge scored 592 responses over ~32 hours of judging across 3 phases. Were the scores calibrated? Does Opus give consistent scores for the same response when asked twice?

**Potential issues:**
- Score drift across a multi-hour session (fatigue equivalent)
- Temperature-dependent variance in judge scores
- Prompt-order effects (does the judge score harder after seeing many responses?)

**Without intra-rater reliability testing** (score 20 responses at the start and end), we don't know if the judge was consistent. The 20-response manual validation checks accuracy (judge vs human agreement) but not consistency (judge vs itself over time).

---

## 🟠 Moderate Issues

### 10. "3-6x" Cost Multiplier Range Is Imprecise

EDITORIAL_REFERENCE.md flags this: minimum tested was a 4-model ensemble (4 API calls), not 3. The BLOG should say "4-6x" or explain the 3x case. Minor but sloppy for a data-driven piece.

### 11. Nova Premier Substitution May Have Changed Results

High-end-reasoning was designed with Nova Premier as a strong proposer. When it returned 404, Haiku was substituted. This weakened the proposer tier, changing the configuration from "strong diverse proposers" to "Opus + Sonnet + Haiku." The original design was the closest match to Wang et al.'s architecture. Those results were never obtained.

### 12. Adversarial Prompts May Skew Averages

5 of 54 prompts (9%) are explicitly adversarial — "designed to trigger hallucinations." The GDP of Lesotho example (48-point degradation) is compelling but also an edge case specifically crafted for ensemble failure. Including these in the overall average ("2-5 point penalty") may overstate the penalty on normal prompts.

**Fix:** Report results with and without adversarial prompts. If the penalty drops to 0-2 points without adversarial prompts, the headline changes.

### 13. Category Imbalance May Distort Averages

54 prompts across 8 categories, ranging from 4 (edge-cases) to 8 (code, creative, factual, analysis). Categories with more prompts carry more weight in overall averages. If ensembles happen to perform worse on the larger categories (e.g., code), the average penalty is inflated.

**Fix:** Report both raw averages and category-weighted averages (equal weight per category).

---

## What Has Already Been Run

### Phase 1: Premium Tier Testing (March 30-31, 2026)

| Config | Type | Prompts | Runs | Judge | Status |
|---|---|---|---|---|---|
| Opus standalone | Individual baseline | 54 | 1 | Opus | ✅ Complete |
| High-end reasoning (3-layer: Opus+Sonnet+Haiku → Opus+Sonnet → Opus) | Ensemble | 54 | 1 | Opus | ✅ Complete |
| Mixed-capability (Nova-lite+Haiku+Llama-8B → Opus) | Ensemble | 54 | 1 | Opus | ✅ Complete |
| Same-model-premium (3×Opus → Opus) | Ensemble (ablation) | 54 | 1 | Opus | ✅ Complete |

**Key results:**
- All ensembles scored lower than Opus standalone
- 2 of 3 comparisons statistically significant (p < 0.01)
- Same-model-premium: -2.0 to -4.8 points (⚠️ depends on which baseline is correct)

### Phase 2: MT-Bench Multi-Turn (April 1-2, 2026)

| Config | Type | Questions | Turns | Runs | Judge | Status |
|---|---|---|---|---|---|---|
| Opus standalone | Individual baseline | 80 | 2 | 1 | Opus | ✅ Complete |
| Ultra-cheap ensemble | Ensemble | 80 | 2 | 1 | Opus | ✅ Complete |

**Key results:**
- Opus: 82.6, Ultra-cheap: 69.6 (p < 0.0001)
- Gap largest on coding (+18.4), reasoning (+18.1), writing (+18.0)
- Only tested weakest ensemble — premium ensembles not tested on MT-Bench

### Phase 3: Persona Diversity (April 3-4, 2026)

| Config | Type | Prompts | Runs | Judge | Status |
|---|---|---|---|---|---|
| Opus standalone | Individual baseline | 54 | 1 | Opus | ✅ Complete |
| Persona-diverse (3×Opus with different personas → Opus synthesizer) | Ensemble | 54 | 1 | Opus | ✅ Complete |
| Reasoning cross-vendor (Opus+Sonnet+Mistral Large → Opus) | Ensemble | 54 | 1 | Opus | ✅ Complete |
| Reasoning + personas (cross-vendor with persona injection) | Ensemble | 54 | 1 | Opus | ✅ Complete |

**Diversity pilot (separate):** 20 prompts × 3 personas, measured 81% Levenshtein diversity.

**Key results:**
- All ensembles scored lower than Opus standalone
- 3 of 3 comparisons statistically significant (p < 0.05)
- Even 81% diversity (pilot-measured) didn't help

### Phase 1 Supplementary: Single-Model Baselines

| Model | Type | Prompts | Runs | Judge | Score | Status |
|---|---|---|---|---|---|---|
| Nova Lite | Individual | 54 | 1 | Opus | 81.8 ± 16.7 | ✅ Complete |
| Haiku 4.5 | Individual | 54 | 1 | Opus | 89.5 ± 12.7 | ✅ Complete |
| Sonnet 4.6 | Individual | 54 | 1 | Opus | 92.2 ± 11.5 | ✅ Complete |
| Opus 4.6 | Individual | 54 | 1 | Opus | 94.4 ± 7.6 | ✅ Complete |

### Additional Testing

| Test | Prompts | Status | Notes |
|---|---|---|---|
| Diversity pilot (Levenshtein measurement) | 20 | ✅ Complete | 81% avg diversity |
| Judge parse failure analysis | 592 | ✅ Complete | 3/592 required manual intervention |
| Manual judge validation | 20 | ✅ Complete | 18/20 agreement (90%) |

---

## What Needs to Be Run

### Priority 0: Verification Tasks (No API Calls)

| # | Task | Purpose | Effort | Blocks |
|---|---|---|---|---|
| V1 | **Trace Opus baseline discrepancy (94.4 vs 82.7) to raw JSON** | Data integrity — all deltas depend on this | 1 hr | Everything |
| V2 | Confirm whether p-values used paired or unpaired t-tests | Statistical validity | 30 min | Publication |
| V3 | Verify Phase 3 diversity was measured on full run, not just pilot | "81% diversity" claim | 30 min | Phase 3 claims |
| V4 | Report results with/without adversarial prompts | Check if 5 adversarial prompts skew average | 1 hr | Headline penalty |
| V5 | Report category-weighted averages alongside raw averages | Check for imbalance distortion | 30 min | Quality |

### Priority 1: Critical New Experiments

| # | Experiment | Config | Benchmark | N | Runs | Judge | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E1 | **Cross-judge validation** | Re-score Phase 1 responses | Custom-54 | 54 × 4 configs = 216 | 1 | **Sonnet** (not Opus) | Test whether Opus self-bias affects rankings | ~$5 |
| E2 | **Phase 1 rerun with variance** | All 4 Phase 1 configs | Custom-54 | 54 | **3** | Opus | Add confidence intervals to all claims | ~$135 |
| E3 | **Premium ensembles on MT-Bench** | Mixed-capability, same-model-premium, persona-diverse | MT-Bench-80 | 80 | 1 | Opus | Close the "only tested weakest ensemble" gap | ~$25 |

### Priority 2: Strengthen the Story

| # | Experiment | Config | Benchmark | N | Runs | Judge | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E4 | **AlpacaEval comparison** | Phase 1 configs (4) | AlpacaEval-50 | 50 | 1 | Opus | Direct comparison to Wang et al.'s benchmark | ~$20 |
| E5 | **Smart routing validation** | Nova-lite + Haiku + Opus with complexity classifier | Custom-54 | 54 | 3 | Opus | Validate the recommended alternative | ~$15 |
| E6 | **Stronger aggregator test** | Cheap proposers → Sonnet aggregator (not Opus) → Opus judge | Custom-54 | 54 | 1 | Opus | Test different aggregator tiers | ~$8 |

### Priority 3: Systematic Error Theory (Cross-Project)

| # | Experiment | Config | Benchmark | N | Runs | Judge | Purpose | Est. Cost |
|---|---|---|---|---|---|---|---|---|
| E7 | **Low-baseline ensemble** | 3×Haiku proposers → Opus aggregator | Custom-54 | 54 | 1 | Opus | Does MoA help when proposers are weak (~85/100)? | ~$5 |
| E8 | **Very-low-baseline ensemble** | 3×Nova-Lite proposers → Haiku aggregator | Custom-54 | 54 | 1 | Opus | Does MoA help when proposers are very weak (~76/100)? | ~$1 |

---

## Complete Experiment Matrix: What Exists vs What's Needed

### Custom-54 Prompts

| Configuration | Phase 1 (1 run) | Rerun (3 runs) | Sonnet Judge | Status |
|---|---|---|---|---|
| Opus standalone | ✅ | ❌ Needed (E2) | ❌ Needed (E1) | Partial |
| High-end reasoning | ✅ | ❌ Needed (E2) | ❌ Needed (E1) | Partial |
| Mixed-capability | ✅ | ❌ Needed (E2) | ❌ Needed (E1) | Partial |
| Same-model-premium | ✅ | ❌ Needed (E2) | ❌ Needed (E1) | Partial |
| Persona-diverse | ✅ (Phase 3) | ❌ | ❌ | Partial |
| Reasoning cross-vendor | ✅ (Phase 3) | ❌ | ❌ | Partial |
| Reasoning + personas | ✅ (Phase 3) | ❌ | ❌ | Partial |
| 3×Haiku → Opus aggregator | ❌ | ❌ | ❌ | Not started (E7) |
| 3×Nova-Lite → Haiku aggregator | ❌ | ❌ | ❌ | Not started (E8) |
| Smart routing (Nova-Lite/Haiku/Opus) | ❌ | ❌ | ❌ | Not started (E5) |

### MT-Bench (80 Questions)

| Configuration | Tested (1 run) | Status |
|---|---|---|
| Opus standalone | ✅ | Complete |
| Ultra-cheap ensemble | ✅ | Complete |
| Mixed-capability | ❌ Needed (E3) | Not started |
| Same-model-premium | ❌ Needed (E3) | Not started |
| Persona-diverse | ❌ Needed (E3) | Not started |

### AlpacaEval (Wang et al. Benchmark)

| Configuration | Tested | Status |
|---|---|---|
| All Phase 1 configs | ❌ Needed (E4) | Not started |

### Individual Model Baselines (Custom-54)

| Model | Tested (1 run) | Multiple Runs | Status |
|---|---|---|---|
| Nova Lite | ✅ (81.8) | ❌ | Partial |
| Haiku 4.5 | ✅ (89.5) | ❌ | Partial |
| Sonnet 4.6 | ✅ (92.2) | ❌ | Partial |
| Opus 4.6 | ✅ (94.4 or 82.7 ⚠️) | ❌ | ⚠️ Inconsistent |

---

## Cost Summary

| Priority | Experiments | Purpose | Est. Cost |
|---|---|---|---|
| P0 (Verify) | V1-V5 | Audit data, reconcile scores, check stats | $0 (time only) |
| P1 (Critical) | E1-E3 | Cross-judge, variance, MT-Bench gap | ~$165 |
| P2 (Strengthen) | E4-E6 | AlpacaEval, smart routing, aggregator tiers | ~$43 |
| P3 (Theory) | E7-E8 | Low-baseline ensemble tests | ~$6 |
| **Total** | **V1-V5 + E1-E8** | **Complete gap closure** | **~$214** |

### Recommended Minimum

| Item | Purpose | Cost |
|---|---|---|
| V1 | **Reconcile 94.4 vs 82.7** — publication blocker | $0 |
| V2 | Confirm paired/unpaired t-tests | $0 |
| V4 | Report with/without adversarial prompts | $0 |
| E1 | Cross-judge validation (Sonnet re-scores Phase 1) | ~$5 |
| **Minimum** | **Closes biggest credibility risks** | **~$5** |

If V1 reveals the baseline is wrong, all deltas need recalculation before anything else matters. If E1 shows Sonnet-as-judge produces different rankings, the Opus self-judging methodology is compromised and the study needs a different judge.

**If budget allows (~$165 more):** Add E2 (repeated runs for variance) and E3 (premium ensembles on MT-Bench). These close the two structural gaps — no variance estimates and incomplete MT-Bench coverage.

---

## Decision Points

**After V1 (baseline reconciliation):**
- If 94.4 is correct → BLOG deltas are all wrong; recalculate everything
- If 82.7 is correct → PREMIUM_TIER_RESULTS has an error; fix that document
- If they're from different scoring approaches → document both, explain the discrepancy

**After E1 (cross-judge):**
- If Sonnet rankings match Opus rankings → judge bias is not a concern; proceed
- If rankings diverge significantly → Opus self-judging is compromised; re-evaluate with independent judge

**After E2 (repeated runs):**
- If variance is low (CIs ≤ 3 points) → single-run p-values are likely valid
- If variance is high (CIs > 5 points) → "statistically significant" findings may not replicate

**After V4 (adversarial analysis):**
- If penalty drops to ≤1 point without adversarial prompts → headline needs revision
- If penalty holds at 2+ points without adversarial → finding is robust

---

## Model Reference

| Model | Role in Study | Input $/1K | Output $/1K | Notes |
|---|---|---|---|---|
| Claude Opus 4.6 | Baseline, proposer, aggregator, judge | $0.015 | $0.075 | Does everything — that's part of the problem |
| Claude Sonnet 4.6 | Proposer (Phase 1, 3) | $0.003 | $0.015 | Recommended as alternative judge (E1) |
| Claude Haiku 4.5 | Proposer (Phase 1) | $0.001 | $0.005 | |
| Amazon Nova Lite | Proposer (cheap tier) | $0.00006 | $0.00024 | |
| Amazon Nova Pro | Not tested in MOA | $0.0008 | $0.0032 | Could be tested as aggregator |
| Meta Llama 3.1 8B | Proposer (cheap tier) | $0.0003 | $0.0003 | |
| Mistral Large | Proposer (Phase 3 cross-vendor) | ~$0.004 | ~$0.012 | |
| Mistral 7B | Proposer (cheap tier) | $0.00015 | $0.0002 | |
| Amazon Nova Premier | Originally planned for high-end | N/A | N/A | Went 404 — substituted with Haiku |

---

*Review completed: April 11, 2026*
*Companion review: `../ensemble-thinking-models/DEVILS_ADVOCATE_REVIEW_2.md` covers the thinking-models project*
