# PreCog Research Brief: AgentEvals — Production Reliability Testing for AI Agents

**Researched:** 2026-03-29
**Status:** ready
**For:** Protogenesis Week 13 build
**Pick brief:** /root/.openclaw/shared/builder-pipeline/candidates/pick-2026-03-27.md

---

## Overview

This week's Protogenesis pick builds a production eval harness for AI agent reliability, grounded in the fact that CABAL runs 8 autonomous agents with zero systematic evaluation. The build extends existing open-source eval frameworks (primarily LangChain's `agentevals`) with CABAL-specific test scenarios covering tool-call correctness, hallucination detection, handoff delivery reliability, and safety gate effectiveness.

Three converging signals make this timely:

1. **Solo.io's agentevals launch** (KubeCon Europe, March 25, 2026) — production-grade agent evaluation for Kubernetes-native agents, validating that the industry sees this as "the biggest unsolved problem" in agentic AI
2. **University of Waterloo coding study** (March 17, 2026) — top AI coding tools fail on 25% of structured output tasks, proving that "vibes-based" quality assessment is insufficient
3. **arXiv 2603.20101** (March 20, 2026) — "Pitfalls in Evaluating Interpretability Agents" reveals that LLM-based agents may appear to work by memorizing published findings rather than genuinely reasoning

---

## 1. The Two "agentevals" — Important Distinction

There are **two different projects** both called "agentevals":

### LangChain agentevals (langchain-ai/agentevals)

- **What:** Open-source Python package for evaluating agent *trajectories* — the sequence of tool calls and messages an agent produces
- **Focus:** Did the agent call the right tools, in the right order, with the right arguments?
- **How it works:**
  - Records agent execution as a trajectory (list of messages + tool calls)
  - Compares actual trajectory against expected/reference trajectory
  - Supports both **deterministic matching** (exact tool call comparison) and **LLM-as-judge** evaluation (semantic equivalence)
  - Integrates with LangSmith for logging and analysis
- **Key evaluators:**
  - `trajectory_match` — Compares actual vs expected tool call sequences
  - `trajectory_llm_match` — Uses an LLM judge to evaluate if trajectories are semantically equivalent
  - Configurable `tool_args_match_mode` for flexible argument comparison (exact, subset, superset, ignore)
- **Best for:** Testing specific agent behaviors against known-good reference trajectories

### Solo.io agentevals (KubeCon 2026 launch)

- **What:** Production benchmarking framework for Kubernetes-native AI agents (part of the kagent ecosystem)
- **Focus:** Continuous quality scoring of agent workflows in production — accuracy, latency, safety, hallucination
- **How it works:**
  - Collects traces from agent executions (tool calls, LLM responses, timing data)
  - Runs evaluators against traces to detect hallucinations, measure accuracy, and score safety
  - Designed for CI/CD integration — run evals as part of deployment pipelines
  - Integrates with kagent (CNCF Sandbox project) for Kubernetes agent orchestration
- **Best for:** Ongoing production monitoring of agent quality at scale

### Which One for CABAL?

**LangChain agentevals is the better foundation for our build.** Reasons:
- CABAL agents run on OpenClaw, not Kubernetes — kagent integration isn't useful
- We need trajectory-level evaluation (did the agent make the right tool calls?) more than production trace scoring
- LangChain agentevals is framework-agnostic — it evaluates message/tool-call sequences, not LangChain-specific structures
- The trajectory format (list of messages with role + tool_calls) maps cleanly to OpenClaw agent outputs

However, Solo.io's conceptual framework (continuous scoring, safety gates, hallucination detection) should inform our eval *dimensions* even if we don't use their code.

---

## 2. Waterloo Study — The 25% Failure Rate

**Paper:** University of Waterloo, March 2026
**Key finding:** Even the most advanced AI coding models fail on ~25% of structured output tasks

### Methodology
- Evaluated **11 LLM models** across **18 structured output benchmarks**
- Focus: reliability of structured outputs (JSON schemas, code generation with specific formats, API response formatting)
- Tests covered: schema compliance, format consistency, edge case handling

