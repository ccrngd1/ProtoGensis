# DocProbe

**Will an agent actually comply with this?**

That's the layer DocProbe audits. markdownlint asks *"is this valid
Markdown?"* Vale asks *"is this good HUMAN prose?"* DocProbe asks whether an
AI agent reading your `AGENTS.md` / `CLAUDE.md` / `.cursorrules` can actually
find, understand, and follow the instructions in it — a different layer than
either tool. (Caveat: markdownlint's and Vale's rule sets evolve; we
characterize their *purpose* here rather than citing specific rules. The
arXiv findings below are safe to cite.)

## ⚠️ What DocProbe is (premise, stated honestly)

Instruction files are the **#1 document type coding agents read — 60.5% of
documentation interactions** (arXiv:2608.20195). That same paper provides
**no scoring rubric**, and no validated rubric for agent instruction files
exists anywhere. DocProbe does **not** "implement the paper's rubric" —
there is no such rubric to implement. Instead, DocProbe synthesizes
scattered, mostly-unvalidated guidance into an **explicit, falsifiable
opinion**: five dimensions, versioned in [`docprobe/rubric.md`](docprobe/rubric.md),
each labeled with how much evidence actually backs it. Disagree with a
threshold? The rubric is a file — argue with it, fork it, test it.

## Five dimensions, three evidence tiers

Evidence tiers drive the weights and are visible in every report:

| Dimension | Tier | Weight | Method | Basis |
|---|---|---|---|---|
| discovery_accessibility | **grounded** | 1.5 | deterministic | arXiv:2608.20195 — instruction files dominate agent doc reads; content must surface early |
| contradiction | **grounded** | 1.5 | LLM judge | arXiv:2608.11095 — contradictory/orphaned directives degrade compliance |
| hierarchy | partial | 1.0 | deterministic | structure aids retrieval; no direct instruction-file study |
| specificity | *opinionated* | 0.75 | LLM judge | DocProbe default: unverifiable directives can't be complied with |
| directive_density | *opinionated* | 0.75 | deterministic | DocProbe default: 0.25–0.60 directives/prose line |

arXiv:2608.13345 ("rules are brittle") is used as a **thematic analogy
only** in the density rationale — it is never treated as a scoring formula.

## Hybrid architecture

- **Deterministic parser** (no LLM, unit-tested for exact values):
  directive density, discovery accessibility, hierarchy. Runs fully offline.
- **LLM judge** for the semantic dimensions (specificity, contradiction):
  litellm → Bedrock, model pinned to `anthropic.claude-sonnet-4-5`,
  temperature 0, content-hash response cache, sections batched per call,
  optional `--prepass` Haiku screen. The judge returns A–F plus quoted
  passages and a one-line rationale per flag. The judge's system prompt is
  loaded **verbatim from [`docprobe/rubric.md`](docprobe/rubric.md)** — the
  rubric file is the product.
- A capped candidate-pair pre-filter keeps the pairwise contradiction check
  tractable on huge files (≤150 directives considered, ≤500 pairs).

## Install

Not published to any package registry — install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd doc-probe
pip install -e .
```

## Usage

```bash
docprobe scan                          # default instruction-file globs
docprobe scan AGENTS.md --no-llm      # deterministic dims only; fully offline
docprobe scan --glob '**/CLAUDE.md' --format json --output report.json
docprobe scan AGENTS.md --model bedrock/anthropic.claude-sonnet-4-5 --prepass
docprobe report AGENTS.md --no-llm    # markdown report
docprobe fix AGENTS.md                 # suggested edits per flag
```

- Exit **0** = scan completed — low scores are findings, not failures.
- Exit **2** = scan error.
- `--no-llm` never imports litellm and works with no network at all; the two
  LLM dimensions are listed under `skipped_dimensions`.
- `fix` mode policy (per arXiv:2608.11095): contradiction flags get an
  **attached rationale comment**, not deletion — an orphaned directive's fix
  *is* the proposed rationale.

Try it: `demo/run_demo.sh` scores a sanitized good/bad corpus offline.

## JSON output schema (stable)

Defined by pydantic models in `docprobe/models.py`. Additive changes only.

```
ScanResult
├─ docprobe_version: str
├─ rubric_version: str
├─ llm: { enabled, model, prepass_model, calls, cache_hits }
└─ files: [FileResult]
   ├─ path: str
   ├─ overall_grade: "A".."F" | null      # weighted by evidence tier
   ├─ overall_score: float | null          # 0–100
   ├─ dimensions: [DimensionScore]
   │  ├─ name, grade, score
   │  ├─ evidence_tier: grounded|partial|opinionated
   │  ├─ evidence_source: str              # citation or "opinionated default"
   │  ├─ weight, method: deterministic|llm
   │  └─ flags: [{passage, line, rationale, suggestion,
   │              related_passage, related_line}]
   ├─ skipped_dimensions: [str]            # e.g. LLM dims under --no-llm
   ├─ error: str | null
   └─ stats: {lines, prose_lines, directives, headings, words, ...}
```

## Approach notes & ambiguities

- Built against the pipeline brief's key-points restatement of the
  requirements; the canonical requirements file was unreadable in the build
  environment (permission denied), so where only the JSON "shape" was
  specified, the schema above is the documented contract and is
  test-enforced for stability.
- LLM dimension scores use letter-grade midpoints (A=95 … F=30) for
  aggregation; the letter is the primary signal.
- Python floor is 3.11 (spec says 3.12+; the build host runs 3.11.2 — no
  3.12-only syntax is used, so the floor was lowered rather than shipping
  untested metadata).
- The 02-19 DAEDALUS retrospective incident data was not accessible, so
  BLOG.md documents the *mechanism* (violation-type → dimension mapping,
  illustrated on the demo corpus) and is explicit about run vs illustrated.

## Tests

```bash
pip install -e ".[dev]"
pytest        # 58 tests; all LLM calls mocked; no network
```

MIT license. Rubric v1.0.0.
