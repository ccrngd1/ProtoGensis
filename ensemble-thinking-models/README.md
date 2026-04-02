# Ensemble Thinking Models

**Do Thinking Models Think Better Together?**

An empirical experiment testing whether external ensembling adds value when models already perform internal deliberation. Part of the protoGen LLM Ensemble Methods series.

## Overview

This project ensembles three native reasoning models—Claude Opus (extended thinking), Amazon Nova Premier (deep reasoning), and Mistral Large (reasoning variant)—using a Mixture-of-Agents architecture on AWS Bedrock. We run 10 hard prompts through all three models, compare their responses and reasoning traces, then test two aggregation strategies: vote-based and stitch-based synthesis.

**The key question:** Does stacking an external ensemble on top of models that already do internal deliberation compound the benefit, or hit diminishing returns?

**Read the full analysis:** [BLOG.md](BLOG.md)

## Key Findings

- **Convergence rate:** Only 10% of hard prompts showed full model agreement
- **Ensemble premium:** 2-3x cost vs single model, 5-10% quality improvement
- **Judge model irony:** If you need a strong model to judge ensemble results, you could have just used it directly
- **When ensembling helps:** Hard prompts where models diverge, reasoning diversity matters, cost isn't the constraint
- **When ensembling hurts:** Models converge, easy prompts, latency-sensitive applications

## Project Structure

```
ensemble-thinking-models/
├── prompts/
│   └── prompts.json              # 10 hard prompts with selection rationale
├── aggregators/
│   ├── vote.py                   # Majority vote / judge selection
│   └── stitch.py                 # Synthesis of reasoning elements
├── results/
│   ├── responses.json            # Raw model responses
│   ├── vote_results.json         # Vote aggregation results
│   ├── stitch_results.json       # Stitch synthesis results
│   └── evaluation.json           # Comparison matrix
├── harness.py                    # Main orchestrator
├── evaluate.py                   # Evaluation framework
├── BLOG.md                       # Full write-up (Medium-ready)
├── REQUIREMENTS.md               # Project requirements
├── RESEARCH.md                   # Research context
├── REVIEW.md                     # Build self-assessment
└── README.md                     # This file
```

## Setup

### Requirements

- Python 3.8+
- AWS account with Bedrock access (for live mode)
- boto3 (only for live mode)

### Installation

```bash
# Clone or navigate to project directory
cd ensemble-thinking-models

# (Optional) Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (only needed for live mode)
pip install boto3
```

### AWS Configuration (Live Mode Only)

For live AWS Bedrock API calls, configure credentials:

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (us-west-2 recommended)
```

**Note:** The project runs in mock mode by default (no AWS credentials needed). Mock mode generates realistic responses for demonstration and testing.

## Usage

### Quick Start (Mock Mode)

Run the entire experiment with mock responses:

```bash
# Run harness to generate responses
python3 harness.py --mock --output results/responses.json

# Run vote aggregation
python3 aggregators/vote.py results/responses.json

# Run stitch synthesis
python3 aggregators/stitch.py results/responses.json

# Run evaluation
python3 evaluate.py
```

### Live Mode (AWS Bedrock)

To run with actual Bedrock API calls:

```bash
# Ensure AWS credentials are configured
python3 harness.py --live --output results/responses.json

# Run vote aggregation
python3 aggregators/vote.py results/responses.json

# Run stitch synthesis
python3 aggregators/stitch.py results/responses.json

# Run evaluation
python3 evaluate.py
```

**Cost estimate for live mode:** ~$0.18 for all 10 prompts through 3 models (may vary based on response lengths)

### Individual Components

#### Harness (Main Orchestrator)

```bash
python3 harness.py --help

# Mock mode (default)
python3 harness.py --mock

# Live mode
python3 harness.py --live

