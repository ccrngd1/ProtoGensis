# AlignBias

**Audit your LLM stack for directional probability bias — optimism or pessimism tilt — with no ground truth required.**

## What it is

Ask a model "what's the probability the student passes the exam?" and it says 72%. Ask the *same* model, in a fresh conversation, "what's the probability the student does **not** pass?" and it says 20%. Those answers should sum to 100. They sum to 92 — the model is leaning 8 points pessimistic, and you just measured it without knowing anything about the student.

AlignBias runs this **inverted-pair** probe across 60 naturalistic scenarios (6 domains) and any set of LLM providers, then reports each model's **Skew**: the signed, systematic gap between its good-outcome and bad-outcome probability estimates. Because the two questions describe the same event, coherence — not correctness — is the yardstick, so no ground-truth labels are needed.

On top of the measurement, AlignBias adds the practitioner layer:

- **audit** — multi-model Skew measurement with bootstrap CIs, refusal filtering, and an exact-50 hedge filter
- **control** — a 15-item calibration track with *stated* base rates ("a fair coin is flipped…") that validates the harness itself: Skew here should be ~0, or your prompting/parsing is broken, not the model
- **routing-advisor** — rank your models per task type against a YAML policy (risk assessment may *want* a pessimist; brainstorming may tolerate an optimist)
- **calibrate** — derive additive correction offsets, with **separate success-side and failure-side coefficients** (tilts are rarely symmetric)
- **report** — Skew cards, cross-model comparison matrix, histogram + domain heatmap charts

## Attribution

Method and scenarios from **OptimismBench** (Cho & Koshiyama, Holistic AI/UCL, arXiv 2607.26981, CC BY 4.0). AlignBias is the practitioner auditing/routing/calibration layer built on top. Bundled scenario data derives from the public [`seonglae/OptimismBench`](https://huggingface.co/datasets/seonglae/OptimismBench) dataset release — see [`assets/ATTRIBUTION.md`](assets/ATTRIBUTION.md).

## Install

Not published to PyPI. Install from source (lives in the ProtoGensis monorepo):

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/align-bias
pip install -e .
```

## Quickstart

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

# Audit two models over the bundled 60-pair Track B set, 5 runs each
alignbias audit \
  --models anthropic:claude-opus-4-8,openai:gpt-5.6 \
  --runs 5 --temperature 0.7 --out ./out

# Validate the harness first (stated-base-rate items, Skew should be ~0)
alignbias control --models anthropic:claude-opus-4-8

# Rank models per task type from the audit results
alignbias routing-advisor --config examples/routing.yaml --report ./out/skew.json

# Derive correction offsets (separate success/failure coefficients)
alignbias calibrate --report ./out/skew.json

# Tiny live demo (degrades gracefully without keys)
alignbias demo
```

Custom scenario files are plain JSONL (`--scenarios ./my-pairs.jsonl`) with one inverted pair per line: `id`, `domain`, `scenario`, `question_positive`, `question_negative`, optional `p_true_positive`.

Library use:

```python
from alignbias import AlignBias

audit = AlignBias(models=["anthropic:claude-opus-4-8", "openai:gpt-5.6"])
reports = audit.run(runs=5)
for model, report in reports.items():
    print(model, f"{report.skew_mean:+.1f} pp", report.verdict)
```

## The math

For scenario *i*, elicit s⁺ (P(good outcome)) and s⁻ (P(bad outcome)) in independent conversations. All values are probability points (pp) on the 0–100 scale:

```
Skew_i    = s+_i − (100 − s-_i)          # 0 = coherent
Skew_mean = (1/n) Σ Skew_i               # >0 optimistic, <0 pessimistic

delta+ = mean(P+) − 50                   # good-side push
delta- = mean(P-) − 50                   # bad-side push
Skew   = delta+ + delta-
```

Worked example (GPT-5.4, from the paper): s⁺ = 72, s⁻ = 20 → Skew = 72 − (100 − 20) = **−8 pp** (pessimistic). The test suite pins this exact fixture.

Refused/unparseable answers are excluded (and counted); exact-50 answers are filtered by default as uncommitted hedges. The elicitation is Strategy A (direct numeric prompting, strict JSON with a tolerant fallback parser) — no logprobs.

## Architecture

```
                 ┌────────────────────────────────────────────────┐
                 │                 alignbias CLI                   │
                 │  audit · control · routing-advisor · calibrate │
                 └───────┬──────────────────┬─────────────┬───────┘
                         │                  │             │
   assets/*.jsonl ──► scenarios/loader   routing.py   calibrate.py
   (Track A 15 +         │               (YAML task     (JSON offsets,
    Track B 60)          ▼                policies)      success/failure
                      prober.py              ▲            coefficients)
              (inverted-pair elicitation,    │                ▲
               JSON + tolerant parsing)      └── skew.json ───┘
                         │                          ▲
                         ▼                          │
                  providers/ ────► skew.py ────► report.py
             (async: anthropic,   (Skew, δ+/δ-,  (cards, matrix,
              openai + compat      bootstrap CI,  histogram,
              endpoints, gemini)   filters)       domain heatmap)
```

## Interpreting results — limitations

- **Skew is an internal-coherence measure, NOT deviation from truth.** A model with Skew 0 can still be badly calibrated against reality; a nonzero Skew tells you its good-outcome and bad-outcome estimates disagree with *each other* in a consistent direction.
- **Magnitudes are meaningful relative to other models** measured on the same scenario set with the same settings — not as absolute constants of the model.
- **The calibration offset is a starting correction, not a universal fix.** It was measured on this scenario distribution at one temperature; your domain may tilt differently. Re-measure on scenarios resembling your workload before trusting corrected numbers.
- Results vary with temperature and sampling; use multiple runs (`--runs 5`) and read the bootstrap CI, not just the point estimate.
- **Real-LLM results: not benchmarked in CI.** The test suite runs exclusively against mock providers with canned responses; any live numbers must come from your own `alignbias audit` runs.

## How this differs from other bias tools

DeepEval, Giskard, LLM BiasScope, and similar evaluation suites measure **social/content bias** — stereotypes, toxicity, demographic disparities in generated text. AlignBias measures something orthogonal: **directional probability tilt** — whether a model's numeric judgments under uncertainty systematically lean toward good or bad outcomes. A model can be spotless on content bias and still be a 10-point optimist that quietly inflates every success estimate your pipeline consumes (or a pessimist that sandbags every forecast). If your stack routes decisions on model-estimated probabilities — triage, risk scoring, forecasting, planning — this is the bias that hits you.

## Development

```bash
pip install -e ".[dev]"
pytest            # all tests use mock providers; no API calls, no keys needed
```

## License

Apache-2.0 for AlignBias code. Scenario data: see `assets/ATTRIBUTION.md` (OptimismBench, CC BY 4.0 method/paper; dataset release Apache-2.0).
