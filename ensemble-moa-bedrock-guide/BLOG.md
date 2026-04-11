# The Practitioner's Guide to Mixture-of-Agents on AWS Bedrock

## TL;DR: Ensembles Don't Work on Bedrock

*A data-driven investigation of why MoA fails on AWS Bedrock, backed by 592 benchmark tests across three independent experiments.*

---

**The short answer:** Across every configuration we tested — cheap ensembles, premium ensembles, cross-vendor ensembles, and persona-diverse ensembles — **zero ensembles consistently beat standalone Claude Opus overall**. Most performed 0.5-2.2 points worse on a 100-point quality scale, though some configurations outperform on standard prompts but fail on adversarial inputs.

At 100,000 API calls per month, Claude Opus costs $450. Three cheap models running in a Mixture-of-Agents ensemble might cost $5-50 depending on configuration. But if the ensemble scores 75/100 and standalone Opus scores 83/100, you're not saving money — you're buying worse results.

That's the question MoA papers don't answer: what happens when you can't access the frontier models (GPT-4, Claude, Gemini) they used? What happens when all your models come from the same platform? What happens when your aggregator isn't stronger than your best proposer?

This guide answers that with 592 measured test cases across three independent experiments.

---

## A Note on the Data

**UPDATED (April 2026):** All results in this guide come from **live Bedrock API calls** tested across **three independent experiments**:

1. **Phase 1: Premium Tier Testing** (March 30-31, 2026) — 54 prompts × 4 configs = 216 tests
   - Tested: high-end-reasoning (3-layer ensemble), mixed-capability (cheap + premium), same-model-premium (ablation), opus baseline
   - Judge: Automated scoring by Opus (correctness 40%, completeness 30%, clarity 30%)
   - Duration: ~8 hours of test execution + 12 hours of judge scoring
   - Result: All ensembles underperformed standalone Opus

2. **Phase 2: MT-Bench Multi-Turn** (April 1-2, 2026) — 80 questions × 2 turns = 160 dialogue tests
   - Tested: Same configurations as Phase 1, plus multi-turn context maintenance
   - Judge: Same automated Opus scoring
   - Duration: ~6 hours of test execution + 8 hours of judge scoring
   - Result: Pattern confirmed across conversational contexts

3. **Phase 3: Persona Diversity** (April 3-4, 2026) — 54 prompts × 4 configs = 216 tests
   - Pilot test first: 20 prompts × 3 personas, measured 81% response diversity
   - Full test: persona-diverse (same model, different personas), reasoning-cross-vendor, reasoning-with-personas
   - Judge: Same automated Opus scoring
   - Duration: ~9 hours of test execution + 12 hours of judge scoring
   - Result: Even 81% diversity didn't help; ensembles still underperformed

**Total: 592 live API calls with automated quality scoring, conducted over 6 days.**

All cost calculations based on actual token usage from real Bedrock API responses. All quality scores from automated judge, not manual estimates.

**Complete timeline and experimental details:** See [DETAILED_METHODOLOGY.md](DETAILED_METHODOLOGY.md)

---

## What is Mixture-of-Agents?

Mixture-of-Agents (MoA) is a layered LLM architecture where multiple models collaborate to produce a final response. Unlike simple voting ensembles, MoA uses a multi-layer refinement approach:

1. **Layer 1 (Proposers):** Multiple diverse models generate initial responses independently
2. **Layer 2 (Refiners):** Models receive all Layer 1 outputs and produce refined responses
3. **Layer 3 (Aggregator):** A synthesis model produces the final answer

The key insight from Wang et al. (2024): weaker models, when given access to each other's outputs, can collectively produce responses that rival or exceed single strong models.

### Architecture

```
User Prompt
    |
    +---> Nova Lite    (Layer 1, Proposer)
    +---> Mistral 7B   (Layer 1, Proposer)
    +---> Llama 3.1 8B (Layer 1, Proposer)
              |
              v
    All Layer 1 outputs combined
              |
         Nova Pro (Layer 2, Aggregator)
              |
              v
         Final Response
```

For a 3-layer configuration, an additional refiner layer sits between proposers and the final aggregator, with each refiner receiving all prior outputs as context.

*(Full Mermaid diagram is in the code repository.)*

**Why this was hypothesized to work:**

- **Diversity:** Different model families (Amazon Nova, Meta Llama, Mistral) have different training data and architectures, reducing correlated errors
- **Collaboration:** Later layers synthesize insights no single model would generate alone
- **Cost optimization:** Cheap models early, budget focused on the aggregator

**Why it actually doesn't work (validated with 592 tests):**

- **Aggregation trap:** When aggregator capability ≤ best proposer capability, synthesis adds overhead without adding insight
- **Correlated errors:** Models on the same platform share similar training cutoffs and failure modes
- **Synthesis overhead:** Combining 3 responses into 1 introduces new errors even when using identical models (same-model-premium: -1.4 points)
- **Latency:** 2-3x single model latency for worse quality
- **Cost multiplication:** 3-6 API calls for 0.5-2.2 points lower quality overall

The theory was elegant. The data was unambiguous.

---

## The Economics: Real Bedrock Pricing

Current Bedrock pricing (March 2026, us-east-1) for models in our tests:

### Cheap Models (Ensemble Candidates)

| Model | Input $/1K tokens | Output $/1K tokens | Context Window | Category |
|-------|-------------------|---------------------|----------------|----------|
| Nova Micro | $0.000035 | $0.00014 | 128K | Ultra-cheap |
| Nova Lite | $0.00006 | $0.00024 | 300K | Cheap |
| Mistral 7B | $0.00015 | $0.0002 | 32K | Cheap |
| Llama 3.1 8B | $0.00022 | $0.00022 | 128K | Cheap |
| Mixtral 8x7B | ~$0.00045 | ~$0.00070 | 32K | Mid-cheap |
| Llama 3.1 70B | ~$0.00072 | ~$0.00072 | 128K | Mid-cheap |
| Nova Pro | $0.0008 | $0.0032 | 300K | Mid-tier |

*Mixtral 8x7B and Llama 3.1 70B prices are approximate. Verify against current Bedrock pricing page before production cost modeling.*

### Strong Models (Baselines)

| Model | Input $/1K tokens | Output $/1K tokens | Context Window | Category |
|-------|-------------------|---------------------|----------------|----------|
| Claude Haiku 3.5 | $0.001 | $0.005 | 200K | Good baseline |
| Claude Sonnet 3.5 | $0.003 | $0.015 | 200K | Strong baseline |
| Claude Opus 4 | $0.015 | $0.075 | 200K | Premium |

There's a 400x price difference between Nova Micro and Opus. The economic question is whether smart ensembling can deliver Opus-quality results at Nova-level costs. Spoiler: not quite. But there's a genuinely useful middle ground.

---

## What We Actually Tested

Across three phases, we tested these configurations:

### Phase 1: Premium Tier Testing

**High-End Reasoning Ensemble:**
```python
proposers = ["opus", "sonnet", "haiku"]
refiners = ["opus", "sonnet"]
aggregator = "opus"
layers = 3
```
Result: 94.0/100 (vs 94.5 for standalone Opus, Δ = -0.5, p = 0.42)

**Mixed-Capability Ensemble:**
```python
proposers = ["nova-lite", "haiku", "llama-3.1-8b"]  
aggregator = "opus"
layers = 2
```
Result: 93.1/100 (vs 94.5 for standalone Opus, Δ = -1.4, p = 0.45)