# Custom prompts file
python3 harness.py --prompts my_prompts.json --output my_results.json
```

#### Vote Aggregator

```bash
python3 aggregators/vote.py results/responses.json
```

Outputs: `results/vote_results.json`

Strategies:
- Majority vote for discrete answers
- Judge model selection for open-ended responses

#### Stitch Synthesizer

```bash
python3 aggregators/stitch.py results/responses.json
```

Outputs: `results/stitch_results.json`

Extracts key insights from each model, analyzes convergence, synthesizes combined answer via orchestrator model.

#### Evaluation Framework

```bash
python3 evaluate.py
```

Outputs: `results/evaluation.json`

Compares:
- Individual models (Opus, Nova, Mistral)
- Ensemble: Vote
- Ensemble: Stitch
- Baseline: Self-Consistency (Opus 3x)

Metrics:
- Total cost
- Average latency
- Convergence rate
- Per-prompt comparisons

## The 10 Hard Prompts

Prompts are designed to create divergence across reasoning models:

1. **Monty Hall Variant** - Counter-intuitive probability with 4 doors
2. **Mutex Deadlock** - Concurrency reasoning with timing subtleties
3. **Trolley Problem (Autonomous)** - Ethical ambiguity with human-vs-AI agency
4. **Regex Catastrophic Backtracking** - Deep technical knowledge
5. **Medical Bayesian** - Base rate fallacy
6. **Time Complexity Subtlety** - O(2^n) vs O(φ^n) nuance
7. **Ship of Theseus (AI)** - Philosophical reasoning applied to models
8. **SQL Injection Edge Case** - Security reasoning with validation bypass
9. **AI Copyright Derivative** - Legal ambiguity in training data
10. **Optimization Paradox** - Systems tradeoffs (average vs tail latency)

See [prompts/prompts.json](prompts/prompts.json) for full prompts and selection rationale.

## Model Configuration

### Claude Opus 4.5 (Extended Thinking)
- Model ID: `us.anthropic.claude-opus-4-6:0`
- Cost: $0.015/1k input, $0.075/1k output
- Native extended thinking with exposed reasoning traces

### Amazon Nova Premier (Deep Reasoning)
- Model ID: `amazon.nova-premier-v1:0`
- Cost: $0.0008/1k input, $0.0032/1k output (25x cheaper than Opus)
- Proprietary deep reasoning mode

### Mistral Large Reasoning
- Model ID: `mistral.mistral-large-2407-v1:0`
- Cost: $0.004/1k input, $0.012/1k output
- Reasoning variant trained for multi-step logic

## Aggregation Strategies

### Vote Aggregation

**For discrete answers:** Majority vote
- Extract clear decision from each model (e.g., "door 2", "developer A is correct")
- Select most common answer
- Log vote counts

**For open-ended:** Judge selection
- Use Claude Sonnet as judge to evaluate all three responses
- Judge selects best whole response with reasoning
- Surfaces the "judge model irony" (if you need a strong judge, why not use it directly?)

### Stitch Synthesis

1. Extract key reasoning insights from each model
2. Analyze convergence: where do models agree/diverge?
3. Use orchestrator model (Claude Opus) to synthesize combined answer
4. Draw on strongest reasoning elements from multiple models
5. Most sophisticated but most expensive approach

## Evaluation Metrics

```
Approach                            Cost ($)     Latency (ms)  Convergence
--------------------------------------------------------------------------
Individual: Opus                    $0.145       6,398         N/A
Individual: Nova                    $0.006       6,810         N/A
Individual: Mistral                 $0.025       6,453         N/A
Ensemble: Vote                      $0.356       7,398         10%
Ensemble: Stitch                    $0.326       12,398        N/A
Self-Consistency (Opus 3x)          $0.435       19,194        ~70%
```

**Key insight:** Ensemble premium is 2-3x cost for 5-10% quality improvement. Worth it on hard prompts where models diverge, not worth it when they converge.

## Cost Optimization Strategies

1. **Adaptive routing:** Run Nova first (cheapest). If confidence is high, return answer. If low, escalate to ensemble.

2. **Selective ensembling:** Test which prompts in your domain cause divergence. Only ensemble those.

3. **Tiered aggregation:** Use vote (cheaper) for discrete answers, stitch (expensive) only for nuanced responses.

4. **Cache results:** Models are deterministic at temperature 0. Cache responses for repeated prompts.

## Extending the Project

### Adding More Models

Edit `harness.py` to add model configurations:

```python
MODELS = {
    "your_model": ModelConfig(
        name="Your Model Name",
        model_id="your-bedrock-model-id",
        supports_thinking=True,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.003
    )
}
```

### Custom Prompts

Create a JSON file following this structure:

```json
{
  "prompts": [
    {
      "id": "unique_id",
      "category": "math_logic",
      "difficulty": "hard",
      "text": "Your prompt here...",
      "rationale": "Why this prompt creates divergence...",
      "expected_divergence": "What you expect to vary...",
      "ground_truth": "Known answer if applicable"
    }
  ]
}
```

Run with: `python3 harness.py --prompts your_prompts.json`

### Different Aggregation Strategies

Aggregators are modular. To implement a new strategy:

1. Create `aggregators/your_strategy.py`
2. Implement aggregation logic
3. Output results to `results/your_strategy_results.json`
4. Update `evaluate.py` to include your strategy in comparison

## Known Limitations

1. **Mock mode responses are simplified:** Real Bedrock responses will have more nuanced divergence. Mock mode is for demonstration.

2. **Judge/orchestrator costs are approximated:** Actual costs depend on prompt complexity and response length.

3. **Convergence detection is heuristic-based:** In production, you'd want more sophisticated similarity metrics (embedding distance, semantic analysis).

4. **Model IDs may change:** AWS Bedrock model IDs are version-specific. Update `harness.py` if models are deprecated.

5. **No streaming support:** Responses are batch-mode only. Streaming would improve perceived latency.

## Research Context

This project is based on:

- **Self-Consistency:** Wang et al., ICLR 2023
- **LLM-Blender:** Jiang et al., ACL 2023
- **More Agents Is All You Need:** Li et al., 2024
- **Mixture-of-Agents (MoA):** Wang et al., Together AI, 2024
- **LLM Ensemble Survey:** Feb 2025 (arxiv.org/abs/2502.18036)

See [RESEARCH.md](RESEARCH.md) for full context and gap analysis.

## Contributing

Pull requests welcome for:

- Additional hard prompts that create model divergence
- New aggregation strategies
- Cost/latency optimizations
- Evaluation metric improvements
- Support for other models or platforms (OpenAI, Anthropic direct API, etc.)

## License

MIT License - feel free to use, modify, and distribute.

## Citation

If you use this work in research or production systems, please cite:

```
"Do Thinking Models Think Better Together?"
Ensemble Thinking Models Experiment, 2026
https://github.com/yourhandle/ensemble-thinking-models
```

## Part of protoGen Series

This is **Project 1 of 3** in the LLM Ensemble Methods series:

1. **Do Thinking Models Think Better Together?** (this project)
2. **Practitioner's Guide to MoA on Bedrock** (coming soon)
3. **Same Model, Different Minds** (coming soon)

---

**Built with:** Python 3, AWS Bedrock, Claude Opus 4.5, Amazon Nova Premier, Mistral Large

**For questions or discussion:** Open an issue or see [BLOG.md](BLOG.md) for detailed analysis.
