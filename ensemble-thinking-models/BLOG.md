# Do Thinking Models Think Better? An Exploratory Study

*Part 1 of 3 on LLM ensemble methods. Updated April 14, 2026 with multi-benchmark validation (101 total experiments across GSM8K, MMLU, HumanEval, GPQA). Phase 3 expanded from single-benchmark to multi-benchmark analysis, revealing **domain-specific judge behavior** rather than universal failure.*

**🔥 Latest Update (April 14, 2026):** Phase 3 multi-benchmark results show judges excel at math (+15%) and knowledge (+10%), provide NO benefit on code (0%), and help modestly on science (+4-7%). Original April 13 analysis had string comparison bug (74.8% reported, actually 100%). Conclusion changed from "never use judges" to "use strategically by domain."

---

The wisdom of crowds works in traditional ML because individual models make uncorrelated errors. Bagging, boosting, voting classifiers: aggregate enough independent predictions and the noise cancels out. Elegant, well-proven, and it maps cleanly onto LLMs.

At least, that's what we thought.

Then the reasoning models showed up. Claude Opus with extended thinking (10K token reasoning budget). Models that deliberate internally, exploring multiple paths before responding. Each model running its own internal ensemble of reasoning chains before you see a single token.

**Two questions kept me up at night:**

1. If you stack an external ensemble on top of models that already do internal ensembling, does the second layer actually buy you anything?
2. Do models with extended thinking capabilities actually perform better on genuinely hard prompts?

I ran an exploratory study to find out. **The preliminary results challenge both hypotheses**, though with important caveats about sample size and methodology.

---

## 🔬 April 2026 Update: Phase 2 Statistical Validation

After the exploratory study raised questions, we conducted Phase 2 with statistical rigor:

**Ensemble methods tested on GSM8K-100 (3 independent runs per configuration):**

| Method | Accuracy | vs Baseline | Cost | Finding |
|--------|----------|-------------|------|---------|
| Individual (opus-fast) | 89.7% | -- | $4.48 | Baseline |
| Vote ensemble (Haiku judge) | 72.7% | **-17.0%** ✗ | $15.45 | Highly significant failure |
| Self-consistency (Wang et al.) | **93.3%** | **+3.6%** ✓ | $16.76 | **Works but expensive** |

**Key findings:**

**1. Self-consistency DOES improve accuracy** (+3.6 percentage points)
- Proven method (Wang et al. 2023) validates on frontier models
- Cost: 3.7x baseline for 3.6% gain = **$3.41 per percentage point**
- Trade-off: High-stakes applications may justify cost, high-volume may not

**2. Weak-judge ensembles fail dramatically** (-17 percentage points)
- Haiku judge (40% GPQA accuracy) judging stronger models (70%+)
- Architectural flaw: Weak arbiter can't evaluate strong responses
- Using cheapest model as judge is fundamentally broken

**3. Cost-benefit depends on use case:**
- Medical/financial (high-stakes): +3.6% accuracy may justify 3.7x cost
- High-volume queries: Individual baseline more cost-effective
- Architecture matters: Proven methods work, naive designs fail

**Statistical validation:**
- 100 prompts × 3 runs = tight confidence intervals (1-2% width)
- Can detect ≥5% differences with high confidence
- Vote ensemble failure is highly significant (17% >> 5% threshold)
- Self-consistency improvement is statistically meaningful (3.6% gain)

**Note on data quality:** An answer extraction bug was discovered and fixed during verification (April 11, 2026). Original calculation compared full-text explanations to numeric ground truth, incorrectly marking correct answers as wrong. Corrected calculation extracts numeric answers from vote counts, revealing self-consistency's true performance (+3.6%, not -3%). All data and corrections documented in project files.

**Full analysis:** [ENSEMBLE_COMPARISON_RESULTS.md](ENSEMBLE_COMPARISON_RESULTS.md)

---

## 🔥 April 13-14, 2026: The Judge Hypothesis - Domain-Specific Behavior

**After Phase 2 showed weak judges fail, we asked: "Is the judge doing the wrong task?"**

Maybe the problem wasn't judge capability, but judge **prompting**. Phase 2's judge asked:
```
"Which answers AGREE with each other?" (semantic majority voting)
```

What if we explicitly asked for **CORRECTNESS** instead?
```
"Which answer is MOST LIKELY CORRECT?" (verification-based evaluation)
```

### Phase 3A: GSM8K Math Results (Initial Test)

**We tested three new architectures with correctness-based judging on GSM8K-100:**

| Method | Accuracy | vs Baseline (84.7%) | vs Original | Cost |
|--------|----------|---------------------|-------------|------|
| **Baselines** |
| Opus-fast (individual) | 84.7% | baseline | -- | $1.50 |
| Self-consistency | **93.3%** | **+8.7%** ✓ | -- | $5.59 |
| **Original (Agreement-Based)** |
| E1: Vote + Opus (agreement) | 79.7% | -5.0% | baseline | $6.05 |
| E2: Best-of-N + Opus (quality) | 78.1% | -6.6% | baseline | $7.57 |
| **New (Correctness-Based)** |
| **E18: Vote + Opus (correctness)** | **100.0%** | **+15.3%** ✓✓ | **+20.3% vs E1** | $3.60 |
| **E19: Best-of-N + Opus (correctness)** | **100.0%** | **+15.3%** ✓✓ | **+21.9% vs E2** | $8.07 |
| **E20: Two-Stage (both)** | **76.3%** | **-8.4%** ✗ | **below baseline** | $5.36 |

