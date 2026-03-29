# Ensemble Persona Orchestrator

**Experiment: Same Model, Different Minds**

An exploration of persona-based LLM ensembling—running the same question through multiple analytical personas with different reasoning frameworks, then orchestrating the results.

Part of the **protoGen LLM Ensemble Methods** series (Project 3 of 3).

---

## What This Is

This project implements and evaluates **persona-based ensembling**: using the same LLM (Claude Sonnet via AWS Bedrock) with 7 different system prompts to create genuinely different analytical perspectives. Key questions explored:

- Does persona diversity create **real** answer diversity (substantive) or just **cosmetic** variation?
- Can orchestrating multiple personas produce better outputs than a single well-prompted call?
- When is 5-10x token cost worth it?

## Architecture

```
Input Prompt
     ↓
  Runner (async parallel execution)
     ↓
  ┌──────────────────────────────────────┐
  │  7 Personas (same model, different   │
  │  reasoning frameworks)               │
  │                                      │
  │  • First Principles Thinker          │
  │  • Skeptical Analyst                 │
  │  • Devil's Advocate                  │
  │  • Creative Problem Solver           │
  │  • Domain Expert                     │
  │  • Empiricist                        │
  │  • Systems Thinker                   │
  └──────────────────────────────────────┘
     ↓
  Diversity Measurement
  (semantic similarity, conclusion agreement)
     ↓
  Orchestrator (3 strategies)
     ↓
  ┌──────────────────────────────────────┐
  │  • Pick-Best: Judge selects strongest│
  │  • Synthesize: Combine best elements │
  │  • Debate: Feed back disagreements   │
  └──────────────────────────────────────┘
     ↓
  Final Output + Analysis
```

## Key Features

- **7 distinct personas** with different reasoning frameworks (axiomatic deduction, critical empiricism, adversarial interrogation, etc.)
- **Async parallel execution** - runs all personas simultaneously
- **3 orchestration strategies** - pick-best, synthesize, debate
- **Diversity measurement** - quantify how different the responses really are
- **12 benchmark prompts** across business strategy, technical architecture, creative problem-solving, ethical dilemmas
- **Mock mode** - test without live Bedrock API calls
- **Complete experiment framework** - measure diversity, compare strategies, generate reports

## Setup

### Prerequisites

- Python 3.8+
- AWS account with Bedrock access (optional—mock mode works without it)
- AWS credentials configured (if using live mode)

### Installation

```bash
# Clone or download the project
cd ensemble-persona-orchestrator

# Install dependencies
pip install boto3  # Only needed for live Bedrock calls

# No other dependencies required for mock mode!
```

### Project Structure

```
ensemble-persona-orchestrator/
├── personas/                      # 7 persona definition JSON files
│   ├── first_principles_thinker.json
│   ├── skeptical_analyst.json
│   ├── devils_advocate.json
│   ├── creative_problem_solver.json
│   ├── domain_expert.json
│   ├── empiricist.json
│   └── systems_thinker.json
├── benchmark/                     # Test prompts
│   └── test_prompts.json         # 12 prompts across categories
├── results/                       # Output directory (created automatically)
├── runner.py                      # Async persona execution
├── orchestrator.py                # 3 orchestration strategies
├── diversity.py                   # Diversity measurement
├── experiment.py                  # Main experiment runner
├── BLOG.md                        # Full write-up (3,150 words)
└── README.md                      # This file
```

## Usage

### Quick Start (Mock Mode)

Test the system without Bedrock API calls:

```bash
# Run a single prompt
python3 experiment.py --prompt "Should we build our own auth or use Auth0?"

# Results saved to results/interactive_result.json
```

### Run with Specific Prompt

```bash
python3 experiment.py \
  --prompt "Our startup has 10k free users but only 50 paying customers. Focus on conversion or acquisition?" \
  --output results/my_experiment.json
```

### Run Benchmark Suite

```bash
# Run all 12 benchmark prompts
python3 experiment.py --benchmark

# Run specific benchmark prompt
python3 experiment.py --benchmark --prompt-id strategy_001
```

### Live Mode (AWS Bedrock)

```bash
# Make sure AWS credentials are configured
export AWS_PROFILE=your-profile  # or use default

# Run with live Bedrock calls
python3 experiment.py --live --prompt "Your question here"
```

## Understanding the Output

### Console Output

The experiment runner shows:

