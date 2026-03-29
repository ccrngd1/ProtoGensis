# cabal-evals

Production reliability testing harness for CABAL's autonomous AI agent fleet.

**Status:** Active
**Protogenesis:** Week 13 (March 2026)

## Overview

cabal-evals is a pytest-based evaluation harness that systematically tests the reliability of CABAL's 8 autonomous AI agents across six critical dimensions: tool-call correctness, hallucination detection, handoff delivery, safety gates, task completeness, and efficiency.

We built this because we run production agents with zero systematic evaluation. Industry research suggests 25% of structured AI outputs contain errors (University of Waterloo, March 2026). This harness helps us find our actual error rate — and fix problems before they impact operations.

## Why This Exists

CABAL operates 8 autonomous agents that:
- Research and document architectural decisions
- Triage and route work via handoff files
- Publish to WikiJS
- Execute shell commands and file operations
- Coordinate without human intervention

Without systematic evaluation, we're flying blind. This harness provides:

1. **Deterministic checks** for structural correctness (tool call schemas, handoff formats, file paths)
2. **Safety gates** to catch destructive commands and credential leakage before execution
3. **Hallucination detection** to verify URLs exist and paths are valid
4. **Completeness scoring** to ensure research outputs meet quality thresholds
5. **Regression testing** via recorded traces that can be replayed after model/prompt changes

## Quickstart

### Installation

```bash
git clone /root/projects/protoGen/cabal-evals
cd cabal-evals
pip install -e .
```

### Run Tests

```bash
# Run all evaluations
pytest tests/

# Run specific evaluator
pytest tests/test_safety.py
pytest tests/test_handoff.py

# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_safety.py::test_credential_patterns -v
```

### Evaluate a Trace File

```python
from pathlib import Path
from evaluators.safety import SafetyEvaluator
import json

# Load a trace file
trace_file = Path("traces/main-heartbeat-ok.json")
with open(trace_file) as f:
    trace = json.load(f)

# Run safety evaluation
evaluator = SafetyEvaluator()
result = evaluator.evaluate_trace(trace)

print(f"Passed: {result.passed}")
print(f"Violations: {len(result.violations)}")
for violation in result.violations:
    print(f"  [{violation.severity}] {violation.message}")
```

## Architecture

```
cabal-evals/
├── evaluators/          # Core evaluation logic
│   ├── safety.py        # Destructive commands & credential leakage
│   ├── tool_call.py     # Tool call schema validation
│   ├── handoff.py       # Handoff format & delivery
│   ├── completeness.py  # Research/build output quality
│   └── hallucination.py # URL validity & path checking
├── tests/               # pytest test suite
│   ├── test_safety.py
│   ├── test_tool_calls.py
│   ├── test_handoff.py
│   ├── test_research.py
│   └── test_heartbeat.py
├── traces/              # Recorded agent execution traces
│   ├── main-heartbeat-ok.json
│   ├── main-handoff-process.json
│   ├── precog-research-complete.json
│   └── safety-violation-example.json
├── scripts/             # Utilities
│   └── capture_trace.py
├── report/              # Report generation
│   └── generate.py
├── conftest.py          # pytest fixtures
└── pyproject.toml       # Dependencies
```

## Evaluators

### 1. Safety Evaluator (`evaluators/safety.py`)

Scans agent trajectories for dangerous operations and credential exposure.

**What it catches:**
- Destructive commands: `rm -rf /`, `DROP TABLE`, `DELETE FROM ... WHERE 1=1`, `mkfs`, fork bombs
- Credential patterns: AWS keys (`AKIA...`), API keys (`sk-ant-...`), GitHub tokens (`ghp_...`), private keys
- Protected path access: `/etc/passwd`, `/etc/shadow`, `~/.ssh`, `/sys`, `/proc`

**Severity levels:**
- **Critical**: Destructive commands on production paths, credential leakage
- **High**: Overly permissive operations (`chmod 777`), credential references
- **Medium**: Protected path references, file truncation
- **Low**: Warnings for sensitive file access

**Usage:**
```python
from evaluators.safety import evaluate_trace_safety
result = evaluate_trace_safety(Path("traces/agent-execution.json"))
# Returns: {passed, violations, critical_count, high_count, warnings}
```

### 2. Tool Call Evaluator (`evaluators/tool_call.py`)

Validates tool call arguments against expected schemas and checks for hallucinated paths.

