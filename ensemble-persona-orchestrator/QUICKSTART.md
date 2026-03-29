# Quick Start Guide

Get up and running with the Ensemble Persona Orchestrator in 2 minutes.

## Install (Optional)

```bash
# Only needed for live Bedrock mode
pip install boto3

# For mock mode (testing), no installation needed!
```

## Run Your First Experiment

```bash
# Interactive mode - you'll be prompted for a question
python3 experiment.py

# Or provide a prompt directly
python3 experiment.py --prompt "Should we build in-house or use a SaaS solution?"
```

Output shows:
1. All 7 persona responses running in parallel
2. Diversity analysis (how different are the responses?)
3. 3 orchestration strategies side-by-side
4. Results saved to JSON

## Try the Examples

### Example 1: Business Decision

```bash
python3 experiment.py --prompt "Our conversion rate is 0.5%. Focus on converting existing users or acquiring more?" --output results/conversion_strategy.json
```

### Example 2: Technical Architecture

```bash
python3 experiment.py --prompt "Database scaling: caching, query optimization, sharding, or NoSQL?" --output results/scaling_decision.json
```

### Example 3: Creative Problem

```bash
python3 experiment.py --prompt "How can a fitness app differentiate in a saturated market?" --output results/differentiation.json
```

## Run Benchmark Suite

Test all 12 pre-built prompts across 6 categories:

```bash
python3 experiment.py --benchmark
```

This generates:
- Individual results for each prompt in `results/benchmark_*.json`
- Summary comparison in `results/benchmark_summary.json`

## Understand the Output

### Console Output

```
DIVERSITY ANALYSIS
==================
**Overall Diversity: HIGH** (score: 0.95)
**Conclusion Agreement: WEAK** (0.29)

Interpretation:
- Personas producing substantively different responses
- Personas disagree on recommendations
```

**High diversity + Low agreement = Genuinely different perspectives**

### Orchestration Strategies

1. **Pick-Best** - Judge selects strongest single response (fastest)
2. **Synthesize** - Combines best elements from all (richest)
3. **Debate** - Simulates one round of critique-and-response (most robust)

Compare all three to see which works best for your question type.

## View Results

Results are saved as JSON:

```bash
# Pretty-print a result file
python3 -m json.tool results/example_auth_decision.json | less

# Or use jq if installed
jq '.diversity_metrics' results/example_auth_decision.json
```

## Use as Python Library

```python
from runner import PersonaRunner
from orchestrator import Orchestrator
from diversity import measure_diversity

# Run personas
runner = PersonaRunner(mock_mode=True)
result = runner.run_ensemble_sync("Your question here")

# Measure diversity
metrics = measure_diversity(result['responses'])
print(f"Diversity: {metrics.diversity_score:.2f}")

# Orchestrate
orchestrator = Orchestrator(mock_mode=True)
final = orchestrator.strategy_synthesize(
    "Your question",
    result['responses']
)
print(final.final_output)
```

## Test Individual Components

```bash
# Test just the runner
python3 runner.py

# Test just the orchestrator
python3 orchestrator.py

# Test just diversity measurement
python3 diversity.py
```

Each module has a `main()` function with a demo.

## Common Issues

**"python: command not found"**
→ Use `python3` instead of `python`

**"No module named 'boto3'"**
→ System is automatically using mock mode (this is fine for testing!)
→ To use live Bedrock: `pip install boto3` and configure AWS credentials

**"Persona files not found"**
→ Make sure you're running from the project root directory

## Next Steps

1. Read **README.md** for comprehensive documentation
2. Read **BLOG.md** for the full write-up and findings
3. Explore **personas/** to understand the reasoning frameworks
4. Check **benchmark/** for example prompts
5. Modify **personas/** to create your own analytical lenses

## Live Mode (AWS Bedrock)

To use real Claude Sonnet instead of mock responses:

```bash
# Configure AWS credentials
export AWS_PROFILE=your-profile

# Run with --live flag
python3 experiment.py --live --prompt "Your question"
```

**Note:** Live mode costs ~$0.30 per question (7 personas + orchestration).

## Questions?

- Check **README.md** for detailed usage
- Check **REVIEW.md** for known limitations
- File issues or questions on GitHub

---

**You're ready to go! Start with a question that genuinely has multiple valid approaches and see if the personas produce meaningfully different perspectives.**