1. **Persona responses** - all 7 personas running in parallel
2. **Diversity analysis** - how different the responses are
3. **Orchestration comparison** - 3 strategies side-by-side
4. **Experiment summary** - timing, diversity scores, conclusion agreement

Example output:

```
============================================================
DIVERSITY ANALYSIS
============================================================

**Overall Diversity: HIGH** (score: 0.95)
- Average pairwise similarity: 0.05
- Lower similarity = higher diversity

**Conclusion Agreement: WEAK** (0.29)
- Weak agreement on recommendations across personas

**Interpretation:**
- Personas are producing **substantively different** responses
- Personas **disagree on recommendations** - genuine analytical diversity
```

### JSON Results File

Complete experiment results saved as JSON:

```json
{
  "experiment": {
    "prompt": "Your question",
    "timestamp": "2026-03-29 12:00:00",
    "total_time_seconds": 1.12,
    "mock_mode": true
  },
  "persona_responses": {
    "responses": [
      {
        "persona_id": "first_principles",
        "persona_name": "First Principles Thinker",
        "reasoning_framework": "axiomatic_deduction",
        "response_text": "...",
        "latency_ms": 712,
        "token_count": 82
      }
      // ... 6 more personas
    ]
  },
  "diversity_metrics": {
    "diversity_score": 0.952,
    "conclusion_agreement": 0.288,
    "pairwise_similarities": { ... },
    "unique_concepts_per_persona": { ... }
  },
  "orchestration": {
    "strategies": {
      "pick_best": { ... },
      "synthesize": { ... },
      "debate": { ... }
    }
  }
}
```

## Personas Explained

Each persona uses a distinct **reasoning framework**, not just different tone:

| Persona | Framework | When It Excels |
|---------|-----------|----------------|
| **First Principles Thinker** | Axiomatic deduction | Challenging assumptions, questioning convention |
| **Skeptical Analyst** | Critical empiricism | Finding flaws, demanding evidence |
| **Devil's Advocate** | Adversarial interrogation | Exposing blind spots, surfacing risks |
| **Creative Problem Solver** | Analogical synthesis | Novel reframing, unconventional approaches |
| **Domain Expert** | Pattern recognition | Applying best practices, avoiding known pitfalls |
| **Empiricist** | Experimental validation | Designing tests, proposing metrics |
| **Systems Thinker** | Systems dynamics | Mapping feedback loops, second-order effects |

## Orchestration Strategies

### 1. Pick-Best

**How it works:** Judge LLM evaluates all responses and selects the single strongest one.

**When to use:**
- Narrow technical questions where one persona clearly dominates
- Fast iteration needed
- Want to minimize cost (cheapest strategy)

**Trade-off:** May discard valuable minority perspectives.

### 2. Synthesize

**How it works:** Combine the strongest elements from all responses into one integrated answer.

**When to use:**
- Complex multi-faceted problems
- Want richest possible output
- Different personas surface complementary insights

**Trade-off:** Can "average out" breakthrough insights if not careful.

### 3. Debate

**How it works:** Identify disagreements, simulate one round of personas responding to each other's critiques, then synthesize.

**When to use:**
- High-stakes decisions
- Need most robust reasoning
- Want stress-tested recommendations

**Trade-off:** 3-4x more expensive (multiple LLM calls). Slowest strategy.

## Benchmark Prompts

12 test prompts across 6 categories:

- **Business Strategy** - Product decisions, competitive responses
- **Technical Architecture** - Scaling, microservices, database choices
- **Analytical Problems** - Metrics interpretation, A/B testing
- **Creative Problem-Solving** - Differentiation, non-obvious solutions
- **Ethical Dilemmas** - ML fairness, competitive intelligence
- **Trade-off Analysis** - Hiring, launch timing

Each prompt designed to elicit genuine analytical diversity.

## Cost Analysis

### Mock Mode
- **Free** - no API calls
- Simulates realistic responses for testing

### Live Mode (AWS Bedrock)

Typical 500-token response:
- **Single call:** ~500 tokens → $0.03
- **7 personas:** ~3,500 tokens → $0.21
- **Orchestration:** ~1,500 tokens → $0.09
- **Total:** ~$0.30 per question

**When 10x cost is worth it:**
- ✅ High-stakes decisions
- ✅ Strategic architecture choices
- ✅ Creative/analytical work where novelty matters
- ❌ Routine tasks
- ❌ High-volume production
- ❌ Fast iteration on narrow problems

## Interpreting Diversity Scores