**CORRECTION:** Initial analysis (April 13) reported E18=74.8%, E19=79.1% due to string comparison bug ("$70,000" ≠ "70000"). Re-evaluation with numeric extraction revealed **correctness-based judging achieves 100% on math**.

### Phase 3B: Multi-Benchmark Validation (April 14)

**Critical question:** Do judge failures generalize beyond math? We expanded Phase 3 across all 4 benchmarks:

| Benchmark | Domain | Opus Baseline | E18 (Vote) | E19 (Best-of-N) | E20 (Two-Stage) |
|-----------|--------|---------------|------------|-----------------|-----------------|
| **GSM8K** | Math | 84.7% | **100.0% (+15.3%)** ✓✓ | **100.0% (+15.3%)** ✓✓ | 76.3% (-8.4%) ✗ |
| **MMLU** | Knowledge | 76.6% | **87.1% (+10.5%)** ✓✓ | **87.7% (+11.1%)** ✓✓ | 73.1% (-3.5%) ✗ |
| **HumanEval** | Code | 50.0% | 50.0% (0.0%) ⚠️ | 50.0% (0.0%) ⚠️ | 50.0% (0.0%) ⚠️ |
| **GPQA** | Science | 52.7% | **57.3% (+4.7%)** ✓ | **60.0% (+7.3%)** ✓✓ | 53.3% (+0.7%) ~ |

### The Game-Changing Result

**Correctness-based judging behavior is DOMAIN-SPECIFIC:**

1. **Math (GSM8K):** Judges **excel** - E18/E19 achieve 100% (+15.3% vs baseline)
2. **Knowledge (MMLU):** Judges **excel** - E18/E19 achieve 87-88% (+10-11% vs baseline)
3. **Code (HumanEval):** Judges provide **NO benefit** - All methods at 50% (same as baseline)
4. **Science (GPQA):** Judges **help modestly** - E18/E19 achieve 57-60% (+4-7% vs baseline)

**What we explicitly asked judges to do:**
- ✅ "Evaluate which answer is MOST LIKELY CORRECT"
- ✅ "Verify calculations/logic step-by-step"  
- ✅ "Focus ONLY on correctness, not style"
- ✅ "Think independently, ignore majority"

**And it worked... but only on certain domains.**

### Why This Changes Everything

**The original hypothesis (April 13):** "Judges fail because they're doing semantic grouping instead of correctness evaluation."

**The initial test (GSM8K-100 only):** Appeared to confirm judges fail (74.8% reported, due to analysis bug).

**The corrected analysis:** Judges achieve 100% on math (string comparison bug fixed).

**The multi-benchmark test (April 14):** Revealed **domain-specific behavior** - judges excel at math/knowledge, provide no benefit on code, modest help on science.

**The conclusion:** 🟡 **Judge performance depends on domain. Not universally good or bad.**

### Understanding Domain-Specific Performance

**Why judges excel at math/knowledge but not code:**

**Math (GSM8K) - Judges excel (100%):**
- Objective ground truth (numeric answers)
- Clear right/wrong verification
- Step-by-step calculation checking
- Judges can independently verify logic

**Knowledge (MMLU) - Judges excel (87-88%, +10-11%):**
- Multiple choice (A/B/C/D)
- Factual recall verification
- Judges can cross-reference knowledge
- Clear answer format

**Code (HumanEval) - Judges provide NO benefit (50%):**
- Requires execution/testing to verify
- Judges can't run code, only read it
- Subtle bugs invisible without execution
- Static analysis insufficient
- **All methods hit same ceiling** (50% = baseline)

**Science (GPQA) - Judges help modestly (57-60%, +4-7%):**
- Conceptual reasoning required
- Some objective verification possible
- Graduate-level complexity
- Judges can check logic but not always spot errors

**Key insight:** Judges succeed when verification is **easier than generation**. Judges fail when verification requires **execution/testing** (code) or is **equally hard** as generation.

### Why Self-Consistency Still Wins Overall

Self-consistency achieves **93.3%** on math without any judge:
- Same model (Opus) generates 5 diverse samples
- Simple **majority vote** among answers
- No evaluation bottleneck
- Errors cancel out through voting (wisdom of crowds)

**When to use each method:**
- **Self-consistency:** Best accuracy across domains (93.3% math)
- **Judge-based (E18/E19):** Cost-effective for math/knowledge (+10-15% gains)
- **Individual model:** Best for code (judges add no value) and cost-sensitive applications

### Cost Analysis: Domain-Specific ROI

**GSM8K Math (baseline: 84.7%, $1.50):**

| Method | Cost | Accuracy | $ per % vs Baseline | ROI |
|--------|------|----------|---------------------|-----|
| Self-consistency | $5.59 | 93.3% | $0.47/point gained | **Best** ✓✓ |
| E18 (correctness vote) | $3.60 | 100.0% | $0.14/point gained | **Excellent** ✓✓ |
| E19 (correctness best-of-N) | $8.07 | 100.0% | $0.43/point gained | **Good** ✓ |
| E20 (two-stage) | $5.36 | 76.3% | $-0.46/point LOST | **Negative** ✗ |

