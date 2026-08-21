# DocProbe Scoring Rubric — v1.0.0

This file is DocProbe's **falsifiable opinion** about what makes an
instruction file agent-friendly. It is shipped in-repo and versioned so it can
be argued with, tested against, and revised. **No validated rubric for agent
instruction files exists** — the primary paper (arXiv:2608.20195) established
that instruction files are the #1 document type agents read (60.5% of
documentation interactions) but provides **no scoring rubric**. DocProbe
synthesizes scattered, mostly-unvalidated guidance into the explicit criteria
below. Where a criterion has empirical support, the source is cited; where it
does not, it is labeled an opinionated default.

The verbatim text of the "LLM judge instructions" sections below is sent as
the system prompt to the judge model for the two semantic dimensions.

## Evidence tiers and weights

| Tier | Weight | Meaning |
|---|---|---|
| grounded | 1.5 | direct empirical support in a cited paper |
| partial | 1.0 | related but indirect evidence |
| opinionated | 0.75 | DocProbe's default opinion, no validated evidence |

## Dimension 1: discovery_accessibility (grounded, deterministic, weight 1.5)

Grounding: arXiv:2608.20195 — instruction files dominate agent documentation
reads, so what an agent will actually see (early lines, skimmable structure,
bounded length) matters most. The *thresholds* are DocProbe's choices:

- First actionable directive within the first 40 lines.
- Ideal file length ≤ 300 lines; hard ceiling 1000 lines.
- Multi-screen files must have headings.

## Dimension 2: contradiction (grounded, LLM-judged, weight 1.5)

Grounding: arXiv:2608.11095 — contradictory and orphaned (rationale-free)
directives measurably degrade compliance, and *attaching rationale* is
preferred over deleting a directive.

### LLM judge instructions — contradiction

You are auditing an AI-agent instruction file for contradictions. You will be
given candidate directive pairs (and section text for context). For each real
problem, report:

- Two directives **conflict** if an agent cannot satisfy both in the same
  situation (e.g., "always use tabs" vs "indent with 4 spaces").
- A directive is **orphaned** if it is absolute ("never", "must") yet gives no
  rationale and no rationale is inferable from context — agents deprioritize
  rules they cannot justify.
- Do NOT flag pairs that merely discuss the same topic, apply to disjoint
  scopes (e.g., "tests use X" vs "docs use Y"), or where one is an explicit
  exception to the other.

Grade the dimension A–F:
- A: no conflicts, no orphaned absolutes.
- B: no conflicts; 1–2 orphaned absolutes.
- C: 1 conflict or 3–5 orphaned absolutes.
- D: 2 conflicts or a pattern of unexplained absolutes.
- F: 3+ conflicts; the file gives inconsistent instructions.

For each flag, quote both passages exactly and give a one-line rationale.
Prefer suggesting an attached rationale comment over deleting a directive.

## Dimension 3: hierarchy (partial, deterministic, weight 1.0)

Partial support: structured documents aid retrieval in general, but no study
ties heading discipline in instruction files to agent compliance. Criteria:
consecutive heading levels, a single h1, no empty sections, ≤ 4 levels deep.

## Dimension 4: specificity (opinionated, LLM-judged, weight 0.75)

Opinionated default: an agent can only comply with a directive it can check.
"Write good tests" is unfalsifiable; "every new function gets a test that
exercises its error path" is checkable. No validated evidence ranks
specificity against compliance — this is DocProbe's opinion.

### LLM judge instructions — specificity

You are auditing an AI-agent instruction file for specificity. For each
section you are given, identify directives an agent could not verify it has
followed:

- Vague quality words with no criterion: "clean", "good", "appropriate",
  "properly", "best practices".
- Unbounded scope: "handle all edge cases", "be thorough".
- Missing referents: "use the standard format" (which standard?), "follow the
  usual process" (defined where?).
- Do NOT flag directives that are concrete and checkable, links to concrete
  definitions elsewhere, or genuinely judgment-based guidance that is honest
  about being judgment-based.

Grade the dimension A–F:
- A: essentially all directives checkable.
- B: a few vague directives in otherwise concrete text.
- C: vague and concrete directives roughly balanced.
- D: mostly vague; an agent must guess what compliance means.
- F: the file is aspirational prose, not instructions.

For each flag, quote the passage exactly, give a one-line rationale, and
suggest a concrete rewrite.

## Dimension 5: directive_density (opinionated, deterministic, weight 0.75)

Opinionated default: 0.25–0.60 directives per prose line. Below the band the
file is narrative an agent cannot act on; above it, a wall of rules. The
"rules are brittle" framing borrows a **thematic analogy only** from
arXiv:2608.13345 — that paper supplies no scoring formula and none is claimed.
Vague qualifiers ("as appropriate", "when possible") discount directives.

## Aggregation

overall = Σ(dimension_score × weight) / Σ(weight), then banded:
A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, else F. Under `--no-llm` only the three
deterministic dimensions aggregate, and the skipped dimensions are listed in
the output.
