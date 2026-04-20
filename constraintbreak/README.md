# ConstraintBreak

**Test whether output constraints silently degrade LLM quality.**

Based on the research paper *"One Token Away from Collapse"* (arXiv 2604.13006), which discovered that common output constraints can cause up to 6.6× quality degradation that standard LLM-as-judge evaluation completely misses.

## Overview

ConstraintBreak is a Python CLI tool for testing how output constraints affect your LLM's quality. Many production systems ban certain words, formatting choices, or style elements, but these restrictions can secretly degrade output comprehensiveness and usefulness.

### Key Features

- **Pairwise Comparison Engine**: Uses position-bias-corrected pairwise judgment instead of standard LLM-as-judge
- **Two-Pass Recovery Testing**: Test if generating unconstrained then rewriting recovers quality
- **Built-in Constraints**: Ships with 6 common constraints (em dash ban, colon ban, bullet ban, etc.)
- **Multiple Providers**: OpenAI, Anthropic/Claude, AWS Bedrock, and mock mode for testing
- **Rich Reports**: Terminal heatmaps, markdown reports, and JSON export

## Installation

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. List Available Constraints

```bash
constraintbreak constraints
```

### 2. Run a Fragility Scan (Mock Mode)

```bash
constraintbreak scan --provider mock --model mock-model
```

### 3. Test Two-Pass Recovery

```bash
constraintbreak recover em_dash_ban --provider mock --model mock-model
```

## Usage

### Scan Command

Run a full constraint fragility scan against a model:

```bash
# With OpenAI
constraintbreak scan --provider openai --model gpt-4 --api-key YOUR_KEY

# With Anthropic
constraintbreak scan --provider anthropic --model claude-3-opus-20240229 --api-key YOUR_KEY

# Test specific constraint
constraintbreak scan --provider openai --model gpt-4 --constraint em_dash_ban

# Filter tasks by category
constraintbreak scan --provider openai --model gpt-4 --category writing

# Save report
constraintbreak scan --provider openai --model gpt-4 --output report.md
```

### Recover Command

Test two-pass recovery for a specific constraint:

```bash
constraintbreak recover em_dash_ban --provider openai --model gpt-4

# With custom tasks
constraintbreak recover colon_ban --provider openai --model gpt-4 --category coding
```

### Report Command

Generate a report from previous scan results:

```bash
constraintbreak report RUN_ID --output report.md
```

## How It Works

### Pairwise Comparison with Position Bias Correction

Standard LLM-as-judge evaluation asks "rate this response 1-10" which is biased and unreliable. ConstraintBreak uses pairwise comparison:

1. Generate unconstrained baseline response
2. Generate constrained response
3. Judge: "Which is more comprehensive?" (A vs B)
4. **Swap positions** and judge again (B vs A)
5. Aggregate results with position bias correction

This controls for position bias and gives reliable quality measurements.

### Two-Pass Recovery

If a constraint hurts quality, you might recover by:

1. Generate unconstrained first
2. Rewrite with constraint applied

ConstraintBreak tests this approach and tells you if it works for your constraint.

## Severity Levels

- 🟢 **None** (<5%): Constraint has minimal impact - safe to use
- 🟡 **Low** (5-15%): Minor degradation - consider two-pass approach
- 🟠 **Medium** (15-30%): Significant quality loss - use two-pass or reconsider
- 🔴 **High** (>30%): Severe degradation - strongly consider dropping constraint

## Custom Constraints

Create a custom `constraints.yaml`:

```yaml
constraints:
  - name: custom_ban
    description: "Ban custom word"
    instruction: "Never use the word 'synergy' in your response."
    tokens: ["synergy", " synergy"]
    logit_bias_value: -100.0
    category: vocabulary
```

Then use it:

```bash
constraintbreak scan --constraints custom_constraints.yaml
```

## Custom Tasks

Create a custom `tasks.yaml`:

```yaml
tasks:
  custom_category:
    - name: custom_task
      prompt: "Your custom prompt here"
      description: "Task description"
```

Then use it:

```bash
constraintbreak scan --tasks custom_tasks.yaml
```

## Architecture

```
constraintbreak/
├── cli.py              # Typer CLI interface
├── engine.py           # Pairwise comparison engine
├── recovery.py         # Two-pass recovery tester
├── storage.py          # SQLite results storage
├── report.py           # Rich heatmap + markdown + JSON
├── providers/          # LLM provider abstraction
│   ├── base.py
│   ├── openai.py
│   ├── anthropic.py
│   ├── bedrock.py
│   └── mock.py
├── constraints/        # Constraint definitions
│   ├── engine.py
│   ├── constraints.yaml
│   └── VOICE.md
└── tasks/              # Test task definitions
    ├── loader.py
    └── tasks.yaml
```

## Testing

Run the full test suite:

```bash
pytest
```

All tests use mock mode and require no API keys.

## Cost Estimation

For a full scan with 6 constraints × 12 tasks = 72 comparisons:
- Each comparison = 2 generations + 2 judgments = 4 API calls
- Total = 288 API calls
- Estimated cost with GPT-4: ~$5-15 depending on response length

Use `--constraint` and `--category` flags to reduce scope and cost.

## Citation

If you use ConstraintBreak in your research or development, please cite:

```
@article{constraintbreak2026,
  title={One Token Away from Collapse: How Output Constraints Degrade LLM Quality},
  author={[Paper Authors]},
  journal={arXiv preprint arXiv:2604.13006},
  year={2026}
}
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.

## Related Work

- MT-Bench: Task evaluation framework
- LLM-as-judge: Standard evaluation approach (which this tool improves upon)
- Pairwise comparison methods in AI evaluation

## Acknowledgments

Built for Protogenesis W17. Inspired by the arXiv 2604.13006 paper on constraint fragility in LLMs.
