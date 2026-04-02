# Pre-Run Checklist

## ✅ Configuration Verified

### Models
- **Total:** 13 models configured
- **Tier 1 (Premium):** opus ($15/1M input)
- **Tier 2 (Mid):** nova-pro, mistral-large, llama-3-1-70b, gpt-oss ($0.72-4/1M)
- **Tier 3 (Budget):** haiku, llama-3-1-8b ($0.22-0.80/1M)
- **Tier 4 (Micro):** nova-2-lite, nova-lite, nova-micro, llama-3-2-3b, llama-3-2-1b, nemotron-nano ($0.035-0.15/1M)
- **All models have pricing configured** ✅

### Prompts
- **Total:** 10 prompts (p1-p10)
- **File:** prompts/prompts.json (default)
- **Categories:** math_logic, code_reasoning, ethical_ambiguity, regex, bayes, complexity, philosophy, security, legal, optimization
- **All have ground truth evaluations** ✅

### Features
- **JSON output format** ✅
- **Confidence scoring** ✅
- **Confidence-weighted voting** ✅
- **Parallelization** ✅
- **Ground truth evaluation** ✅
- **Dual experiment (WITH/WITHOUT Opus)** ✅

---

## 📊 Expected Results

### Cost Estimate
- **WITH Opus experiment:** ~$0.70
- **WITHOUT Opus experiment:** ~$0.28
- **Total cost:** ~$0.98 (less than $1!)

### Time Estimate (with parallelization)
- **WITH Opus experiment:** ~2.7 minutes
- **WITHOUT Opus experiment:** ~2.7 minutes
- **Total time:** ~5.4 minutes

### API Calls
- **WITH Opus:** 13 models × 10 prompts + 10 votes + 10 stitches = 150 calls
- **WITHOUT Opus:** 12 models × 10 prompts + 10 votes + 10 stitches = 140 calls
- **Total:** 290 API calls

---

## 🎯 What to Expect

### Output Files

**Experiment 1 (WITH Opus):**
- `results/responses_with_opus.json` - All 13 model responses
- `results/vote_results_with_opus.json` - Confidence-weighted vote outcomes
- `results/stitch_results_with_opus.json` - Synthesized answers
- `results/evaluation_with_opus.json` - Ground truth accuracy analysis

**Experiment 2 (WITHOUT Opus):**
- `results/responses_without_opus.json` - 12 model responses (no Opus)
- `results/vote_results_without_opus.json` - Vote outcomes
- `results/stitch_results_without_opus.json` - Synthesized answers
- `results/evaluation_without_opus.json` - Ground truth accuracy analysis

### Key Metrics to Watch

**1. Accuracy (Ground Truth)**
- Individual model accuracy vs ensemble accuracy
- Does ensemble beat best individual model?
- Does Opus improve ensemble accuracy?

**2. Cost-Effectiveness**
- Cost per correct answer
- Does Opus justify its premium price?
- Which tier provides best value?

**3. Convergence**
- How often do models agree semantically?
- Does diversity actually exist or do models converge?
- Do cheaper models agree with expensive models?

**4. Confidence Calibration**
- Are higher confidence scores correlated with correctness?
- Do expensive models have better calibrated confidence?

---

## ⚠️ Potential Issues to Watch For

### 1. Model Failures
**What:** Some models may return empty responses or errors
**Impact:** Won't break experiment, but reduces ensemble diversity
**Check:** Look for "❌ Error" messages in output

### 2. Rate Limiting
**What:** AWS may throttle if too many parallel requests
**Impact:** Automatic retry with exponential backoff
**Check:** Look for "Throttled (429)" messages

### 3. JSON Parsing Failures
**What:** Some models may not follow JSON format perfectly
**Impact:** Falls back to raw text + default confidence (0.5)
**Check:** Look for "⚠️ JSON parsing failed" warnings

### 4. Ground Truth Evaluation
**What:** Some prompts have "no objective ground truth" (e.g., trolley problem)
**Impact:** Those prompts excluded from accuracy calculation
**Check:** evaluation.json will show which prompts have ground truth

### 5. Empty Opus Responses
**What:** Opus may still return empty answers (though we fixed the multi-block bug)
**Impact:** Opus excluded from aggregation for that prompt
**Check:** Look for empty answers in responses_with_opus.json

---

## 🚀 Ready to Run

### Command
```bash
export AWS_BEARER_TOKEN_BEDROCK=<your-token>
./run_expanded_experiment.sh
```

### What You'll See

1. **Experiment 1 banner** with model list
2. **Harness progress:** 10 prompts, each showing parallel model execution
3. **Vote aggregation:** Parallel processing with confidence weighting
4. **Stitch synthesis:** Parallel processing with convergence analysis
5. **Evaluation:** Ground truth comparison and accuracy metrics
6. **Experiment 2** (same steps, without Opus)
7. **Comparison summary:** Cost and accuracy differences

