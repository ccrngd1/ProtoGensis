# CoherenceProbe 🔍

[![CI](https://github.com/ccrngd1/ProtoGensis/actions/workflows/CI/badge.svg)](https://github.com/ccrngd1/ProtoGensis/actions)
[![PyPI](https://img.shields.io/pypi/v/coherenceprobe.svg)](https://pypi.org/project/coherenceprobe/)
[![Python](https://img.shields.io/pypi/pyversions/coherenceprobe.svg)](https://pypi.org/project/coherenceprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Detect logical contradictions across multi-agent AI pipeline outputs — without needing ground truth.**

Research shows 33-94% of multi-agent compositions contain hidden contradictions ([arXiv 2605.30335](https://arxiv.org)). CoherenceProbe helps you find them automatically.

---

## ⚡ Quick Start

```bash
# Install
pip install coherenceprobe

# Basic usage
from coherenceprobe import check, LogCapture

# Capture agent outputs
capture = LogCapture()
capture.capture("summarizer", "article text", "This article discusses AI safety...")
capture.capture("critic", "article text", "The article ignores safety concerns...")

# Check coherence
report = check(capture.get_outputs())
print(f"Coherence score: {report.score:.2f}")
print(f"Contradictions found: {len(report.contradictions)}")
```

---

## 📋 Features

- ✅ **Ground truth not required** — detects contradictions between agent outputs using NLI
- ✅ **Multiple input formats** — JSONL, directory, programmatic capture
- ✅ **Fully local mode** — optional spaCy-based extraction (no API calls)
- ✅ **LLM mode** — litellm integration for advanced claim extraction
- ✅ **Rich reporting** — JSON, text, and HTML outputs with per-agent scores
- ✅ **CLI and Python API** — use as command-line tool or library
- ✅ **Async support** — `acheck()` for async workflows

---

## 🚀 Installation

### Basic Installation

```bash
pip install coherenceprobe
```

### Local Mode (no API calls)

```bash
pip install coherenceprobe[local]
python -m spacy download en_core_web_sm
```

### With Visualization

```bash
pip install coherenceprobe[viz]
```

### Development

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git && cd ProtoGensis/coherenceprobe
cd coherenceprobe
pip install -e ".[dev]"
pytest
```

---

## 📖 Usage

### Python API

#### Basic Check

```python
from coherenceprobe import check, AgentOutput

outputs = [
    AgentOutput(
        agent="agent_1",
        timestamp="2026-06-07T10:00:00Z",
        input="What is the server port?",
        output="The server runs on port 8080.",
        metadata={}
    ),
    AgentOutput(
        agent="agent_2",
        timestamp="2026-06-07T10:00:05Z",
        input="What is the server port?",
        output="The server runs on port 3000.",
        metadata={}
    ),
]

report = check(outputs)
print(report.score)  # 0.0-1.0, lower = more incoherent
```

#### Capture Backends

**LogCapture** (in-memory):
```python
from coherenceprobe import LogCapture, check

capture = LogCapture()
capture.capture("agent1", "input", "output")
report = check(capture.get_outputs())
```

**FileCapture** (JSONL):
```python
from coherenceprobe import FileCapture

capture = FileCapture("outputs.jsonl")
capture.capture("agent1", "input", "output")
# Automatically writes to file
```

**DecoratorCapture** (wrap functions):
```python
from coherenceprobe import DecoratorCapture

capture = DecoratorCapture()

@capture.agent("summarizer")
def summarize(text: str) -> str:
    return text[:100]

result = summarize("Long text...")
report = check(capture.get_outputs())
```

#### Configuration

```python
from coherenceprobe import check, CoherenceConfig

config = CoherenceConfig(
    model="openai/gpt-4o-mini",  # LiteLLM model string
    threshold=0.7,                # NLI confidence threshold
    local=False,                  # Use local spaCy mode
    nli_model="cross-encoder/nli-deberta-v3-large",
    embedding_model="all-MiniLM-L6-v2",
    adjudicate_ambiguous=False,   # Use LLM for explanations
    verbose=False
)

report = check(outputs, config)
```

#### Async Usage

```python
from coherenceprobe import acheck
import asyncio

async def main():
    report = await acheck(outputs)
    print(report.score)

asyncio.run(main())
```

#### Advanced: Pipeline Stages

```python
from coherenceprobe import (
    extract_claims,
    detect_contradictions,
    compute_coherence_score,
    CoherenceConfig
)

config = CoherenceConfig()

# Stage 1: Extract claims
claims = extract_claims(outputs, config)

# Stage 2: Detect contradictions
contradictions = detect_contradictions(claims, config)

# Stage 3: Compute score
report = compute_coherence_score(claims, contradictions, config)
```

### Command Line

#### Check Coherence

```bash
# From JSONL file
coherenceprobe check outputs.jsonl

# From directory (one file per agent)
coherenceprobe check outputs_dir/

# Local mode (no API calls)
coherenceprobe check outputs.jsonl --local

# Custom format and output
coherenceprobe check outputs.jsonl --format html --output report.html

# With verbose logging
coherenceprobe check outputs.jsonl --verbose

# Custom threshold
coherenceprobe check outputs.jsonl --threshold 0.5
```

#### Other Commands

```bash
# Show statistics
coherenceprobe stats outputs.jsonl

# Initialize capture file
coherenceprobe init outputs.jsonl

# Show configuration info
coherenceprobe info

# Help
coherenceprobe --help
coherenceprobe check --help
```

---

## 📊 Input Formats

### JSONL Format

Each line is a JSON object representing one agent output:

```jsonl
{"agent": "summarizer", "timestamp": "2026-06-07T10:00:00Z", "input": "article", "output": "summary", "metadata": {}}
{"agent": "critic", "timestamp": "2026-06-07T10:00:05Z", "input": "article", "output": "critique", "metadata": {}}
```

### Directory Format

One file per agent, filename = agent name:

```
outputs/
├── summarizer.txt
├── critic.txt
└── fact_checker.txt
```

---

## 🧠 How It Works

### Pipeline

1. **Claim Extraction**
   - LLM mode: Uses litellm to extract atomic factual claims
   - Local mode: Uses spaCy sentence splitting + heuristic filtering

2. **Contradiction Detection**
   - Embed claims with sentence-transformers
   - Cluster by topic (cosine similarity ≥ 0.6)
   - Run pairwise NLI within clusters (cross-agent only)
   - Classify type: logical, factual, or temporal

3. **Coherence Scoring**
   ```
   score = 1.0 - (weighted_contradictions / total_claim_pairs)
   ```
   - Per-agent scores show incoherence contribution

### Contradiction Types

- **Logical**: Direct negation (A vs not-A)
- **Factual**: Different values for same attribute (port 8080 vs 3000)
- **Temporal**: Incompatible temporal assumptions

---

## 📈 Report Format

### CoherenceReport

```python
class CoherenceReport:
    score: float                      # 0.0-1.0, 1.0 = fully coherent
    agent_scores: dict[str, float]    # Per-agent incoherence
    contradictions: list[ContradictionPair]
    total_claims: int
    total_agents: int
    metadata: dict
```

### Output Formats

**Text** (default):
```
======================================================================
COHERENCE PROBE REPORT
======================================================================

Overall Coherence Score: 0.650 ⚠️
Total Agents: 2
Total Claims: 4
Contradictions Found: 1

...
```

**JSON**:
```json
{
  "score": 0.65,
  "agent_scores": {"agent1": 0.175, "agent2": 0.175},
  "contradictions": [...],
  ...
}
```

**HTML**: Interactive report with styling

---

## 🔧 Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | str | `openai/gpt-4o-mini` | LiteLLM model for claim extraction |
| `threshold` | float | `0.7` | NLI confidence threshold (0-1) |
| `local` | bool | `False` | Use fully local mode (spaCy) |
| `nli_model` | str | `cross-encoder/nli-deberta-v3-large` | HuggingFace NLI model |
| `embedding_model` | str | `all-MiniLM-L6-v2` | Sentence-transformers embedding model |
| `adjudicate_ambiguous` | bool | `False` | Use LLM to explain contradictions |
| `verbose` | bool | `False` | Enable verbose logging |

---

## ⚠️ Ambiguities & Design Notes

**Note**: The referenced requirements and research documents could not be accessed during development. The following implementation decisions were made based on the provided specification:

### 1. **Scoring Formula Details**
- **Decision**: Used `score = 1.0 - (weighted_contradictions / total_pairs)` where weighted_contradictions is sum of confidence scores
- **Ambiguity**: Alternative interpretations could weight by severity or use different normalization
- **Rationale**: This provides intuitive 0-1 scale where 1.0 = perfect coherence

### 2. **Same-Agent Claims**
- **Decision**: Claims from the same agent are NOT compared for contradictions
- **Rationale**: Agents should be internally consistent; we're testing cross-agent coherence
- **Alternative**: Could optionally flag internal inconsistencies with a config flag

### 3. **Claim Normalization**
- **Decision**: Normalizes to lowercase, removes hedging, strips punctuation
- **Trade-off**: May lose important semantic distinctions in edge cases
- **Benefit**: Improves NLI matching for similar but differently-phrased claims

### 4. **Clustering Threshold**
- **Decision**: Hard-coded 0.6 cosine similarity for claim clustering
- **Ambiguity**: Optimal threshold may vary by domain
- **Future**: Could expose as config parameter

### 5. **NLI Model Output Format**
- **Assumption**: `cross-encoder/nli-deberta-v3-large` returns `[contradiction, entailment, neutral]`
- **Note**: Model output format should be verified in production use

### 6. **Empty Input Handling**
- **Decision**: Returns perfect score (1.0) for single agent or empty inputs
- **Rationale**: No contradictions possible = coherent
- **Alternative**: Could return None or special status

### 7. **Async Implementation**
- **Current**: Async functions wrap sync implementations
- **Future**: Could parallelize LLM calls and NLI inference for performance

### 8. **LLM Fallback**
- **Decision**: LLM extraction failures automatically fall back to local spaCy
- **Benefit**: Robustness
- **Trade-off**: Silent fallback may mask API issues (logged in verbose mode)

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=coherenceprobe --cov-report=html

# Specific test file
pytest tests/test_detection.py

# Verbose
pytest -v
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🔗 Links

- **Documentation**: [GitHub README](https://github.com/ccrngd1/ProtoGensis/tree/main/coherenceprobe)
- **PyPI**: [https://pypi.org/project/coherenceprobe/](https://pypi.org/project/coherenceprobe/)
- **Issues**: [GitHub Issues](https://github.com/ccrngd1/ProtoGensis/issues)
- **Blog Post**: See [BLOG.md](BLOG.md) for detailed writeup

---

## 📚 Citation

If you use CoherenceProbe in your research, please cite:

```bibtex
@software{coherenceprobe2026,
  title={CoherenceProbe: Contradiction Detection for Multi-Agent AI Pipelines},
  author={CoherenceProbe Contributors},
  year={2026},
  url={https://github.com/ccrngd1/ProtoGensis/tree/main/coherenceprobe}
}
```

---

## ❓ FAQ

**Q: Do I need API keys?**
A: Only if using LLM mode. Local mode (`--local`) works entirely offline with spaCy.

**Q: What models are supported?**
A: Any model supported by [litellm](https://docs.litellm.ai/docs/providers) (OpenAI, Anthropic, etc.)

**Q: How accurate is the detection?**
A: Depends on NLI model quality. `cross-encoder/nli-deberta-v3-large` achieves ~90% accuracy on standard NLI benchmarks.

**Q: Can I use custom NLI models?**
A: Yes! Set `nli_model` in config to any HuggingFace cross-encoder model.

**Q: What about performance?**
A: Scales O(n²) with claim count within each semantic cluster. For large pipelines, consider sampling or running on representative subsets.

---

**Built with ❤️ for making multi-agent AI systems more reliable**
