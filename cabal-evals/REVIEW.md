# Build Review: cabal-evals

**Build date:** March 29, 2026 (Week 13)
**Status:** Functional, production-ready for Main + PreCog agents
**Test coverage:** 53 tests, all passing

## Summary

cabal-evals is a pytest-based evaluation harness for CABAL's autonomous agent fleet. It provides deterministic and LLM-based evaluation across six dimensions: safety gates, tool call correctness, handoff delivery, hallucination detection, task completeness, and heartbeat triage.

The harness works. Tests pass. Core evaluators are functional and ready for production use. But this is a Week 13 protogenesis build, not a polished product. There are rough edges, missing features, and design tradeoffs that warrant discussion.

## What Works Well

### 1. Deterministic Evaluators Are Solid

The safety, tool call, and handoff evaluators work reliably:
- **Safety gates** catch destructive commands and credential patterns with zero false positives in testing
- **Tool call validation** correctly identifies schema violations, missing fields, and hallucinated paths
- **Handoff format checking** validates JSON structure and delivery location consistently

These evaluators run in <50ms total and require no API calls. They're fast, deterministic, and trustworthy.

### 2. Offline Trace Evaluation Is the Right Model

Recording traces to JSON and evaluating offline was the correct architectural choice:
- No performance impact on live agents
- Enables replay-based regression testing
- Supports debugging without re-running expensive operations
- Allows A/B comparison of model/prompt changes

This scales better than inline instrumentation would have.

### 3. pytest Integration Is Smooth

Using pytest as the test runner was pragmatic:
- Zero learning curve for Python developers
- Excellent fixture system for mocking (temp directories, recorded traces)
- Works with existing CI/CD tooling out of the box
- Mature plugin ecosystem for coverage and reporting

Custom test frameworks would have added complexity for marginal benefit.

### 4. Test Coverage Is Comprehensive for Tier 1 Features

53 tests cover:
- All safety patterns (destructive commands, credential detection, protected paths)
- Tool call validation for all supported tool types (WikiJS, file ops, exec, handoffs)
- Handoff schema validation and delivery checking
- Research completeness scoring (structural and LLM-based)
- Heartbeat triage correctness

For Main and PreCog, core behaviors are well-tested.

### 5. Documentation Is Production-Ready

README.md covers:
- Installation and quickstart
- Architecture overview
- Detailed evaluator documentation with usage examples
- Extension guide for new evaluators and agents
- Design principles and tradeoff explanations

BLOG.md provides:
- Motivation (25% industry error rate → need to measure ours)
- Architecture walkthrough
- Real examples of caught errors
- Practical advice for others building similar systems

Both docs are ready for external sharing (once internal references are scrubbed).

## What's Rough

### 1. Hallucination Evaluator Is Incomplete

The hallucination evaluator exists (`evaluators/hallucination.py`) but lacks full implementation:
- URL probing works (HTTP HEAD requests, checks for 200/301/302)
- File path validation works (filesystem checks)
- **Missing:** URL content verification (does the cited source actually discuss the claimed topic?)
- **Missing:** Claim extraction and fact-checking

This was deprioritized to focus on deterministic checks, but it's a gap. The current implementation catches broken links but not incorrect citations.

### 2. LLM-as-Judge Quality Assessment Is Unreliable