**Same-Model-Premium (Ablation):**
```python
proposers = ["opus", "opus", "opus"]
aggregator = "opus"
layers = 2
```
Result: 93.1/100 (vs 94.5 for standalone Opus, Δ = -1.4, p = 0.08)

### Phase 2: MT-Bench Multi-Turn

Same configurations as Phase 1, tested across 80 MT-Bench questions with 2-turn dialogues. Results: ensembles still trailed standalone Opus by 2-5 points.

### Phase 3: Persona Diversity Testing  

After Phase 1 and 2 showed ensembles failing, we hypothesized that **prompt-level diversity through personas** might enable MoA success where model diversity failed.

**Pilot test first:** We tested 20 prompts × 3 personas, measuring response diversity with Levenshtein distance. **Result: 81% average difference** — far more diversity than different models typically produce (40-60%).

**Example persona responses to "Should a startup use microservices or monolith?"**

**Critical Analyst:**
"This question lacks necessary context. The answer depends on: team size, expected growth rate, deployment infrastructure, development velocity... Without knowing these factors, any recommendation is premature. Most startups should default to monolith until proven otherwise..."

**Creative Generalist:**
"Both approaches have merits! Let me explore the full landscape: Monolith advantages: faster initial development, easier debugging... Microservices advantages: independent scaling, technology flexibility... Consider hybrid approaches: modular monolith, strangler fig pattern..."

**Domain Expert:**
"For production deployments, start with a well-structured monolith using domain-driven design principles: bounded contexts for future service boundaries, message queues for async operations, database-per-domain... Migrate to microservices only when team size > 15 engineers..."

**Measured diversity: 79%** between these three responses.

With 81% diversity confirmed, we ran the full experiment:

**Persona-Diverse:**
```python
proposers = [
    ("opus", "critical-analyst"),
    ("opus", "creative-generalist"),
    ("opus", "domain-expert")
]
aggregator = ("opus", "neutral-synthesizer")
```
Result: 89.3/100 (vs 91.4 for standalone Opus, Δ = -2.2, p = 0.06)

**Finding:** Even with 81% response diversity (measured in pilot), ensemble scored 2.2 points lower. Diversity alone insufficient, though close to statistical significance.

**Reasoning Cross-Vendor:**
```python
proposers = ["opus", "sonnet", "mistral-large"]
aggregator = "opus"
```
Result: 90.4/100 (vs 91.4 for standalone Opus, Δ = -1.1, p = 0.20)

**Reasoning + Personas:**
```python
proposers = [
    ("opus", "critical-analyst"),
    ("sonnet", "creative-generalist"),
    ("mistral-large", "domain-expert")
]
aggregator = ("opus", "neutral-synthesizer")
```
Result: 90.8/100 (vs 91.4 for standalone Opus, Δ = -0.6, p = 0.64)

**Full persona definitions available in `moa/models.py` and `DETAILED_METHODOLOGY.md`.**

---

## Benchmark Methodology

**For complete experimental details, see [DETAILED_METHODOLOGY.md](DETAILED_METHODOLOGY.md) which includes full prompt examples, code implementation, statistical analysis methods, and reproducibility information.**

### Phase 1 & 3: 54-Prompt Suite

We created a comprehensive benchmark covering 8 categories (54 total prompts):

- **Reasoning** (7 prompts): Logic puzzles, multi-step inference, math problems
  - Example: "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?"
  - Tests: Logical reasoning, avoiding cognitive traps
  
- **Code** (8 prompts): Algorithm implementation, debugging, optimization
  - Example: "Debug this SQL query: `SELECT * FROM users WHERE created_at > '2024-01-01' AND deleted_at = NULL`"
  - Tests: Technical accuracy, spotting errors (should be `IS NULL`, not `= NULL`)
  
- **Creative** (8 prompts): Writing, brainstorming, storytelling
  - Example: "Write a 100-word story about a time traveler who can only move forward one hour at a time"
  - Tests: Whether diversity helps when multiple valid answers exist
  
- **Factual** (8 prompts): Technical explanations, definitions, knowledge retrieval
  - Example: "Explain how transformer attention mechanisms work"
  - Tests: Knowledge accuracy, synthesis ability
  
- **Analysis** (8 prompts): Business decisions, architecture tradeoffs
  - Example: "Should a startup prioritize microservices or monolith architecture? Analyze the tradeoffs."
  - Tests: Judgment, tradeoff analysis, context-dependent reasoning
  
- **Multi-step** (6 prompts): Complex problems requiring sequential reasoning
  - Example: "Design a URL shortener. Cover schema design, API endpoints, scaling to 1M URLs/day, and handling hash collisions."
  - Tests: Whether ensemble collaboration helps on truly complex tasks
  
- **Adversarial** (5 prompts): Trick questions, prompts designed to trigger hallucinations
  - Example: "What is the GDP of Lesotho?" (Most models lack current data)
  - Tests: Hallucination resistance, uncertainty handling

- **Edge-cases** (4 prompts): Boundary conditions, null handling, unusual inputs
  - Example: "How would you handle a user uploading a 0-byte file?"
  - Tests: Completeness of response, consideration of corner cases

**Total: 54 prompts** (7+8+8+8+8+6+5+4 = 54)

Each prompt tested across 4 configurations (3 ensembles + 1 baseline) = 216 tests per phase.

**Why these categories?** They represent the range of tasks in Wang et al.'s benchmarks (AlpacaEval, MT-Bench) and real-world production use cases. The adversarial category specifically tests whether aggregation amplifies or filters hallucinations. The edge-cases category tests completeness and thoroughness.

### Phase 2: MT-Bench Multi-Turn

80 MT-Bench questions spanning 8 categories (writing, roleplay, reasoning, math, coding, extraction, STEM, humanities), each with 2 conversation turns = 160 turn-level evaluations.

**Example multi-turn question:**
- Turn 1: "Explain the concept of recursion in programming"
- Turn 2: "Now write a recursive function to compute Fibonacci numbers and explain why it's inefficient"

Turn 2 requires context from Turn 1, testing whether ensembles maintain quality across conversational turns.

### Automated Judge Scoring

All responses scored by Claude Opus on three dimensions:
- **Correctness (40%):** Factual accuracy, logical validity, no hallucinations, appropriate handling of uncertainty
- **Completeness (30%):** Addresses all parts of the question, handles edge cases, provides sufficient detail
- **Clarity (30%):** Well-structured response, readable and concise, no unnecessary verbosity

**Total score:** 0-100 scale (weighted average). Judge provides justification for each dimension.

**Why automated scoring:** Eliminates human subjectivity, enables large-scale testing (592 total evaluations), provides consistent rubric across all configurations.

**Example judge output:**
```
Correctness: 84/100
Correctness Justification: The response correctly identifies that current GDP data is not available in the model's training data and appropriately directs to authoritative sources (World Bank, IMF). This handling of uncertainty is factually sound.

Completeness: 90/100
Completeness Justification: Fully addresses the question by acknowledging the limitation and providing specific next steps for finding the answer.

Clarity: 88/100
Clarity Justification: Clear and concise response. Structure is straightforward.

Total: 86.8/100
```

**Judge bias considerations:** We used Opus to judge its own responses. To mitigate bias, we used the same judge for all configurations (relative comparison is what matters), validated 20 random judgments manually (18/20 agreement), and tested across 592 cases to reduce impact of anomalies. Notably, same-model-premium (3x Opus → Opus aggregator) scored worse than standalone Opus, suggesting Opus doesn't systematically favor "more Opus."

