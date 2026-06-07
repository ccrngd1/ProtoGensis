# Testing Multi-Agent AI Systems: The Hidden Contradiction Problem

## Why Your Multi-Agent Pipeline Might Be Lying to You (And How to Find Out)

Multi-agent AI systems are everywhere. You chain together a summarizer, fact-checker, and critic. You compose Claude with GPT-4 and Gemini. You build agentic workflows where specialized models collaborate. The output looks polished. The metrics look good.

But here's the problem: **33-94% of multi-agent compositions contain hidden contradictions.**

Not hallucinations. Not factual errors you can check against ground truth. *Logical contradictions between the agents themselves.*

Agent A says the server runs on port 8080. Agent B says it runs on port 3000. Both sound confident. Both are hallucinating, but in different directions. Your pipeline just told your users two incompatible truths.

This is the multi-agent coherence problem, and until now, you probably weren't testing for it.

---

## The Ground Truth Trap

Traditional AI testing assumes you have ground truth:
- Does the summary match the original text?
- Is the translation accurate?
- Did the model predict the correct label?

But multi-agent systems operate differently. You're not testing *correctness* — you're testing *consistency*. When you ask three agents to analyze a codebase, you don't have a golden answer. You just need to know if they agree with each other.

The question isn't "Is Agent A right?" It's "Do Agent A and Agent B contradict each other?"

This is where traditional testing breaks down. You need a different approach.

---

## Enter CoherenceProbe

CoherenceProbe is a Python package and CLI that answers one question:

**"Given N outputs from N agents, are they mutually consistent?"**

No ground truth required. No manual review. Just automated contradiction detection across your entire multi-agent pipeline.

### Quick Example

```python
from coherenceprobe import check, LogCapture

# Capture your agent outputs
capture = LogCapture()
capture.capture("summarizer", "article", "The study found positive results...")
capture.capture("critic", "article", "The study found negative results...")

# Check coherence
report = check(capture.get_outputs())

print(f"Coherence score: {report.score}")
# Output: 0.23 ❌

print(f"Contradictions found: {len(report.contradictions)}")
# Output: 1

print(report.contradictions[0].explanation)
# Output: "Agent 'summarizer' claims positive results while 'critic' claims negative results"
```

The package caught the contradiction automatically. No ground truth needed.

---

## How It Works: The Three-Stage Pipeline

### Stage 1: Claim Extraction

First, we extract *atomic factual claims* from each agent's output.

**LLM Mode** (default):
```python
# Uses litellm to extract claims via LLM
"The server runs on port 8080 and handles 1000 requests per second."
→ [
    "The server runs on port 8080",
    "The server handles 1000 requests per second"
  ]
```

**Local Mode** (no API calls):
```python
# Uses spaCy for sentence splitting + heuristic filtering
# Filters questions, uncertainty markers, etc.
config = CoherenceConfig(local=True)
```

Claims are normalized: lowercase, hedging removed ("might", "possibly"), punctuation stripped.

### Stage 2: Contradiction Detection

Here's where the magic happens.

1. **Embed claims** using sentence-transformers (all-MiniLM-L6-v2)
2. **Cluster by topic** — group semantically similar claims (cosine similarity ≥ 0.6)
3. **Run pairwise NLI** within clusters using cross-encoder/nli-deberta-v3-large
4. **Only compare cross-agent** — same agent's claims aren't checked against each other

The NLI (Natural Language Inference) model gives us three scores:
- CONTRADICTION
- ENTAILMENT
- NEUTRAL

If `CONTRADICTION ≥ threshold` (default 0.7), we flag it.

### Stage 3: Scoring

We compute an overall coherence score:

```python
coherence_score = 1.0 - (weighted_contradictions / total_claim_pairs)
```

- **1.0** = Perfect coherence (no contradictions)
- **0.0** = Maximum incoherence

We also compute **per-agent scores** showing which agents contribute most to incoherence:

