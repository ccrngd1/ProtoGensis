# PseudoAct - Pseudocode Planning for LLM Agents

> **TL;DR:** PseudoAct cuts AI agent costs by having an expensive model write a plan once and a cheap model carry it out — instead of running the expensive model at every single step.

## Why This Exists

AI agents that use powerful models are expensive because those models think through every action at full cost, even for simple mechanical steps like "call this tool with this result." Most of that spending is waste — you don't need a genius to follow instructions, only to write them.

## What It Does

PseudoAct splits agent work into two phases: a capable model (Sonnet) writes a structured pseudocode plan with conditionals and loops, and then a smaller, cheaper model (Haiku) executes that plan step by step. The plan is real Python-like code parsed with Python's built-in AST module, so execution is deterministic and safe.

## Why It Matters

Same quality output as running a powerful model end-to-end — at a fraction of the cost. Plan once with the expensive model, execute many times with the cheap one.

---

> **Protogenesis W10** | **Based on:** [arXiv:2602.23668](https://arxiv.org/abs/2602.23668) — *"Leveraging Pseudocode Synthesis for Flexible Planning and Action Control in Large Language Model Agents"* (Wen & Chen, Texas A&M, Feb 2026)

A two-phase agent execution framework that separates planning from execution.

## Overview

PseudoAct is a framework that improves LLM agent efficiency by separating the planning phase from the execution phase:

- **Phase 1: Plan Synthesis** - Uses Sonnet 4.6 to generate a structured pseudocode plan with control flow (if/else, loops)
- **Phase 2: Control-Flow Execution** - Parses the pseudocode into an AST and executes it step-by-step using Haiku 4.5
- **ReAct Baseline** - Traditional ReAct (Reasoning + Acting) implementation for comparison

## Key Features

- **Structured Planning**: Generate Python-like pseudocode with control flow (conditionals, bounded loops)
- **AST-based Execution**: Parse and execute plans with full variable context sharing
- **Bounded Loops**: All loops require `max_iterations` parameter (safety guarantee)
- **Token Efficiency**: Separate cheap planning (Sonnet) from repeated execution (Haiku)
- **Plan Persistence**: Save generated plans to disk for inspection
- **Comprehensive Testing**: Full test suite with mocked Bedrock calls

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PseudoAct Framework                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Phase 1: Plan Synthesis (Sonnet 4.6)                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Query + Tools → Generate Pseudocode Plan           │    │
│  │ - Control flow (if/else, loops)                    │    │
│  │ - Variable assignments                              │    │
│  │ - Tool calls                                        │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  Phase 2: Parse & Execute (Haiku 4.5)                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Parse Pseudocode → AST → Execute with Context      │    │
│  │ - Walk AST nodes                                    │    │
│  │ - Maintain variable context                         │    │
│  │ - Execute tools                                     │    │
│  │ - Enforce loop bounds                               │    │
│  └────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Installation

It's recommended to use a virtual environment:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

**Quick Setup:**

For a one-command setup and demo, use the provided script:

```bash
./run.sh
```

This script will:
1. Create a virtual environment (if not exists)
2. Install dependencies
3. Run the demo

**Requirements:**
- Python 3.11+
- boto3 (for AWS Bedrock)
- AWS credentials configured for Bedrock access

## Usage

### Quick Start

```python
from pseudoact import run_pseudoact, run_react

# Run with PseudoAct approach
result = run_pseudoact("Calculate (15 + 7) * 3 and take the square root")
print(f"Result: {result['result']}")
print(f"Token usage: {result['usage']['total_input']} input, {result['usage']['total_output']} output")

# Run with ReAct baseline
result = run_react("Calculate (15 + 7) * 3 and take the square root")
print(f"Result: {result['result']}")
print(f"Iterations: {result['iterations']}")
```

### Custom Tools

```python
from pseudoact import PlanSynthesizer, PseudocodeParser, PlanExecutor
from pseudoact.tools import ToolRegistry, Tool

# Define a custom tool
class MyCustomTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Does something custom",
            parameters={"type": "object", "properties": {...}}
        )

    def execute(self, **kwargs):
        # Your implementation
        return "result"

# Create registry and add tools
registry = ToolRegistry()
registry.register(MyCustomTool())

# Use in PseudoAct
synthesizer = PlanSynthesizer()
plan_result = synthesizer.synthesize_plan(
    query="Your query here",
    tools=registry.get_tool_descriptions()
)

parser = PseudocodeParser()
nodes = parser.parse(plan_result["plan"])

executor = PlanExecutor(registry)
result = executor.execute_plan(nodes)
```

## Running the Demo

```bash
python demo/run_demo.py
```

This runs three example tasks comparing PseudoAct and ReAct approaches:
1. Calculator task (simple arithmetic)
2. Search task (information gathering)
3. Conditional task (control flow)

## Running the Benchmark

```bash
python benchmark.py
```

Runs 6 tasks comparing PseudoAct vs ReAct on:
- Token usage
- Execution time
- Success rate
- Iterations (ReAct)

Results are saved to `benchmark_results.json`.

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_parser.py

# Run with coverage
python -m pytest tests/ --cov=pseudoact
```

## Project Structure

```
pseudoact/
├── pseudoact/           # Main package
│   ├── __init__.py      # Public API
│   ├── synthesizer.py   # Plan synthesis (Sonnet 4.6)
│   ├── parser.py        # Pseudocode AST parser
│   ├── executor.py      # Control-flow executor (Haiku 4.5)
│   ├── react.py         # ReAct baseline
│   ├── tools.py         # Tool definitions
│   ├── context.py       # Execution context
│   └── utils.py         # Bedrock utilities
├── demo/
│   └── run_demo.py      # Demo script
├── tests/               # Test suite
│   ├── test_parser.py
│   ├── test_executor.py
│   ├── test_synthesizer.py
│   └── test_tools.py
├── benchmark.py         # Benchmark script
├── requirements.txt     # Dependencies
└── README.md           # This file
```

## Key Design Decisions

1. **Sonnet for Planning, Haiku for Execution**: Leverage Sonnet's superior reasoning for plan generation, then use efficient Haiku for step execution.

2. **Python-like Pseudocode**: Claude naturally generates Python syntax, making it easy to parse with Python's `ast` module.

3. **Bounded Loops Mandatory**: Every loop must specify `max_iterations` to prevent infinite loops.

4. **Plans Saved to Disk**: Generated plans are saved for inspection and debugging.

5. **No Auto-replanning**: V1 executes the initial plan without dynamic replanning (future enhancement).

6. **Serialized Parallel Blocks**: V1 serializes parallel operations (future enhancement for true parallelism).

## AWS Bedrock Configuration

**Models Used:**
- Sonnet 4.6: `us.anthropic.claude-sonnet-4-6-20251001-v2:0`
- Haiku 4.5: `us.anthropic.claude-haiku-4-5-20251001-v1:0`

**Region:** us-east-1

**API Version:** bedrock-2023-05-31

## Example Pseudocode Plan

```python
# Step 1: Get initial data
data = search(query="Python programming")

# Step 2: Process with iteration
results = []
for i in range(max_iterations=3):
    item = get_fact(topic=data, aspect="feature")
    results = results + [item]

# Step 3: Conditional logic
if len(results) > 0:
    answer = summarize(results)
else:
    answer = "No results found"
```

**Note:** Method calls like `list.append()` are not supported in v0.1. Use list concatenation (`results = results + [item]`) instead.

## Token Efficiency Comparison

PseudoAct aims to reduce token usage by:
- One-time planning phase (Sonnet)
- Cheap step execution (Haiku)
- No repeated reasoning in execution phase

ReAct baseline:
- Full reasoning at each step (Sonnet)
- Iterative think-act-observe cycles
- Higher token usage per task

Run the benchmark to see actual comparison metrics.

## Limitations (V1)

- No dynamic replanning during execution
- Parallel blocks are serialized
- Limited to built-in tool types
- Condition evaluation uses LLM (could be optimized)

## Future Enhancements

- Dynamic replanning on failures
- True parallel execution of independent steps
- More sophisticated tool calling patterns
- Optimized condition evaluation
- Plan validation and safety checks

## License

MIT License - See LICENSE file for details.

## Citation

```
PseudoAct - Pseudocode Planning for LLM Agents
Protogenesis W10
```

## Contributing

This is a research prototype. Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Troubleshooting

**AWS Credentials**: Ensure your AWS credentials are configured:
```bash
aws configure
```

**Bedrock Access**: Verify you have access to Claude models in us-east-1:
```bash
aws bedrock list-foundation-models --region us-east-1
```

**Import Errors**: Make sure you're running from the project root:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Contact

For questions or issues, please open a GitHub issue.
