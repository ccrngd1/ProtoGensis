# Your LLM Is a Secret Optimist (or Pessimist). Here's How to Measure It Without Ground Truth.

*By CC*

---

Ask a model: "What's the probability the student passes the exam?" It says 72%.

Now ask the same model, fresh conversation: "What's the probability the student does *not* pass?" It says 20%.

Those should sum to 100. They sum to 92. The model is leaning 8 points pessimistic, and you just measured it without knowing anything about the student, the exam, or whether the real answer is 72, 50, or 99.

That's the insight behind AlignBias. And once you see it, you can't unsee it.

## The Problem Nobody Is Measuring

If you've worked with bias evaluation tools, you've probably used something like DeepEval, Giskard, or LLM BiasScope. Those are excellent at what they do: catching stereotypes, toxicity, demographic disparities in generated text. Social and content bias. Important stuff.

But there's a completely orthogonal bias that none of those tools touch: **directional probability tilt**. Whether a model's numeric estimates under uncertainty systematically lean toward good outcomes or bad outcomes.

Here's why that matters. If your stack uses model-estimated probabilities for anything (triage scoring, risk assessment, forecasting, planning), a 10-point optimist is quietly inflating every success estimate your pipeline consumes. A 10-point pessimist is sandbaging every forecast. And you'd never know, because the text reads fine and the reasoning sounds plausible.

A model can be perfectly clean on content bias and still be a systematic optimist that distorts every probability it touches.

## The Method: Coherence, Not Correctness

This is what makes the approach elegant. Traditional calibration requires ground truth. You need to know the right answer to measure how wrong the model is. That's expensive, domain-specific, and often impossible at scale.

AlignBias uses a different yardstick entirely: **coherence**.

The logic is simple. "P(pass)" and "P(not pass)" describe the same event from opposite directions. A coherent model's answers must sum to 100. No exceptions. No domain knowledge required. No labels needed. You don't need to know whether the real probability is 30 or 70. You just need to check whether the model agrees with itself.

The formula is straightforward:

```
Skew_i = P+(good outcome) - (100 - P-(bad outcome))
```

If Skew > 0, the model is optimistic (inflating good outcomes). If Skew < 0, pessimistic (inflating bad outcomes). If Skew = 0, the model is internally coherent. Still might be wrong about reality, but at least it's consistent.

Run this across 60 naturalistic scenarios spanning six domains (academic, business, everyday, health habits, policy, project), multiple runs, and you get a reliable signed measurement of each model's directional tilt with bootstrap confidence intervals.

## Where This Came From

Credit where it's due. The method and scenarios come from **OptimismBench** by Cho & Koshiyama (Holistic AI/UCL, arXiv 2607.26981, CC BY 4.0). Solid research paper that established the inverted-pair approach and demonstrated real, measurable differences across major LLMs.

AlignBias is the practitioner layer I built on top. The paper proves the phenomenon exists. AlignBias turns that into something you can actually use in a production audit pipeline.

## The Practitioner Layer: What AlignBias Actually Does

The measurement is step one. What practitioners need is the full workflow around it. That's what the tool provides.

### audit

Multi-model Skew measurement. Point it at your LLM providers, it runs the inverted-pair probes concurrently, computes per-model Skew with bootstrap CIs, filters refused answers and exact-50 hedges (models that punt with "50%" on everything get flagged, not counted). You get a clear number: this model tilts +4.2 pp optimistic, that one tilts -7.1 pp pessimistic.

```bash
alignbias audit \
  --models anthropic:claude-opus-4-8,openai:gpt-5.6 \
  --runs 5 --temperature 0.7 --out ./out
```

### control

A self-validation track. 15 items where the correct probability is stated in the question itself ("a fair coin is flipped"). Skew on this track should be approximately zero. If it isn't, your prompting or parsing is broken, not the model. Run this first. Trust but verify.

```bash
alignbias control --models anthropic:claude-opus-4-8
```

### routing-advisor

Here's where it gets practical. You define a YAML policy that says which tasks *want* which tilt:

```yaml
tasks:
  risk-assessment:
    preferred_tilt: pessimistic
    max_abs_skew: 15
  brainstorming:
    preferred_tilt: optimistic
  forecasting:
    preferred_tilt: neutral
    max_abs_skew: 5
```

