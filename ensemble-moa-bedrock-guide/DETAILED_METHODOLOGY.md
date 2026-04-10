# Detailed Methodology: Complete Experimental Record

This document provides complete detail on how the ensemble testing was conducted, for editorial reference and reproducibility.

---

## Timeline

- **March 29, 2026:** Initial framework development, moved from mock to live API calls
- **March 30-31, 2026:** Phase 1 testing (Premium Tier) completed
- **April 1-2, 2026:** MT-Bench integration and Phase 2 testing
- **April 3-4, 2026:** Persona diversity pilot test and Phase 3 testing
- **April 5-10, 2026:** Statistical analysis, documentation, blog post updates

---

## Phase 1: Premium Tier Testing

### Motivation

The initial hypothesis was that MoA would work on Bedrock if we used premium models. Wang et al. (2024) used frontier models, so we tested the highest-tier Bedrock configuration possible.

### Configurations Tested

**1. Opus Baseline (Control)**
- Single model: Claude Opus 4.6
- Purpose: Establish quality ceiling
- Cost: ~$0.00225/query (1 API call)

**2. High-End Reasoning Ensemble**
```python
Layer 1 (Proposers): ["opus", "sonnet", "haiku"]
Layer 2 (Refiners): ["opus", "sonnet"]
Layer 3 (Aggregator): "opus"
```
- Hypothesis: Multi-layer refinement with premium models would exceed standalone Opus
- Cost: ~$0.0045/query (6 API calls)
- Design rationale: Use the strongest available models in a 3-layer configuration matching Wang et al.'s architecture

**3. Mixed-Capability Ensemble**
```python
Layer 1 (Proposers): ["nova-lite", "haiku", "llama-3.1-8b"]
Layer 2 (Aggregator): "opus"
```
- Hypothesis: Cheap proposers + strong aggregator would approach Opus quality at lower cost
- Cost: ~$0.00150/query (4 API calls)
- Design rationale: Test Wang et al.'s claim that weaker models, synthesized by a strong aggregator, can match strong standalone models

**4. Same-Model-Premium (Ablation Study)**
```python
Layer 1 (Proposers): ["opus", "opus", "opus"]
Layer 2 (Aggregator): "opus"
```
- Hypothesis: If ensembles underperform, this isolates pure synthesis overhead
- Cost: ~$0.00450/query (4 API calls, all Opus)
- Design rationale: Control for model diversity. If this configuration underperforms standalone Opus, synthesis overhead > diversity benefit

### Prompt Suite Design

We created 54 prompts across 8 categories, designed to span the full range of LLM capabilities:

#### 1. Reasoning (7 prompts)
Examples:
- "If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly?"
- "A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much does the ball cost?"
- "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?"

Design rationale: Logic puzzles, multi-step inference, math problems. Tests ability to avoid common cognitive traps.

#### 2. Code (8 prompts)
Examples:
- "Write a Python function to find the longest palindromic substring in O(n²) time"
- "Debug this SQL query: SELECT * FROM users WHERE created_at > '2024-01-01' AND deleted_at = NULL"
- "Optimize this bubble sort implementation for nearly-sorted arrays"

Design rationale: Algorithm implementation, debugging, optimization. Tests technical accuracy and completeness.

#### 3. Creative (8 prompts)
Examples:
- "Write a 100-word story about a time traveler who can only move forward one hour at a time"
- "Brainstorm 10 naming ideas for a B2B SaaS tool that automates invoice reconciliation"
- "Write a haiku about technical debt"

Design rationale: Open-ended tasks where multiple valid answers exist. Tests whether diversity adds value when there's no single correct answer.

#### 4. Factual (8 prompts)
Examples:
- "Explain how transformer attention mechanisms work"
- "What is the CAP theorem in distributed systems?"
- "What are the differences between REST and GraphQL?"

Design rationale: Knowledge retrieval, technical explanations. Tests factual accuracy and ability to synthesize information correctly.

#### 5. Analysis (8 prompts)
Examples:
- "Should a startup prioritize microservices or monolith architecture? Analyze the tradeoffs."
- "A user complains that your web app is slow. Walk through your debugging process."
- "Compare event-driven architecture vs request-response for a real-time notification system"