### Success Criteria

✅ All experiments complete without fatal errors
✅ Output files generated for both experiments
✅ Comparison summary shows cost/accuracy trade-offs
✅ Most models return valid JSON with confidence scores
✅ Vote and stitch produce different aggregated answers
✅ Evaluation shows ground truth accuracy for most prompts

---

## 🔍 Post-Run Analysis

### Questions to Answer

1. **Does ensemble beat best individual?**
   - Look at evaluation.json: `ensemble_accuracy` vs `best_individual_accuracy`

2. **Does Opus add value?**
   - Compare `evaluation_with_opus.json` vs `evaluation_without_opus.json`
   - Is the accuracy gain worth $0.42 extra cost?

3. **Which tier provides best value?**
   - Cost per correct answer across tiers
   - Tier 4 (micro models) may surprise with good accuracy at 1/100th the cost

4. **How often do models converge?**
   - Look at convergence rates in vote_results.json
   - High convergence = low diversity = limited ensemble benefit

5. **Are confidence scores meaningful?**
   - Do models with 0.9+ confidence get it right more often?
   - Or are all models overconfident?

6. **Does confidence weighting help?**
   - Compare weighted vs unweighted voting
   - Does giving more weight to confident models improve accuracy?

---

## 📝 Expected Insights

Based on previous runs with 3 models, we expect:

**Likely Finding 1: Limited Ensemble Value**
- Models may converge on the same answer 70-90% of the time
- When they agree, ensemble just picks the already-correct answer
- When they disagree, ensemble may not beat individual models

**Likely Finding 2: Opus Adds Cost, Not Accuracy**
- Opus is 60x more expensive than Tier 4 models
- But may not produce significantly better answers
- Ensemble without Opus may perform just as well

**Likely Finding 3: Tier 2-3 Sweet Spot**
- Mistral, Nova Pro, Haiku likely provide best value
- Close to Opus accuracy at 1/20th the cost
- Good enough for most prompts

**Likely Finding 4: Micro Models Underrated**
- Llama 3.2 1B/3B, Nova Micro surprisingly capable
- May get 60-70% accuracy at $0.0001 per call
- 1000x cheaper than Opus for similar performance on easier prompts

**Likely Finding 5: Overconfident Models**
- Most models will report 0.8-0.95 confidence even when wrong
- Little correlation between confidence and correctness
- Confidence weighting may not help much

---

## 🎓 What This Experiment Tests

### Core Hypotheses

**H1: Ensemble thinking beats individual models**
- **Prediction:** FALSE - ensemble just picks the already-correct model
- **Test:** Compare ensemble accuracy to max(individual accuracies)

**H2: Expensive models are worth the cost**
- **Prediction:** FALSE - cheaper models get similar accuracy
- **Test:** Cost per correct answer across tiers

**H3: Models provide diverse reasoning**
- **Prediction:** FALSE - models converge on same conclusions
- **Test:** Convergence rate in vote_results.json

**H4: Confidence scores are calibrated**
- **Prediction:** FALSE - models are overconfident
- **Test:** Accuracy of high-confidence (0.9+) answers

**H5: Confidence weighting improves voting**
- **Prediction:** MAYBE - depends on calibration
- **Test:** Compare weighted vs unweighted (would need separate run)

---

## 🔧 If Something Goes Wrong

### Script Fails Midway
```bash
# Check which step failed
cat results/responses_with_opus.json  # Did harness complete?
cat results/vote_results_with_opus.json  # Did vote complete?
cat results/evaluation_with_opus.json  # Did evaluation complete?

# Resume from where it failed (edit run_expanded_experiment.sh to skip completed steps)
```

### AWS Token Expires
```bash
# Get new token and export it
export AWS_BEARER_TOKEN_BEDROCK=<new-token>

# Re-run from failed experiment
```

### Rate Limiting Issues
```bash
# Add --sequential flag to vote and stitch to reduce parallelism
python3 aggregators/vote.py results/responses.json --live --sequential
python3 aggregators/stitch.py results/responses.json --live --sequential
```

### Model Consistently Fails
```bash
# Exclude the failing model and continue
python3 harness.py --exclude-opus --models haiku nova-lite mistral-large llama-3-1-70b ...
```

---

## ✅ Final Check

Before running, verify:

- [ ] AWS_BEARER_TOKEN_BEDROCK is set
- [ ] You have ~$1 budget for API calls
- [ ] You have ~5-6 minutes available
- [ ] Results directory exists: `mkdir -p results`
- [ ] Git is clean (or ready to commit results): `git status`
- [ ] Parallelization is working: `./test_parallelization.sh` (optional)

---

## 🚀 Let's Go!

```bash
export AWS_BEARER_TOKEN_BEDROCK=<your-token>
time ./run_expanded_experiment.sh
```

Good luck! 🎉