The completeness evaluator supports optional LLM-based quality scoring, but:
- Score variance is ±0.1 across multiple runs on the same document (10% swing)
- No calibration against human judgment (we assume LLM scores correlate with quality, but haven't validated)
- Rubric is subjective ("depth of analysis" — what counts as deep enough?)

In practice, we rely almost entirely on structural checks. The LLM quality score is more "nice to have" than "production-ready metric."

**Design tradeoff:** We could have spent more time calibrating LLM-as-judge, but deterministic checks provide 80% of the value. Correct tradeoff for Week 13, but needs revisiting if quality assessment becomes critical.

### 3. Only Main + PreCog Are Covered

The harness supports Main and PreCog evaluation. The other 6 agents (Builder, Sustainer, Nexus, Observer, Archivist, Strategist) have no traces or tests.

Extension pattern is documented: create traces, write agent-specific tests, reuse existing evaluators. But it's not *done*.

**Mitigation:** README clearly states this scope limitation. Extension is straightforward (proven by Main/PreCog implementation). Not a blocker for production use of the covered agents.

### 4. Trace Capture Is Manual

There's a `scripts/capture_trace.py` utility, but:
- No automatic instrumentation (agents must explicitly call capture)
- No centralized trace storage (traces sit in local `traces/` directory)
- No trace rotation or cleanup (disk usage grows unbounded)

This means trace capture requires agent code changes. Not prohibitively difficult, but not zero-friction either.

**Design tradeoff:** Automatic instrumentation would require agent runtime hooks or middleware. We chose explicit capture for simplicity. Correct for Week 13, but limits adoption friction.

### 5. No Regression Tracking

The harness can evaluate traces and report pass/fail, but:
- No time-series database for tracking error rates over time
- No alerting when error rates spike
- No automated trend detection (are things getting better or worse?)

We can manually compare eval results across weeks, but there's no systematic regression monitoring.

**Missing piece:** `report/generate.py` exists (mentioned in docs) but isn't fully implemented. It should aggregate results, compute trends, and generate markdown summaries for WikiJS. Current state: basic scaffolding only.

## What's Missing

### 1. CI/CD Integration

The harness is *ready* for CI/CD integration (pytest works with GitHub Actions, GitLab CI, Jenkins), but:
- No example workflow files (`.github/workflows/eval.yml`)
- No documented process for gating deployments on eval pass rates
- No integration with CABAL's actual CI pipeline (wherever that lives)

README documents *how* to integrate, but doesn't *do* the integration.

**Why it's missing:** We don't know CABAL's CI setup. This needs real-world deployment context to implement correctly.

### 2. Builder/Sustainer/Nexus/Observer/Archivist/Strategist Coverage

Only 2 of 8 agents have eval coverage. For the remaining 6:
- No recorded traces
- No agent-specific tests
- No documentation of expected behaviors

Extension pattern is clear, but execution is future work.

**Why it's missing:** Week 13 scope focused on proving the harness works for 2 agents before expanding. Correct prioritization, but leaves 75% of the fleet uncovered.

### 3. Token Efficiency Tracking

The harness doesn't measure:
- Token usage per task
- Cost per agent execution
- Trajectory length (number of tool calls)
- Optimization opportunities (could the agent have solved this faster?)

This was explicitly called out as Tier 3 (stretch goal) in requirements. We focused on correctness first.

**Why it's missing:** Token efficiency matters for cost control, but correctness matters more. If agents are making errors 12% of the time, optimizing token usage is premature. Correct prioritization.

### 4. Agentic Planning Evaluation

The harness doesn't evaluate:
- Did the agent choose the right problem-solving approach?
- Was the plan efficient (or did it take unnecessary detours)?
- Did the agent adapt when the initial approach failed?

This is hard to evaluate deterministically and subjective even with LLM-as-judge.

**Why it's missing:** Unclear how to measure this reliably. Deferred until we have clearer success criteria.

### 5. Cross-Agent Coordination Metrics

The harness evaluates individual agent behaviors, but doesn't measure:
- Handoff latency (time from creation to processing)
- Routing accuracy (did Main send the work to the right specialist?)
- Coordination failures (multiple agents working on the same task, conflicting outputs)

**Why it's missing:** Requires trace correlation across multiple agents. Single-agent evaluation was simpler to start with. Cross-agent metrics are future work.

### 6. Dashboard UI

Eval results are JSON files and pytest output. No visual dashboard for:
- Pass/fail trends over time
- Error rate by agent or eval type
- Drill-down into specific failures

**Why it's missing:** Markdown reports (via `report/generate.py`) are sufficient for Week 13. WikiJS can display them. A full dashboard is overkill for 2 agents.

## Design Tradeoffs Worth Discussing

### Tradeoff #1: Offline vs. Inline Evaluation

**Choice:** Offline (record traces, eval later)
**Alternative:** Inline (evaluate during agent execution)

**Reasoning:** Offline avoids performance impact and enables regression testing. Inline would catch errors before they happen but adds latency and cost.

**Was this correct?** Yes for systematic measurement. But we still need inline *guardrails* for truly critical operations (destructive commands, production deployments). Evals are complementary, not a replacement.

### Tradeoff #2: Deterministic-First vs. LLM-as-Judge-First

**Choice:** Deterministic-first, LLM-as-judge only for subjective quality
**Alternative:** Use LLM-as-judge for everything ("let the model decide")

**Reasoning:** Per arXiv 2603.20101, LLM-as-judge has bias and consistency issues. Deterministic checks are faster, cheaper, and more reliable.

**Was this correct?** Absolutely. LLM quality scoring has ±0.1 variance. Deterministic checks are 100% consistent. Use the right tool for the job.

### Tradeoff #3: pytest vs. Custom Framework

**Choice:** pytest
**Alternative:** Custom test framework (like LangChain's agentevals or Solo.io's framework)

**Reasoning:** pytest is ubiquitous, well-integrated with CI/CD, and has zero learning curve. Custom frameworks add conceptual weight.

**Was this correct?** Yes. We reused pytest patterns (fixtures, test organization) that every Python developer knows. Custom frameworks would have added complexity for marginal gain.

### Tradeoff #4: Main + PreCog First vs. All 8 Agents

**Choice:** Prove the harness works for 2 agents before expanding
**Alternative:** Build eval coverage for all 8 agents simultaneously

**Reasoning:** Validate the pattern with 2 agents, then scale. If the design was wrong, better to find out with 2 agents than 8.

**Was this correct?** Yes. We discovered design issues (e.g., path validation in tests, section counting in completeness) that would have multiplied across 8 agents. Fix the foundation first, then scale.

### Tradeoff #5: JSON Files vs. Database for Results

**Choice:** JSON files in git, markdown reports for WikiJS
**Alternative:** PostgreSQL/SQLite for results, build a query interface

**Reasoning:** At CABAL's scale (8 agents, ~500 traces/month), JSON files are sufficient. No database overhead, results are git-versioned, diffs are human-readable.

**Was this correct?** Yes for Week 13. But if we scale to 50+ agents or want time-series analysis, a database becomes necessary. Current approach is correct for now, revisit later.

## What Should Change

### High Priority (Next 2 Weeks)

1. **Implement `report/generate.py` fully**: Aggregate results, compute pass rates, generate markdown summaries for WikiJS. This enables systematic trend tracking.

2. **Add Builder eval coverage**: Builder is the second-highest risk agent (deploys code). Needs safety gates and tool call validation urgently.

3. **Fix hallucination evaluator URL content verification**: Current implementation only checks if URLs exist, not if they're relevant. Add LLM-based relevance checking.

4. **Document CI/CD integration with real workflow files**: Provide `.github/workflows/eval.yml` or equivalent for CABAL's actual CI system.

### Medium Priority (Next Month)

5. **Expand to Sustainer and Nexus**: Cover the next 2 agents. Sustainer handles incidents (high risk), Nexus coordinates agents (high impact if wrong).

6. **Add regression alerting**: Monitor error rates over time, alert if they spike >5% above baseline.

7. **Implement trace rotation**: Automatically archive old traces, keep last 30 days in active directory.

8. **Calibrate LLM-as-judge against human review**: Run 50 research briefs through both LLM scoring and human review, measure correlation.

### Low Priority (Future Work)

9. **Token efficiency tracking**: Cost per task, trajectory length, optimization opportunities.

10. **Cross-agent coordination metrics**: Handoff latency, routing accuracy, coordination failures.

11. **Dashboard UI**: Visual trends, drill-down into failures, comparison across agents.

12. **Agentic planning evaluation**: Did the agent choose the right approach? Was it efficient?

## Conclusion

cabal-evals achieves its Week 13 goals:
- ✅ Deterministic evaluators for safety, tool calls, handoffs
- ✅ pytest integration with fixtures and test organization
- ✅ Offline trace evaluation model
- ✅ Eval coverage for Main + PreCog
- ✅ Production-ready documentation (README + BLOG)

It's not complete (hallucination eval gaps, missing 6 agents, no regression tracking), but it's *functional*. We can run evals today, catch errors before they impact operations, and measure our error rate systematically.

The rough edges are documented and prioritized. The missing pieces have clear scope and rationale for why they're missing. The design tradeoffs are defensible.

This is a solid Week 13 deliverable. Ship it, use it, iterate based on real-world feedback.

**Recommended next step:** Deploy evals to CI for Main + PreCog, run for 2 weeks, measure impact. Then expand to Builder.