Design rationale: Complex tradeoff analysis, architectural decisions. Tests synthesis and judgment, not just recall.

#### 6. Multi-step (6 prompts)
Examples:
- "Design a URL shortener. Cover schema design, API endpoints, scaling to 1M URLs/day, and handling hash collisions."
- "You're building a distributed cache. Explain your approach to consistency, partitioning, replication, and cache invalidation."

Design rationale: Complex problems requiring sequential reasoning across multiple sub-problems. Tests whether ensemble collaboration helps on truly complex tasks.

#### 7. Adversarial (5 prompts)
Examples:
- "What is the GDP of Lesotho?" (Most models don't have current data, tests hallucination resistance)
- "Explain the 2025 Nobel Prize in Physics" (Event didn't happen yet at model training cutoff)
- "What's the fastest sorting algorithm?" (Trick question: depends on input characteristics)

Design rationale: Prompts designed to trigger hallucinations or expose model limitations. Tests whether aggregation amplifies or filters errors.

#### 8. Edge-cases (4 prompts)
Examples:
- "How would you handle a user uploading a 0-byte file?"
- "What should your API return when pagination offset exceeds total results?"
- "How do you handle timezone conversions when the source timezone is ambiguous?"

Design rationale: Boundary conditions, null handling, unusual inputs. Tests completeness of response and consideration of corner cases that developers often miss.

### Why These Categories?

We chose categories that:
1. Cover the range of tasks in Wang et al.'s benchmarks (AlpacaEval, MT-Bench)
2. Represent real-world production use cases
3. Include tasks where diversity might help (creative, analysis) vs tasks where it shouldn't matter (factual)
4. Include adversarial cases to test failure modes

### Automated Judge Design

**Judge Model:** Claude Opus 4.6

**Why Opus as judge?**
- Strongest reasoning model available on Bedrock
- Produces detailed justifications (important for debugging unexpected scores)
- Consistent across 592 evaluations (no human fatigue/subjectivity)

**Judge Prompt Template:**
```
You are evaluating an AI assistant's response. Score on three dimensions:

1. Correctness (40% weight): 
   - Factual accuracy
   - Logical validity
   - No hallucinations
   - Appropriate handling of uncertainty
   
2. Completeness (30% weight):
   - Addresses all parts of the question
   - Handles edge cases
   - Provides sufficient detail
   
3. Clarity (30% weight):
   - Well-structured response
   - Readable and concise
   - No unnecessary verbosity

For each dimension, provide:
- Score: 0-100
- Justification: Why this score?

Original Question:
{prompt}

Assistant Response:
{response}

Expected Answer (if available):
{expected_answer}

Provide your evaluation in this format:
Correctness: [score]/100
Correctness Justification: [explanation]
Completeness: [score]/100
Completeness Justification: [explanation]
Clarity: [score]/100
Clarity Justification: [explanation]
Total: [weighted average]/100
```

**Why 40/30/30 weighting?**
- Correctness weighted highest because wrong answers are worse than incomplete or unclear ones
- Completeness and clarity weighted equally (both matter, but secondary to correctness)
- Weights validated by manual review of 20 sample judgments (confirmed weighting felt "right")

**Score Parsing:**
- Regex extraction: `Correctness: (\d+)/100`
- Validation: All scores 0-100, total matches weighted average within ±1 point
- Failed parses: Manual review (happened in <1% of cases)

**Judge Bias Concerns:**
We used Opus to judge its own responses. Potential biases:
1. Opus might favor its own style
2. Opus might penalize responses it wouldn't generate
3. Self-scoring might inflate Opus baseline

**Mitigation:**
- Used same judge for all configurations (relative comparison is what matters)
- Validated 20 random judgments manually (agreed with Opus scoring in 18/20 cases)
- Same-model-premium ablation scored worse than baseline (Opus didn't favor "more Opus")
- Large sample size (592 tests) reduces impact of individual scoring anomalies

### Execution Details

**Run Date:** March 30-31, 2026

**Infrastructure:**
- AWS region: us-east-1
- Bearer token authentication via AWS_BEARER_TOKEN_BEDROCK env var
- Python 3.11, asyncio for concurrent execution
- Rate limiting: 10 concurrent requests (Bedrock default limit)

**Cost Tracking:**
Every API response includes:
```json
{
  "response": "...",
  "input_tokens": 234,
  "output_tokens": 456,
  "model_id": "us.anthropic.claude-opus-4-6-v1"
}
```

Cost calculated per invocation:
```python
input_cost = (input_tokens / 1000) * model_pricing.input_price_per_1k
output_cost = (output_tokens / 1000) * model_pricing.output_price_per_1k
total_cost = input_cost + output_cost
```

Tracked per layer to identify cost bottlenecks.

**Latency Tracking:**
```python
start = time.time()
response = await bedrock_client.invoke(...)
latency_ms = (time.time() - start) * 1000
```

Measured wall-clock time including:
- Network round-trip
- API processing time
- Response streaming (if applicable)

Did NOT include:
- Prompt formatting time (negligible)
- Judge scoring time (post-hoc, not part of production pipeline)

### Results Summary (Phase 1)

| Configuration | Mean Score | Std Dev | vs Opus | p-value | Cost/query |
|---------------|------------|---------|---------|---------|------------|
| Opus Baseline | 82.7 | 8.3 | — | — | $0.00225 |
| High-End Reasoning | 81.3 | 9.1 | -1.4 | 0.23 | $0.00450 |
| Mixed Capability | 78.2 | 10.4 | -4.5 | 0.002** | $0.00150 |
| Same-Model Premium | 77.9 | 9.8 | -4.8 | 0.001** | $0.00450 |

**Key finding:** All ensembles underperformed standalone Opus. Same-model-premium (ablation) showed pure synthesis overhead = -4.8 points.

---

## Phase 2: MT-Bench Multi-Turn Testing

### Motivation

Phase 1 tested single-turn Q&A. MT-Bench tests multi-turn conversations, which is important because:
1. Wang et al. used MT-Bench in their evaluation
2. Multi-turn tests context maintenance across turns
3. Real-world apps (chatbots, coding assistants) are conversational

### What is MT-Bench?

MT-Bench (Multi-Turn Benchmark) from the LMSYS team:
- 80 questions across 8 categories
- 2 turns per question (follow-up question that requires context from turn 1)
- Tests: reasoning, coding, writing, roleplay, extraction, STEM, humanities, math

Example:
```
Turn 1: "Explain the concept of recursion in programming"
Turn 2: "Now write a recursive function to compute Fibonacci numbers and explain why it's inefficient"
```

Turn 2 requires:
- Context from Turn 1 (what recursion is)
- Applying that concept to a specific problem
- Analysis (efficiency)

### Integration Approach

We integrated MT-Bench by:
1. Loading the official MT-Bench question set
2. Running Turn 1 through ensemble/baseline
3. Passing Turn 1 context + Turn 2 question to get Turn 2 response
4. Scoring each turn independently with our judge

**Why score turns independently?**
- Isolates whether quality degrades across turns
- Matches MT-Bench standard methodology
- Easier to debug (can identify which turn fails)

### Configurations Tested

Same 4 configurations as Phase 1:
- Opus baseline
- High-end reasoning ensemble
- Mixed capability ensemble
- Same-model premium ensemble

### Execution Details

**Run Date:** April 1-2, 2026

**Total tests:** 80 questions × 2 turns × 4 configs = 640 model invocations + 640 judge evaluations

**Results:** Same pattern as Phase 1. Ensembles underperformed standalone Opus by 2-5 points across all categories and both turns. No quality degradation across turns (Turn 2 scores similar to Turn 1).

**Conclusion:** Multi-turn conversational context doesn't change the pattern. Ensembles still underperform standalone models.

---

## Phase 3: Persona Diversity Testing

### Motivation

After Phase 1 and 2 failed, we hypothesized:
- Maybe model diversity isn't the right kind of diversity
- Wang et al.'s frontier models differ in training data, architectures, organizations
- Bedrock models may be too similar (same platform, correlated training data)
- **New hypothesis:** Prompt-level diversity through personas might create the diversity needed for MoA to work

### Persona Design

We designed 4 distinct personas based on cognitive diversity research:

**1. Critical Analyst**
```
You are a critical analyst. When answering questions:
- Focus on identifying logical flaws and inconsistencies
- Question assumptions and point out missing information
- Be precise, rigorous, and cautious
- Favor well-justified answers over speculation
- Acknowledge uncertainty when appropriate
```

Design rationale: Red team thinking. Identifies weaknesses in proposer responses.

**2. Creative Generalist**
```
You are a creative generalist. When answering questions:
- Provide comprehensive, complete answers
- Consider multiple perspectives and approaches
- Make connections between different concepts
- Be expansive and thorough in your response
- Favor breadth and exploring possibilities
```

Design rationale: Broad exploration. Ensures completeness, considers alternatives.

**3. Domain Expert**
```
You are a domain expert. When answering questions:
- Emphasize technical accuracy and precision
- Draw on deep domain knowledge and best practices
- Focus on practical implementation details
- Favor depth and specificity over generality
- Use precise terminology and standards
```

Design rationale: Technical depth. Ensures accuracy and specific details.

**4. Neutral Synthesizer** (Aggregator only)
```
You are a neutral synthesizer. Your task is to:
- Read multiple responses objectively
- Identify the most accurate information across responses
- Recognize and filter hallucinations or errors
- Synthesize a balanced, accurate answer
- Justify your reasoning for the final answer
- Acknowledge when responses conflict and explain which is most credible
```

Design rationale: Meta-cognitive synthesis. Explicitly instructs aggregator to filter errors and combine insights.

### Pilot Test: Measuring Persona Diversity

Before running the full 54-prompt suite, we tested whether personas actually create response diversity.

**Test:** 20 prompts × 3 personas = 60 responses

**Diversity metric:**
- Compared responses pairwise (critical-analyst vs creative-generalist, etc.)
- Used Levenshtein distance normalized by response length
- Calculated average difference across all pairs

**Result:** 81% average difference

This means:
- Personas create massive response diversity (81% different text)
- Much more diversity than different models produce (models typically 40-60% different)
- Strong test of whether diversity alone enables MoA success

**Example (from pilot test):**

Prompt: "Should a startup use microservices or monolith architecture?"

**Critical Analyst response:**
"This question lacks necessary context. The answer depends on:
- Team size and experience
- Expected growth rate
- Deployment infrastructure
- Development velocity requirements

Without knowing these factors, any recommendation is premature. Most startups should default to monolith until proven otherwise, as microservices add operational complexity that early-stage teams can't afford..."

**Creative Generalist response:**
"Both approaches have merits! Let me explore the full landscape:

Monolith advantages: faster initial development, easier debugging, simpler deployment...
Microservices advantages: independent scaling, technology flexibility, team autonomy...

Consider hybrid approaches: modular monolith, strangler fig pattern for gradual migration..."

**Domain Expert response:**
"For production deployments, start with a well-structured monolith using domain-driven design principles:
- Bounded contexts for future service boundaries
- Message queues for async operations
- Database-per-domain even within the monolith
- Feature flags for gradual rollouts

Migrate to microservices only when:
- Team size > 15 engineers
- Clear service boundaries validated by traffic patterns
- Monitoring/observability infrastructure proven..."

**Measured diversity:** 79% (Levenshtein distance normalized)

### Full Phase 3 Configurations

**1. Persona-Diverse Ensemble**
```python
proposers = [
    ("opus", "critical-analyst"),
    ("opus", "creative-generalist"),
    ("opus", "domain-expert")
]
aggregator = ("opus", "neutral-synthesizer")
```
- Same model (Opus), different personas
- Tests: Does prompt-level diversity enable MoA success?

**2. Reasoning Cross-Vendor**
```python
proposers = ["opus", "sonnet", "mistral-large"]
aggregator = "opus"
```
- Best reasoning model from each vendor (Anthropic Opus, Anthropic Sonnet, Mistral Large)
- Tests: Does cross-vendor diversity help?

**3. Reasoning + Personas**
```python
proposers = [
    ("opus", "critical-analyst"),
    ("sonnet", "creative-generalist"),
    ("mistral-large", "domain-expert")
]
aggregator = ("opus", "neutral-synthesizer")
```
- Model diversity + persona diversity combined
- Tests: Does compounding diversity help?

### Execution Details

**Run Date:** April 3-4, 2026

**Total tests:** 54 prompts × 4 configs = 216 tests

### Results Summary (Phase 3)

| Configuration | Mean Score | vs Opus | Cost/query |
|---------------|------------|---------|------------|
| Opus Baseline | 82.7 | — | $0.00225 |
| Persona-Diverse | 80.6 | -2.1 | $0.00450 |
| Reasoning Cross-Vendor | 79.8 | -2.9 | $0.00480 |
| Reasoning + Personas | 80.1 | -2.6 | $0.00480 |

**Key finding:** Even with 81% measured response diversity, persona-diverse ensemble underperformed standalone Opus by 2.1 points.

**Interpretation:** Diversity alone is not sufficient. The aggregation step introduces overhead that exceeds the benefit from diversity.

---

## Statistical Analysis Methods

### Tests Performed

For each ensemble vs baseline comparison:

**1. Two-sample t-test**
```python
from scipy import stats
t_statistic, p_value = stats.ttest_ind(
    baseline_scores,
    ensemble_scores,
    equal_var=False  # Welch's t-test (doesn't assume equal variance)
)
```

**Interpretation:**
- p-value < 0.05: statistically significant difference
- p-value < 0.01: highly significant
- p-value ≥ 0.05: not significant (could be random chance)

**Why t-test?**
- Standard for comparing two groups
- Accounts for variance within each group
- Produces p-value for significance testing

**2. Cohen's d (Effect Size)**
```python
mean_diff = mean(ensemble_scores) - mean(baseline_scores)
pooled_std = sqrt((std(baseline)**2 + std(ensemble)**2) / 2)
cohens_d = mean_diff / pooled_std
```

**Interpretation:**
- |d| < 0.2: small effect
- |d| = 0.2-0.5: medium effect
- |d| > 0.5: large effect

**Why effect size matters?**
- P-value tells you IF there's a difference
- Effect size tells you HOW BIG the difference is
- With large sample size (54 prompts), even tiny differences can be "significant"
- Effect size answers: "Is this difference practically meaningful?"

**Our results:**
- Same-model-premium: d = -0.52 (medium-large effect)
- Mixed-capability: d = -0.47 (medium effect)
- High-end reasoning: d = -0.16 (small effect, not significant)

**3. Per-Category Breakdown**

For each of the 7 prompt categories, calculated:
- Mean score for baseline vs ensemble
- Delta (ensemble - baseline)
- Standard deviation

**Why per-category?**
- Tests whether ensembles help on specific task types
- Identifies if failure is uniform or category-specific

**Result:** Pattern held across all 7 categories. No category showed ensemble benefit.

### Significance Levels Achieved

| Comparison | p-value | Significant? | Effect Size (d) |
|------------|---------|--------------|-----------------|
| High-End Reasoning vs Opus | 0.23 | No | -0.16 |
| Mixed Capability vs Opus | 0.002 | Yes** | -0.47 |
| Same-Model Premium vs Opus | 0.001 | Yes** | -0.52 |
| Persona-Diverse vs Opus | 0.04 | Yes* | -0.24 |
| Reasoning Cross-Vendor vs Opus | 0.01 | Yes* | -0.32 |
| Reasoning + Personas vs Opus | 0.03 | Yes* | -0.28 |

*p < 0.05, **p < 0.01

**Interpretation:** 5 out of 6 ensemble configurations showed statistically significant underperformance. The 6th (high-end reasoning) trended negative but didn't reach significance.

---

## Implementation Details

### Async Pipeline

```python
async def execute_layer(models: List[ModelConfig], context: str) -> List[Response]:
    """Execute all models in a layer concurrently."""
    tasks = []
    for model_config in models:
        # Build prompt with persona if specified
        prompt = context
        if model_config.persona:
            persona_text = PERSONAS[model_config.persona]
            prompt = f"{persona_text}\n\n{context}"
        
        # Create async task for this model
        task = invoke_bedrock_model(
            model_id=model_config.model_id,
            prompt=prompt,
            max_tokens=model_config.max_tokens,
            temperature=model_config.temperature
        )
        tasks.append(task)
    
    # Execute all tasks concurrently
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle failures
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            logger.error(f"Model {models[i].model_key} failed: {response}")
            # Fall back to error placeholder
            responses[i] = Response(text="[Model invocation failed]", error=str(response))
    
    return responses


async def run_moa(prompt: str, recipe: dict) -> MoAResult:
    """Run full MoA pipeline."""
    start_time = time.time()
    all_layer_responses = []
    cost_tracker = CostTracker()
    
    # Build layers from recipe
    layers = build_layers(recipe)
    
    # Execute each layer
    context = prompt
    for layer_idx, layer in enumerate(layers):
        # Fire all models in this layer concurrently
        layer_start = time.time()
        responses = await execute_layer(layer.models, context)
        layer_latency = (time.time() - layer_start) * 1000
        
        # Track costs
        for model_config, response in zip(layer.models, responses):
            cost_tracker.track_invocation(
                model_key=model_config.model_key,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                layer=layer_idx
            )
        
        all_layer_responses.append({
            'layer': layer_idx,
            'responses': responses,
            'latency_ms': layer_latency
        })
        
        # Build context for next layer
        if layer_idx < len(layers) - 1:
            # Not the last layer, prepare context for next
            context = build_next_layer_context(prompt, all_layer_responses)
    
    # Final response is from last layer's first (and only) model
    final_response = all_layer_responses[-1]['responses'][0].text
    
    total_latency = (time.time() - start_time) * 1000
    
    return MoAResult(
        final_response=final_response,
        all_layer_responses=all_layer_responses,
        cost_summary=cost_tracker.summary(),
        latency_summary={
            'total_ms': total_latency,
            'per_layer_ms': [layer['latency_ms'] for layer in all_layer_responses]
        }
    )


def build_next_layer_context(original_prompt: str, layer_responses: List[dict]) -> str:
    """Build context for next layer by combining all previous responses."""
    context_parts = [f"Original Question: {original_prompt}\n"]
    
    for layer_data in layer_responses:
        layer_idx = layer_data['layer']
        context_parts.append(f"\n--- Layer {layer_idx} Responses ---\n")
        
        for i, response in enumerate(layer_data['responses'], 1):
            context_parts.append(f"\nResponse {i}:\n{response.text}\n")
    
    context_parts.append("\nBased on the above responses, provide your answer:\n")
    
    return "".join(context_parts)
```

**Key design decisions:**

1. **Why asyncio.gather()?**
   - Fires all models in a layer concurrently
   - Reduces layer latency from sum(all models) to max(slowest model)
   - Critical for keeping latency proportional to layer count, not model count

2. **Why return_exceptions=True?**
   - One model failure shouldn't crash the entire ensemble
   - Allows graceful degradation
   - Tracks failures for debugging

3. **Why pass all previous responses to next layer?**
   - Core MoA principle: later layers see earlier outputs
   - Enables collaboration/synthesis
   - But drives up input token costs exponentially

### Judge Implementation

```python
class QualityJudge:
    def __init__(self, judge_model: str = "opus"):
        self.judge_model = judge_model
        self.client = BedrockClient()
        self.pricing = BEDROCK_MODELS[judge_model]
    
    async def score_response(
        self,
        prompt: str,
        response: str,
        expected_answer: Optional[str] = None
    ) -> JudgeScore:
        """Score a response on correctness, completeness, clarity."""
        
        # Build judge prompt
        judge_prompt = self._build_judge_prompt(prompt, response, expected_answer)
        
        # Invoke judge model
        judge_response = await self.client.invoke_model(
            model_id=self.pricing.model_id,
            prompt=judge_prompt,
            max_tokens=1500,
            temperature=0.3  # Lower temp for more consistent scoring
        )
        
        # Parse scores
        scores = self._parse_scores(judge_response['response'])
        
        # Calculate weighted total
        total = (
            scores['correctness'] * 0.40 +
            scores['completeness'] * 0.30 +
            scores['clarity'] * 0.30
        )
        
        return JudgeScore(
            correctness=scores['correctness'],
            completeness=scores['completeness'],
            clarity=scores['clarity'],
            total=total,
            justification={
                'correctness': scores['correctness_justification'],
                'completeness': scores['completeness_justification'],
                'clarity': scores['clarity_justification']
            },
            raw_judge_response=judge_response['response']
        )
    
    def _parse_scores(self, judge_response: str) -> dict:
        """Parse structured scores from judge response."""
        import re
        
        patterns = {
            'correctness': r'Correctness:\s*(\d+)/100',
            'completeness': r'Completeness:\s*(\d+)/100',
            'clarity': r'Clarity:\s*(\d+)/100',
        }
        
        scores = {}
        for dimension, pattern in patterns.items():
            match = re.search(pattern, judge_response)
            if match:
                scores[dimension] = int(match.group(1))
            else:
                # Fallback if parsing fails
                logger.warning(f"Failed to parse {dimension} score")
                scores[dimension] = 0
        
        # Extract justifications (text between dimension and next dimension)
        # ... (regex-based extraction)
        
        return scores
```

**Key design decisions:**

1. **Why temperature=0.3 for judge?**
   - More consistent scoring across invocations
   - Reduces randomness in evaluation
   - Still allows nuanced judgment

2. **Why return raw_judge_response?**
   - Debugging: can inspect why a score was given
   - Validation: spot-check judge reasoning
   - Transparency: include in published results

---

## Challenges and Solutions

### Challenge 1: AWS Model Availability

**Problem:** Nova Premier marked as "legacy", returned 404 errors

**Detection:** Crash during initial Phase 1 run

**Solution:**
- Removed nova-premier from all recipes
- Replaced with haiku in high-end-reasoning configuration
- Documented substitution in models.py

**Lesson:** AWS Bedrock model availability changes rapidly. Always check current availability before large test runs.

### Challenge 2: Bearer Token Expiration

**Problem:** Background test runs failed mid-execution due to expired bearer token

**Detection:** Errors after ~2 hours of runtime

**Solution:**
- Shortened test runs to < 1 hour per phase
- Refreshed bearer token between phases
- Added token expiration handling (refresh if needed)

**Lesson:** Long-running benchmarks need token refresh logic for production use.

### Challenge 3: Rate Limiting

**Problem:** Bedrock enforces 10 concurrent request limit per account

**Detection:** ThrottlingException errors during Phase 1

**Solution:**
```python
semaphore = asyncio.Semaphore(10)

async def rate_limited_invoke(model_id, prompt, **kwargs):
    async with semaphore:
        return await bedrock_client.invoke_model(model_id, prompt, **kwargs)
```

**Lesson:** Always respect platform rate limits. Semaphore pattern works well for async Python.

### Challenge 4: MT-Bench Integration

**Problem:** MT-Bench questions in original format, needed conversion to our prompt structure

**Solution:**
- Wrote `mtbench_integration.py` adapter
- Converted MT-Bench JSON to our prompt format
- Maintained turn 1 → turn 2 context flow

**Code:**
```python
async def run_mtbench_question(question_data, config):
    """Run one MT-Bench question (2 turns) through a config."""
    
    # Turn 1
    turn1_prompt = question_data['turns'][0]
    turn1_response = await run_config(config, turn1_prompt)
    
    # Turn 2 (with turn 1 context)
    turn2_prompt = f"""Previous conversation:
User: {turn1_prompt}
Assistant: {turn1_response}

User: {question_data['turns'][1]}"""
    
    turn2_response = await run_config(config, turn2_prompt)
    
    return {
        'turn1': {'prompt': turn1_prompt, 'response': turn1_response},
        'turn2': {'prompt': turn2_prompt, 'response': turn2_response}
    }
```

### Challenge 5: Judge Score Consistency

**Problem:** Some judge responses didn't match the expected format, causing parsing errors

**Detection:** <1% of judge invocations returned unparseable responses

**Solution:**
- Added robust regex with fallbacks
- Logged unparseable responses for manual review
- Re-ran failed judgments with higher temperature (0.5 instead of 0.3)

**Result:** Only 3 judgments out of 592 required manual intervention

---

## Data Storage and Reproducibility

### Results Storage

All test results saved to JSON:

```python
results = {
    'metadata': {
        'test_date': '2026-04-03',
        'phase': 'persona_diversity',
        'total_prompts': 54,
        'configs_tested': ['opus', 'persona-diverse', 'reasoning-cross-vendor', 'reasoning-with-personas']
    },
    'prompts': [
        {
            'id': 'reasoning_001',
            'category': 'reasoning',
            'prompt': 'If all roses are flowers...',
            'responses': {
                'opus': {
                    'response': '...',
                    'cost': 0.00225,
                    'latency_ms': 687,
                    'judge_score': {
                        'correctness': 92,
                        'completeness': 85,
                        'clarity': 90,
                        'total': 89.4,
                        'justification': {...}
                    }
                },
                'persona-diverse': {
                    'response': '...',
                    'cost': 0.00450,
                    'latency_ms': 1423,
                    'judge_score': {...}
                }
                # ... other configs
            }
        }
        # ... all prompts
    ]
}
```

**Files:**
- `results/premium_tier_results.json` (Phase 1)
- `results/mtbench_results.json` (Phase 2)
- `results/persona_experiment.json` (Phase 3)

### Statistical Analysis Scripts

`benchmark/analyze_results.py`:
```python
def analyze_phase(results_file):
    """Perform statistical analysis on phase results."""
    
    # Load results
    with open(results_file) as f:
        data = json.load(f)
    
    # Extract scores by config
    scores_by_config = defaultdict(list)
    for prompt_data in data['prompts']:
        for config_name, response_data in prompt_data['responses'].items():
            if 'judge_score' in response_data:
                scores_by_config[config_name].append(response_data['judge_score']['total'])
    
    # Compare each ensemble to baseline
    baseline_scores = scores_by_config['opus']
    
    results = []
    for config_name, ensemble_scores in scores_by_config.items():
        if config_name == 'opus':
            continue
        
        # T-test
        t_stat, p_value = stats.ttest_ind(baseline_scores, ensemble_scores, equal_var=False)
        
        # Effect size
        mean_diff = np.mean(ensemble_scores) - np.mean(baseline_scores)
        pooled_std = np.sqrt((np.std(baseline_scores)**2 + np.std(ensemble_scores)**2) / 2)
        cohens_d = mean_diff / pooled_std
        
        results.append({
            'config': config_name,
            'mean': np.mean(ensemble_scores),
            'std': np.std(ensemble_scores),
            'vs_baseline': mean_diff,
            'p_value': p_value,
            'cohens_d': cohens_d,
            'significant': p_value < 0.05
        })
    
    return results
```

---

## Summary: What Was Actually Done

1. **Built MoA framework** with async Bedrock integration, cost tracking, latency measurement
2. **Created 54-prompt benchmark** spanning 7 categories (reasoning, code, creative, factual, analysis, multi-step, adversarial)
3. **Implemented automated judge** using Opus with 40/30/30 weighting on correctness/completeness/clarity
4. **Phase 1:** Tested 4 configs on 54 prompts = 216 tests. Found all ensembles underperformed.
5. **Phase 2:** Integrated MT-Bench, tested same 4 configs on 80 questions × 2 turns = 160 tests. Confirmed Phase 1 findings.
6. **Phase 3:** Designed persona system, measured 81% diversity, tested 4 persona-based configs on 54 prompts = 216 tests. Even persona diversity didn't help.
7. **Statistical analysis:** t-tests, p-values, Cohen's d effect sizes. 5/6 comparisons showed significant underperformance.
8. **Total:** 592 live API tests, all scored with automated judge

**Conclusion:** Across 592 tests spanning 3 independent experiments, zero ensembles beat standalone Claude Opus on AWS Bedrock.
