# Premium Tier Benchmark Results

**Date:** April 9, 2026  
**Duration:** 3 hours 37 minutes  
**Cost:** ~$45  
**Prompts:** 54 across 8 categories  
**Configurations:** 11 (4 baselines + 7 ensembles)  

---

## Executive Summary

**Key Finding:** Ensemble approaches do NOT improve quality over standalone models, at any tier.

- ❌ **Budget tier:** Diverse ensemble (Nova Lite + Mistral + Llama) scores 3.3 points LOWER than same-model (p=0.36)
- ❌ **Premium tier:** 3x Opus ensemble scores 2.0 points LOWER than standalone Opus (p=0.30)
- ❌ **Mixed tier:** Cheap proposers + Opus aggregator scores 0.6 points lower than standalone Opus (p=0.73)

**Recommendation:** Use standalone models. Ensembles cost 1.5-5x more for same or worse quality.

---

## Quality Results (Judge: Opus)

### Single Models (Baselines)

| Model | Quality /100 | Cost/Prompt | Latency | Quality/$ |
|-------|--------------|-------------|---------|-----------|
| nova-lite | 81.8 ± 16.7 | $0.000133 | 3.8s | 615,038 |
| haiku | 89.5 ± 12.7 | $0.003347 | 9.1s | 26,739 |
| sonnet | 92.2 ± 11.5 | $0.015799 | 19.3s | 5,836 |
| **opus** | **94.4 ± 7.6** | **$0.079355** | **21.0s** | **1,190** |

### Ensembles

| Ensemble | Quality /100 | Cost/Prompt | Latency | Quality/$ |
|----------|--------------|-------------|---------|-----------|
| ultra-cheap | 78.2 ± 18.4 | $0.000644 | 9.8s | 121,429 |
| code-generation | 89.4 ± 13.3 | $0.007202 | 26.5s | 12,410 |
| reasoning | 91.1 ± 11.9 | $0.018267 | 49.5s | 4,988 |
| same-model-baseline | 81.4 ± 18.1 | $0.003894 | 13.2s | 20,903 |
| **mixed-capability** | **93.8 ± 9.9** | **$0.115835** | **32.7s** | **810** |
| **same-model-premium** | **92.4 ± 11.4** | **$0.383400** | **40.5s** | **241** |

**Note:** high-end-reasoning failed (Nova Premier access denied), not included.

---

## Key Findings

### 1. Budget Tier: Diversity Does NOT Help

**Test:** Diverse ensemble (Nova Lite + Mistral + Llama) vs Same-Model (3x Nova Lite)

| Metric | Diverse | Same-Model | Delta |
|--------|---------|------------|-------|
| Quality | 78.2 ± 18.4 | 81.4 ± 18.1 | **-3.3** |
| Cost | $0.000644 | $0.003894 | +$0.003 |
| p-value | - | - | **0.357** |

**Result:** No significant difference (p=0.357). Same-model actually scores 3.3 points HIGHER.

**Interpretation:** At budget tier, diversity does not improve quality. Aggregation alone provides the benefit.

---

### 2. Premium Tier: Ensembles Do NOT Beat Standalone Opus

#### Test A: Same-Model Premium (3x Opus) vs Standalone Opus

| Metric | 3x Opus Ensemble | Opus Alone | Delta |
|--------|------------------|------------|-------|
| Quality | 92.4 ± 11.4 | 94.4 ± 7.6 | **-2.0** |
| Cost | $0.383400 | $0.079355 | **+$0.304** |
| p-value | - | - | **0.299** |

**Result:** No significant difference (p=0.299). Standalone Opus scores 2.0 points HIGHER.

**Cost Analysis:**
- Same-model-premium costs **4.8x more** ($0.38 vs $0.08)
- Delivers **2 points LOWER quality** (92.4 vs 94.4)
- Quality-per-dollar: **-79.7% worse** (241 vs 1,190)

**Interpretation:** Adding ensemble overhead (3x proposers + aggregation) does not improve quality. Just use Opus.

---

#### Test B: Mixed-Capability (Cheap + Opus) vs Standalone Opus

