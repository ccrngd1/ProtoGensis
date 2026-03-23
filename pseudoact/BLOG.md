# Stop Using Your Expensive Model for Every Step

*PseudoAct separates planning from execution so you only pay for big thinking once.*

---

## The Token Problem Nobody Wants to Do Math On

Here's how a standard ReAct agent works. You give it a task. It thinks. It calls a tool. It thinks again. It calls another tool. It thinks again.

Every "thinks" step hits your expensive model. Sonnet. Opus. Whatever you're running. And the thinking isn't all equally valuable. Some of it is strategy. But a lot of it is just: "Okay, I called the search tool and got a result. Now I'll call the summarize tool."

That second kind of thinking doesn't need Sonnet. It needs a model that can read a variable and call a function. That's Haiku territory.

PseudoAct, based on [arXiv:2602.23668](https://arxiv.org/abs/2602.23668) from Wen and Chen at Texas A&M, makes a simple observation: split the work. Let the expensive model do the planning once. Let the cheap model handle the execution steps.

The result is a two-phase agent that generates a pseudocode plan upfront, then walks through it node by node.

## The Two Phases

**Phase 1: Plan Synthesis.** Claude Sonnet 4.6 takes your query and the available tools, then generates a Python-like pseudocode plan with full control flow. If/else branches. Bounded loops. Variable assignments. The whole structure of what the agent is going to do.

**Phase 2: Control-Flow Execution.** Python's `ast` module parses that pseudocode into an AST. A custom executor walks the tree node by node, using Haiku 4.5 for individual decisions like condition evaluation.

Sonnet thinks once. Haiku executes many times.

Here's what a generated plan looks like for a search-and-summarize task:

```python
# Step 1: Search for relevant results
data = search(query="Python programming")

# Step 2: Gather facts iteratively
results = []
for i in range(max_iterations=3):
    item = get_fact(topic=data, aspect="feature")
    results = results + [item]

# Step 3: Conditional summary
if len(results) > 0:
    answer = summarize(results)
else:
    answer = "No results found"
```

That plan gets saved to disk for inspection. Then the executor picks it up and runs it step by step.

## Why This Works: AST Parsing Is Free

The elegant part of this approach is that Claude naturally writes Python-like syntax. The researchers didn't need to invent a custom grammar or build a DSL parser. Python's built-in `ast` module handles the heavy lifting.

```python
import ast

# Parse pseudocode Claude generated
tree = ast.parse(pseudocode)

# Walk the AST nodes
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        # Handle variable assignment
        ...
    elif isinstance(node, ast.For):
        # Handle bounded loop
        ...
    elif isinstance(node, ast.If):
        # Handle conditional
        ...
```

The framework converts AST nodes into its own execution nodes (AssignNode, ToolCallNode, ConditionalNode, LoopNode), maintains a shared variable context, and executes each one in sequence.

All loops require a `max_iterations` parameter. No infinite loops. That's a hard safety guarantee baked into the architecture.

## The Architecture in Code

The public API is intentionally simple:

```python
from pseudoact import run_pseudoact, run_react

# Two-phase PseudoAct approach
result = run_pseudoact("Calculate (15 + 7) * 3 and take the square root")
print(f"Result: {result['result']}")
print(f"Tokens: {result['usage']['total_input']} in, {result['usage']['total_output']} out")

# Traditional ReAct baseline for comparison
result = run_react("Calculate (15 + 7) * 3 and take the square root")
print(f"Result: {result['result']}")
print(f"Iterations: {result['iterations']}")
```

Under the hood, three components do the work:

```python
from pseudoact import PlanSynthesizer, PseudocodeParser, PlanExecutor
from pseudoact.tools import ToolRegistry

# Phase 1: Sonnet generates the plan
synthesizer = PlanSynthesizer()
plan_result = synthesizer.synthesize_plan(
    query="Search for Python features and summarize",
    tools=registry.get_tool_descriptions()
)

# Phase 2a: Parse pseudocode into AST nodes
parser = PseudocodeParser()
nodes = parser.parse(plan_result["plan"])

# Phase 2b: Execute with Haiku
executor = PlanExecutor(registry)
result = executor.execute_plan(nodes)
```

The separation is clean. Synthesizer handles Sonnet. Parser is pure Python. Executor handles Haiku. Each component is independently testable with mocked Bedrock calls.

The project ships with three built-in tools (Calculator, Search, GetFact), a ReAct baseline for head-to-head comparison, and a benchmark script that measures token usage, execution time, and success rate across six tasks.

## The Review: 55/55, But Read the Fine Print

The test suite is comprehensive: 55 tests covering parser, executor, synthesizer, and tools. All pass in under a second. The code review gave it a B- overall (74/100), which is an honest grade for a research prototype.

The architecture is clean. The separation of concerns is well-executed. The tool registry is pluggable. Dependency injection makes mocking straightforward.

But the reviewer found several critical bugs worth knowing about before you run this in production. Spoiler: don't run this in production yet.

**The `eval()` issue.** The CalculatorTool uses Python's `eval()` for expression evaluation. The builtins are restricted, but restricted `eval()` is still an attack surface. The fix is straightforward: swap in `simpleeval` or `asteval`. Thirty minutes of work.

**Variable substitution corruption.** The executor resolves variable references using naive string replacement. If your context contains a variable named `i` with value `0`, and you have a string like `"items"` anywhere in your plan, the substitution corrupts it to `"0tems"`. Single-letter loop variables are the usual culprit. The fix is regex with word boundaries instead of `str.replace()`.

**While loops don't work.** The `_extract_max_iterations()` function always returns `None` for while loops, which immediately triggers an error. The feature is documented but not functional in v0.1. Work around it by using bounded `for` loops.

**Method calls fail to parse.** The system prompt and README examples show `list.append()`, but the parser raises `ValueError: Only simple function calls supported` for method calls. Use list concatenation instead: `results = results + [item]`.

These are real bugs. They're also fixable bugs. For a research prototype exploring a novel architecture, this is normal territory. The bones are good.

## The Interesting Insight

The deeper idea here is about *amortization*.

In a traditional ReAct loop, you pay for reasoning at every step. The model has to figure out where it is, what it's done, and what to do next. That reasoning gets repeated and rebuilt with every iteration.

PseudoAct front-loads that reasoning. Sonnet does one expensive planning pass, encodes the strategy as structured code, and then Haiku just executes the instructions. No repeated context rebuilding. No strategic re-evaluation at each step.

The efficiency argument is strongest for tasks with predictable structure: multi-step data gathering, iterative processing with known bounds, conditional branching on tool results. Tasks where you can reason about the structure upfront.

It's weaker for dynamic tasks where the plan needs to adapt mid-execution. V1 doesn't support dynamic replanning. If the plan is wrong, the whole execution fails. That's a deliberate scope limitation the authors acknowledge.

## What's Next

A few obvious places to take this:

**Dynamic replanning.** On tool failure or unexpected results, trigger a re-synthesis. Let the plan adapt. This is the biggest missing capability.

**Native condition evaluation.** Right now, even simple conditions like `x > 5` get sent to Haiku for evaluation. That's wasteful. Try `eval()` with a safe context first, fall back to LLM only for semantic conditions.

**Parallel execution.** Independent nodes in the plan could run concurrently. The AST structure makes dependency analysis possible. V1 serializes everything.

**Token efficiency validation.** The ≥30% savings claim is theoretical. Running the benchmark against real Bedrock across a large task set would validate (or complicate) the hypothesis.

## Try It

The project runs with Python 3.11+ and AWS Bedrock credentials for Sonnet 4.6 and Haiku 4.5.

```bash
git clone <repo>
cd pseudoact
./run.sh          # Sets up venv, installs deps, runs demo
```

Or run the comparison benchmark directly:

```bash
python benchmark.py
# Outputs JSON with token usage, execution time, success rate
# PseudoAct vs ReAct across 6 tasks
```

The architecture is worth exploring even with the known bugs. The planning/execution split is a genuinely useful primitive. Using Python's AST as a free pseudocode parser is clever. And the test suite gives you a solid foundation to build fixes on top of.

The bugs are real. The idea is better.

---

*Built during Protogenesis Week 10. PseudoAct implements the approach from "Leveraging Pseudocode Synthesis for Flexible Planning and Action Control in Large Language Model Agents" (Wen & Chen, Texas A&M, arXiv:2602.23668, Feb 2026).*
