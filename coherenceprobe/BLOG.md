# Testing Multi-Agent AI Systems: The Hidden Contradiction Problem

## Why Your Multi-Agent Pipeline Might Be Lying to You (And How to Find Out)

Multi-agent AI systems are everywhere. You chain together a summarizer, fact-checker, and critic. You compose Claude with GPT-4 and Gemini. You build agentic workflows where specialized models collaborate. The output looks polished. The metrics look good.

But here's the problem: **33-94% of multi-agent compositions contain hidden contradictions** (arXiv 2605.30335). The range depends on pipeline complexity. Simple two-agent summaries sit near the bottom; multi-step reasoning chains with 5+ agents push toward the top.

Not hallucinations. Not factual errors you can check against ground truth. Logical contradictions *between the agents themselves.*

Agent A says the server runs on port 8080. Agent B says it runs on port 3000. Both sound confident. Both are hallucinating, but in different directions. Your pipeline just told your users two incompatible truths.

This is the multi-agent coherence problem, and until now, you probably weren't testing for it.

---

## The Ground Truth Trap

I ran into this building my own agent pipelines. Three agents analyzing the same codebase, each producing confident analysis. The outputs looked great individually. But when I actually cross-referenced them, they were contradicting each other in subtle ways that a quick skim wouldn't catch.

Traditional AI testing assumes you have ground truth. Does the summary match the original text? Is the translation accurate? Did the model predict the correct label? But multi-agent systems operate differently. You're not testing correctness. You're testing consistency. When you ask three agents to analyze a codebase, you don't have a golden answer. You just need to know if they agree with each other.

The question isn't "Is Agent A right?" It's "Do Agent A and Agent B contradict each other?"

If you're using RAGAS, DeepEval, or custom evals, great. Those test accuracy against ground truth. But they can't test internal consistency across agents when no ground truth exists. That's a different problem, and it needs a different tool.

---

## What I Built

So I built CoherenceProbe. It takes N outputs from N agents and tells you if they contradict each other. No ground truth needed. No manual review. Here's what it looks like:

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

The package caught the contradiction automatically. That's the whole pitch.

---

## How It Works

The first problem was breaking agent output into testable claims. A paragraph of text might contain five separate factual assertions, and you need to compare each one independently.

**Claim extraction** uses an LLM by default (via litellm) to pull out atomic factual claims. "The server runs on port 8080 and handles 1000 requests per second" becomes two separate claims. There's also a local mode using spaCy if you don't want API calls. Claims get normalized: lowercase, hedging stripped, punctuation removed. One tradeoff worth noting: removing hedging ("might", "possibly") increases detection recall but can produce false positives when a hedged claim gets compared against a confident one. The threshold is tunable for this reason.

Once I had claims, I needed to compare them without drowning in O(n²) pairs. The solution is **semantic clustering**. Embed all claims using sentence-transformers (all-MiniLM-L6-v2), group semantically similar ones (cosine similarity ≥ 0.6, configurable), then only run pairwise NLI *within* clusters and only *across* agents. Same agent's claims don't get compared against each other.

The NLI step uses cross-encoder/nli-deberta-v3-large. For each pair, it scores CONTRADICTION, ENTAILMENT, and NEUTRAL. If contradiction confidence hits the threshold (default 0.7, also tunable), it gets flagged. Both key thresholds (0.6 for clustering, 0.7 for NLI) were chosen empirically. You can adjust them depending on your tolerance for false positives vs. missed contradictions.

**The score is simple:**

```python
coherence_score = 1.0 - (weighted_contradictions / total_claim_pairs)
# Weights = NLI confidence scores
```

1.0 means perfect coherence. 0.0 means maximum incoherence. You also get per-agent scores showing which agent contributes most to disagreements, so you know exactly where to investigate.

In practice, a 3-agent pipeline with 5 claims each means about 75 NLI checks total. Sub-second on GPU, a few seconds on CPU. For typical pipelines (under 10 agents), this fits comfortably in CI/CD.

---

## What It Actually Catches

The NLI model catches three flavors of contradiction. Direct negation ("system is operational" vs "system is not operational"), factual conflicts ("port 8080" vs "port 3000"), and temporal mismatches ("event occurred before the update" vs "event occurred after"). They all get flagged the same way.

Here's where it gets interesting in practice. I had a code analysis pipeline with a security agent and a code review agent. The security agent reported "no SQL injection vulnerabilities found." The code review agent flagged "line 47 contains a SQL injection vulnerability." CoherenceProbe caught that in under a second. Without it, I would have shipped a report containing both statements and looked like an idiot.