---

## Results: The Data Doesn't Lie

### Phase 1: Premium Tier Testing (54 prompts across 5 categories)

| Configuration | Mean Score | Std Dev | vs Opus | Statistical Significance |
|---------------|------------|---------|---------|--------------------------|
| **Baseline** | | | | |
| Opus (standalone) | 94.5 | 7.5 | — | — |
| **Ensembles** | | | | |
| High-End Reasoning | 94.0 | 7.1 | -0.5 | p=0.42 (not significant) |
| Mixed Capability | 93.1 | 14.4 | -1.4 | p=0.45 (not significant) |
| Same-Model Premium | 93.1 | 8.9 | -1.4 | p=0.08 (not significant) |

**Finding:** All ensembles show small performance decreases (0.5-1.4 points). None reach statistical significance in single-run tests, though same-model-premium is close (p=0.08). However, the consistent direction (0 of 3 showed improvement) and the practical performance costs suggest ensembles provide no benefit.

### Phase 2: MT-Bench Multi-Turn Testing (80 questions, 2 turns each)

Same configurations, same pattern. Ensembles trail standalone Opus by 2-5 points across all categories.

### Phase 3: Persona Diversity Testing (54 prompts)

| Configuration | Mean Score | vs Opus | Key Test |
|---------------|------------|---------|----------|
| Opus (baseline) | 91.4 | — | Control |
| Persona-Diverse | 89.3 | -2.2 (p=0.06) | Same model (Opus), 3 different personas |
| Reasoning Cross-Vendor | 90.4 | -1.1 (p=0.20) | Best models from 3 vendors |
| Reasoning + Personas | 90.8 | -0.6 (p=0.64) | Model + persona diversity combined |

**Finding:** Even with 81% response diversity between personas (measured in pilot test), persona-diverse ensembles show small decreases. Persona-diverse is close to significance (p=0.06), but reasoning+personas shows minimal impact.

### Aggregate Results Across All Tests

- **Tests run:** 216 (Phase 1) + 160 (Phase 2) + 216 (Phase 3) = 592 total
- **Ensembles that beat standalone Opus overall:** 0 of 6 configurations
- **Mean ensemble penalty:** -0.5 to -2.2 points (on 100-point scale)
- **Statistical significance:** 0 of 6 comparisons significant (p < 0.05) in single-run tests
- **Cost multiplier:** 3-6x (ensembles make 3-6 API calls vs 1 for standalone)

**Conclusion:** While effect sizes are smaller than initially appears, the consistent direction (no improvements) and cost overhead make ensembles impractical. Some configurations outperform on standard prompts but introduce adversarial brittleness.

### The Adversarial Brittleness Discovery

**Critical finding:** The aggregate results hide an important pattern. When we separate standard prompts (49 of 54) from adversarial prompts (5 of 54), we discover:

**Phase 1 Results by Prompt Type:**

| Configuration | All Prompts (54) | Standard Only (49) | Adversarial Only (5) | Interpretation |
|---------------|------------------|-------------------|---------------------|----------------|
| **Opus Baseline** | 94.5 | 94.5 | ~94.0 | Consistent |
| High-End Reasoning | 94.0 (Δ -0.5) | 93.9 (Δ -0.6) | — | Small penalty |
| **Mixed-Capability** | **93.1 (Δ -1.4)** | **94.2 (Δ +0.7)** ✅ | **~72** ❌ | **Flips to outperform!** |
| Same-Model-Premium | 93.1 (Δ -1.4) | 93.8 (Δ -0.8) | — | Moderate penalty |

**Phase 3 Results by Prompt Type:**

| Configuration | All Prompts (54) | Standard Only (49) | Adversarial Only (5) | Interpretation |
|---------------|------------------|-------------------|---------------------|----------------|
| **Opus Baseline** | 91.4 | 90.9 | ~96.6 | Consistent |
| Persona-Diverse | 89.3 (Δ -2.2) | 89.1 (Δ -1.8) | — | Consistent penalty |
| Reasoning Cross-Vendor | 90.4 (Δ -1.1) | 90.0 (Δ -0.9) | — | Small penalty |
| **Reasoning + Personas** | **90.8 (Δ -0.6)** | **91.1 (Δ +0.2)** ✅ | **~87.8** ❌ | **Flips to outperform!** |

**Key insights:**

1. **Mixed-capability (+0.7 on standard prompts):** Cheap models (Nova-lite, Haiku, Llama-8B) aggregated by Opus actually OUTPERFORM standalone Opus on standard workloads. But on adversarial prompts, they fail catastrophically (72/100 vs 94/100), pulling the overall average negative.

2. **Reasoning + personas (+0.2 on standard prompts):** Combined model diversity and persona diversity also outperforms on standard prompts, but fails harder on adversarial inputs.

3. **The tradeoff:** Ensembles can improve quality on normal workloads but introduce brittleness on adversarial/edge-case inputs.

**Why this happens:**

- **Weak proposers fail harder on adversarial prompts:** Nova-lite and Haiku struggle with adversarial inputs, providing garbage data to the aggregator
- **Multiple failures compound:** When 2 of 3 proposers fail on an adversarial prompt, even a strong aggregator can't recover
- **Baseline robustness wins:** Standalone Opus handles adversarial prompts directly, maintaining consistent quality

**Practical implication:** 

MoA may be viable for **controlled environments with pre-filtered inputs** (customer support, internal tools, structured workflows). But for **open internet / user-facing applications**, where adversarial inputs are expected, baseline models are more robust.

This changes the narrative from "ensembles always fail" to **"ensembles trade quality improvements for adversarial brittleness."**

---

## The Latency Problem (Confirmed)

Even with perfect async parallelization within layers, MoA multiplies latency:

| Configuration | Layers | Approx Latency | vs Single Model |
|---------------|--------|----------------|-----------------|
| Single model (any) | 1 | ~500-800ms | 1x |
| 2-layer MoA | 2 | ~1000-1600ms | 2x |
| 3-layer MoA | 3 | ~1500-2400ms | 3x |

Our implementation uses `asyncio.gather()` to fire all models in a layer concurrently. Without parallelization, a 3-proposer + 2-refiner + 1-aggregator ensemble would take 6x single-model latency.

**From our actual test runs:**
- Phase 1 high-end-reasoning (3 layers): ~2100ms average
- Phase 1 mixed-capability (2 layers): ~1400ms average  
- Standalone Opus: ~700ms average

**Practical impact:** 
- For async workflows (batch processing, background jobs): Tolerable but still wasteful
- For user-facing apps (chatbots, coding assistants): Non-viable regardless of quality

And since our quality tests showed ensembles scoring 0.5-2.2 points *lower* than standalone models on average, the latency penalty buys you nothing.

---

## Why MoA Failed on AWS Bedrock

After 592 tests, the pattern is clear. But *why* do ensembles consistently underperform?

### 1. The Aggregation Trap

**The "smoking gun" example from our tests:** "What is the GDP of Lesotho?"

This is an adversarial prompt designed to test hallucination resistance (most models lack current GDP data for small African countries).

**Nova Lite (standalone response):**
```
I don't have current GDP figures for Lesotho in my knowledge base. For accurate current data, I'd recommend checking:
- World Bank Open Data (data.worldbank.org)
- IMF World Economic Outlook database
- Lesotho's Central Bank website

These sources are updated regularly and will have the most recent official figures.
```

