# The Practitioner's Guide to MoA on AWS Bedrock

> **Does a $0.0005/call ensemble of cheap models beat a $0.015/call strong model on AWS Bedrock?**
>
> **TL;DR: It depends on your architecture.** After 11 completed experiments (3,500+ API calls, $165.36 validation investment), we found that **ensembles work when proposers are significantly weaker than the aggregator** — but fail for equal-capability architectures.

A hands-on implementation and empirical evaluation of Mixture-of-Agents (MoA) on AWS Bedrock, with validated cost/quality measurements and evidence-based analysis of when MoA works and when it doesn't.

**Read the full story:** [BLOG.md](./BLOG.md)  
**Validation findings:** [docs/EXPERIMENTS_RESULTS.md](./docs/EXPERIMENTS_RESULTS.md)  
**Full methodology:** [docs/DETAILED_METHODOLOGY.md](./docs/DETAILED_METHODOLOGY.md)

---

## Key Findings (April 2026)

### ✅ When MoA WORKS

**1. Weak Proposers + Strong Aggregator (Validated ✅)**

| Configuration | Score | Baseline | Gain | Cost/Prompt |
|--------------|-------|----------|------|-------------|
| 3×Nova → Sonnet | 92.4 | 78.6 (Nova) | **+13.8** ✅ | $0.022 |
| 3×Haiku → Opus | 91.1 | 85.2 (Haiku) | **+5.9** ✅ | $0.07 |
| 3×Nova → Haiku | 87.2 | 78.6 (Nova) | **+8.6** ✅ | $0.07 |

**2. AlpacaEval Instruction-Following (Validated ✅)**

All Phase 1 ensembles beat baseline on AlpacaEval: +0.7 to +1.4 points. Aligns with Wang et al. (2024).

**3. Strong-Judge Vote Ensemble (Validated ✅)**

Opus judge selecting from 5 diverse candidates: 94.5 (matches baseline). Fails with weak judge.

### ❌ When MoA DOESN'T WORK

**1. Equal-Capability Architectures**

| Configuration | Score | vs Opus (94.5) | Cost Multiplier |
|--------------|-------|----------------|-----------------|
| High-end reasoning | 94.0 | -0.5 | 6× |
| Mixed-capability | 93.1 | -1.4 | 3× |
| Same-model-premium | 93.1 | -1.4 | 5× |

When proposers ≈ aggregator, synthesis overhead > diversity benefit.

**2. Cost Optimization**

| Approach | Score | Cost | Quality/$ |
|----------|-------|------|-----------|
| Haiku (standalone) | 85.2 | $0.003 | 28,400 ✅ |
| Smart routing | 87.0 | $0.026 | 3,346 |
| Best ensemble | 92.4 | $0.022 | 4,200 |
| Opus (standalone) | 92.3 | $0.079 | 1,168 |

Haiku is the cost-efficiency winner by a wide margin. Ensembles are not the right tool for saving money.

**3. Best-of-N at Matched Cost**

At equal cost, Best-of-N sampling from a strong model beats ensemble architecture every time.

---

## Decision Framework

| Your situation | Recommended approach | Score | Cost |
|----------------|---------------------|-------|------|
| Need max quality | Pure Opus | 92.3 | $0.079 |
| Using Nova-Lite, need better | 3×Nova → Sonnet | 92.4 | $0.022 |
| Using Haiku, need better | 3×Haiku → Opus | 91.1 | $0.07 |
| Best cost-efficiency | Pure Haiku | 85.2 | $0.003 |
| AlpacaEval optimization | Any ensemble | 97–98 | Varies |
| Need diversity + max quality | Strong-judge vote | 94.5 | $0.32 |

---

## Quick Start

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ensemble-moa-bedrock-guide
pip install -r requirements.txt
export AWS_BEARER_TOKEN_BEDROCK=your_token_here
export AWS_DEFAULT_REGION=us-east-1
```

**Run a standalone model (recommended baseline):**

```python
import asyncio
from moa.bedrock_client import BedrockClient
from moa.models import BEDROCK_MODELS

async def main():
    client = BedrockClient()
    result = await client.invoke_model(
        model_id=BEDROCK_MODELS["haiku"].model_id,
        prompt="Explain the CAP theorem in distributed systems.",
        max_tokens=2048,
        temperature=0.7
    )
    print(result['response'])

asyncio.run(main())
```

**Run an ensemble (for comparison):**

```python
import asyncio
from moa import create_moa_from_recipe

async def main():
    moa = create_moa_from_recipe("nova-to-sonnet")  # Best ensemble found
    response = await moa.run("Explain the CAP theorem in distributed systems.")
    print(response.final_response)
    print(response.cost_summary)

asyncio.run(main())
```

---

## Project Structure

```
ensemble-moa-bedrock-guide/
├── moa/                    # Core MoA framework
│   ├── core.py             # Async MoA pipeline
│   ├── models.py           # Model definitions, pricing, pre-built recipes
│   ├── judge.py            # Automated quality scoring (Opus-based)
│   ├── cost_tracker.py     # Per-token cost tracking
│   └── bedrock_client.py   # Bedrock API client (bearer token auth)
│
├── benchmark/              # Evaluation infrastructure
│   ├── prompts.json        # 54-prompt test suite (8 categories)
│   ├── run.py              # Main benchmark runner
│   ├── mtbench_integration.py
│   └── analyze_diversity.py
│
├── experiments/            # Validation experiment runners (E1–E14)
│   ├── run_e4_alpacaeval.py
│   ├── run_e6_aggregator_tiers.py
│   ├── run_e7_e8_low_baseline.py
│   └── ...
│
├── tests/                  # Test and analysis scripts
│   ├── test_judge.py
│   ├── verify_baseline_scores.py
│   └── ...
│
├── results/                # Raw JSON results from all experiments
│
├── docs/                   # Supporting documentation
│   ├── DETAILED_METHODOLOGY.md   # Full experimental methodology
│   ├── EXPERIMENTS_RESULTS.md    # Validation experiment findings
│   ├── EXPERIMENTS_README.md     # Experiment execution notes
│   ├── ANALYSIS.md               # Statistical analysis summary
│   └── RESEARCH.md               # Background research
│
├── BLOG.md                 # Full practitioner guide (start here)
├── README.md               # This file
├── example.py              # Simple usage example
└── requirements.txt
```

---

## Running Benchmarks

⚠️ **Running full benchmarks will incur AWS charges.** Test with `--limit 3` first (~$0.15).

```bash
# Full 54-prompt suite (~$5–10)
python benchmark/run.py --output results/my_benchmark.json

# Small test run
python benchmark/run.py --limit 3

# MT-Bench multi-turn
python benchmark/mtbench_integration.py opus ultra-cheap

# Analyze results
python benchmark/analyze_diversity.py results/my_benchmark.json
```

Validation investment for this project: $165.36 across 11 experiments.

---

## Resources

- **Full write-up:** [BLOG.md](./BLOG.md)
- **MoA Paper (Wang et al. 2024):** https://arxiv.org/abs/2406.04692
- **AWS Bedrock Pricing:** https://aws.amazon.com/bedrock/pricing/
- **Validation results:** [docs/EXPERIMENTS_RESULTS.md](./docs/EXPERIMENTS_RESULTS.md)
- **Methodology:** [docs/DETAILED_METHODOLOGY.md](./docs/DETAILED_METHODOLOGY.md)

---

*Based on 3,500+ live API calls, March–April 2026. All costs measured from actual Bedrock responses, not estimates.*