The same pattern shows up in multi-agent RAG systems. Your vector retrieval agent says the company was founded in 2019. Your hybrid search agent says 2021. Both chunks came from your database. Both sound confident. The contradiction slips through unless you're explicitly checking for it.

And in agentic workflows (CrewAI, LangGraph, whatever framework you're using), you can capture outputs with decorators:

```python
from coherenceprobe import DecoratorCapture, check

capture = DecoratorCapture()

@capture.agent("planner")
def plan_task(goal): ...

@capture.agent("executor")
def execute_task(plan): ...

@capture.agent("critic")
def review_execution(result): ...

# Run your workflow, then check coherence
result = workflow.run()
report = check(capture.get_outputs())
```

---

## Using It in CI/CD

The CLI is straightforward:

```bash
# Check coherence from JSONL file
coherenceprobe check outputs.jsonl

# Local mode (no API calls, runs entirely on CPU)
coherenceprobe check outputs.jsonl --local

# Custom threshold if you want more/fewer flags
coherenceprobe check outputs.jsonl --threshold 0.5
```

Input format is one JSON object per line:
```jsonl
{"agent": "summarizer", "timestamp": "2026-06-07T10:00:00Z", "input": "...", "output": "..."}
{"agent": "critic", "timestamp": "2026-06-07T10:00:05Z", "input": "...", "output": "..."}
```

And here's the pytest integration I use:

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

Full CLI docs and additional integrations (GitHub Actions, LangChain) are in the repo README.

---

## Local vs. Cloud

By default, CoherenceProbe uses an LLM for claim extraction (any model litellm supports). More accurate, but requires an API key.

There's also a fully local mode: spaCy for claim extraction, sentence-transformers for embeddings, DeBERTa for NLI. No API calls, no data leaving your machine. I use local mode in CI because it's faster and doesn't burn API credits. It's also the right choice for sensitive data or air-gapped environments.

```bash
pip install coherenceprobe[local]
python -m spacy download en_core_web_sm
coherenceprobe check outputs.jsonl --local
```

One security note: in LLM mode, agent outputs get sent to an LLM for claim extraction. If an agent's output contains prompt injection payloads, the extraction step could theoretically be compromised. Local mode sidesteps this entirely since no LLM is in the loop.

---

## What This Doesn't Do

Let's be honest about limitations:

❌ **Does not verify factual correctness.** It checks consistency, not truth. Agent A and Agent B can both be wrong but coherent. You still need accuracy testing.

❌ **Does not replace ground truth testing.** Use traditional eval for accuracy. Use CoherenceProbe for coherence. They're complementary layers.

❌ **Does not guarantee perfect detection.** NLI models have failure modes: complex negation, quantifier scope, domain-specific language. Adversarial examples exist. The 0.7 threshold catches most clear contradictions with low false-positive rates, but it's not an oracle.

✅ **What it does:** Catches the majority of contradictions automatically. That's far better than manual review or (more commonly) no testing at all.

The deeper point: coherence testing doesn't replace good pipeline architecture. If your agents contradict each other because they're operating on different context windows, the real fix is sharing context properly. CoherenceProbe is the test suite that verifies your architecture is actually working. Same reason you write tests even when you're confident in your code.

---

## Getting Started

```bash
pip install coherenceprobe
```

```python
from coherenceprobe import check, AgentOutput

outputs = [
    AgentOutput(agent="a1", timestamp="...", input="...", output="Port is 8080"),
    AgentOutput(agent="a2", timestamp="...", input="...", output="Port is 3000"),
]

report = check(outputs)
print(report.score)  # Low score = contradiction detected
```

**Resources:**
- GitHub: https://github.com/ccrngd1/ProtoGensis/tree/main/coherenceprobe
- PyPI: https://pypi.org/project/coherenceprobe/

---

## Why This Matters

As multi-agent systems become the norm, testing needs to evolve. We can't just test individual agents. We need to test the *system*:

- Are agents contradicting each other?
- Which agent is the problematic one?
- Is the pipeline internally consistent?

CoherenceProbe makes this automatic, fast, and practical.

Because the worst bugs aren't the ones where your system is wrong. They're the ones where your system tells users two different truths, and you never notice until it's too late.

```bash
pip install coherenceprobe
coherenceprobe check your_outputs.jsonl
```

---

*Have you run into contradictions in your own multi-agent pipelines? What's your testing strategy? I'd love to hear what you've tried.*

*GitHub: https://github.com/ccrngd1/ProtoGensis/tree/main/coherenceprobe*