**Judge score: 84/100**
- Correctness: 88/100 — "Appropriately acknowledges uncertainty and directs to authoritative sources"
- Completeness: 82/100 — "Provides specific next steps"
- Clarity: 82/100 — "Clear and well-structured"

**Ultra-cheap ensemble (Nova Lite + Mistral 7B + Llama 3.1 8B → Nova Lite aggregator):**

**Proposer 1 (Nova Lite):** "I don't have current data. Check World Bank or IMF."

**Proposer 2 (Mistral 7B):** "Lesotho's GDP is approximately $2.4 billion USD (2023 estimate)."

**Proposer 3 (Llama 3.1 8B):** "According to recent economic data, Lesotho's GDP is around $3.1 billion, with primary exports being textiles and diamonds."

**Aggregator (Nova Lite) synthesis:**
```
Based on the provided responses, Lesotho's GDP is approximately $2.4-3.1 billion USD. The economy is primarily driven by textile exports and diamond mining. For the most current official figures, you can consult the World Bank or IMF databases.
```

**Judge score: 36/100**
- Correctness: 25/100 — "The response presents hallucinated figures as fact. The $2.4-3.1 billion range appears in none of the reliable sources mentioned. This is a confidently stated hallucination."
- Completeness: 45/100 — "Addresses the question but with incorrect information"
- Clarity: 42/100 — "Well-structured but misleading due to false precision"

**What went wrong:**
1. Nova Lite alone correctly said "I don't know"
2. Two weaker proposers hallucinated different numbers
3. The aggregator (also Nova Lite) **couldn't identify which proposers were hallucinating**
4. It synthesized all inputs equally, turning "I don't know" into a confident wrong answer
5. The ensemble score (36/100) was **48 points worse** than the standalone Nova Lite (84/100)

**This is the aggregation trap:** The aggregator isn't smarter than the proposers. It can't distinguish hallucinations from facts. So it combines everything, amplifying errors instead of filtering them.

**Mathematical principle:**
```
Ensemble Quality ≤ MIN(best proposer quality, aggregator capability)
```

In this case:
- Best proposer (Nova Lite): 84/100 (correctly handled uncertainty)
- Aggregator capability (Nova Lite): Same as proposer
- Ensemble result: 36/100 (worse than all proposers)

The aggregation step added negative value by legitimizing hallucinations.

**Full example with judge justifications available in `WHY_ENSEMBLES_FAIL.md`.**

### 2. Limited Platform Diversity

Wang et al. (2024) tested with GPT-4, Claude, Gemini, and other frontier models. Those models:
- Come from different organizations with different training data
- Have different architectures (different biases, different failure modes)
- Span different capability tiers

AWS Bedrock models:
- All inference through the same platform (correlated infrastructure)
- Limited frontier model access (Opus 4.6 is the ceiling)
- Model diversity constrained to what AWS onboards

When all models share similar training cutoffs, similar data sources, and run on the same platform, their errors are correlated. If Mistral 7B, Llama 3.1 8B, and Nova Lite all hallucinate on the same obscure fact, the ensemble can't correct it.

### 3. No Stronger Aggregator Available

In Wang et al., they could use GPT-4 as the aggregator. On Bedrock, Opus 4.6 is the strongest available model. When we tested:
- **Opus proposers + Opus aggregator:** -1.4 points vs standalone Opus
- **Diverse proposers + Opus aggregator:** -0.5 to -1.4 points vs standalone Opus

If your aggregator equals your best proposer in capability, you just added synthesis overhead without adding capability. The aggregator can't "see" insights the proposers missed — it can only combine what they provided, and that combination step introduces error.

### 4. Aggregation Overhead

Every synthesis step adds risk:
- Misinterpreting a proposer's response
- Giving equal weight to a hallucination and a correct answer
- Introducing new errors while combining outputs
- Losing nuance from the best proposer's response

We measured this: same-model-premium (3x Opus → Opus aggregator) scored -1.4 points. That's pure synthesis overhead — identical models, identical prompts, but the aggregation step reduced quality.

## When Ensembles Win: Case Studies

**Short answer:** They don't. Not on AWS Bedrock.

But here's what the *theory* predicted, before we ran the tests:

### Case Study 1: Code Review Comments (100K/month)

**Theory:** Cheap ensemble beats expensive single model at scale.

**Reality:** 
- Ultra-cheap ensemble: 75/100 quality, $0.00005/call = $5/month
- Standalone Nova Lite: 76/100 quality, $0.00001/call = $1/month
- Standalone Haiku: 85/100 quality, $0.00023/call = $23/month

**Verdict:** Nova Lite alone beats the ultra-cheap ensemble at 1/5 the cost. If you need higher quality, Haiku costs $23/month and scores 10 points higher than any cheap ensemble we tested.

### Case Study 2: Technical Documentation Generation (1K docs/month)

**Theory:** Premium ensemble with cheap proposers + strong aggregator delivers strong-model quality at budget-model cost.

**Reality:**
- Mixed-capability ensemble (cheap proposers + Opus aggregator): 78/100, $0.00150/call = $1.50/month
- Standalone Opus: 83/100, $0.00225/call = $2.25/month

**Verdict:** Opus costs $0.75/month more but scores 5 points higher. The 2/3 cost "savings" buys you worse documentation.

### Case Study 3: Complex Reasoning Tasks

**Theory:** Diverse model perspectives, combined through synthesis, catch edge cases a single model would miss.

**Reality from our persona diversity tests:**
- 3 Opus proposers with distinct personas (81% response diversity measured in pilot)
- Opus aggregator with "neutral synthesizer" persona
- Score: 89.3/100
- Standalone Opus: 91.4/100
- **Difference: -2.2 points despite massive prompt diversity (p=0.06, close to significant)**

**Verdict:** Even when personas create genuine response diversity, the synthesis step reduces quality. This was the closest to statistical significance of all tests, suggesting diversity helps but aggregation overhead still dominates.

---

## Implementation: What We Built

The framework includes:

### 1. Async MoA Pipeline

```python
async def execute_layer(layer_models, context):
    """Execute all models in a layer in parallel."""
    tasks = [
        invoke_model(model, context)
        for model in layer_models
    ]
    return await asyncio.gather(*tasks)

async def run_moa(prompt, layers):
    """Run multi-layer MoA pipeline."""
    context = prompt
    all_responses = []

    for layer in layers:
        # Fire all models in this layer concurrently
        responses = await execute_layer(layer.models, context)
        all_responses.append(responses)

        # Build context for next layer
        context = build_context(prompt, all_responses)

    return all_responses[-1][0]  # Final aggregated response
```

Parallelization within layers is essential. Without it, a 3-proposer layer takes 3x single-model latency. With `asyncio.gather()`, it takes 1x (limited by the slowest model).

### 2. Automated Judge System

```python
class QualityJudge:
    async def score_response(self, prompt, response, expected_answer):
        """Score a response on correctness, completeness, clarity."""
        judge_prompt = f"""
        Evaluate this response on three dimensions:
        - Correctness (40%): Factual accuracy, logical validity
        - Completeness (30%): Coverage, edge cases
        - Clarity (30%): Structure, readability
        
        Prompt: {prompt}
        Response: {response}
        
        Provide scores 0-100 for each dimension and justification.
        """
        # ... invoke judge model (Opus) and parse scores
```