Risk assessment *wants* a pessimist. Under-promising is the safe failure mode. Brainstorming can tolerate a mild optimist. Forecasting wants closest-to-zero.

Feed it your audit results and it ranks your available models per task type. Instead of routing all traffic to one "best" model, you route by disposition.

### calibrate

Derives additive correction offsets from the measured tilt. The key design choice: **separate success-side and failure-side coefficients**. Because tilts are rarely symmetric.

A model might be accurate on failure questions (P(not pass) is well-calibrated) while systematically deflating success estimates. A single correction scalar would overcorrect the failure side while fixing the success side. Splitting the coefficients into `offset_success_pp` and `offset_failure_pp` handles this cleanly:

```
corrected P(success) = clamp(raw + offset_success, 0, 100)
corrected P(failure) = clamp(raw + offset_failure, 0, 100)
```

These are starting corrections measured on the audit scenario distribution. Not universal fixes. Your domain may tilt differently. But it's a measured starting point, not a guess.

## How It Differs from Social/Content Bias Tools

Let me be direct about what this is and isn't.

| | DeepEval / Giskard / BiasScope | AlignBias |
|---|---|---|
| **Measures** | Stereotypes, toxicity, demographic disparities in text | Directional probability tilt in numeric estimates |
| **Requires** | Generated text samples, demographic categories | Just a model endpoint. No labels, no ground truth |
| **Yardstick** | Social fairness norms | Internal mathematical coherence |
| **Catches** | Model says biased things | Model *thinks* biased probabilities |
| **Matters when** | Content generation, chat | Routing, scoring, forecasting, planning |

They're complementary, not competing. A model can ace every social bias benchmark and still be an 8-point optimist that warps your risk scores.

## The Math, Quickly

For the technically curious. All values are probability points (pp) on a 0-100 scale.

For each scenario *i*, you elicit s⁺ (probability of the good outcome) and s⁻ (probability of the bad outcome) in independent conversations. The model never sees both framings.

```
Skew_i    = s⁺ - (100 - s⁻)           # 0 = coherent
Skew_mean = (1/n) Σ Skew_i             # >0 optimistic, <0 pessimistic

delta+    = mean(all s⁺) - 50          # good-side push from midpoint
delta-    = mean(all s⁻) - 50          # bad-side push from midpoint
Skew      = delta+ + delta-            # decomposition
```

The delta decomposition tells you *where* the tilt lives. A model with delta+ = -6 and delta- = +2 (Skew = -4) is mostly deflating success estimates while being roughly accurate on failures. That's actionable. You know which side to correct.

## Limitations (the Honest Part)

Let's be clear about what Skew is *not*:

**Skew is not deviation from truth.** A model with Skew 0 can still be terribly calibrated against reality. It just agrees with itself. Zero Skew means coherent, not correct.

**Magnitudes are relative.** Compare models measured on the same scenario set with the same settings. Don't treat the number as a universal constant.

**The calibration offset is a starting point.** It was measured on this scenario distribution at one temperature. Re-measure on scenarios resembling your actual workload before trusting corrected numbers in production.

**Temperature and sampling matter.** Use multiple runs (5 minimum) and read the bootstrap CI, not just the point estimate.

## Getting Started

Not on PyPI. Install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/align-bias
pip install -e .
```

Or use it as a library:

```python
from alignbias import AlignBias

audit = AlignBias(models=["anthropic:claude-opus-4-8", "openai:gpt-5.6"])
reports = audit.run(runs=5)
for model, report in reports.items():
    print(model, f"{report.skew_mean:+.1f} pp", report.verdict)
```

The test suite uses mock providers exclusively. No API keys needed to explore the codebase. But for real measurements, you'll want to run `alignbias audit` with live models.

## Why This Matters for Production Stacks

If your application treats model-generated probabilities as inputs to decisions (and many do, implicitly or explicitly), you have an unmeasured systematic error baked into every output. Not random noise. Systematic. Directional. Consistent enough to measure with 60 questions.

Now you can measure it. Decompose where it lives. Route around it. Or correct for it.

That seems worth knowing.

---

*AlignBias is Apache-2.0. Method and scenarios from OptimismBench (Cho & Koshiyama, Holistic AI/UCL, arXiv 2607.26981, CC BY 4.0). Scenario data from the [seonglae/OptimismBench](https://huggingface.co/datasets/seonglae/OptimismBench) dataset release.*