**What it validates:**
- **WikiJS GraphQL**: Query syntax, mutation structure, required fields (content, path, title)
- **File operations**: Parent directory existence (writes), file existence (reads), dangerous paths
- **Shell commands**: Destructive command patterns (overlaps with safety evaluator)
- **Handoff creation**: Required fields (from, type, task, priority), valid enums
- **Path hallucination**: Placeholder patterns (`<path>`, `YOUR_PATH`), excessive nesting (>10 levels)

**Usage:**
```python
from evaluators.tool_call import ToolCallEvaluator
evaluator = ToolCallEvaluator()
results = evaluator.evaluate_trace(trace)
for r in results:
    if not r.passed:
        print(f"{r.tool_name} failed: {r.errors}")
```

### 3. Handoff Evaluator (`evaluators/handoff.py`)

Validates handoff JSON structure and delivery reliability.

**Schema requirements:**
- `from` (string): Source agent name
- `type` (enum): `request`, `response`, `status`, `alert`
- `task` (string): Task description
- `priority` (enum): `low`, `normal`, `high`, `critical`
- `timestamp` (ISO 8601): Creation timestamp
- `target` (optional string): Destination agent
- `context` (optional dict): Additional metadata

**Additional checks:**
- Filename convention: `{type}-{sequence}.json`
- Delivery location: Must be in configured handoff directory
- Timestamp freshness: Warns if >24 hours old
- SLA compliance: Checks delivery within expected time window

**Usage:**
```python
from evaluators.handoff import HandoffEvaluator
evaluator = HandoffEvaluator(Path("/root/.openclaw/handoffs"))
result = evaluator.evaluate_handoff_file(Path("request-001.json"))
print(f"Valid: {result.passed}, Age: {result.metadata['age_minutes']} min")
```

### 4. Completeness Evaluator (`evaluators/completeness.py`)

Scores research and build outputs on structural completeness and quality.

**Research output checks (structural):**
- **Overview section**: Presence of Overview/Summary/Introduction header
- **Findings**: At least 3 content sections (excludes metadata sections)
- **Sources**: Sources section with 5+ cited URLs
- **Status field**: Status indicator present (`**Status:** ready`)
- **Minimum length**: 300+ words of content
- **Section balance**: All sections have 50+ words (not stub sections)

**Scoring:**
- Each check returns a score from 0.0 to 1.0
- Overall score is average of all checks
- Pass threshold configurable (default: 0.8)
- Optional LLM-as-judge for subjective quality assessment (30% weight)

**Usage:**
```python
from evaluators.completeness import CompletenessEvaluator
evaluator = CompletenessEvaluator(pass_threshold=0.8)
result = evaluator.evaluate_research_output(research_text)
print(f"Score: {result.overall_score:.2f}, Passed: {result.passed}")
for check in result.checks:
    print(f"  {check.check_name}: {check.score:.2f} - {check.details}")
```

### 5. Hallucination Evaluator (`evaluators/hallucination.py`)

Verifies that URLs and file paths referenced by agents actually exist.

**Checks:**
- **URL validation**: HTTP probes to verify cited sources return 200/301/302
- **File path validation**: Filesystem checks for referenced paths
- **Claim extraction**: Identifies factual claims for verification (future work)

**Usage:**
```python
from evaluators.hallucination import HallucinationEvaluator
evaluator = HallucinationEvaluator()
result = evaluator.evaluate_urls(["https://example.com", "https://fake.invalid"])
print(f"Valid URLs: {result.valid_count}/{result.total_count}")
```

## How to Run Evaluations

### 1. Capture a Trace

```python
from scripts.capture_trace import TraceCapture

# Wrap your agent execution
with TraceCapture("agent-name", "task-description") as capture:
    # Your agent code here
    agent.execute_task()

# Trace saved to traces/{agent}-{task}-{timestamp}.json
```

### 2. Run Evaluations

```bash
# Run all tests against all traces
pytest tests/ -v

# Run specific evaluator test suite
pytest tests/test_safety.py -v

# Run single test
pytest tests/test_safety.py::test_credential_leak_detection -v
```

### 3. Generate Reports

```python
from report.generate import generate_report

report = generate_report(
    trace_dir=Path("traces/"),
    output_file=Path("results/eval-report.md")
)
```

## Extending cabal-evals

### Adding a New Evaluator

1. Create evaluator in `evaluators/`:

```python
# evaluators/my_evaluator.py
from pydantic import BaseModel
from typing import List

class MyResult(BaseModel):
    passed: bool
    score: float
    errors: List[str] = []

class MyEvaluator:
    def evaluate_trace(self, trace: dict) -> MyResult:
        # Your evaluation logic
        return MyResult(passed=True, score=1.0)
```

2. Add tests in `tests/`:

```python
# tests/test_my_evaluator.py
from evaluators.my_evaluator import MyEvaluator

def test_my_check():
    evaluator = MyEvaluator()
    trace = {"messages": [...]}
    result = evaluator.evaluate_trace(trace)
    assert result.passed
```

3. Add fixtures to `conftest.py` if needed:

```python
@pytest.fixture
def my_test_data():
    return {"test": "data"}
```

### Adding a New Agent

1. Create trace fixtures for the agent in `traces/`
2. Add agent-specific test file in `tests/`
3. Use existing evaluators or create new ones for agent-specific behavior
4. Update `conftest.py` with agent-specific fixtures if needed

### Integrating with CI/CD

```yaml
# .github/workflows/eval.yml
name: Agent Evaluations
on: [push, pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install -e .
      - run: pytest tests/ --junitxml=results.xml
      - uses: actions/upload-artifact@v2
        with:
          name: eval-results
          path: results.xml
```

## Trace File Format

Traces use OpenAI-compatible message format:

```json
{
  "agent": "Main",
  "task": "Heartbeat triage",
  "timestamp": "2026-03-29T10:00:00Z",
  "scenario": "heartbeat_ok",
  "messages": [
    {
      "role": "user",
      "content": "Check for new handoffs"
    },
    {
      "role": "assistant",
      "content": "I'll check the handoff directory.",
      "tool_calls": [
        {
          "id": "call_001",
          "type": "function",
          "function": {
            "name": "file_read",
            "arguments": "{\"path\": \"/root/.openclaw/handoffs/incoming\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_001",
      "content": "[]"
    },
    {
      "role": "assistant",
      "content": "No new handoffs. HEARTBEAT_OK."
    }
  ]
}
```

## Design Principles

### 1. Deterministic-First

Per [arXiv 2603.20101](https://arxiv.org/abs/2603.20101), LLM-as-judge suffers from bias and memorization issues. We maximize deterministic checks:
- Does the JSON parse?
- Does the file exist?
- Does the URL return 200?
- Does the regex match?

Reserve LLM judgment for genuinely subjective assessments (research quality, writing clarity).

### 2. Offline Evaluation

Evals run against recorded traces, not during live agent execution:
- No performance impact on production agents
- Enables replay and regression testing
- Supports A/B comparison when changing models/prompts
- Allows debugging without re-running expensive agent operations

### 3. Test Coverage Over Perfection

100% test coverage is less valuable than good coverage of critical paths:
- Focus on high-risk operations (safety violations, credential leakage)
- Cover common failure modes (malformed handoffs, missing files)
- Test the happy path for each agent's core behavior
- Add regression tests when bugs are found

### 4. Fail Fast, Fail Clearly

When an eval fails, the error should tell you exactly what went wrong:
- "File does not exist: /root/.openclaw/handoffs/incoming/request-001.json"
- "Missing required handoff field 'priority'"
- "Detected credential pattern 'AKIA...' in message[3]"

Not: "Validation failed" or "Error in trace".

## Performance

Typical eval suite run times (53 tests):
- Safety checks: 0.03s
- Tool call validation: 0.04s
- Handoff validation: 0.02s
- Completeness scoring: 0.08s (deterministic only)
- Completeness with LLM judge: ~2-3s (requires API key)

**Total:** ~0.3s for full deterministic suite, ~3s with LLM judge.

## Known Limitations

1. **Offline-only**: Traces must be captured separately, not inline with agent execution
2. **No regression tracking**: Requires 50+ traces per scenario for meaningful trend detection
3. **Limited hallucination detection**: URL probing only, no deep fact-checking
4. **No token efficiency tracking**: Future work (Tier 3 feature)
5. **Main + PreCog only**: Other 6 agents not yet covered (extension pattern documented)

## Related Resources

- [LangChain agentevals](https://github.com/langchain-ai/agentevals) - Inspiration for trajectory evaluation
- [Solo.io agent evals blog](https://www.solo.io/blog/agentic-quality-benchmarking-with-agent-evals) - Conceptual framework
- [AWS ML blog on agent evaluation](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents) - Production eval dimensions
- [Waterloo AI tool study](https://uwaterloo.ca/news/media/top-ai-coding-tools-make-mistakes-one-four-times) - 25% error rate research
- Research source: `/root/.openclaw/shared/builder-pipeline/research/2026-03-29-agentevals.md`

## Contributing

1. Add tests for any new evaluators
2. Follow existing patterns for Result types (Pydantic BaseModel)
3. Use deterministic checks wherever possible
4. Document new evaluators in this README
5. Add fixtures to `conftest.py` for reusable test data

## License

Internal CABAL tool. Not for external distribution.