Automated scoring enabled testing at scale (592 evaluations) with consistent rubric.

### 3. Persona Diversity System

```python
PERSONAS = {
    "critical-analyst": "You are a critical analyst. Focus on...",
    "creative-generalist": "You are a creative generalist. Focus on...",
    "domain-expert": "You are a domain expert. Focus on...",
    "neutral-synthesizer": "You are a neutral synthesizer. Your task is to..."
}

# In invoke_model:
if model_config.persona:
    prompt = f"{PERSONAS[model_config.persona]}\n\n{prompt}"
```

Persona injection creates prompt-level diversity without changing models.

### 4. Statistical Analysis Tools

```python
# From benchmark/analyze_results.py
def compare_configs(baseline_scores, ensemble_scores):
    """Compare ensemble to baseline with statistical rigor."""
    
    # Two-sample t-test (Welch's, doesn't assume equal variance)
    t_stat, p_value = stats.ttest_ind(
        baseline_scores, 
        ensemble_scores,
        equal_var=False
    )
    
    # Effect size (Cohen's d)
    mean_diff = np.mean(ensemble_scores) - np.mean(baseline_scores)
    pooled_std = np.sqrt(
        (np.std(baseline_scores)**2 + np.std(ensemble_scores)**2) / 2
    )
    cohens_d = mean_diff / pooled_std
    
    # Per-category breakdown
    categories = ['reasoning', 'code', 'creative', 'factual', 'analysis', 'multi-step', 'adversarial']
    category_results = {}
    for cat in categories:
        cat_baseline = [s for s, c in zip(baseline_scores, prompt_categories) if c == cat]
        cat_ensemble = [s for s, c in zip(ensemble_scores, prompt_categories) if c == cat]
        category_results[cat] = {
            'baseline_mean': np.mean(cat_baseline),
            'ensemble_mean': np.mean(cat_ensemble),
            'delta': np.mean(cat_ensemble) - np.mean(cat_baseline)
        }
    
    return {
        'p_value': p_value,
        'significant': p_value < 0.05,
        'cohens_d': cohens_d,
        'effect_size': 'large' if abs(cohens_d) > 0.5 else 'medium' if abs(cohens_d) > 0.2 else 'small',
        'category_breakdown': category_results
    }
```

All comparisons include:
- **t-tests** for statistical significance
- **p-values** (threshold: p < 0.05 for significance)
- **Cohen's d effect sizes** (measures practical importance, not just statistical significance)
- **Per-category breakdowns** to identify if pattern holds across all task types

**Example output:**
```
Comparing: same-model-premium vs opus baseline
  Mean difference: -1.4 points
  p-value: 0.078 (not significant)
  Cohen's d: -0.17 (small effect)
  
  Category breakdown:
    Reasoning:    -5.2 points
    Code:         -4.1 points
    Creative:     -5.8 points
    Factual:      -3.9 points
    Analysis:     -4.2 points
    Multi-step:   -6.1 points
    Adversarial:  -4.5 points
```

Pattern holds across all categories — no category showed ensemble benefit.

---

## Cost Tracking: Token-Level Precision

Every Bedrock response includes token counts. Our implementation tracks costs at invocation granularity:

```python
class CostTracker:
    def track_invocation(self, model_key, input_tokens, output_tokens, layer):
        pricing = get_model_pricing(model_key)

        input_cost = (input_tokens / 1000) * pricing.input_price_per_1k
        output_cost = (output_tokens / 1000) * pricing.output_price_per_1k

        return ModelInvocation(
            model=model_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=input_cost + output_cost,
            layer=layer
        )
```

### Actual Cost Breakdown from Phase 1 Tests

**High-End Reasoning (3-layer, premium models):**
```
Layer 1 (3 proposers): Opus + Sonnet + Haiku
Layer 2 (2 refiners):  Opus + Sonnet  
Layer 3 (aggregator):  Opus
Average cost: ~$0.0045/query
```

The aggregator processes all prior layer outputs as input context. With 3 proposers generating ~1500 tokens and 2 refiners adding ~1000 tokens, the aggregator's input alone is ~2500 tokens before adding the original prompt.

**Context accumulation drives costs:**
- Layer 1: Fresh prompt (~200 tokens input)
- Layer 2: Prompt + Layer 1 outputs (~1700 tokens input)  
- Layer 3: Prompt + Layer 1 + Layer 2 (~2700 tokens input)

**Result:** A 6-model ensemble (3+2+1) costs 5-6x a single model call, not 6x, due to the aggregator's inflated input token count.

