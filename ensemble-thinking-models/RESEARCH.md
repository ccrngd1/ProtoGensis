# LLM Ensemble Methods — Research & Discussion Notes

_Context document for three protoGen projects. Compiled from DAEDALUS research + CC discussion on 2026-03-29._

---

## Origin

CC proposed the angle: traditional ML ensemble methods (bagging, boosting, stacking, voting classifiers) mapped to LLMs. The "wisdom of crowds" effect works in traditional ML because individual models make uncorrelated errors, so aggregation cancels noise. The question: does the same principle hold for LLMs?

## Existing Research Landscape

The field is active but almost entirely academic benchmark-focused. Nobody has written the practitioner take yet.

### Foundational Papers

| Paper | Authors/Year | Key Contribution | URL |
|-------|-------------|-----------------|-----|
| **Self-Consistency** | Wang et al., ICLR 2023 | Sample multiple CoT reasoning paths from same model, majority vote. The OG of LLM ensembling. | arxiv.org/abs/2203.11171 |
| **LLM-Blender** | Jiang et al., ACL 2023 | First multi-model ensemble framework. PairRanker (pairwise preferences) + GenFuse (blended response). No single LLM wins all examples. | arxiv.org/abs/2306.02561 |
| **More Agents Is All You Need** | Li et al., 2024 | Provocatively simple: sample-and-vote with more agent instances scales performance consistently. Just run the same LLM more times. | arxiv.org/abs/2402.05120 |
| **Mixture-of-Agents (MoA)** | Wang et al., Together AI, June 2024 | Layered architecture: each layer has multiple LLM agents taking all prior layer outputs as input. Weaker models collaborating via MoA can outperform stronger individual models. | arxiv.org/abs/2406.04692 |

### Survey Papers

| Paper | Year | Notes | URL |
|-------|------|-------|-----|
| **Harnessing Multiple LLMs: A Survey on LLM Ensemble** | Feb 2025 | First systematic review. Taxonomy of ensemble approaches. Has an Awesome list on GitHub (junchenzhi/Awesome-LLM-Ensemble). | arxiv.org/abs/2502.18036 |
| **Ensemble Large Language Models** | MDPI 2025 | Another comprehensive survey: techniques, benchmarks, practical considerations. | mdpi.com/2078-2489/16/8/688 |

### Newer/Niche Work

- **"Beyond Majority Voting"** (2025) — leverages higher-order information in LLM response aggregation instead of simple voting
- **Ranked Voting Self-Consistency** (ACL Findings 2025) — ranked choice voting improves on original self-consistency (arxiv.org/abs/2505.10772)
- **Efficient Dynamic Ensembling** (IJCAI 2025) — dynamically selects which LLMs to include instead of running all every time (addresses cost)
- **LLM-Synergy for Medical QA** (PMC 2025) — domain-specific ensemble for medical question answering (relevant to CC's healthcare AI work)
- **Collab: Controlled Decoding using MoA** (March 2025) — inference-time alignment via mixture of agent policies (arxiv.org/abs/2503.21720)
- **Distributed MoA for Edge Inference** (Dec 2024) — edge deployment of MoA (arxiv.org/abs/2412.21200)

---

## What Maps Cleanly from Traditional ML → LLMs

- Multiple LLMs answering same question + majority voting or judge model to pick best answer (already in practice, some coding benchmarks use this)
- MoA architectures where different LLMs critique/refine each other before final synthesis
- Self-consistency prompting = single-model ensembling (same model, multiple reasoning paths, majority vote)

## Where LLM Ensembles Differ from Traditional ML

- **Correlated errors:** LLM errors may be MORE correlated than traditional ensemble members (similar training data). This weakens the crowd effect.
- **Cost profile:** Running 5 LLMs is expensive. When is accuracy gain worth the latency and cost?
- **Quality-vs-consensus tension:** Sometimes the minority answer from a stronger model is correct and the "crowd" is wrong. Naive voting can make things worse.
- **Multi-agent systems** (like CABAL) are arguably a form of stacking, not voting. Specialized agents with different "expertise" collaborating.

## Gaps in the Literature (CC's Opportunity)

1. **Ensemble economics** — every paper shows accuracy gains, hand-waves cost. No practical ROI framework exists.
2. **False equivalence** — papers borrow ML ensemble terminology but skip the hard question of correlated failure modes in LLMs trained on similar data.
3. **Multi-agent as stacking** — research treats ensembles as "same question, multiple models, vote." Multi-agent systems are "different tasks, coordinated output." That bridge hasn't been written.
4. **When NOT to ensemble** — contrarian piece: when does a single strong model + better prompting beat an ensemble? When does consensus degrade quality?

---

## Three Approved Projects

### Project 1: "Do Thinking Models Think Better Together?"

**Core idea:** MoA architecture using models with NATIVE extended thinking / chain-of-thought: Opus (extended thinking), Nova Premier (deep reasoning mode), and a Mistral/reasoning-class model. Not prompted CoT — models that already deliberate internally.

**The compelling tension:** You're stacking two ensemble layers:
1. Each model's *internal* ensemble of reasoning paths (built-in CoT)
2. An *external* ensemble across models (MoA layer)

Does that second layer still add value when each model already did its own reasoning work? Does reasoning-on-top-of-reasoning compound, or hit diminishing returns?

**Vote vs Stitch (the real meat):**
- Voting works for discrete answers (code, classification, yes/no)
- For nuanced responses, stitching is harder:
  - Pick best whole response?
  - Extract strongest reasoning chain from each and synthesize?
  - Use one model's draft + another's reasoning as critique?
- Each approach is a different architecture with different tradeoffs

**Key experiment:** 10 hard prompts, run all three reasoning models, compare:
- Do they converge (95% agreement = ensemble isn't buying much)?
- Where they diverge, especially *which parts* of reasoning differ — that's where it gets powerful

**Format:** The exploration IS the blog post. Show methodology, results, what worked and what didn't. Practical, not academic.

### Project 2: "Practitioner's Guide to MoA on Bedrock"

**Core idea:** Hands-on implementation guide for MoA using smaller/cheaper Bedrock models (Nova Lite, Nova Pro, Haiku, Mistral, Llama).

**Unique angle nobody has published:**
- Real per-invocation cost comparisons across Bedrock model roster
- Latency measurements at each ensemble layer
- The actual ROI curve: at what point does running 3 cheap models cost more than one good model?
- Benchmark: cheap-model ensemble vs single strong model (Sonnet/Opus)

**Deliverables:** Working code, architecture diagrams, Bedrock API patterns. Practitioner-first, zero academic tone.

### Project 3: "Same Model, Different Minds"

**Core idea:** Same LLM with different system prompts/personas answers a question, then a central orchestrator synthesizes the final output. This is the CABAL pattern generalized.

**Why this is the most original:**
- Least explored in literature (research focuses on different models, not same model + different personas)
- CC is literally living this architecture with CABAL
- Connects multi-agent patterns to ensemble theory in a way nobody has written up

**Key questions to answer:**
- Does persona diversity create real answer diversity, or do you get superficial variation?
- Does the orchestrator "pick the best" or "synthesize something better"?
- When does this beat a single carefully-prompted call?
- How does the "committee makes mediocre decisions" problem manifest?

**Format:** Blog + experiment. Build it, test it, show what happens.

---

## CC's Positioning

- Left academia deliberately — these should be practitioner pieces, not papers
- Has direct lived experience with multi-agent ensembling (CABAL)
- AWS/Bedrock expertise makes the cost analysis credible
- Healthcare AI work provides domain-specific validation angles