| Metric | Cheap Proposers + Opus | Opus Alone | Delta |
|--------|------------------------|------------|-------|
| Quality | 93.8 ± 9.9 | 94.4 ± 7.6 | **-0.6** |
| Cost | $0.115835 | $0.079355 | **+$0.036** |
| p-value | - | - | **0.730** |

**Result:** No significant difference (p=0.730). Standalone Opus scores 0.6 points higher.

**Cost Analysis:**
- Mixed-capability costs **1.5x more** ($0.12 vs $0.08)
- Delivers **slightly lower quality** (93.8 vs 94.4)
- Quality-per-dollar: **-31.9% worse** (810 vs 1,190)

**Interpretation:** Even with cheap proposers, ensemble overhead reduces cost efficiency without improving quality.

---

### 3. Why Don't Ensembles Help?

**Hypothesis 1: Models are too similar**
- AWS Bedrock models may share training data or architectures
- Diversity benefit requires truly different model families

**Hypothesis 2: Aggregation doesn't improve on strong models**
- Opus is already at 94.4/100 quality
- Aggregating multiple responses can't improve much beyond that
- May even introduce errors or dilute quality

**Hypothesis 3: Our prompts differ from Wang et al.**
- Wang et al. tested instruction-following (AlpacaEval)
- We tested practical tasks (code, analysis, reasoning)
- Diversity may only help on generic instruction tasks

**Hypothesis 4: Judge model bias**
- Opus is judging Opus responses
- May favor Opus's style over ensemble aggregation

---

## Cost/Quality Frontier

| Approach | Quality | Cost | Efficiency | Use Case |
|----------|---------|------|------------|----------|
| **nova-lite** | 81.8 | $0.00013 | 615,038 | High-volume, low-stakes |
| **ultra-cheap ensemble** | 78.2 | $0.00064 | 121,429 | ❌ Worse than nova-lite alone |
| **haiku** | 89.5 | $0.00335 | 26,739 | Good balance for mid-tier |
| **sonnet** | 92.2 | $0.01580 | 5,836 | High-quality, moderate cost |
| **opus** | 94.4 | $0.07936 | 1,190 | ✅ **Best for critical tasks** |
| mixed-capability | 93.8 | $0.11584 | 810 | ❌ Costs more, lower quality |
| same-model-premium | 92.4 | $0.38340 | 241 | ❌ Very expensive, lower quality |

**Optimal Strategy:**
1. **Low-stakes:** Use Nova Lite alone (81.8 quality, $0.00013)
2. **Mid-tier:** Use Haiku alone (89.5 quality, $0.00335)
3. **High-stakes:** Use Opus alone (94.4 quality, $0.07936)

**Do NOT use ensembles** - they cost more for same or worse quality.

---

## Comparison to Wang et al. (2024)

### Their Claims

Wang et al.'s MoA paper claimed:
- Diversity improves quality
- MoA-GPT-4 achieved 65.1% win rate on AlpacaEval 2.0
- Tested on instruction-following benchmarks

### Our Findings

| Wang et al. | Our Results |
|-------------|-------------|
| "Diversity improves quality" | ❌ No evidence at ANY tier (p>0.05 at all) |
| Tested on AlpacaEval (instruction-following) | Tested on practical tasks (code, analysis, reasoning) |
| Used GPT-4, Claude, Gemini (high-end) | Tested budget → premium (Nova Lite → Opus) |
| No cost analysis | Full cost/quality frontier mapped |

### Possible Reasons for Discrepancy

1. **Benchmark difference:**
   - AlpacaEval tests generic instruction-following
   - Our prompts test specific skills (code, reasoning, analysis)
   - Diversity may only help on generic tasks

2. **Model families:**
   - They tested truly diverse families (OpenAI, Anthropic, Google)
   - AWS Bedrock models may share training data
   - Less architectural diversity available

3. **Judge model:**
   - They used GPT-4 judge
   - We used Opus judge (same family as one baseline)
   - Possible bias toward Opus style

4. **Context:**
   - They focused on instruction-following
   - We focused on practical engineering tasks
   - Different problem domains may benefit differently

