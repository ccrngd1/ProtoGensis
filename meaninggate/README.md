# MeaningGate

**Semantic governance for healthcare claims denial analysis.**

MeaningGate demonstrates how typed semantic tools (metrics, knowledge graphs, policy search) prevent LLM agents from making ambiguous or incorrect interpretations compared to raw SQL access over the same data.

⚠️ **Note:** "MeaningGate" is a provisional working name only, not a product brand.

## The Problem

Healthcare denial rates vary 2-3× depending on how you calculate them—same data, different SQL queries. When LLMs have raw SQL access, they inherit this ambiguity. MeaningGate fixes this by replacing SQL with semantic boundaries: pre-compiled metrics, SHACL-validated graphs, and structured policy lookups.

## Architecture

**Five phases:**

- **P1**: Generate deterministic seeded world (claims, auth requests, policies)
- **P2**: Semantic layer - pre-compiled denial metrics (6 definitions, LLM-free)
- **P3**: Knowledge graph (RDF + SHACL) with inference-from-absence (HS-14 auth gap)
- **P4**: Two agents - ungoverned (raw SQL) vs governed (typed semantic tools)
- **P5**: Verification layer + 50-question eval set

## Quick Start

### Prerequisites

- Python 3.11+
- AWS credentials for Bedrock (optional - mock mode available)

### Installation

```bash
git clone <repo-url>
cd meaninggate

# Install dependencies
pip install -r requirements.txt
```

### Run Demo

```bash
# With live LLM (requires AWS Bedrock creds)
python3 demo.py --question "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?"

# Mock mode (no LLM required)
python3 demo.py --mock
```

### Run Tests

```bash
# Offline test suite (no LLM required)
pytest tests/test_offline.py -v
```

## Verification Commands

### P2: Semantic Layer (LLM-free)

```bash
python3 semantic/compiler.py
```

Expected: 6 denial rate definitions produce 2-3× spread on identical data.

### P3: Knowledge Graph + SHACL

```bash
python3 ontology/graph.py
```

Expected:
- Clean data passes SHACL validation
- Seeded violations fail SHACL validation
- Inference-from-absence identifies HS-14 notification gap
- Completes in ~3 seconds

### P4+P5: End-to-End Demo

```bash
python3 demo.py --mock
```

Expected:
- Ungoverned agent: ambiguous, no root cause tracing
- Governed agent: precise, policy-cited, verified
- Verification: diff_count=0 (governed answer matches truth.json)

## Key Files

- `generate/truth.json` - Ground truth for verification
- `semantic/metrics/denials.yml` - Metric definitions
- `ontology/payor.ttl` - Healthcare payor ontology (RDF)
- `ontology/shapes/denial_shapes.shacl.ttl` - SHACL constraints
- `eval/questions.yml` - 50-question evaluation set
- `demo.py` - Side-by-side comparison CLI

## Honesty Caveats

### P3 SHACL Inference

pyshacl validation runs with `inference='none'` (not OWL-RL) to avoid timeouts on 5,800 claim lines. The simplified SHACL shapes (property constraints only, no SPARQL-based shapes) still demonstrate:

1. Validation passes on clean data
2. Validation fails on seeded violations (denial without CARC, PR typed as Denial)
3. Inference-from-absence via Python iteration (not SPARQL FILTER NOT EXISTS)

### P4 Ungoverned Failure Mode

The ungoverned agent must fail **honestly** on realistic schema ambiguity—never a rigged schema. The warehouse schema is real X12 837/835 terminology. If the ungoverned agent succeeds consistently, the semantic governance claim weakens.

### Mock Mode

When AWS credentials are unavailable, demo.py runs in mock mode with cached responses. This allows clone-and-run verification without Bedrock access, but does not test live LLM behavior.

## License

Prototype research code - not for production use.