```python
{
  "summarizer": 0.05,  # Mostly coherent
  "critic": 0.42,      # Highly problematic
  "fact_checker": 0.08
}
```

Now you know exactly which agent to investigate.

---

## Contradiction Types

CoherenceProbe classifies contradictions into three types:

### 1. Logical Contradictions
Direct negation:
- Agent A: "The system is operational"
- Agent B: "The system is not operational"

### 2. Factual Contradictions
Different values for the same attribute:
- Agent A: "The server runs on port 8080"
- Agent B: "The server runs on port 3000"

### 3. Temporal Contradictions
Incompatible timeline assumptions:
- Agent A: "The event occurred before the update"
- Agent B: "The event occurred after the update"

---

## Real-World Use Cases

### 1. Code Analysis Pipelines

You have three agents analyzing a codebase:
- SecurityAgent: "No SQL injection vulnerabilities found"
- CodeReviewAgent: "Line 47 contains a SQL injection vulnerability"

CoherenceProbe catches this instantly. You don't need ground truth — you just need to know your agents disagree.

### 2. Research Paper Summarization

Multiple LLMs summarize the same paper:
- Agent A: "The study found a 20% improvement"
- Agent B: "The study found a 50% improvement"

Which one is hallucinating? You might not have time to read the paper. But you *can* detect that they contradict each other.

### 3. Multi-Agent RAG Systems

Your RAG pipeline uses multiple retrieval strategies:
- VectorAgent: "The company was founded in 2019"
- HybridAgent: "The company was founded in 2021"

Even if both chunks came from your database, the agents are giving conflicting information. CoherenceProbe flags it.

### 4. Agentic Workflows

CrewAI, AutoGPT, BabyAGI — any framework where agents collaborate:
```python
from coherenceprobe import DecoratorCapture, check

capture = DecoratorCapture()

@capture.agent("planner")
def plan_task(goal): ...

@capture.agent("executor")
def execute_task(plan): ...

@capture.agent("critic")
def review_execution(result): ...

# Run your workflow
result = workflow.run()

# Check coherence
report = check(capture.get_outputs())
```

Automatic coherence testing for your entire agent swarm.

---

## Command-Line Usage

For CI/CD pipelines and quick checks:

```bash
# Check coherence from JSONL file
coherenceprobe check outputs.jsonl

# Generate HTML report
coherenceprobe check outputs.jsonl --format html --output report.html

# Local mode (no API calls)
coherenceprobe check outputs.jsonl --local

# Verbose output with statistics
coherenceprobe check outputs.jsonl --verbose

# Custom NLI threshold
coherenceprobe check outputs.jsonl --threshold 0.5
```

Input format:
```jsonl
{"agent": "summarizer", "timestamp": "2026-06-07T10:00:00Z", "input": "...", "output": "..."}
{"agent": "critic", "timestamp": "2026-06-07T10:00:05Z", "input": "...", "output": "..."}
```

Or use a directory where each file = one agent's output:
```bash
coherenceprobe check outputs_dir/
```

---

## Integration Examples

### Pytest Integration

```python
import pytest
from coherenceprobe import check

def test_agent_coherence(agent_outputs):
    """Test that multi-agent pipeline produces coherent outputs."""
    report = check(agent_outputs)

    assert report.score >= 0.8, f"Coherence too low: {report.score}"
    assert len(report.contradictions) == 0, \
        f"Found {len(report.contradictions)} contradictions"
```

### CI/CD Integration

```yaml
# .github/workflows/coherence.yml
name: Coherence Check

on: [push, pull_request]

jobs:
  test-coherence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install CoherenceProbe
        run: pip install coherenceprobe[local]
      - name: Run coherence check
        run: |
          coherenceprobe check test_outputs.jsonl --local
```

### LangChain Integration

```python
from langchain.chains import SequentialChain
from coherenceprobe import FileCapture, check

capture = FileCapture("chain_outputs.jsonl")

# Wrap your chain calls
def run_chain_with_capture(chain_name, input_data):
    result = chain.run(input_data)
    capture.capture(chain_name, str(input_data), result)
    return result

# After running your chains
report = check(capture.get_outputs())
```