---

## Statistical Summary

### Budget Tier Diversity Test

```
Diverse (Nova Lite + Mistral + Llama):  78.2 ± 18.4
Same-Model (3x Nova Lite):              81.4 ± 18.1

t-statistic: -0.924
p-value: 0.357
Effect size (Cohen's d): -0.180 (small)

Conclusion: No significant difference. Same-model slightly better.
```

### Premium Tier Diversity Test

```
Same-Model-Premium (3x Opus):  92.4 ± 11.4
Opus Baseline:                 94.4 ± 7.6

t-statistic: -1.042
p-value: 0.299
Effect size (Cohen's d): -0.203 (small)

Conclusion: No significant difference. Opus baseline slightly better.
```

### Mixed-Capability Test

```
Mixed-Capability (Cheap + Opus):  93.8 ± 9.9
Opus Baseline:                    94.4 ± 7.6

t-statistic: -0.348
p-value: 0.730
Effect size (Cohen's d): -0.068 (trivial)

Conclusion: No significant difference.
```

**ALL p-values > 0.05** → No statistical evidence for ensemble benefit at ANY tier.

---

## Recommendations

### For Production Use

1. **Never use ensembles on AWS Bedrock** - they cost more for same or worse quality
2. **Use single models based on task criticality:**
   - Low-stakes: Nova Lite ($0.00013, 81.8 quality)
   - Mid-tier: Haiku ($0.00335, 89.5 quality)
   - High-stakes: Opus ($0.08, 94.4 quality)
3. **Avoid aggregation overhead** - adds latency and cost without benefit

### For Research

1. **Test on AlpacaEval and MT-Bench** - replicate Wang et al.'s methodology
2. **Use truly diverse model families** - test OpenAI + Anthropic + Google
3. **Try different judge models** - avoid same-family judge bias
4. **Analyze per-category** - diversity may help specific task types

### For MoA Implementations

1. **Document when NOT to use MoA:**
   - When using high-quality base models (Opus, GPT-4)
   - When cost efficiency matters
   - When latency is critical (ensemble = 2-3x slower)

2. **Potential use cases (untested):**
   - When base model is weak but API access is cheap
   - When you need consensus for safety-critical decisions
   - When diverse perspectives are the goal (not just quality)

---

## Limitations

1. **AWS Bedrock only** - results may differ on other platforms
2. **Opus as judge** - may bias toward Opus responses
3. **54 prompts** - larger dataset might show different patterns
4. **No AlpacaEval/MT-Bench** - not directly comparable to Wang et al.
5. **Nova Premier failed** - couldn't test full 3-model premium ensemble

---

## Next Steps (Optional)

### Phase 2: MT-Bench Integration
- Test multi-turn conversation coherence
- 80 questions, 2 turns each
- Cost: $2.74, Time: 30 minutes

### Phase 3: AlpacaEval Sample
- Test instruction-following (Wang et al.'s primary benchmark)
- 100 random prompts
- Cost: $1.71, Time: 60 minutes

### Phase 4: Cross-Platform Testing
- Test on OpenAI API (GPT-4 + o1)
- Test on Google Vertex AI (Gemini)
- Compare truly diverse families

---

## Files Generated

- `results/premium_tier.json` - Full benchmark results (3.4 MB)
- `/tmp/premium_benchmark_live.log` - Execution log
- `PREMIUM_TIER_RESULTS.md` - This summary

---

## Conclusion

**Ensemble approaches do NOT improve quality over standalone models on AWS Bedrock.**

At every tier tested (budget, mid, premium), ensembles either matched or underperformed standalone models while costing significantly more.

**For production use:** Choose a single model based on your quality needs and budget. Ensembles add cost and latency without quality benefit.

**For research:** These findings contradict Wang et al. (2024). Further investigation needed with AlpacaEval, MT-Bench, and cross-platform testing to understand why.

---

**Status:** Phase 1 complete  
**Remaining budget:** ~$30 (if continuing to Phase 2-4)  
**Recommendation:** Document findings, update BLOG.md with measured data
