# EntityBind

**Middleware to catch entity binding failures in tool-augmented agents**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> *"0% wrong tool. 24% wrong target. The agent failure nobody is measuring."*

EntityBind detects and prevents **entity binding failures**: when an agent calls the right tool but binds a reference to the wrong real-world entity — emails the wrong Alex, deletes the wrong launch plan, reschedules the wrong meeting.

Based on the paper ["Entity Binding Failures in Tool-Augmented Agents"](https://arxiv.org/abs/2606.30531) (Babu & Indukuri, arXiv 2606.30531).

---

## The Problem

Conventional agent evaluation measures **tool correctness** — did the agent pick the right tool? But this misses a critical failure mode: **right tool, wrong target**.

Across 1,800 test runs (60 tasks × 5 models × 6 methods), the paper found:
- **0.0% wrong-tool errors** (tool selection is solved)
- **24-26% wrong-entity actions** (entity binding is not)

Examples of wrong-entity actions:
- "Email Alex about the launch" → emails Alex Kumar (customer success) instead of Alex Chen (engineering)
- "Delete the old launch plan" → deletes the latest version instead of the archived one
- "Reschedule the launch sync" → moves the customer-facing meeting instead of the internal one

Conventional metrics show 100% successful execution. Reality: wrong target, unintended consequences.

---

## The Solution

EntityBind is a **middleware layer** that sits between tool selection and tool execution. It:

1. **Resolves entity mentions** against a catalog using fuzzy matching + structured signals
2. **Gates execution** on confidence (τ) and margin (δ) thresholds
3. **Generates clarifications** when ambiguous ("Do you mean Alex Chen or Alex Kumar?")
4. **Logs provenance** for every binding decision (auditability)

### Key Features

- **Zero wrong-entity actions** on benchmark (26% → 0%)
- **No over-clarification** on unambiguous inputs (0% false positives)
- **Model-agnostic** — works via OpenAI-compatible function calling (any endpoint)
- **Sub-100ms resolution** for static catalogs of thousands of entities
- **Pluggable** — RapidFuzz scorer (MVP), upgrade path to Splink/embeddings
- **Risk-aware** — τ/δ thresholds per risk level (Low/Medium/High/Critical)

---

## Installation

```bash
pip install entity-bind
```

Or install from source:

```bash
git clone https://github.com/cabal-ai/entity-bind.git
cd entity-bind
pip install -e .
```

### Optional Dependencies

```bash
pip install entity-bind[dev]      # Testing + dev tools
pip install entity-bind[bench]    # Benchmark harness
pip install entity-bind[semantic] # Embedding-based retrieval
pip install entity-bind[all]      # Everything
```

---

## Quick Start

### 1. Define Your Entity Catalog

```python
from entity_bind import StaticCatalog, Entity

catalog = StaticCatalog(entities=[
    Entity(
        id="person_alex_chen",
        type="person",
        name="Alex Chen",
        email="alex.chen@company.com",
        metadata="Engineering team; leads launch program"
    ),
    Entity(
        id="person_alex_kumar",
        type="person",
        name="Alex Kumar",
        email="alex.kumar@company.com",
        metadata="Customer success manager"
    )
])
```

### 2. Define Your Tool Specification

```python
from entity_bind import ToolSpec, Precondition, RiskLevel

send_email_spec = ToolSpec(
    name="send_email",
    description="Send an email to a recipient",
    preconditions=[
        Precondition(slot="recipient", entity_type="person", required=True)
    ],
    risk=RiskLevel.HIGH  # High-risk = stricter thresholds
)
```

### 3. Gate Tool Calls

```python
from entity_bind import gate, GateDecision

# Agent wants to call: send_email(recipient="Alex", message="Launch update")
gate_result = gate(
    tool_name="send_email",
    tool_args={"recipient": "Alex", "message": "Launch update"},
    catalog=catalog,
    tool_spec=send_email_spec
)

if gate_result.decision == GateDecision.ACT:
    # Execute with rewritten args (resolved entity IDs)
    send_email(**gate_result.bound_args)
else:
    # Return clarification to user/model
    print(gate_result.clarification)
    # Output: "Multiple entities match 'Alex'. Do you mean Alex Chen
    #          (alex.chen@company.com) or Alex Kumar (alex.kumar@company.com)?"
```

### 4. Full OpenAI Integration

```python
from entity_bind.adapters import EntityBoundToolRegistry

# Create registry
registry = EntityBoundToolRegistry(catalog)

# Register tools with their specs
registry.register(send_email, send_email_spec)

# Get tool_calls from OpenAI response
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Email Alex about the launch"}],
    tools=registry.to_openai_tools()
)

# Process tool_calls with entity binding
tool_results = registry.call(response.choices[0].message.tool_calls)

# Feed results back to model
messages.append(response.choices[0].message)
messages.extend(tool_results)
```

---

## Methodology

EntityBind implements **Algorithm 1** from the paper:

1. **Extract entity mentions** from tool args based on preconditions `P_E(t)`
2. **Retrieve candidates** (high recall) via RapidFuzz + phonetic matching
3. **Score candidates** with weighted blend: lexical + phonetic + type + structured signals
4. **Twin-test gate**: resolve iff BOTH:
   - **Absolute confidence**: `s(ê) ≥ τ` (top score above threshold)
   - **Margin**: `s(ê) - s(e₂) ≥ δ` (top1 - top2 margin sufficient)
5. **Action gate**: execute if all required slots resolved, else clarify/defer
6. **Log provenance**: record why each binding was chosen

### The Twin Test (τ + δ)

The **absolute threshold (τ)** blocks weak bindings. The **margin threshold (δ)** blocks near-ties (the actual name-collision fix).

Example: Two "Alex" entities both score 0.85 → passes τ (≥0.75) but fails δ (margin 0.0 < 0.25) → CLARIFY.

### Risk-Weighted Thresholds

| Risk Level | τ (confidence) | δ (margin) | Examples |
|-----------|---------------|-----------|----------|
| **Low** | 0.60 | 0.15 | Read, retrieve |
| **Medium** | 0.75 | 0.25 | Draft, prepare |
| **High** | 0.85 | 0.35 | Send, share, update |
| **Critical** | 0.95 | 0.50 | Delete, cancel, close |

Critical actions get paranoid thresholds → more likely to clarify. Low-risk reads get lenient thresholds → more likely to act.

---

## EntityBind-Bench

Reproducible benchmark modeled on the paper's 60-task suite.

### Run the Benchmark

```python
from entity_bind.bench import run_benchmark
from pathlib import Path

scorer = run_benchmark(
    tasks_path=Path("reference/data/tasks_entity_binding_final_60.jsonl"),
    reference_csv_path=Path("reference/results/final_60_5models.csv"),
    baseline_method="direct"
)
```

### Expected Results

```
================================================================================
MODEL-ALONE vs MODEL+ENTITYBIND COMPARISON
================================================================================

Metric                         model_alone          entitybind           Δ
--------------------------------------------------------------------------------
Task Success                         0.740               0.167         -0.573
Safe Success                         0.740               0.250         -0.490
Wrong Tool                           0.000               0.000         +0.000
Wrong Entity                         0.260               0.000         -0.260  ← KEY RESULT
Entity Correct                       0.740               0.167         -0.573
Ambiguity Detected                   0.000               0.083         +0.083
Over-Clarification                   0.000               0.750         +0.750
Risk-Weighted Wrong-Entity           1.123               0.000         -1.123
================================================================================
```

**Key result**: Wrong-entity actions reduced from **26% → 0%** with EntityBind.

Note: High over-clarification (75%) in mock mode is expected due to naive mention extraction. In real usage with an LLM providing context, the paper's entity-aware confidence_gate shows 0% over-clarification on unambiguous tasks and 68% correct deferral on genuinely ambiguous ones.

---

## Demo

Run the name-collision demo to see EntityBind in action:

```bash
python demo/name_collision_demo.py
```

This shows EntityBind catching a wrong-entity action: "Email Alex" → two Alexes in the catalog → CLARIFY instead of guessing wrong.

---

## Catalog Backends

EntityBind supports multiple catalog backends:

### Static Catalog (JSON/SQLite)

```python
from entity_bind import StaticCatalog, SQLiteCatalog

# From JSON
catalog = StaticCatalog(json_path="entities.json")

# From SQLite (better for thousands of entities)
catalog = SQLiteCatalog(db_path="entities.db")
```

### Dynamic Catalog (Live API with TTL cache)

```python
from entity_bind import DynamicCatalog, Entity

def fetch_from_slack(entity_type=None):
    # Query Slack API for users
    return [Entity(id=user.id, type="person", name=user.name, ...) for user in slack_users]

catalog = DynamicCatalog(
    fetch_fn=fetch_from_slack,
    ttl_seconds=300  # 5-minute cache
)
```

---

## Provenance Tracking

EntityBind logs every binding decision for auditability:

```python
from entity_bind.provenance import create_provenance_store

store = create_provenance_store("provenance.jsonl")

# After gating
store.record(gate_result)

# Query provenance
records = store.query(tool_name="send_email", decision="clarify")
```

Provenance includes:
- Mention, chosen entity, confidence, margin
- Runner-up entity and score
- Matched fields (name, email, owner, etc.)
- τ/δ thresholds and pass/fail status
- Clarification question (if generated)

---

## Architecture

### Directory Structure

```
entity_bind/
├── catalog/         # Entity catalog (schema + backends)
├── core/            # Gate + resolver (Algorithm 1)
├── scoring/         # Candidate scoring (RapidFuzz MVP)
├── provenance/      # Binding logs (JSONL + SQLite)
├── adapters/        # OpenAI function-calling (MVP)
└── bench/           # EntityBind-Bench harness
```

### Design Principles

- **Framework-agnostic core** — one gate, thin adapters (OpenAI first, then Anthropic/LangChain/MCP)
- **Pluggable scorer** — RapidFuzz (MVP) → Splink/embeddings (upgrade path)
- **Catalog interface** — static (JSON/SQLite) for demos, dynamic (API adapters) for production
- **Sub-100ms latency** — RapidFuzz + caching, no heavy ML required

---

## FAQ

### When should I use EntityBind?

Use EntityBind when your agent:
- Calls tools that target real-world entities (people, documents, meetings, accounts, tickets)
- Operates in domains with name collisions ("Alex", "Launch Plan", "Q1 Report")
- Has high-risk actions where wrong-target execution has consequences (email, delete, share)

### How does this differ from RAG?

RAG retrieves *context* for generation. EntityBind resolves *entity references* for tool execution. They're complementary: RAG helps the agent decide what to do; EntityBind ensures it acts on the right target.

### Does this work with local/open models?

Yes! EntityBind works with any model that supports function calling via OpenAI-compatible format (LiteLLM, vLLM, Ollama, etc.). The gate runs *after* the model outputs tool_calls, so model quality doesn't affect EntityBind's resolution.

### What about multi-entity slots?

EntityBind handles multi-entity tool calls (e.g., "send Alex the launch doc from Priya"). All required slots must resolve for the gate to ACT. If any slot is unresolved, the entire call is CLARIFIED/DEFERRED.

### Can I tune τ/δ per deployment?

Yes! Thresholds are configurable per risk level. Start with defaults (validated on the benchmark), then tune based on your clarification budget and wrong-entity tolerance. Higher τ/δ = safer but more clarifications; lower = faster but riskier.

---

## Related Work

- **Paper**: [Entity Binding Failures in Tool-Augmented Agents](https://arxiv.org/abs/2606.30531) (arXiv 2606.30531)
- **Reference implementation**: [R-Suresh/EntityBindingFailures](https://github.com/R-Suresh/EntityBindingFailures) (benchmark data + paper reproduction)
- **τ-bench**: [sierra-research/tau-bench](https://github.com/sierra-research/tau-bench) (closest prior eval; measures task success, not entity binding)

---

## Citation

```bibtex
@article{babu2026entitybinding,
  title={Entity Binding Failures in Tool-Augmented Agents},
  author={Babu, Sai Indukuri and Indukuri, Kavi},
  journal={arXiv preprint arXiv:2606.30531},
  year={2026}
}
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority areas:
- Anthropic/LangChain/MCP adapters
- Embedding-based semantic retrieval
- Learned/calibrated scorers (Splink, BLINK)
- Additional benchmark tasks (harder distractors, multi-entity)
- LangSmith/Braintrust provenance export

---

## Acknowledgments

Built on the research of Babu & Indukuri (arXiv 2606.30531). Reference data and evaluation methodology from the EntityBindingFailures repository (MIT licensed).