### Relevant Findings for CABAL Evals
- **Best models (GPT-4o, Claude 3.5) still fail ~25% of the time** on structured tasks — this isn't a "bad model" problem, it's fundamental to current LLM architecture
- **Failure modes cluster around:** edge cases in nested structures, inconsistent schema adherence under complex prompts, silent format corruption (output looks valid but contains subtle structural errors)
- **Key insight for us:** If top models fail 25% of structured tasks in controlled benchmarks, production agents handling real-world complexity likely have *higher* failure rates. We don't know CABAL's number because we've never measured it.

### What This Means for Our Eval Harness
- Must test structured outputs (tool call arguments, JSON payloads, file paths) — not just "did the agent respond?"
- Need regression detection: track failure rates over time, not just pass/fail per run
- Silent corruption is harder to catch than total failure — evals need structural validators, not just content checks

---

## 3. arXiv 2603.20101 — Pitfalls in Evaluating Interpretability Agents

**Title:** "Pitfalls in Evaluating Interpretability Agents"
**Authors:** Haklay, Prakash, Pandey, Torralba, Mueller (MIT, Northeastern)

### Core Argument
LLM-based agents that appear to perform research tasks (running experiments, analyzing results) may actually be:
1. **Memorizing published findings** from training data rather than genuinely discovering them
2. **Informed guessing** based on pattern-matching rather than rigorous analysis
3. **Reproducing known results** without the ability to generalize to novel problems

### Pitfalls Identified
1. **Contamination from training data** — Agent "discovers" a result that was in its training set. Looks like reasoning, is actually recall.
2. **Benchmark overfitting** — Agents score well on published benchmarks because examples leak into training data
3. **Evaluation circularity** — Using an LLM to judge another LLM's reasoning can inherit the same biases

### What This Means for CABAL Evals
- **Don't trust LLM-as-judge exclusively.** Our eval harness should use deterministic checks wherever possible (did the file get created? does the JSON parse? was the API called with correct params?) and reserve LLM-as-judge for genuinely subjective assessments.
- **Test novel scenarios, not just replays.** If we only test agents on tasks they've seen before (or that are in their training data), we're measuring recall, not capability.
- **Separate "looks right" from "is right."** An agent can produce a plausible-looking research summary that's actually confabulated. Evals need to verify factual claims, not just fluency.

---

## 4. Eval Dimensions for Production Agent Fleets

Synthesizing across the research landscape, here are the dimensions that matter for evaluating production agents like CABAL:

### Dimension 1: Tool-Call Correctness
- **What:** Did the agent call the right tool, with the right arguments, at the right time?
- **How to test:** Trajectory matching (LangChain agentevals), argument validation, schema compliance
- **CABAL scenarios:**
  - Agent calls WikiJS GraphQL API with correct query syntax
  - Agent creates files at expected paths with valid content
  - Agent uses correct git commands in proper sequence
  - Tool arguments contain no hallucinated paths, URLs, or API endpoints

### Dimension 2: Hallucination Detection
- **What:** Did the agent fabricate information, cite non-existent sources, or claim to have done things it didn't do?
- **How to test:** Fact-checking against ground truth, source verification, claim extraction + validation
- **CABAL scenarios:**
  - PreCog research contains valid, accessible URLs (not hallucinated links)
  - Agent status reports accurately reflect actual system state (not confabulated)
  - Code generation references real APIs/libraries, not made-up ones
  - Agent doesn't claim to have completed actions it failed or skipped

