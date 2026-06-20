# Installation Guide

## Quick Install

```bash
pip install coherenceprobe
```

## Local Mode (No API Calls)

For fully local operation with spaCy-based claim extraction:

```bash
pip install coherenceprobe[local]
python -m spacy download en_core_web_sm
```

## With Visualization

```bash
pip install coherenceprobe[viz]
```

## Development Setup

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git && cd ProtoGensis/coherenceprobe
cd coherenceprobe
pip install -e ".[dev,local,viz]"
python -m spacy download en_core_web_sm
pytest
```

## Troubleshooting

### Keras 3 Compatibility Error

**Error:**
```
ValueError: Your currently installed version of Keras is Keras 3,
but this is not yet supported in Transformers.
```

**Solution:**

The package now includes `tf-keras` in its dependencies. If you still encounter this error:

```bash
pip install tf-keras
```

This installs the backwards-compatible Keras package required by the `transformers` library (a dependency of `sentence-transformers`).

### SpaCy Model Not Found

**Error:**
```
ModuleNotFoundError: No module named 'spacy'
# or
OSError: [E050] Can't find model 'en_core_web_sm'
```

**Solution:**

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

### Import Errors with sentence-transformers

If you encounter issues importing sentence-transformers:

```bash
pip install --upgrade sentence-transformers torch
```

## System Requirements

- **Python**: 3.9+
- **OS**: Linux, macOS, Windows
- **Memory**: 2GB+ RAM recommended (for NLI models)
- **Storage**: ~1GB for models (sentence-transformers + spaCy)

## Optional Dependencies

### For LLM Mode (API-based extraction)

CoherenceProbe uses [LiteLLM](https://docs.litellm.ai/docs/) for LLM-based claim extraction.

Set up API keys for your chosen provider:

```bash
# OpenAI
export OPENAI_API_KEY="your-key-here"

# Anthropic
export ANTHROPIC_API_KEY="your-key-here"

# Other providers supported via LiteLLM
```

Then configure:

```python
from coherenceprobe import CoherenceConfig

config = CoherenceConfig(
    local=False,
    model="openai/gpt-4o-mini"  # or any LiteLLM-supported model
)
```

### For GPU Acceleration

If you have a CUDA-capable GPU:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

This will speed up NLI and embedding operations significantly.

## Verifying Installation

```python
from coherenceprobe import check, AgentOutput, CoherenceConfig

# Test basic functionality
outputs = [
    AgentOutput(
        agent="test1",
        timestamp="2026-06-07T10:00:00Z",
        input="test",
        output="The server runs on port 8080.",
        metadata={}
    ),
    AgentOutput(
        agent="test2",
        timestamp="2026-06-07T10:00:05Z",
        input="test",
        output="The server runs on port 3000.",
        metadata={}
    ),
]

config = CoherenceConfig(local=True)
report = check(outputs, config)

print(f"✅ Installation successful!")
print(f"   Score: {report.score:.2f}")
print(f"   Contradictions: {len(report.contradictions)}")
```

## Docker Installation

For containerized deployment:

```dockerfile
FROM python:3.11-slim

RUN pip install coherenceprobe[local]
RUN python -m spacy download en_core_web_sm

WORKDIR /app
COPY . .

CMD ["coherenceprobe", "check", "outputs.jsonl", "--local"]
```

## Common Installation Issues

### Issue: `externally-managed-environment` error

**Solution:** Use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install coherenceprobe[local]
```

### Issue: Slow model downloads

**Solution:** Models are downloaded from HuggingFace. If you're behind a firewall or have slow connectivity:

```bash
# Pre-download models
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
python -c "from transformers import AutoModelForSequenceClassification; AutoModelForSequenceClassification.from_pretrained('cross-encoder/nli-deberta-v3-large')"
```

### Issue: Out of memory during NLI

**Solution:** Process in smaller batches or use a smaller NLI model:

```python
config = CoherenceConfig(
    nli_model="cross-encoder/nli-deberta-v3-small",  # Smaller model
    embedding_model="all-MiniLM-L6-v2"
)
```

## Platform-Specific Notes

### macOS (Apple Silicon)

PyTorch with MPS acceleration:

```bash
pip install torch torchvision torchaudio
```

### Windows

If you encounter build issues with torch:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Linux (ARM/Raspberry Pi)

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install coherenceprobe[local]
```

## Getting Help

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/ccrngd1/ProtoGensis/issues)
- **Blog Post**: [BLOG.md](BLOG.md)

---

**Need more help?** Open an issue with:
- Python version (`python --version`)
- OS and version
- Full error traceback
- Installation command used