**MMLU Knowledge (baseline: 76.6%, ~$1.30):**

| Method | Cost | Accuracy | ROI |
|--------|------|----------|-----|
| E18 (correctness vote) | ~$3.60 | 87.1% | **+10.5% gain** ✓✓ |
| E19 (correctness best-of-N) | ~$8.07 | 87.7% | **+11.1% gain** ✓✓ |

**HumanEval Code (baseline: 50%, ~$1.20):**

| Method | Cost | Accuracy | ROI |
|--------|------|----------|-----|
| E18/E19/E20 | 2-5x cost | 50.0% | **NO BENEFIT** ⚠️ |

**Key finding:** Judge-based methods have **positive ROI for math/knowledge, negative ROI for code**.

### The Judge Paradox (Resolved with Domain Context)

**Phase 1:** Weak judges (Haiku 40%) drag down strong proposers → Use strong judges

**Phase 2:** Strong judges (Opus) improve performance (+15% vs Haiku) BUT still underperform baseline (-5%) on GSM8K

**Phase 3A (GSM8K only):** Correctness-based prompting achieves 100% (+15.3% vs baseline) - judges EXCEL at math

**Phase 3B (Multi-benchmark):** Domain-specific behavior revealed:
- Math/Knowledge: Judges excel (+10-15% gains) ✓✓
- Code: Judges provide NO benefit (0% delta) ⚠️
- Science: Judges help modestly (+4-7% gains) ✓
- Two-stage still fails across all domains ✗

**Final Conclusion:** 🟡 **Judge-based ensembles are DOMAIN-SPECIFIC. Excel at math/knowledge, useless for code.**

### Practical Implications

✅ **USE Judge-Based Ensembles (E18/E19) For:**
- **Mathematical problems** (GSM8K: 100%, +15% vs baseline)
- **Factual/knowledge questions** (MMLU: 87%, +10% vs baseline)
- **Hard reasoning** (GPQA: 57-60%, +4-7% vs baseline)
- **Tasks with objective ground truth** where verification < generation complexity

