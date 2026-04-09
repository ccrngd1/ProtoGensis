# Critical Review: Ensemble Thinking Models Experiment

*Internal review — methodology critique and validity assessment.*

---

## 🔴 Critical Methodology Issues

### 1. N=10 Is Not a Study, It's an Anecdote

This is the biggest problem. 10 prompts, single run per prompt, no statistical significance testing. The limitations section acknowledges this but the conclusions don't reflect it — sweeping claims like "Don't use ensembles" and "Extended thinking provides ZERO value" are stated with red X emojis and definitive language.

With n=10, **one prompt flip changes accuracy by 10 percentage points**. Opus-thinking scored 87.5% (7/8 completed) vs 90% (9/10) for others. That's a difference of maybe two prompts. On a bigger sample, that could easily be noise. You can't reject a hypothesis with p-values you never calculated.

The benchmark validation (n=20 per benchmark) helps, but 20 isn't much better. You'd need hundreds of prompts per category to make claims this strong.

### 2. The Evaluation Is Subjective and Fragile

The `evaluate.py` grading is keyword matching and pattern detection. For custom prompts, ground truth evaluation checks things like "does the answer contain '3/8' AND 'switch'" or "do 30% of key words overlap." That's not rigorous accuracy measurement.

For open-ended prompts like h5 (X12→HL7 conversion), h6 (ICD-10 coding), h7 (entity extraction) — there's a huge space of "correct enough" answers. The automated keyword matchers could mark a substantively correct answer wrong for missing a keyword, or mark a subtly wrong answer correct for hitting the right tokens.

**This matters especially for the thinking vs fast comparison.** If thinking mode produces more nuanced answers that don't hit keyword patterns as cleanly, the evaluation would systematically penalize it.

### 3. Opus-Thinking "Failed" on Timeouts — That's a Configuration Problem, Not a Finding

Opus-thinking "failed" 2/10 prompts due to timeouts at 360 seconds. But the timeout is a harness parameter. If the model needed 400 seconds, the harness limited the model — the model didn't fail the task.

Removing those 2 prompts, Opus-thinking scored 7/8 = 87.5%. But if it had completed them (which Opus-fast did), it might have scored 9/10 or 10/10. **The experiment penalized the model for an infrastructure constraint, then declared it the worst performer.** That's not a fair comparison.

### 4. The Ensemble Design Is Naive — Then Ensembles Were Declared Useless

The ensemble methods tested:
- **Vote**: Haiku as a judge picks the "best" answer
- **Stitch**: Haiku synthesizes all responses

Haiku — the weakest Claude model — was used as both judge and synthesizer. On GPQA, Haiku scored 40%. It was then asked to judge responses from models scoring 70%. Of course the ensemble failed. **One specific, arguably bad, ensemble architecture was tested and ensembles in general were declared worthless.**

Real ensemble methods in the literature include:
- Weighted voting (by model confidence or historical accuracy)
- Self-consistency (same model, multiple samples, majority vote)
- Best-of-N with a strong verifier
- Debate-style adversarial aggregation
- Universal Self-Consistency (no judge needed — models verify each other)

Using the weakest model as the arbiter is like having the intern grade the senior engineers' work and concluding that "team reviews don't add value."

### 5. The Prompts Are Heavily Domain-Skewed

6/10 prompts are healthcare/medical (h4, h5, h6, h7, h8, h10). That's not "10 hard reasoning tasks" — it's "6 healthcare tasks and 4 others." The findings may say more about model performance on healthcare-specific knowledge than about reasoning in general.

If Nova-lite happened to have strong healthcare training data, it would look like a genius. If Opus-thinking's extended reasoning is better suited to pure math/logic (which the GSM8K validation actually suggests — thinking 100% vs fast 85%), that wouldn't show up because 60% of the test is one domain.

### 6. Thinking Budgets Were Fixed, Not Optimized

Opus got 10K tokens, Sonnet 5K, Haiku 2K. Were these optimal? Too low and thinking mode can't finish reasoning. Too high and it overthinks.

The thinking budget is a hyperparameter. One setting was tested and thinking mode was declared useless. That's like testing a neural network with one learning rate and concluding neural networks don't work.

### 7. The "Nova-lite Wins Everything" Narrative Is Overfitted

Nova-lite matching Opus at 90% on 10 prompts doesn't mean Nova-lite is generally equivalent to Opus. On a different prompt set — complex multi-step math, long-context reasoning, nuanced creative writing — the gap might be enormous.

The benchmark validation exposed this gap: Nova-lite wasn't tested on the standard benchmarks (only Claude variants were). So the "1000x better value" claim rests entirely on the 10 custom prompts.

### 8. Single Run = No Variance Estimate

LLMs are stochastic. Temperature > 0 means the same prompt can produce different answers on different runs. Each prompt was run once per model. Opus-thinking's two timeouts could be unlucky draws. Nova-lite's 90% could include lucky draws.

Without multiple runs per prompt, there are no error bars, no confidence intervals, no way to distinguish signal from noise. The "0/40 ensemble win rate" sounds devastating but could look very different as "2/40" or "5/40" with repeated trials — still not great, but a different story.

---

## 🟡 Moderate Concerns

### 9. Cost Comparisons Assume Token Pricing Is the Only Cost

Cost per correct answer is calculated using API pricing. But in production, there are other costs: integration complexity, model availability, rate limits, regional latency, feature support. Nova-lite being cheap per token doesn't help if it lacks tool use, structured output, or an org requires Anthropic's safety guarantees.

### 10. "0/40" Conflates Different Failure Modes

The ensemble failing on converged prompts (all models already right) and failing on diverged prompts (models disagree) are fundamentally different problems. Lumping them into one "0/40" stat is misleading.

The interesting question is: *on prompts where models disagreed AND the best individual was wrong*, did ensembles help? With only 10 prompts per experiment, there are probably ~1-2 such cases — not enough to say anything.

### 11. The Benchmark Validation Has Its Own Issues

20 problems per benchmark, only Claude models tested (not Nova-lite), and HumanEval best accuracy at 30% suggests something may be off with the harness for code execution tasks (HumanEval typically sees 80%+ from frontier models). Were code solutions actually executed and tested, or just keyword-matched?

---

## Summary

The experiment is interesting as a **pilot study** or **exploratory analysis**. The directional findings — cheap models can surprise you, thinking mode isn't a silver bullet, naive ensembles don't help — are plausible and worth investigating further.

But the claims are **significantly stronger than the evidence supports**. "REJECTED" with definitive language on n=10 with no statistical testing, subjective grading, a capped timeout that penalizes the model under test, and a naive ensemble design used to dismiss the entire concept — that's preliminary findings presented as conclusions.

### Recommended Fixes

1. **More prompts** — 50-100 minimum per category, ideally 200+
2. **Multiple runs** — 3-5 per prompt per model, report means and confidence intervals
3. **Proper statistical testing** — paired t-tests or bootstrap confidence intervals on accuracy differences
4. **Stronger ensemble baselines** — Best-of-N, weighted voting, self-consistency, strong verifier model
5. **Remove or extend timeout** — Don't penalize a model for infrastructure limits, or report it separately from accuracy
6. **Diversify prompt domains** — Balance healthcare with math, code, logic, creative reasoning
7. **Test Nova-lite on benchmarks** — If it's the headline finding, validate it on standard datasets
8. **Honest framing** — "preliminary findings" or "exploratory study", not hypothesis rejection

---

*Review date: April 9, 2026*
