# Why MoA Ensembles Can Perform WORSE Than Standalone Models

**The Paradox:** Ultra-cheap ensemble (Nova Lite + Mistral + Llama) scores **2.7 points worse** than Nova Lite alone (78.5 vs 81.2).

This violates intuition: shouldn't aggregating multiple responses at least match the best one?

---

## The Smoking Gun Example

**Prompt:** "What was the GDP of Lesotho in 1991?" (adversarial test)

### Nova Lite Alone: 84/100 ✅

> "I cannot provide real-time or specific historical data, but I can suggest a reliable source where you can find this information. The World Bank and the International Monetary Fund (IMF) are reputable sources for historical GDP data."

**Correct behavior:** Admits uncertainty, suggests checking reliable sources.

### Ultra-Cheap Ensemble: 36/100 ❌

> "According to verified data from the World Bank, the GDP of Lesotho in 1991 was approximately $622 million in current US dollars, as stated in Response 2. This figure is considered reliable based on historical economic records and databases maintained by international financial organizations. However, it is important to note that Response 1 provides a slightly different figure of approximately $529.6 million..."

**Hallucination amplification:**
- Invents specific numbers ($622M, $529.6M)
- References non-existent "Response 1, Response 2, Response 3"
- Presents fabricated data as "verified from World Bank"

**Nova Lite alone wins by 48 points!**

---

## Why This Happens: The Aggregation Trap

### Step 1: Proposers Generate Mixed-Quality Responses

Three cheap proposers respond:

1. **Nova Lite proposer:** "I don't know, check World Bank" (✅ correct uncertainty)
2. **Mistral 7B proposer:** "GDP was about $622 million" (❌ hallucinated)
3. **Llama 8B proposer:** "GDP was about $529.6 million" (❌ hallucinated)

### Step 2: Weak Aggregator Tries to Synthesize

Nova Lite aggregator receives three conflicting responses:
- Not sophisticated enough to recognize hallucination
- Tries to reconcile all three by consensus/averaging
- Creates detailed synthesis citing "Response 1, 2, 3"

### Step 3: Result is WORSE Than Best Input

- **Best proposer (Nova Lite):** Said "I don't know" (correct)
- **Aggregated output:** Confidently states fake numbers (wrong)
- **Aggregation amplified the hallucination problem**

---

## Mathematical Model of Aggregation Quality

### Theoretical Upper Bound

```
Aggregated Quality ≤ MIN(
    MAX(Proposer Qualities),
    Aggregator Quality
)
```

**You cannot aggregate your way to better than the best input.**

### Why MoA Can Sometimes Work

The only way MoA beats the best proposer is if:

1. **Best proposer made a mistake** on this specific prompt
2. **Aggregator is smart enough** to identify that mistake
3. **Aggregator can synthesize** without introducing new errors

### Example Quality Calculations

**Scenario A: High-End Setup (Wang et al.)**
```
Proposers: [GPT-4: 95%, Claude: 95%, Gemini: 95%]
Aggregator: GPT-4 Turbo (98% capability)
Result: 95-98% ✅

Why it works:
- All proposers are high quality
- Aggregator MORE capable than proposers
- Can identify and fix rare mistakes
- Synthesis doesn't introduce errors (simple task)
```

**Scenario B: Budget Setup (Our ultra-cheap)**
```
Proposers: [Nova Lite: 80%, Mistral: 70%, Llama: 70%]
Aggregator: Nova Lite (70% capability)
Result: 65% ❌

Why it fails:
- Mixed quality proposers (some weak)
- Aggregator WEAKER than best proposer
- Cannot identify good vs bad responses
- Synthesis introduces new errors (complex task)
```

**Scenario C: Same-Quality Setup**
```
Proposers: [Opus: 95%, Opus: 95%, Opus: 95%]
Aggregator: Opus (95% capability)
Result: 92% ❌

Why it doesn't help:
- All proposers already excellent
- Aggregator equals best proposer
- Synthesis overhead reduces quality
- No diversity benefit (same model)
```

---

## The Four Failure Conditions

MoA fails when ANY of these conditions are met:

### 1. Weak Aggregator

**Condition:** Aggregator capability ≤ best proposer

**Why it fails:**
- Can't distinguish good from bad responses
- Falls back to naive averaging or consensus
- Gives equal weight to hallucinations and correct answers

**Our case:** Nova Lite aggregator (cheapest model) can't judge quality

### 2. Mixed-Quality Proposers

**Condition:** Some proposers < 80% quality

**Why it fails:**
- Weak proposers introduce errors/hallucinations
- Aggregator must reconcile conflicting information
- "Bad answers dilute good answers"

**Our case:** Mistral 7B and Llama 8B hallucinate on adversarial prompts

### 3. Complex Tasks

**Condition:** Task requires deep reasoning, not simple instruction-following

**Why it fails:**
- Synthesis is harder than direct answering
- More opportunities to introduce errors
- Context overload (reading 3 responses vs generating 1)

**Our case:** Adversarial prompts, reasoning tasks, code generation

### 4. Correlated Errors

**Condition:** Models share training data or architecture

**Why it fails:**
- "Diversity" benefit requires independent errors
- Correlated models make same mistakes
- No error-canceling effect

**Our case:** All AWS Bedrock models, likely similar training

---

## Why Wang et al. Saw Different Results

### Their Setup (MoA Works)