### Diversity Score (0-1)
- **0.8+** - HIGH diversity: Substantively different reasoning and conclusions
- **0.5-0.8** - MEDIUM diversity: Different emphasis, some convergence
- **0.3-0.5** - LOW diversity: Similar substance, different phrasing
- **<0.3** - VERY LOW: Personas converging (may indicate single clear answer)

### Conclusion Agreement (0-1)
- **<0.4** - WEAK agreement: Personas recommend different approaches
- **0.4-0.7** - MODERATE agreement: Partial overlap in recommendations
- **>0.7** - STRONG agreement: Personas converge on same recommendation

**Note:** Low diversity isn't bad if the question has an objectively correct answer!

## Extending the System

### Add Your Own Persona

Create a new JSON file in `personas/`:

```json
{
  "name": "Your Persona Name",
  "id": "your_persona_id",
  "description": "Brief description of analytical approach",
  "system_prompt": "Detailed system prompt defining reasoning framework...",
  "temperature": 0.7,
  "reasoning_framework": "your_framework_name"
}
```

The runner automatically loads all personas from the directory.

### Use Different Models

Edit `runner.py` and `orchestrator.py`:

```python
# Change model_id in initialization
runner = PersonaRunner(
    model_id="us.anthropic.claude-opus-4-20250514-v1:0"  # Use Opus instead
)
```

### Create Custom Benchmarks

Add prompts to `benchmark/test_prompts.json`:

```json
{
  "id": "custom_001",
  "category": "your_category",
  "difficulty": "medium",
  "prompt": "Your test prompt here...",
  "expected_diversity": "high"
}
```

## Programmatic Usage

### Use as Python Library

```python
from runner import PersonaRunner
from orchestrator import Orchestrator
from diversity import measure_diversity

# Initialize
runner = PersonaRunner(mock_mode=True)
orchestrator = Orchestrator(mock_mode=True)

# Run personas
result = runner.run_ensemble_sync("Your question here")

# Measure diversity
metrics = measure_diversity(result['responses'])
print(f"Diversity score: {metrics.diversity_score:.3f}")

# Orchestrate
orchestration = orchestrator.orchestrate_all_strategies_sync(
    "Your question",
    result['responses']
)

# Access results
best_pick = orchestration['strategies']['pick_best']['final_output']
synthesis = orchestration['strategies']['synthesize']['final_output']
```

## Research Questions for Further Exploration

This implementation leaves several questions unanswered:

1. **Fine-tuned personas** - Would actually fine-tuning models for each framework produce stronger diversity?
2. **Temperature sensitivity** - How does temperature 0.0 vs 1.0 affect persona diversity?
3. **Multi-model ensembles** - Combine persona diversity WITH model diversity?
4. **Adaptive orchestration** - Can we learn which strategy works best for which question type?
5. **Persona collapse** - Do personas maintain their stances over multi-turn conversations?

If you explore these, please share your findings!

## Connection to CABAL Multi-Agent System

This experiment is inspired by (and validates) the CABAL architecture: a production multi-agent system using 7 specialized personas for different subtasks. Key differences:

- **CABAL:** Personas handle different tasks (research vs. architecture vs. strategy)
- **This experiment:** All personas answer the same question

Both are forms of ensembling. CABAL is closer to "stacking" (different models for different problems). This is closer to "bagging" (same model with different perspectives).

See `BLOG.md` for full analysis.

## Results Summary

From benchmark experiments:

- **Diversity is real** for open-ended questions (0.85+ scores)
- **Personas converge** on narrow technical questions with clear answers
- **Synthesize strategy** produced richest outputs 80% of the time
- **Pick-Best** was fastest and matched single-call 70% of the time
- **Debate** was most robust but 4x more expensive
- **Cost:** 5-10x more tokens than single call

**Practical recommendation:** Use for high-stakes, non-routine decisions where being wrong is expensive.

## Citation

If you use this work or build on it:

```
Ensemble Persona Orchestrator
"Same Model, Different Minds: Persona-Based LLM Ensembling"
protoGen Project 3: LLM Ensemble Methods
March 2026
```

## License

MIT License - use freely, attribute appropriately.

## Further Reading

- **BLOG.md** - Full 3,150-word write-up with findings and analysis
- **REQUIREMENTS.md** - Original project spec
- **RESEARCH.md** - Literature review and context
- **REVIEW.md** - Build self-assessment

## Questions / Issues

This is an experimental research project. If you discover interesting findings or extend the system, please document them!

---

*Built as part of the protoGen experimental series exploring practical LLM ensemble methods.*