### Dimension 3: Handoff Delivery Reliability
- **What:** When an agent produces an output for another agent (handoff), does it arrive complete, well-formed, and on time?
- **How to test:** File existence checks, schema validation on handoff JSON, content completeness scoring
- **CABAL scenarios:**
  - Research handoffs contain all required fields (from, type, task, priority, timestamp)
  - Builder pipeline outputs follow the expected format (research → requirements → build)
  - Cross-agent references resolve (if agent A references agent B's output, it exists)
  - Handoff timing: was research delivered within the expected SLA?

### Dimension 4: Safety Gate Effectiveness
- **What:** Do agents respect boundaries? Do they avoid destructive actions, refuse inappropriate requests, and escalate when uncertain?
- **How to test:** Red-team scenarios (deliberately adversarial inputs), boundary condition testing, escalation verification
- **CABAL scenarios:**
  - Agent refuses to execute destructive commands (rm -rf, DROP TABLE)
  - Agent escalates to CC when uncertain rather than guessing
  - Agent stays within its declared scope (PreCog doesn't try to deploy code, NetOps doesn't try to write blog posts)
  - Secrets/credentials never appear in agent outputs or logs

### Dimension 5: Task Completion Rate
- **What:** Of tasks assigned, how many reach successful completion? What's the distribution of failure modes?
- **How to test:** End-to-end test scenarios with known-good outcomes, tracking completion/failure/timeout/retry rates
- **CABAL scenarios:**
  - Heartbeat tasks: does the agent correctly identify when action is needed vs HEARTBEAT_OK?
  - Research tasks: does the output contain all requested sections?
  - Build tasks: does the generated code compile/run?
  - Publish tasks: does the content actually reach the destination (Medium, WikiJS, etc.)?

### Dimension 6: Efficiency
- **What:** How many steps/tokens/API calls does the agent use to complete a task? Are there unnecessary loops or redundant calls?
- **How to test:** Token counting, step counting, trajectory length comparison against optimal paths
- **CABAL scenarios:**
  - Agent doesn't make redundant API calls (e.g., reading the same file multiple times)
  - Research tasks don't over-search (diminishing returns detection)
  - Heartbeat processing completes within expected time bounds
  - Token efficiency: comparable outcomes with fewer tokens over time

---

## 5. Eval Framework Landscape (March 2026)

| Framework | Type | Best For | Limitations | License |
|-----------|------|----------|-------------|---------|
| **LangChain agentevals** | OSS library | Trajectory evaluation, tool-call matching | No production monitoring, no UI dashboard | MIT |
| **Solo.io agentevals** | OSS framework | K8s-native production agent scoring | Requires kagent/K8s ecosystem | Apache 2.0 |
| **DeepEval** | OSS + Cloud | Pytest-style LLM testing, 14+ metrics | Heavier dependency footprint, some features cloud-only | Apache 2.0 |
| **RAGAS** | OSS library | RAG evaluation (retrieval + generation quality) | Narrow focus on RAG, no agent trajectory eval | Apache 2.0 |
| **Braintrust** | Cloud platform | Production LLM eval with team collab | Cloud-dependent, paid tiers for features | Proprietary |
| **LangSmith** | Cloud platform | Full LLM observability + evals | Vendor lock-in to LangChain ecosystem | Proprietary |
| **Patronus AI** | Cloud platform | Hallucination detection, safety testing | Enterprise-focused, expensive | Proprietary |
| **AWS Agent Evaluation** | OSS library | Testing virtual agents on AWS | AWS-centric design | Apache 2.0 |
| **Promptfoo** | OSS CLI | Prompt testing and comparison | Limited agent trajectory support | MIT |
| **Maxim AI** | Cloud platform | Multi-modal agent eval | Cloud-dependent | Proprietary |

### Recommended Stack for CABAL

**Core:** LangChain `agentevals` for trajectory evaluation mechanics
**Extension:** Custom CABAL-specific evaluators for handoff validation, scope compliance, and safety gates
**Observation:** Lightweight custom logging (JSON-structured trace files) — no need for LangSmith/Braintrust overhead
**Execution:** pytest-based test runner (consistent with Python ecosystem, easy CI/CD integration)
**Dashboard:** Simple markdown reports or WikiJS page (CABAL can update its own eval dashboard)

---

## 6. CABAL-Specific Test Scenarios

### Tier 1: Critical (Must Ship)

| Scenario | Eval Type | Expected Behavior |
|----------|-----------|-------------------|
| **Heartbeat triage** | Deterministic | Given empty handoff dir + unchanged interests → HEARTBEAT_OK |
| **Heartbeat with new handoff** | Deterministic | Given new request-*.json in handoff dir → process it, move to done/ |
| **Tool-call schema compliance** | Deterministic | All WikiJS GraphQL mutations use valid syntax and required fields |
| **Handoff file format** | Deterministic | All handoff JSON files parse, contain required fields, valid types |
| **File path validity** | Deterministic | No hallucinated file paths in agent tool calls |
| **Safety: no destructive commands** | Red-team | Agent never executes rm -rf, DROP, DELETE on production paths |
| **Safety: no credential leakage** | Deterministic | API keys/tokens never appear in agent text outputs |

### Tier 2: Important (Should Ship)

| Scenario | Eval Type | Expected Behavior |
|----------|-----------|-------------------|
| **Research completeness** | LLM-as-judge + structural | Research output contains: overview, findings, sources, status |
| **Cross-agent scope compliance** | Deterministic | Agent only calls tools/APIs within its declared scope |
| **Handoff timing SLA** | Deterministic | Research handoff delivered within 2 heartbeat cycles of request |
| **WikiJS publish success** | End-to-end | After publish workflow, page exists at expected path with correct content |
| **Research source validity** | HTTP probe | All URLs cited in research actually resolve (not 404) |

### Tier 3: Nice-to-Have (Stretch Goals)

| Scenario | Eval Type | Expected Behavior |
|----------|-----------|-------------------|
| **Token efficiency tracking** | Quantitative | Track tokens per task type, alert on >2σ deviation |
| **Trajectory optimization** | Comparative | Compare agent trajectories to optimal paths, flag inefficiency |
| **Regression detection** | Statistical | Detect degradation in task completion rate across agent versions/models |
| **Novel scenario generalization** | LLM-as-judge | Agent handles tasks not seen in test suite with reasonable quality |

---

## 7. Architectural Decisions for the Eval Harness

### Decision 1: Test Runner Framework
**Choice: pytest**
- Standard Python testing framework, everyone knows it
- DeepEval already uses pytest-style patterns — proven model
- Easy to add to CI/CD, familiar output format
- Fixtures can set up mock agent environments (fake handoff dirs, mock APIs)

### Decision 2: Trajectory Capture Format
**Choice: OpenAI-compatible message format (role + content + tool_calls)**
- LangChain agentevals already uses this format
- Maps naturally to OpenClaw agent outputs
- Can be captured by wrapping agent API calls with a logging interceptor
- JSON-serializable for storage and comparison

### Decision 3: Deterministic vs LLM-as-Judge
**Choice: Deterministic first, LLM-as-judge only where necessary**
- Per arXiv 2603.20101 warnings, LLM judges can be unreliable
- Most CABAL eval scenarios CAN be tested deterministically (file exists? JSON parses? API returned 200?)
- Reserve LLM-as-judge for genuinely subjective assessments (research quality, writing quality)
- When using LLM-as-judge, always log the judge's reasoning for human review

### Decision 4: Where to Run Evals
**Choice: Separate eval pipeline, not inline with agent execution**
- Evals should run against recorded agent traces, not during live execution (avoids performance impact)
- Can replay historical agent sessions for regression testing
- Supports A/B comparison when changing models or prompts
- Scheduled eval runs (daily or per-deployment) via cron or n8n workflow

### Decision 5: Results Storage
**Choice: JSON + markdown summary**
- Raw results as JSON (machine-readable, diff-friendly)
- Summary as markdown (human-readable, can publish to WikiJS)
- Track results over time for trend analysis
- No external database needed — files in git are sufficient for CABAL's scale

### Decision 6: Scope of First Release
**Choice: Start with Tier 1 scenarios for 2-3 agents, expand from there**
- Focus on PreCog and Main (highest heartbeat frequency, most handoffs)
- Validate the harness architecture with well-understood agent behaviors
- Expand to remaining agents after the pattern is proven
- Blog post can show real data from these first evals

---

## 8. Implementation Sketch

```
cabal-evals/
├── pyproject.toml              # Dependencies: agentevals, pytest, httpx
├── README.md                   # Usage, architecture, contributing
├── conftest.py                 # Shared fixtures (mock dirs, API mocks)
├── traces/                     # Recorded agent trajectories for replay
│   ├── precog-heartbeat-ok.json
│   ├── precog-handoff-process.json
│   └── main-heartbeat-triage.json
├── evaluators/
│   ├── tool_call.py            # Tool-call schema validation
│   ├── handoff.py              # Handoff format + delivery checks
│   ├── safety.py               # Destructive command + credential leak detection
│   ├── hallucination.py        # URL verification, path existence, claim checking
│   └── completeness.py         # Output structural completeness scoring
├── tests/
│   ├── test_heartbeat.py       # Heartbeat triage scenarios
│   ├── test_handoff.py         # Handoff delivery scenarios
│   ├── test_tool_calls.py      # Tool-call correctness scenarios
│   ├── test_safety.py          # Safety gate scenarios
│   └── test_research.py        # Research output quality scenarios
├── report/
│   └── generate.py             # Markdown report generator
└── scripts/
    ├── capture_trace.py        # Record agent execution trace
    └── run_evals.sh            # Full eval suite runner
```

### Core Flow
1. **Capture:** Record agent execution traces (tool calls, messages, outputs) during normal operation
2. **Store:** Save traces as JSON files (one per execution)
3. **Evaluate:** Run pytest suite against captured traces
4. **Report:** Generate markdown summary with pass/fail rates, failure details, trends
5. **Publish:** Optionally push report to WikiJS eval dashboard

---

## Sources

1. [LangChain agentevals (GitHub)](https://github.com/langchain-ai/agentevals) — Trajectory evaluation framework
2. [Solo.io agentevals announcement](https://www.solo.io/press-releases/introducing-new-agentic-open-source-project-agentevals) — KubeCon Europe 2026 launch
3. [Solo.io blog: Agentic Quality Benchmarking](https://www.solo.io/blog/agentic-quality-benchmarking-with-agent-evals) — Technical deep-dive on eval methodology
4. [University of Waterloo: AI coding tools fail 25%](https://uwaterloo.ca/news/media/top-ai-coding-tools-make-mistakes-one-four-times) — March 2026 structured output study
5. [arXiv 2603.20101: Pitfalls in Evaluating Interpretability Agents](https://arxiv.org/abs/2603.20101) — Memorization vs reasoning risks
6. [LangChain: How we build evals for Deep Agents](https://blog.langchain.com/how-we-build-evals-for-deep-agents) — Trajectory evaluation patterns
7. [LangSmith trajectory evaluation docs](https://docs.langchain.com/langsmith/trajectory-evals) — Practical implementation guide
8. [AWS blog: Evaluating AI agents — real-world lessons](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-real-world-lessons-from-building-agentic-systems-at-amazon) — Production eval dimensions from Amazon
9. [QuantumBlack/McKinsey: Evaluations for the agentic world](https://medium.com/quantumblack/evaluations-for-the-agentic-world-c3c150f0dd5a) — Framework for agent eval dimensions
10. [DeepEval alternatives 2026 (Braintrust)](https://www.braintrust.dev/articles/deepeval-alternatives-2026) — Framework comparison landscape
11. [Top 5 AI Agent Evaluation Platforms 2026](https://www.getmaxim.ai/articles/top-5-ai-agent-evaluation-platforms-in-2026) — Market overview
12. [The New Stack: Solo.io agentevals](https://thenewstack.io/soloio-agentevals-evaluates-ai-agents) — Technical analysis of Solo.io approach

---

## Open Questions for Build Phase

- Should the eval harness be a standalone repo (`cabal-evals/`) or embedded in the OpenClaw workspace?
- Does CC want evals to run automatically (via n8n cron — meta-appropriate given last week's research!) or manually triggered?
- Should we expose eval results as a WikiJS dashboard that CABAL updates, or keep it as files in git?
- How many historical traces do we need before trend analysis becomes meaningful? (Estimate: ~50 traces per agent per scenario)
- Should the blog post include real CABAL eval data (showing actual failure rates), or sanitized/synthetic examples?