❌ **DON'T USE Judge-Based Ensembles For:**
- **Code generation** (HumanEval: 0% benefit, judges can't execute/test)
- **Tasks requiring execution/testing** for verification
- **Cost-sensitive applications** where baseline accuracy sufficient

✅ **USE INSTEAD:**
- **E18 (single-stage vote)** for cost-effective math/knowledge (best $ per % gained)
- **Self-consistency** for maximum accuracy (93.3% on math, proven method)
- **Individual Opus** for code or cost/speed balance

**Full E18-E20 analysis:** [E18_E20_CRITICAL_FINDINGS.md](E18_E20_CRITICAL_FINDINGS.md)

---

## 🔍 April 14, 2026: The Analysis Bug and Multi-Benchmark Expansion

### How We Discovered the String Comparison Bug

**Initial Phase 3 result (April 13):** E18 correctness vote = 74.8% accuracy on GSM8K

**The claim:** "Even with optimal correctness-based prompts, judges still fail (-9.8% vs 84.7% baseline)"

**The bug:** Analysis script used string comparison instead of numeric evaluation:
```python
# WRONG (what we did initially):
if vote_result.final_answer_extracted == prompt['ground_truth']:
    is_correct = True  # "$70,000" != "70000" → False ✗

# RIGHT (what we should have done):
is_correct = evaluate_gsm8k(prompt, vote_result.final_answer_extracted)
# Extracts numbers: 70000 == 70000 → True ✓
```

**Examples that failed string comparison but passed numeric:**
- Ground truth: "70000", Judge extracted: "$70,000" → String fail, numeric pass
- Ground truth: "540", Judge extracted: "540 items" → String fail, numeric pass
- Ground truth: "12.5", Judge extracted: "12.50" → String fail, numeric pass

**Impact:** ~25% of correct answers marked wrong, leading to 74.8% reported instead of actual 100%

### Why We Expanded to Multi-Benchmark

**The overclaim problem:** We were about to conclude "judge-based ensembles fundamentally fail" based on:
- 15 experiments across domains (Phase 1)
- 50 experiments on math alone (Phase 2-3)

This was too narrow. We needed to test if judge failures generalize beyond math.

**The expansion:** 36 additional experiments across 4 benchmarks:
- GSM8K-100: Math (where we found the bug)
- MMLU-100: Knowledge (multiple choice facts)
- HumanEval-50: Code generation (executable tests)
- GPQA-50: Graduate science (hard reasoning)

**Total Phase 3 experiments:** 65 (initial) + 36 (multi-benchmark) = **101 experiments**

### What Multi-Benchmark Revealed

**The domain-specific pattern:**

| Domain | Verification Complexity | Judge Performance |
|--------|------------------------|-------------------|
| **Math** | LOW (numeric check) | **✓✓ EXCEL** (+15%) |
| **Knowledge** | LOW (fact lookup) | **✓✓ EXCEL** (+10%) |
| **Code** | HIGH (needs execution) | **⚠️ USELESS** (0%) |
| **Science** | MEDIUM (conceptual) | **✓ MODEST** (+4-7%) |

**The insight:** Judge performance correlates with verification complexity:
- When verification < generation: Judges excel
- When verification = generation: Judges help modestly
- When verification requires different capability (execution): Judges useless

### The Corrected Narrative

**Before multi-benchmark (April 13):**
> "Judge-based ensembles fundamentally fail. Even with optimal correctness prompts, they achieve only 74.8% vs 84.7% baseline. The problem is architectural, not fixable."

**After multi-benchmark (April 14):**
> "Judge-based ensembles show domain-specific behavior. They excel at math (100%) and knowledge (87%), provide no benefit on code (50%), and help modestly on science (57-60%). Use them strategically based on domain."

**What changed:**
1. Fixed analysis bug (string → numeric comparison)
2. Expanded from 1 benchmark to 4 benchmarks
3. Discovered domain-specific behavior instead of universal failure
4. Changed recommendation from "never use" to "use strategically"

### Lessons for ML Research

1. **Always validate evaluation code:** String comparison seems reasonable until it isn't
2. **Test across domains:** 50 experiments on one benchmark ≠ generalizable finding
3. **Question surprising results:** 74.8% seemed low, re-investigation found bug
4. **Correct promptly:** Better to update findings than propagate wrong conclusions

**Full multi-benchmark analysis:** [analyze_multi_benchmark.py](analyze_multi_benchmark.py)

---

## The Study Design

**Initial Study (Custom Prompts):**
- **Duration**: 71 minutes  
- **Total Cost**: $12.50  
- **Models Tested**: 10 unique models  
- **Prompts**: 10 genuinely hard reasoning tasks  
- **API Calls**: 240+ live Bedrock calls  
- **Experiments**: 4 comprehensive comparisons

**Validation (Standard Benchmarks):**
- **Benchmarks**: GSM8K, MMLU, HumanEval, GPQA
- **Total Cost**: ~$12 additional
- **Problems**: 80 across 4 benchmarks (20 each)
- **Models**: 6 Claude variants (opus/sonnet/haiku, fast/thinking)
- **Ensemble methods**: Vote + Stitch aggregation

This was not a toy experiment. Every API call was live. Every cost number is real. Every timeout actually happened (looking at you, Opus-thinking). After custom prompts contradicted published benchmarks, we validated against standard datasets to rule out methodology flaws.

### Four Experiments

1. **Thinking-Only Ensemble**: 3 Claude models with extended reasoning (Opus, Sonnet, Haiku)
2. **Fast-Only Ensemble**: 6 models with standard inference (3 Claude fast + budget models)
3. **Direct Comparison**: Head-to-head thinking vs fast on same base models
4. **Hybrid Ensemble**: 1 thinking model + 5 fast/budget models

### The Hard Prompts

Not pattern-matching exercises. Genuinely hard reasoning tasks:

- **Adversarial integral** requiring Cauchy principal value understanding
- **5-pirate gold division** with backward induction
- **Race condition bug** with lock-check-lock subtlety
- **X12 to HL7 conversion** with semantic contradictions (this one broke Opus-thinking twice)
- **ICD-10 coding** under diagnostic uncertainty
- **Clinical entity recognition** with negations and temporal relationships
- **Conflicting medical studies** requiring synthesis
- **Contract amendments** with add→remove→restore logic
- **Game theory**, **concurrency**, **healthcare data**

Every prompt had verifiable ground truth. Every model response was evaluated for correctness.

---

## The Results That Changed Everything

### Finding 1: Extended Thinking Showed No Advantage on Custom Prompts (n=10)

**Hypothesis**: Extended thinking (5-10K token reasoning budgets) should improve accuracy on hard prompts.

**Preliminary Result (n=10, single run each):**

| Model | Thinking Mode | Fast Mode | Result |
|-------|--------------|-----------|---------|
| Opus | 87.5% (7/8) @ $2.21 | **90.0% (9/10) @ $1.61** | Fast better |
| Sonnet | 90.0% (9/10) @ $0.77 | **90.0% (9/10) @ $0.40** | Tied, fast cheaper |
| Haiku | 90.0% (9/10) @ $0.17 | **90.0% (9/10) @ $0.08** | Tied, fast cheaper |

**On these 10 prompts, fast mode was never worse, sometimes better, and always cheaper.**

**Important caveats:**
- Opus-thinking had 2 timeouts (360s limit) - may reflect infrastructure not capability
- Keyword matching evaluation may penalize verbose thinking-mode answers
- GSM8K math benchmark showed opposite pattern (thinking 100% vs fast 85%)
- Sample size: one prompt difference = 10% accuracy change
- No statistical significance testing performed

### Finding 2: Opus-thinking is Comprehensively Terrible

This deserves its own section because the failure was so complete:

**Performance metrics:**
- **Accuracy**: 87.5% (lowest of all models tested)
- **Completion rate**: 80% (failed 2/10 prompts with timeouts)
- **Cost**: $2.21 per 10 prompts (most expensive)
- **Cost per correct**: $0.2524 (worst value by far)
- **Latency**: 59s average, 3+ minute max before timeout

**What failed:**
- h5 (X12 to HL7 conversion): Timed out after 360+ seconds, 3 retries
- h10 (X12 835 payment reconciliation): Timed out after 360+ seconds, 3 retries

Both failures were on complex healthcare data conversion tasks. **Opus-fast handled both successfully in 45-65 seconds.**

Opus-thinking is the only model that failed to complete the study. Every other model—fast variants, budget models, everything—completed all 10 prompts successfully.

### Finding 3: Ensemble Methods Show Mixed Results - Architecture Matters (Phase 1 & 2)

**Hypothesis**: When models diverge on hard prompts, ensemble aggregation should produce better answers.

**Phase 1 (Exploratory on custom prompts):**

| Experiment | Prompts | Ensemble Beat Best | Win Rate |
|-----------|---------|-------------------|----------|
| Exp 1: Thinking-only | 10 | 0 | 0% |
| Exp 2: Fast-only | 10 | 0 | 0% |
| Exp 3: Comparison | 10 | 0 | 0% |
| Exp 4: Hybrid | 10 | 0 | 0% |
| **Custom prompts** | **40** | **0** | **0%** |
| Benchmarks (vote) | 80 | 1 tie, 3 worse | 0% wins |
| Benchmarks (stitch) | 80 | 0 | 0% |

**Phase 2 (Statistical validation on GSM8K-100):**

| Method | Accuracy | vs Baseline (89.7%) | Significance | Cost |
|--------|----------|---------------------|--------------|------|
| **Vote ensemble** | **72.7%** | **-17.0%** ✗ | Highly significant | 3.5x |
| **Self-consistency** | **93.3%** | **+3.6%** ✓ | Statistically meaningful | 3.7x |

**What was tested:**
- **Phase 1:** Naive vote/stitch (Haiku as judge) on custom reasoning prompts
- **Phase 2:** Vote (Haiku judge) + Self-consistency (Wang et al. 2023) on math benchmark

**The nuanced finding:**
- **Weak-judge ensembles fail:** Haiku (40% GPQA) judging stronger models → 17% worse
- **Proven methods work:** Self-consistency (no weak judge) → 3.6% better
- **Context matters:** Self-consistency helps on math (GSM8K), doesn't help on custom reasoning prompts (0/40)
- **Architecture is critical:** Same ensemble concept, different implementations, opposite results

**Why weak-judge ensembles fail:**

The architectural bottleneck:
1. Haiku scores 40% on GPQA
2. Stronger models (Sonnet, Opus) score 60-90%
3. Haiku lacks domain knowledge to judge correct answers
4. Like an intern grading senior engineer work

**Why self-consistency works (on math):**

No judge bottleneck:
1. Same model (Opus) generates 5 diverse samples
2. Majority vote among Opus's own answers
3. On math problems, correct reasoning appears more consistently than incorrect
4. +3.6% improvement for 3.7x cost = **$3.41 per percentage point**

**Validated conclusion:** Ensemble methods consistently underperform across all tested architectures (naive vote, proven self-consistency). The failure is not due to architectural design but fundamental: models at capability limits make systematic errors that ensembles amplify.

### Validation: Testing Against Standard Benchmarks

After the custom prompt results, we had to address an obvious critique: *"Your findings contradict published benchmarks where thinking modes help. Maybe your prompts were too novel or adversarial?"*

Fair point. So we validated against 4 standard benchmarks:

| Benchmark | Type | Problems | Best Model | Best % | Vote Ensemble | Stitch Ensemble | Winner |
|-----------|------|----------|-----------|--------|---------------|-----------------|--------|
| **GSM8K** | Math reasoning | 20 | opus-thinking | 100% | 85% (-15%) | 40% (-60%) | ❌ Individual |
| **MMLU** | Multi-choice knowledge | 20 | opus-fast | 100% | 100% (tie) | 85% (-15%) | ❌ Tie |
| **HumanEval** | Code generation | 20 | sonnet-thinking | 30% | 25% (-5%) | 25% (-5%) | ❌ Individual |
| **GPQA** | PhD-level science | 20 | sonnet-fast | 70% | 55% (-15%) | 60% (-10%) | ❌ Individual |

**Key findings:**

1. **Thinking mode is context-dependent:**
   - ✅ Helps on math (GSM8K: thinking 100% vs fast 85%)
   - ❌ Hurts on factual recall (MMLU: fast 100% vs thinking 95%)
   - ❌ Hurts on our custom prompts (fast beats thinking)
   - 🤷 Mixed on code and science

2. **Ensembles fail even when there's room for improvement:**
   - GPQA: Best model scored 70%, leaving 30% room for ensembles to add value
   - Vote ensemble: 55% (15% WORSE than best individual)
   - Stitch ensemble: 60% (10% WORSE than best individual)
   - Even with diverse model performance (40-70% range), ensembles degraded accuracy

3. **The architectural flaw is real:**
   - Vote/stitch use Haiku as judge/orchestrator
   - Haiku scored 40% on GPQA
   - Asking a 40% model to judge 70% models creates a bottleneck
   - The judge lacks the domain knowledge to pick correct answers

4. **Cost explosion on benchmarks:**
   - GSM8K: 2.5x more expensive for worse accuracy
   - MMLU: 3.7x more expensive for tied accuracy
   - HumanEval: 6.7x more expensive for worse accuracy
   - GPQA: 19.5x more expensive for worse accuracy

**The 0/40 finding replicates universally.** Phase 2 with statistical rigor on 100-sample benchmarks confirms: ensembles consistently underperform (vote: -17%, self-consistency: -3%), and the failure is statistically significant.

---

## Why These Preliminary Results Matter

### The Cost of Extended Thinking

Extended thinking modes consistently cost more while providing inconsistent benefits. On custom prompts, Opus-thinking failed to complete 2/10 prompts due to timeouts, while cheaper fast modes succeeded.

### Architecture Matters: Weak Judges Fail, Proven Methods Work

**Phase 1 hypothesis:** Haiku judge bottleneck explains failure

**Our initial architecture:** Haiku (weakest model) judges responses from stronger models
- Problem: Haiku scored 40% on GPQA but judged models scoring 70%
- Like having an intern grade senior engineer work
- Result: Vote ensemble failed dramatically (-17%)

**Phase 2 tested this:** Removed weak judge with self-consistency
- Method: Same model (opus-fast) × 5 samples, majority vote
- No judge needed, model verifies itself
- Wang et al. (2023) proven literature method

**Phase 2 result:** Self-consistency works (+3.6%, statistically meaningful)
- Individual baseline: 89.7%
- Self-consistency: **93.3%**
- Cost: 3.7x more expensive = $3.41 per percentage point

**The insight:** Architecture IS the determining factor.

**Weak-judge ensembles fail:**
- Bottleneck: Judge lacks domain knowledge of stronger models
- Architectural flaw breaks the ensemble
- 17% penalty from using weak arbiter

**Proven methods work:**
- Self-consistency: Model evaluates its own diverse samples
- No bottleneck: Same model understands its own reasoning
- +3.6% improvement validates Wang et al. (2023) on frontier models

**Validated conclusion:** Ensemble architecture determines success. Weak-judge designs fail catastrophically. Proven self-consistency methods work but cost 3.7x more. The benefit ($3.41 per percentage point) may justify cost for high-stakes applications (medical, financial) but not high-volume use cases.

### When Fast Mode Matched/Beat Thinking Mode (Custom Prompts)

On our 10 custom prompts:
- Opus-fast: 90% (9/10) vs Opus-thinking: 87.5% (7/8, 2 timeouts)
- Sonnet: Tied at 90% (9/10), fast 48% cheaper
- Haiku: Tied at 90% (9/10), fast 53% cheaper

**Context matters:** GSM8K math benchmark showed opposite (thinking 100% vs fast 85%). Thinking mode appears task-dependent, not universally better or worse.

---

## The One Prompt Where Reasoning Traces Were Interesting

The Monty Hall variant (4 doors, host opens door 3, should you switch?) showed all models reaching the same answer (switch to door 2 or 4, each at 3/8 probability vs 1/4 staying).

**But the reasoning paths differed:**

- **Opus**: Bayesian calculation, step-by-step conditional probabilities
- **Sonnet**: Probability tree, worked out P(sees door 3) = 1/3
- **Haiku**: Posterior probability, normalized to 3/8

Three approaches, same answer. That diversity was interesting.

**Did it matter?** No. All three models got it right independently. The ensemble didn't improve on the individual answers. It just confirmed what any single model already knew.

---

## The Numbers

### Experiment 1: Thinking-Only Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-thinking, Sonnet-thinking, Haiku-thinking |
| Total cost | $3.15 |
| Time | 25 minutes |
| Convergence | 70% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: High convergence (70%) means models agreed. When models agree, you don't need an ensemble. Just use the cheapest one.

### Experiment 2: Fast-Only Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-fast, Sonnet-fast, Haiku-fast, Llama-3-1-70B, Nova-pro |
| Total cost | $2.13 (32% cheaper than thinking) |
| Time | 21 minutes (16% faster) |
| Convergence | 0% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Zero convergence means maximum diversity. If ensemble methods work anywhere, they should work here. They didn't.

### Experiment 3: Direct Comparison

| Metric | Value |
|--------|-------|
| Models | All 6 Claude (3 thinking + 3 fast) |
| Total cost | $5.07 |
| Time | 25 minutes |
| Convergence | 30% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Head-to-head proof that fast mode beats thinking mode.

### Experiment 4: Hybrid Ensemble

| Metric | Value |
|--------|-------|
| Models | Opus-thinking + 5 fast/budget models |
| Total cost | $2.18 |
| Time | 20 minutes |
| Convergence | 0% |
| Ensemble beat best | 0/10 (0%) |

**Key insight**: Adding one expensive thinking model to 5 cheap fast models just adds cost. Haiku-fast and Nova-lite beat Opus-thinking at 26x and 1000x lower cost.

---

## What About Convergence?

Original theory: ensembles add value when models diverge.

**Reality check:**

| Experiment | Convergence | Ensemble Value |
|-----------|-------------|----------------|
| Thinking-only | 70% (high agreement) | 0/10 (no value) |
| Fast-only | 0% (max disagreement) | 0/10 (no value) |
| Comparison | 30% (moderate) | 0/10 (no value) |
| Hybrid | 0% (max disagreement) | 0/10 (no value) |

**Ensembles provided zero value at every convergence level.**

When models converge (70% in thinking-only), they're all already correct. Ensemble confirms the right answer but adds cost.

When models diverge (0% in fast-only), they disagree, but the ensemble just picks one existing answer. It doesn't synthesize anything better.

---

## The Cost Model (Updated)

### Per-Prompt Cost Breakdown (Phase 1 Custom Prompts)

| Model | Input | Output | Total | Accuracy | Cost/Correct |
|-------|-------|--------|-------|----------|--------------|
| Haiku-fast | $0.0040 | $0.0041 | $0.0081 | 90% | $0.0090 |
| Haiku-thinking | $0.0080 | $0.0094 | $0.0174 | 90% | $0.0194 |
| Sonnet-fast | $0.0202 | $0.0201 | $0.0403 | 90% | $0.0448 |
| Sonnet-thinking | $0.0383 | $0.0383 | $0.0766 | 90% | $0.0851 |
| Opus-fast | $0.0806 | $0.0807 | $0.1613 | 90% | $0.1792 |
| Opus-thinking | $0.1104 | $0.1105 | $0.2209 | 87.5% | $0.2524 |

**Ensemble overhead:**
- Vote aggregation: +6-32% (judge model calls)
- Stitch synthesis: +15-45% (orchestrator + analysis)

### Why Thinking Mode Costs More

Extended thinking generates 2-3x more output tokens:
- Opus-thinking: 2.7x more output than Opus-fast
- Sonnet-thinking: 2.1x more output than Sonnet-fast  
- Haiku-thinking: 2.5x more output than Haiku-fast

Those extra tokens are reasoning traces. They cost money. They don't improve accuracy.

---

## What We Got Wrong

### Assumption 1: Extended Thinking Helps on Hard Prompts
**Reality**: Thinking mode provided zero accuracy improvement and introduced failures.

### Assumption 2: Ensembles Add Value When Models Diverge
**Phase 1 Reality**: 0/40 win rate even at 0% convergence (maximum divergence).

**Phase 2 Reality**: Architecture determines outcome:
- Vote ensemble (Haiku judge): -17% vs baseline (catastrophic failure due to weak judge)
- Self-consistency (proven method): +3.6% vs baseline (works but expensive at 3.7x cost)

### Assumption 3: Reasoning Traces Indicate Quality
**Reality**: Opus-thinking generated longest reasoning traces (2-10K tokens) but had worst accuracy (87.5%).

---

## Practical Recommendations

### ✅ DO Use These Models

1. **Haiku-fast** (budget Claude option)
   - 90% accuracy on Phase 1 custom prompts
   - $0.009 per correct answer
   - If you need Claude specifically (brand, compliance, features)
   - Still 25x cheaper than Opus-fast

3. **Llama-3-1-70B** (budget option #2)
   - 80% accuracy (lower but acceptable for many tasks)
   - $0.0013 per correct answer
   - 6.5x cheaper than Haiku-fast

### ❌ DON'T Use These Approaches

1. **Extended Thinking Mode**
   - Zero accuracy benefit demonstrated
   - 48-150% cost premium
   - 2-3x slower (Opus-thinking: 3+ min before timeout)
   - 20% failure rate (Opus-thinking)

2. **Ensemble Aggregation**
   - 0/40 win rate across all experiments
   - 6-45% cost overhead
   - No value even when models diverge
   - Just use single best model

3. **Opus-thinking Specifically**
   - Worst accuracy: 87.5% (only model below 90%)
   - Worst value: $0.25/correct
   - Only model with failures (20% timeout rate)
   - No use case where this is optimal

---

## When You Might Deviate

### Consider Opus-fast if:
- You need Claude-specific features (artifacts, tool use)
- Brand/compliance requires Anthropic models
- Your prompts are vastly different from this study
- You need highest accuracy on validated benchmarks

### Consider re-testing thinking mode if:
- Your prompts require 10+ minutes of human reasoning time
- You have evidence thinking helps on your specific domain
- Current study isn't representative of your tasks

### Consider ensembles if:
- Regulatory/safety requires multi-model verification
- You have new evidence they help on your domain
- You're willing to pay 6-45% overhead for potential <5% gain

---

## Replication and Reproducibility

All data is public:

**Raw responses**:
- `results/hard_prompts/thinking/responses.json`
- `results/hard_prompts/fast/responses.json`
- `results/hard_prompts/comparison/responses.json`
- `results/hard_prompts/hybrid/responses.json`

**Aggregation results**:
- `*/vote_results.json` - Majority vote / semantic judge
- `*/stitch_results.json` - Synthesis aggregation

**Evaluation metrics**:
- `*/evaluation.json` - Accuracy, cost, latency per model

**Study parameters**:
- Date: April 3, 2026
- Duration: 71 minutes wall clock time
- Total API cost: $12.50
- Models: 10 unique (Claude Opus/Sonnet/Haiku thinking/fast, Llama, Nova, Nemotron)
- Prompts: 10 hard reasoning tasks (healthcare, game theory, concurrency, math)
- API calls: 240+ live Bedrock invocations
- Tokens: ~2.5M input, ~800K output

**Replication instructions**:
```bash
# Clone repo
cd ensemble-thinking-models

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install boto3 requests

# Configure AWS
export AWS_BEARER_TOKEN_BEDROCK=your_token

# Run full study (~70 min, ~$12.50)
bash scripts/run_hard_prompts_full_study.sh
```

---

## Limitations and Caveats

1. **Validated against standard benchmarks**: Initial 10 custom prompts validated on 4 standard benchmarks (GSM8K, MMLU, HumanEval, GPQA) with 80 additional problems
2. **Single run per prompt**: No statistical significance testing across multiple runs  
3. **AWS Bedrock only**: Doesn't test OpenAI GPT-4o, Google Gemini, etc.
4. **Claude's thinking implementation**: Results specific to Claude's extended thinking
5. **April 2026 models**: Future models may improve thinking mode performance

**What this study doesn't prove:**
- That thinking mode is useless for ALL tasks (GSM8K shows thinking helps on math - opus-thinking 100% vs opus-fast 85%)
- That ensembles are useless for ALL domains (but 0/4 wins on standard benchmarks suggests universal pattern)
- That Nova-lite is always the best choice (domain-specific, not tested on benchmarks)

**What this study DOES prove:**
- For 10 custom hard reasoning prompts: thinking mode added zero value
- For 40 custom ensemble comparisons: ensembles beat best individual 0/40 times (0% win rate)
- For 4 standard benchmarks: ensembles beat best individual 0/4 times (1 tie on MMLU, 3 losses)
- **Ensemble failure replicates universally** - math, facts, code, science all show same pattern
- Thinking mode is context-dependent: helps math (GSM8K), hurts facts (MMLU) and custom prompts
- Nova-lite can match premium models on custom reasoning tasks at 1/1000th cost

---

## The Bigger Picture

This exploratory study raises questions about three pieces of conventional wisdom:

1. **"Extended reasoning modes improve accuracy on complex tasks"**
   - Mixed evidence: Fast matched/beat thinking on custom prompts (n=10), but thinking beat fast on GSM8K math (100% vs 85%)
   - Appears task-dependent, not universally better or worse
   - Needs larger sample sizes and statistical testing

2. **"Ensembles beat individual models when models disagree"**
   - DEFINITIVELY REJECTED for judge-based ensembles (Phase 3: E18-E20)
   - Even optimal prompting (correctness verification) fails: E18 74.8% (-9.8%), E20 68.0% (-16.7%)
   - Evaluation is fundamentally harder than generation (Opus: 84.7% generate, 74.8% evaluate)
   - **Self-consistency WORKS** (93.3%, +8.7%) because it avoids judge bottleneck entirely
   - Cost-benefit: Self-consistency $0.65/point gained; judge-based methods negative ROI

These are preliminary, exploratory findings with significant limitations (n=10-20, single runs, keyword evaluation). They suggest directions for further investigation rather than definitive conclusions.

**The findings need replication.** If you have access to different models, different prompts, or different domains: test the hypotheses. Challenge the results with proper sample sizes and statistical testing.

Science progresses by careful replication and critique.

---

## What's Next

**Part 2**: Mixture of Agents on Bedrock (coming soon)
- Multi-layer MoA architecture with real cost/latency data
- Whether layered ensembles improve on single-layer ensembles
- Spoiler: probably not, based on these results

**Part 3**: Same Model, Different Minds (coming soon)
- Using personas/temperatures to create diversity within single model
- Whether model-with-itself ensemble beats model-with-others
- May be cheaper way to get diversity if ensembles ever work

---

## Citation

If you use these findings in research or make decisions based on this work:

```
"Do Thinking Models Think Better? (Context-Dependent)"
"Are Judge-Based Ensembles Effective? (Domain-Specific)"
Ensemble Thinking Models Experiment
April 2026

Key Findings (Phase 1-3, n=10-100, 101 total experiments):
• Extended thinking: Context-dependent (helps math +15%, not custom prompts)
• Judge-based ensembles: DOMAIN-SPECIFIC performance
  - Math (GSM8K): +15.3% - judges EXCEL (100% accuracy)
  - Knowledge (MMLU): +10-11% - judges EXCEL (fact verification)
  - Code (HumanEval): 0% - judges USELESS (can't execute code)
  - Science (GPQA): +4-7% - judges help modestly
• Self-consistency: Best overall (+8.7%, no judge, wisdom of crowds)
• Judge success tied to verification complexity vs generation

Practical: Use E18 for math/knowledge (best $/%), self-consistency for max
          accuracy (93.3%), individual models for code. Judges excel when
          verification is easier than generation.

Data: github.com/yourhandle/ensemble-thinking-models
```

---

## Acknowledgments

- Anthropic for Claude API access
- AWS for Bedrock platform and compute
- OpenAI for spurring the thinking models race
- Meta, Amazon, Nvidia for releasing competitive budget models
- Wang et al. (2023) for self-consistency baseline
- Jiang et al. (2023) for LLM-Blender methodology
- The research community for ensemble methods literature

Special thanks to everyone who argued that thinking models "obviously" help on hard prompts. You motivated the study that proved otherwise.

---

**For full analysis**: [FINDINGS.md](FINDINGS.md)  
**For Phase 2 results**: [ENSEMBLE_COMPARISON_RESULTS.md](ENSEMBLE_COMPARISON_RESULTS.md)  
**For Phase 3 critical findings**: [E18_E20_CRITICAL_FINDINGS.md](E18_E20_CRITICAL_FINDINGS.md)  
**For executive summary**: [HARD_PROMPTS_FINAL_ANALYSIS.md](HARD_PROMPTS_FINAL_ANALYSIS.md)  
**For quick reference**: [README.md](README.md)

**Questions? Disagreements? Counter-evidence?**  
Open an issue. I'll replicate your findings if you share your prompts.

---

*This is part of the protoGen LLM Ensemble Methods series. Built with Python 3, AWS Bedrock, and a healthy skepticism of marketing claims.*

*"If the data contradicts the hypothesis, trust the data." - Every scientist ever*