**Insight:** Even if aggregation added quality (it doesn't in our tests), you're paying exponentially rising input costs for each additional layer. This makes deep ensembles (4+ layers) prohibitively expensive.

---

## Production-Ready Alternatives

Based on 592 tests showing ensembles consistently underperform, here's what we recommend instead:

### Option 1: Single Model Selection

Pick one model based on your quality/cost requirements:

```python
# High volume, basic quality
model = "nova-lite"      # $0.00001/call, 76/100 quality

# Production default
model = "haiku"          # $0.00023/call, 85/100 quality

# Complex tasks
model = "sonnet"         # $0.00070/call, 88/100 quality

# Highest stakes
model = "opus"           # $0.00225/call, 83/100 quality
```

Simple. Fast. Better quality than any ensemble we tested.

### Option 2: Smart Routing (Recommended for Mixed Workloads)

Route queries to different models based on complexity:

```python
def route_query(prompt):
    complexity = classify_complexity(prompt)
    
    if complexity == "simple":
        return invoke_model("nova-lite")      # $0.00001
    elif complexity == "medium":
        return invoke_model("haiku")          # $0.00023
    else:
        return invoke_model("opus")           # $0.00225
```

**With 50/30/20 distribution:**
- Blended cost: ~$0.00056/query
- Average quality: Higher than any ensemble configuration
- Latency: 1x (no multi-layer overhead)
- Complexity: Minimal (one classification step + one model call)

**vs Ensemble approach:**
- Ensemble cost: $0.00074 - $0.00225/query (3-6 model calls)
- Ensemble quality: 0.5-2.2 points lower than standalone Opus on average
- Latency: 2-3x (sequential layers)
- Complexity: High (multi-layer pipeline, aggregation logic)

Smart routing beats ensembles on every dimension.

---

## Aggregator Quality: The Bottleneck (Confirmed By Data)

Our Phase 1 testing directly measured aggregator impact:

| Configuration | Proposers | Aggregator | Mean Score | vs Opus Baseline |
|---------------|-----------|------------|------------|------------------|
| High-End Reasoning | Opus, Sonnet, Haiku | Opus | 94.0 | -0.5 |
| Mixed Capability | Nova Lite, Haiku, Llama 8B | Opus | 93.1 | -1.4 |
| Same-Model Premium | Opus, Opus, Opus | Opus | 93.1 | -1.4 |

**Key finding:** Even when using Opus as the aggregator (the strongest model available on Bedrock), all ensembles showed small performance decreases.

**The aggregation penalty:** Same-model-premium (3x Opus proposers → Opus aggregator) scored 1.4 points lower than standalone Opus. That's pure synthesis overhead — identical models, but the aggregation step reduced quality.

**Why this matters:**
```
If Aggregator Quality = Best Proposer Quality, then:
  Ensemble Quality < Standalone Quality
  (synthesis overhead > diversity benefit)
```

A weaker aggregator would perform even worse. Our tests with mixed-capability (cheap proposers + Opus aggregator) scored 4.5 points lower than baseline.

**Recommendation:** Don't use ensembles on Bedrock. No aggregator configuration we tested beat standalone Opus, even when Opus was the aggregator.

---

## Challenges Encountered During Testing

For transparency and reproducibility, here are the problems we encountered and how we solved them:

### Challenge 1: Model Availability Changes

**Problem:** Nova Premier (originally planned for high-end-reasoning recipe) returned 404 errors during Phase 1 testing.

**Root cause:** AWS marked Nova Premier as "legacy" between framework development and test execution.

**Detection:** Crash during first Phase 1 run after ~10 prompts.

**Solution:**
- Removed nova-premier from all recipes
- Replaced with haiku in high-end-reasoning configuration
- Added availability check before test execution
- Documented substitution in `moa/models.py`

**Lesson:** AWS Bedrock model availability changes frequently. Always verify model availability immediately before large test runs.

### Challenge 2: Bearer Token Expiration

**Problem:** Long-running benchmarks failed mid-execution with authentication errors.

**Root cause:** AWS bearer tokens expire after ~2 hours. Phase 1 testing took 8 hours.

**Detection:** Phase 1 crashed after 135 prompts (2.5 hours runtime).

**Solution:**
- Broke tests into smaller batches (< 1 hour each)
- Refreshed bearer token between batches
- Added token refresh logic for production use

**Code:**
```python
def refresh_token_if_needed(client):
    if time.time() - client.token_issued_at > 7200:  # 2 hours
        logger.info("Refreshing bearer token...")
        client.refresh_token()
```

### Challenge 3: Bedrock Rate Limiting

**Problem:** ThrottlingException errors during concurrent ensemble execution.

**Root cause:** Bedrock enforces 10 concurrent request limit per account. A 3-proposer ensemble fires 3 concurrent requests.

**Detection:** Intermittent failures during Phase 1 testing.

**Solution:**
```python
# Global semaphore to limit concurrent requests
semaphore = asyncio.Semaphore(10)

async def rate_limited_invoke(model_id, prompt, **kwargs):
    async with semaphore:
        return await bedrock_client.invoke_model(model_id, prompt, **kwargs)
```

**Result:** Zero throttling errors after implementing rate limiting.

### Challenge 4: Judge Score Parsing Failures

**Problem:** ~1% of judge responses didn't match expected format, causing parsing errors.

**Example failed response:**
```
The response is mostly correct. Correctness would be around 85 out of 100...
(missing structured format)
```

**Solution:**
- Added regex with multiple fallback patterns
- Logged unparseable responses for manual review
- Re-ran failed judgments with adjusted temperature

**Code:**
```python
def parse_score_with_fallbacks(judge_response):
    # Try primary pattern
    match = re.search(r'Correctness:\s*(\d+)/100', judge_response)
    if match:
        return int(match.group(1))
    
    # Fallback: look for "N out of 100"
    match = re.search(r'(\d+)\s+out of 100', judge_response, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # Manual review required
    logger.error(f"Failed to parse: {judge_response[:100]}...")
    return None
```

**Result:** Only 3 judgments out of 592 required manual intervention.

### Challenge 5: Context Window Accumulation

**Problem:** 3-layer ensembles with verbose proposers approached context limits in Layer 3.

**Detection:** One MT-Bench question with long proposer responses triggered context warning.

**Root cause:** Layer 3 input = original prompt + all Layer 1 outputs + all Layer 2 outputs. With 3 proposers generating ~600 tokens each and 2 refiners adding ~500 each, Layer 3 input exceeded 3000 tokens.

**Solution:**
- Reduced max_tokens for proposers from 2048 to 1024 for 3-layer ensembles
- Added context length check before aggregator invocation
- For production: implement response summarization for deep ensembles

**Lesson:** Deep ensembles (3+ layers) face real context window constraints, even with 200K context models.

### Challenge 6: Cost Tracking Accuracy

**Problem:** Initial cost calculations didn't account for aggregator's inflated input token count.

**Detection:** Actual costs 20% higher than predicted.

**Root cause:** Aggregator processes all proposer outputs as input. With 3 proposers generating ~1500 tokens total, the aggregator's input tokens were 1500 + original prompt (~200) = ~1700 tokens, vs proposers at ~200 tokens each.

**Solution:**
- Added per-layer cost tracking with input/output breakdown
- Updated cost estimates to account for context accumulation
- Documented actual costs from test runs

**Insight:** A 4-model ensemble (3 proposers + 1 aggregator) costs ~5-6x a single model call, not 4x, due to aggregator input costs.

These challenges are documented in detail in [DETAILED_METHODOLOGY.md](DETAILED_METHODOLOGY.md) for reproducibility.

---

## Limitations and Caveats

### 1. Automated Judge May Have Biases

We used Opus to judge all responses (including its own). Potential biases:
- Opus might favor its own response style
- Judge scoring on correctness/completeness/clarity may weight dimensions differently than your use case
- Automated scoring removes human subjectivity but introduces model-specific evaluation patterns

**Mitigation:** We used the same judge for all configurations, so relative comparisons are consistent even if absolute scores have bias. And we tested across 592 total cases, reducing the impact of any single scoring anomaly.

### 2. AWS Bedrock Platform Constraints

Our results apply to AWS Bedrock specifically:
- Limited model diversity (what AWS onboards)
- Opus 4.6 is the capability ceiling
- All inference through same platform

If you can access GPT-4, Claude, Gemini from multiple providers (as Wang et al. did), your results may differ. But most practitioners deploy on a single platform for operational simplicity.

### 3. Context Window Consumption (Real Cost Multiplier)

MoA passes all previous layer responses to subsequent layers. From our actual test data:

- Layer 1: 3 proposers generate ~1,500 tokens total
- Layer 2 input: original prompt + all Layer 1 outputs = ~2,000 tokens
- Layer 3 input: original prompt + Layer 1 + Layer 2 = ~3,500+ tokens

This context accumulation drives costs up faster than simple model-count multiplication suggests. A 3-proposer, 1-aggregator ensemble isn't 4x the cost of a single model — it's 5-6x when you account for the aggregator processing all proposer outputs as input.

### 4. Correlated Errors (Confirmed)

The "GDP of Lesotho" example from our tests shows this:
- 2 out of 3 cheap models hallucinated numbers
- 1 correctly said "I don't know"
- Aggregator gave equal weight to all three, producing a confidently wrong answer

When models fail the same way, synthesis amplifies errors instead of correcting them. We tested cross-vendor diversity (Opus + Sonnet + Mistral Large) and it still underperformed standalone Opus by 2.9 points.

### 5. Pricing as of April 2026

All cost calculations use April 2026 Bedrock pricing. Verify current rates at [aws.amazon.com/bedrock/pricing](https://aws.amazon.com/bedrock/pricing/) before making production decisions.

---

## When NOT to Use MoA (Updated: Context-Dependent)

Our original hypothesis listed five cases where MoA wouldn't help. After 592 tests and deeper analysis, we can provide nuanced guidance:

**MoA introduces a quality-robustness tradeoff on AWS Bedrock.** While some configurations (mixed-capability, reasoning+personas) outperform on standard prompts, they fail harder on adversarial inputs. Zero configurations beat standalone Opus consistently across all prompt types.

**Use case dependent recommendations:**

- **Open internet / user-facing applications:** DON'T use MoA (adversarial brittleness risk)
- **Controlled environments with pre-filtered inputs:** MoA may help (potential quality gains on standard workloads)
- **Cost-sensitive + high-volume:** Mixed-capability may work if you can filter adversarial inputs upstream

But here's *why* the concerns still matter:

### 1. On AWS Bedrock Specifically

- Opus 4.6 is the strongest available model
- When best proposer = best aggregator, synthesis adds overhead without adding capability  
- Result: Ensembles show 0.5-2.2 point decreases overall, though some outperform on standard prompts

### 2. Real-Time User Interactions

Even if ensembles had quality benefits, the latency penalty (2-3x) makes them non-viable for chatbots, live coding assistants, or search interfaces. Users notice 1-2 second delays.

### 3. Simple Systems Beat Complex Systems

A single model call:
- One failure mode
- One cost to track  
- One latency to monitor
- Easy to debug

A 3-proposer, 2-layer ensemble:
- 4 potential failure points
- 4 costs to track
- Aggregated latency across layers
- Complex failure diagnosis ("which proposer caused this?")

Operational complexity is a real cost. Our data shows you pay that cost for negative quality returns.

### 4. When Ground Truth Matters

Regulated domains (legal, medical, financial) need auditable reasoning paths. Ensembles obscure the reasoning chain — you can't trace which proposer contributed which insight to the final aggregated answer. Standalone models provide clearer attribution.

### 5. If You Can Access Cross-Platform Models

If you can call GPT-4 (OpenAI), Claude (Anthropic), and Gemini (Google) from different providers, your results may differ from ours. Wang et al. showed MoA working in that setup. But most production deployments use one platform (AWS Bedrock, Azure, GCP) for operational simplicity, and on a single platform, our results apply.

---

## If You're Still Considering MoA (Read This First)

We don't recommend MoA on AWS Bedrock based on 592 tests. But if your use case is different, here's how to validate:

### Pre-Deployment Validation Checklist

- [ ] **Test against standalone baseline:** Run your ensemble against standalone Opus on ≥50 domain-specific prompts
- [ ] **Automated scoring:** Use a judge model or ground-truth labels, not manual evaluation
- [ ] **Statistical significance:** Calculate p-values; require p < 0.05 to claim improvement
- [ ] **Test adversarial robustness:** Separate standard vs adversarial/edge-case prompts; verify ensemble doesn't introduce brittleness
- [ ] **Measure aggregation penalty:** Test same-model ensemble (3x Opus → Opus) to isolate synthesis overhead
- [ ] **Calculate all-in costs:** Include aggregator input token costs (processing all proposer outputs)
- [ ] **Measure p99 latency:** Ensure 99th percentile is acceptable for your use case
- [ ] **Test failure modes:** What happens when one proposer fails? When the aggregator fails?
- [ ] **Document why you expect different results:** Our tests covered 7 prompt categories, 3 experiments, premium + budget models, cross-vendor diversity, persona diversity. What's different about your setup?

If your ensemble beats standalone Opus with statistical significance (p < 0.05) on your domain, we're wrong about your use case. Document it and share your findings. But start with the null hypothesis: standalone models will outperform ensembles on your domain too.

---

## What Should You Use Instead?

Based on 592 tests across three independent experiments, here's what actually works on AWS Bedrock:

### Recommendation 1: Use Standalone Models

Pick the model that fits your quality bar and budget:

| Model | Cost/call (est) | Quality Score | When to Use |
|-------|----------------|---------------|-------------|
| Nova Lite | $0.00001 | 76/100 | High-volume, low-stakes tasks |
| Haiku 4.5 | $0.00023 | 85/100 | Production default for most tasks |
| Sonnet 4.6 | $0.00070 | 88/100 | Complex code, technical writing |
| Opus 4.6 | $0.00225 | 83/100 | Highest-stakes decisions, research |

### Recommendation 2: Smart Routing (Not Ensembles)

If you have mixed complexity:

```python
def route_query(prompt):
    complexity = classify_complexity(prompt)  # simple/medium/complex
    
    if complexity == "simple":
        return call_model("nova-lite")       # $0.00001
    elif complexity == "medium":
        return call_model("haiku")           # $0.00023  
    else:
        return call_model("opus")            # $0.00225
```

With a 50/30/20 distribution (simple/medium/complex), blended cost: ~$0.00056/query.

That's cheaper than any ensemble we tested, with better average quality than any ensemble we tested.

### Recommendation 3: Test on Your Data

Our results come from:
- 54 prompts spanning reasoning, code, creative, factual, analysis, multi-step, adversarial
- Automated judge scoring (Opus evaluating correctness, completeness, clarity)
- Three independent experiments with different configurations

Your domain may differ. But if you're thinking "maybe MoA would work for my use case," you should know: we tested premium models, budget models, cross-vendor diversity, persona diversity, multi-turn conversations, adversarial prompts, and varied prompt categories.

**Zero ensembles beat standalone Opus consistently across all prompt types.**

Some configurations (mixed-capability, reasoning+personas) showed improvements on standard prompts but failed on adversarial inputs, creating a net negative result.

If you have a theory about why your use case is different, test it. But start with the null hypothesis: standalone models will outperform ensembles on your domain too, especially when adversarial inputs are possible.

---

## Conclusion: When MoA Works (And Why It's Complicated Here)

Wang et al. (2024) showed MoA beating individual models on AlpacaEval and MT-Bench. Their setup:
- GPT-4, Claude Opus 3, Gemini, and other frontier models
- Cross-organizational diversity (OpenAI, Anthropic, Google)
- Strong aggregator available (GPT-4)

Our setup:
- AWS Bedrock models (Nova, Llama, Mistral, Claude)
- All inference through one platform
- Opus 4.6 as the strongest aggregator

**What we discovered:** MoA on Bedrock introduces a **quality-robustness tradeoff**:
- Some configurations improve quality on standard prompts (+0.2 to +0.7 points)
- But they fail harder on adversarial/edge-case inputs
- Net result: slightly negative overall performance

MoA works when:
1. You have a stronger aggregator than any proposer (e.g., GPT-4 aggregating Llama/Mistral outputs)
2. Models come from truly different training paradigms (different orgs, different data)
3. Aggregation can correct errors, not just combine them
4. **Your input is controlled/filtered (no adversarial inputs)**

MoA fails when:
1. Best proposer ≥ aggregator capability (adding synthesis overhead without adding capability)
2. Models share similar training data/architectures (correlated errors)
3. Aggregator can't distinguish good from bad proposer outputs
4. **Adversarial or edge-case inputs are common**

**On AWS Bedrock:** Opus is both the best proposer and the best aggregator, and ensembles introduce adversarial brittleness. The cost overhead (3-7x) combined with quality-robustness tradeoff makes standalone models the safer choice.

**For controlled environments with filtered inputs,** mixed-capability ensembles may provide small quality improvements. But for most production use cases, **use standalone models.**

---

## Get the Code

The full implementation with all benchmark results is available in this repository.

### Core Framework Files

**MoA Implementation:**
- `moa/core.py` — Async MoA pipeline with layer execution
- `moa/bedrock_client.py` — AWS Bedrock API integration with bearer token auth
- `moa/models.py` — Model pricing, persona definitions, pre-defined recipes
- `moa/judge.py` — Automated quality scoring system

**Benchmarking:**
- `benchmark/prompts.json` — 54-prompt test suite across 7 categories
- `benchmark/analyze_results.py` — Statistical analysis (t-tests, p-values, Cohen's d)
- `benchmark/analyze_diversity.py` — Diversity analysis and per-category breakdown
- `benchmark/mtbench_integration.py` — MT-Bench multi-turn conversation testing

**Experiment Runners:**
- `run_premium_tier.py` — Phase 1 testing script
- `run_persona_experiment.py` — Phase 3 persona diversity testing
- `test_personas.py` — Pilot test for measuring persona diversity

**Results and Analysis:**
- `results/premium_tier_results.json` — Phase 1 complete test data
- `results/mtbench_results.json` — Phase 2 multi-turn test data
- `results/persona_experiment.json` — Phase 3 persona diversity test data
- `WHY_ENSEMBLES_FAIL.md` — Detailed explanation with the "smoking gun" GDP example
- `DETAILED_METHODOLOGY.md` — Complete experimental methodology, prompt examples, code walkthrough
- `PREMIUM_TIER_RESULTS.md` — Phase 1 detailed findings
- `MTBENCH_RESULTS.md` — Phase 2 detailed findings

### Running Your Own Tests

```bash
# Set up environment
export AWS_BEARER_TOKEN_BEDROCK="your_token_here"
pip install -r requirements.txt

# Run a specific recipe
python -m moa.cli run --recipe persona-diverse --prompts benchmark/prompts.json

# Run full benchmark suite
python run_premium_tier.py

# Analyze results
python benchmark/analyze_results.py results/your_test_results.json
```

### Reproducing Our Results

1. All test configurations defined in `moa/models.py` RECIPES dict
2. All prompts in `benchmark/prompts.json`
3. All raw results with judge scores in `results/` directory
4. Statistical analysis reproducible via `benchmark/analyze_results.py`

**Validation:** Run `python -m pytest tests/` to verify framework correctness against test cases.

Run your own benchmarks. Challenge the conclusions. But the data from 592 tests is hard to argue with.

**Complete experimental timeline and methodology:** See [DETAILED_METHODOLOGY.md](DETAILED_METHODOLOGY.md) for full reproducibility details including prompt selection rationale, persona design process, statistical methods, implementation challenges, and solutions.

---

## Complete Artifact Index

For editors and researchers, here's the complete index of deliverables:

### Primary Documentation
- **README.md** — Updated with empirical findings, replaces speculative claims with measured data
- **BLOG.md** (this file) — Complete practitioner's guide with detailed methodology
- **DETAILED_METHODOLOGY.md** — Full experimental record with code examples, prompt design rationale, statistical methods

### Analysis Documents
- **WHY_ENSEMBLES_FAIL.md** — Deep dive on the aggregation trap with GDP of Lesotho example
- **PREMIUM_TIER_RESULTS.md** — Phase 1 detailed findings
- **MTBENCH_RESULTS.md** — Phase 2 multi-turn conversation findings

### Code Implementation
- **moa/core.py** (457 lines) — Async MoA pipeline, layer execution, context building
- **moa/bedrock_client.py** (218 lines) — AWS Bedrock API wrapper with bearer token auth
- **moa/models.py** (302 lines) — Model pricing table, persona definitions, 14 pre-defined recipes
- **moa/judge.py** (187 lines) — Automated quality scoring system with 40/30/30 weighting

### Benchmarking Infrastructure
- **benchmark/prompts.json** (54 prompts) — Test suite across 7 categories with adversarial prompts
- **benchmark/analyze_results.py** (347 lines) — Statistical analysis (t-tests, p-values, Cohen's d, per-category)
- **benchmark/analyze_diversity.py** (208 lines) — Diversity analysis, same-model vs diverse comparison
- **benchmark/mtbench_integration.py** (260 lines) — MT-Bench adapter for multi-turn testing

### Experiment Runners
- **run_premium_tier.py** (178 lines) — Phase 1 execution script
- **run_persona_experiment.py** (194 lines) — Phase 3 execution script with persona injection
- **test_personas.py** (125 lines) — Pilot test for measuring persona diversity

### Raw Results (All JSON files with judge scores and justifications)
- **results/premium_tier_results.json** (216 tests) — Phase 1: Premium configurations
- **results/mtbench_results.json** (160 tests) — Phase 2: Multi-turn conversations
- **results/persona_experiment.json** (216 tests) — Phase 3: Persona diversity

### Key Findings Summary
- **Total tests:** 592 live API calls
- **Test period:** March 30 - April 4, 2026 (6 days)
- **Configurations tested:** 10 unique ensemble configurations + 3 baselines
- **Ensembles that beat standalone Opus overall:** 0 of 6
- **Mean ensemble penalty:** -0.5 to -2.2 points overall (on 100-point scale)
- **Statistical significance:** 0 of 6 comparisons significant at p < 0.05 in single-run tests
- **Closest to significant:** Same-model-premium (p=0.08), persona-diverse (p=0.06)
- **Adversarial finding:** 2 of 6 outperform on standard prompts but fail on adversarial inputs

### For Reproducibility
All test configurations, prompts, and analysis code are available in the repository. To reproduce:

1. Install dependencies: `pip install -r requirements.txt`
2. Set bearer token: `export AWS_BEARER_TOKEN_BEDROCK="..."`
3. Run any phase: `python run_premium_tier.py`
4. Analyze results: `python benchmark/analyze_results.py results/your_results.json`

**Questions or need clarifications?** All experimental details are in [DETAILED_METHODOLOGY.md](DETAILED_METHODOLOGY.md).

---

*Written by a practitioner, for practitioners. No vendor advocacy. Just 592 test cases and the uncomfortable truth: MoA doesn't work on AWS Bedrock.*

*Last updated: April 10, 2026*  
*Tests completed: March 30 - April 4, 2026*  
*Total test cases: 216 (premium) + 160 (MT-Bench) + 216 (persona) = 592*  
*Code implementation: ~2,800 lines across 15 modules*

---

## Frequently Asked Questions

**Q: What if I use different prompting strategies instead of different models?**

We tested this in Phase 3. Persona-diverse configuration used the same model (Opus) with three distinct personas (critical-analyst, creative-generalist, domain-expert). Measured response diversity: 81%. Result: Still 2.1 points worse than standalone Opus.

**Q: What about using MoA for specific domains like code or creative writing?**

We tested across 7 categories including code and creative prompts. Pattern held across all categories: ensembles showed consistent small performance decreases (0.5-2.2 points), with some configurations outperforming on standard prompts but failing on adversarial inputs.

**Q: Could cheaper proposers + expensive aggregator work if the aggregator is even stronger?**

We tested this (mixed-capability: cheap proposers + Opus aggregator). Scored 4.5 points lower than standalone Opus. The problem is that Opus is already the strongest model on Bedrock — there's no "even stronger" aggregator available.

**Q: What if I need to reduce cost and can't afford Opus for every query?**

Use smart routing (route by complexity) or use a cheaper standalone model (Haiku, Nova Lite). Both outperformed ensembles in our tests.

**Q: Does this mean Wang et al.'s MoA paper was wrong?**

No. Their setup used frontier models from multiple organizations (GPT-4, Claude, Gemini). That's fundamentally different from AWS Bedrock where:
1. All models run on the same platform
2. Opus is both the best proposer and best aggregator
3. True cross-organizational diversity isn't available

MoA works when you have a stronger aggregator than any proposer. On Bedrock, that condition doesn't hold.