---

## Local vs Cloud Mode

CoherenceProbe offers two modes:

### LLM Mode (Default)
- Uses litellm for claim extraction (any LLM: GPT-4, Claude, etc.)
- More accurate claim extraction
- Requires API key

```python
config = CoherenceConfig(
    model="openai/gpt-4o-mini",
    threshold=0.7
)
```

### Local Mode (Privacy-First)
- Uses spaCy for claim extraction
- Sentence-transformers for embeddings + NLI
- 100% local, no API calls
- Runs on CPU (or GPU if available)

```bash
pip install coherenceprobe[local]
python -m spacy download en_core_web_sm

coherenceprobe check outputs.jsonl --local
```

Perfect for:
- Sensitive data
- Air-gapped environments
- Cost optimization
- High-throughput scenarios

---

## Performance Considerations

**Complexity**: O(n²) within each semantic cluster

For a pipeline with 3 agents producing 5 claims each:
- Total claims: 15
- After clustering: ~3-5 clusters
- NLI checks per cluster: ~25 (only cross-agent)
- Total NLI calls: ~75

**Optimizations**:
1. Claims are clustered by topic first (reduces comparisons)
2. Only cross-agent pairs are checked (no self-comparison)
3. Async support for parallel LLM calls: `await acheck(outputs)`

**Scaling**:
- For large pipelines, consider sampling outputs
- Or run on representative test cases rather than production traffic

---

## The Research Behind It

The multi-agent contradiction problem isn't hypothetical. Research paper arXiv 2605.30335 found that:

- **33-94%** of multi-agent compositions contain contradictions
- Contradictions scale with pipeline complexity
- Human annotators miss ~40% of subtle contradictions

CoherenceProbe automates what would otherwise require:
- Manual review of every agent output
- Cross-referencing claims across agents
- NLI expertise to catch subtle contradictions

---

## What CoherenceProbe Doesn't Do

Let's be clear about limitations:

❌ **Does not verify factual correctness**
- It checks *consistency*, not truth
- Agent A and Agent B can both be wrong but coherent

❌ **Does not replace ground truth testing**
- Use traditional eval for accuracy
- Use CoherenceProbe for coherence

❌ **Does not guarantee semantic understanding**
- NLI models can miss context-dependent contradictions
- Adversarial examples exist

✅ **What it does do**: Catches the majority of contradictions automatically, which is far better than manual review or no testing.

---

## Getting Started

```bash
# Install
pip install coherenceprobe

# Quick test
from coherenceprobe import check, AgentOutput

outputs = [
    AgentOutput(agent="a1", timestamp="...", input="...", output="Port is 8080"),
    AgentOutput(agent="a2", timestamp="...", input="...", output="Port is 3000"),
]

report = check(outputs)
print(report.score)  # Low score = contradiction detected
```

**Resources**:
- GitHub: https://github.com/yourusername/coherenceprobe
- Docs: See README.md
- PyPI: https://pypi.org/project/coherenceprobe/

---

## Conclusion: Test What Matters

As multi-agent systems become the norm, testing needs to evolve. We can't just test individual agents. We need to test the *system*:

- Are agents contradicting each other?
- Which agent is the problematic one?
- Is the pipeline internally consistent?

CoherenceProbe makes this automatic, fast, and practical.

Because the worst bugs aren't the ones where your system is wrong.

They're the ones where your system tells users two different truths — and you never notice until it's too late.

---

**Try it today:**

```bash
pip install coherenceprobe
coherenceprobe check your_outputs.jsonl
```

**Your multi-agent systems deserve coherence testing.**

---

*Have you encountered contradictions in your multi-agent pipelines? What's your testing strategy? Let me know in the comments.*

*Star the project on GitHub if you find it useful: https://github.com/yourusername/coherenceprobe*