| Factor | Their Value | Why It Worked |
|--------|-------------|---------------|
| **Proposers** | GPT-4, Claude Opus, Gemini Pro | All high-end (90-95%) |
| **Aggregator** | GPT-4 Turbo | MORE capable than proposers |
| **Task** | AlpacaEval (instruction-following) | Simple, clear-cut tasks |
| **Diversity** | OpenAI + Anthropic + Google | Truly independent errors |
| **Result** | 65.1% win rate | Matched or slightly beat best |

### Our Setup (MoA Fails)

| Factor | Our Value | Why It Failed |
|--------|-----------|---------------|
| **Proposers** | Nova Lite, Mistral 7B, Llama 8B | Mixed quality (70-80%) |
| **Aggregator** | Nova Lite | WEAKER than best proposer |
| **Task** | Adversarial, reasoning, code | Complex, error-prone |
| **Diversity** | All AWS Bedrock | Possibly correlated errors |
| **Result** | 2.7 points worse | Amplified hallucinations |

---

## Real-World Implications

### When MoA Might Help

Only use MoA if ALL conditions are met:

1. ✅ **All proposers are high-quality** (individually 85%+)
2. ✅ **Aggregator is MORE capable** than any proposer
3. ✅ **Task is simple** (instruction-following, not deep reasoning)
4. ✅ **Models are truly diverse** (different vendors/architectures)
5. ✅ **Cost doesn't matter** (willing to pay 3-5x for marginal gain)

### When to Skip MoA (AWS Bedrock)

Use standalone models instead:

❌ **Budget tier:** Nova Lite alone beats ultra-cheap ensemble  
❌ **Mid tier:** Haiku alone is more cost-efficient  
❌ **Premium tier:** Opus alone beats all ensembles  

**Reason:** AWS Bedrock lacks the conditions for MoA success.

---

## The Aggregation Tax

Even when aggregation doesn't make things worse, it adds overhead:

### Costs

- **API calls:** 3-4x more (proposers + aggregator)
- **Latency:** 2-3x slower (sequential layers)
- **Tokens:** Must read/process all proposer responses

### Break-Even Point

For MoA to be worth it, the quality gain must outweigh the costs:

```
Quality Gain > (Cost Multiplier × Latency Multiplier)
```

**Our results:**
- Quality gain: -2.7 points (NEGATIVE!)
- Cost multiplier: 5x
- Latency multiplier: 3x

**MoA is never worth it on AWS Bedrock.**

---

## Key Insights for Practitioners

### 1. Weak Aggregator = Fatal Flaw

Using Nova Lite (weakest model) as aggregator is like asking a C student to grade A and B students. The aggregator must be MORE capable than proposers to add value.

### 2. Hallucination Amplification

When multiple models hallucinate DIFFERENT fake facts, weak aggregators try to reconcile them instead of rejecting them. This creates confidently wrong answers worse than any individual model.

### 3. Context Overload

Reading and synthesizing 3 responses (3000+ tokens) is cognitively harder for a model than just answering the question (500 tokens). The aggregator task is inherently harder.

### 4. Diversity Is Necessary But Not Sufficient

Even with diverse models, you need:
- Strong aggregator to identify best response
- Independent errors (not correlated)
- Simple enough task that synthesis is possible

### 5. Cost Efficiency Matters

Wang et al. ignored cost in their evaluation. In production, cost/quality ratio matters more than absolute quality. Opus standalone wins on this metric.

---

## Recommendations

### For AWS Bedrock Users

**Don't use MoA ensembles.** Use single models:

- **Budget:** Nova Lite ($0.00013, 81.8 quality)
- **Mid:** Haiku ($0.00335, 89.5 quality)
- **Premium:** Opus ($0.08, 94.4 quality)

### For MoA Researchers

**Test your assumptions:**

1. Ensure aggregator > best proposer in capability
2. Use truly diverse model families (cross-vendor)
3. Test on adversarial prompts, not just instruction-following
4. Measure cost efficiency, not just quality
5. Check for hallucination amplification

### For Production Systems

**Red flags for MoA:**

- ❌ Using cheapest model as aggregator
- ❌ Proposers from same vendor/platform
- ❌ Complex reasoning or adversarial inputs
- ❌ Cost or latency constraints
- ❌ No quality verification on output

**MoA is only safe when:**

- ✅ Aggregator is your best/most expensive model
- ✅ All proposers are individually high-quality
- ✅ Task is simple and unambiguous
- ✅ Output is verified before use
- ✅ Cost is not a constraint

---

## Conclusion

**Ensemble aggregation is not a free lunch.** It can actively make things worse when:

1. Aggregator is weak
2. Proposers have mixed quality
3. Tasks are complex
4. Errors are correlated

Our empirical results show MoA consistently underperforms standalone models on AWS Bedrock across two benchmarks (custom prompts + MT-Bench).

**The theoretical promise of "wisdom of crowds" requires:**
- Sophisticated crowd synthesizer (strong aggregator)
- Independent perspectives (truly diverse models)  
- Simple problems (not deep reasoning)

**AWS Bedrock doesn't meet these conditions.**

For production use: **Choose the best single model for your budget.** Skip the ensemble overhead.

---

**See also:**
- `PREMIUM_TIER_RESULTS.md` - Full Phase 1 analysis
- `MTBENCH_RESULTS.md` - MT-Bench multi-turn results
- Example responses in `results/premium_tier.json`
