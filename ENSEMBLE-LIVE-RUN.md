# Task: Refactor Ensemble Experiments for Live Bedrock Execution

## Context

Three ensemble experiment frameworks exist in this repo, currently running in mock mode with template responses. We need them running against real Bedrock models with real outputs, real costs, and real latency measurements.

## Auth

Bedrock API key is available as env var `AWS_BEARER_TOKEN_BEDROCK`. This is an ABSK-style bearer token.

The Bedrock Converse API endpoint is: `https://bedrock-runtime.us-east-1.amazonaws.com`

**Do NOT use boto3.** The system's boto3 is ancient (1.26.27) and doesn't support Bedrock. Use `requests` or `urllib3` (both available) to call the Bedrock Converse API directly via HTTP.

### Converse API Details

The endpoint pattern is:
```
POST https://bedrock-runtime.{region}.amazonaws.com/model/{modelId}/converse
```

Headers:
```
Authorization: Bearer {ABSK_TOKEN}
Content-Type: application/json
Accept: application/json
```

Request body (Converse API format):
```json
{
  "messages": [{"role": "user", "content": [{"text": "your prompt"}]}],
  "inferenceConfig": {
    "maxTokens": 2048,
    "temperature": 0.7
  }
}
```

For system prompts (personas):
```json
{
  "system": [{"text": "system prompt here"}],
  "messages": [{"role": "user", "content": [{"text": "your prompt"}]}],
  "inferenceConfig": {
    "maxTokens": 2048,
    "temperature": 0.7
  }
}
```

Response includes `usage.inputTokens` and `usage.outputTokens` for real cost calculation.

For Claude models with extended thinking, use:
```json
{
  "messages": [...],
  "inferenceConfig": {
    "maxTokens": 16000
  },
  "additionalModelRequestFields": {
    "thinking": {
      "type": "enabled",
      "budget_tokens": 10000
    }
  }
}
```

Note: When extended thinking is enabled, temperature must NOT be set (remove it from inferenceConfig), and maxTokens must be >= budget_tokens.

## Available Models (confirmed on this account)

Use ONLY cross-region inference profile IDs (the `global.` prefix or `us.` prefix versions) for Claude models:
- `us.anthropic.claude-opus-4-6-v1` (Opus — expensive, use sparingly)
- `us.anthropic.claude-sonnet-4-6` (Sonnet)
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Haiku)
- `us.amazon.nova-lite-v1:0` (Nova Lite)
- `us.amazon.nova-pro-v1:0` (Nova Pro)  
- `us.amazon.nova-premier-v1:0` (Nova Premier)

**Additional models confirmed available:**
- `mistral.mistral-7b-instruct-v0:2` (Mistral 7B)
- `mistral.mixtral-8x7b-instruct-v0:1` (Mixtral 8x7B)
- `mistral.mistral-large-2402-v1:0` (Mistral Large)
- `us.meta.llama3-1-8b-instruct-v1:0` (Llama 3.1 8B — use cross-region `us.` prefix)
- `us.meta.llama3-1-70b-instruct-v1:0` (Llama 3.1 70B — use cross-region `us.` prefix)

**Note:** Mistral models do NOT use the `us.` cross-region prefix. Llama models DO require it.

**No substitutions needed.** Use the exact models from the blog article.

## Three Experiments to Refactor

### 1. Ensemble Thinking Models (`ensemble-thinking-models/`)
- **Key files:** `harness.py`, `evaluate.py`, `aggregators/vote.py`, `aggregators/stitch.py`
- **What it does:** Runs 3 reasoning models on 10 hard prompts, uses vote and stitch aggregation
- **Models:** Opus (with extended thinking), Nova Premier (deep reasoning), Sonnet (substituting for Mistral Large)
- **Judge model for vote:** Haiku (cheaper than Sonnet, still capable)
- **Keep:** All 10 prompts, both aggregation strategies, self-consistency baseline (Opus 3x)

### 2. MoA Bedrock Guide (`ensemble-moa-bedrock-guide/`)
- **Key files:** `moa/core.py`, `moa/bedrock_client.py`, `moa/cost_tracker.py`, `benchmark/run.py`
- **What it does:** Multi-layer Mixture-of-Agents with 3 configs across 20 prompts
- **Ultra-cheap config:** Nova Lite × 3 as proposers (substituting for the 3 different cheap models), Nova Lite as aggregator
- **Code-gen config:** Nova Pro × 2 + Haiku as proposers, Haiku as aggregator
- **Reasoning config:** Nova Pro + Haiku + Nova Lite as proposers, Nova Pro as refiner, Haiku as aggregator
- **Baselines:** Nova Lite alone, Haiku alone, Sonnet alone

### 3. Persona Orchestrator (`ensemble-persona-orchestrator/`)
- **Key files:** `orchestrator.py`, `experiment.py`, `diversity.py`
- **What it does:** 7 persona prompts on the same model, 3 orchestration strategies, 12 prompts
- **Model:** Sonnet (for all personas + synthesis)
- **Keep:** All 7 personas, all 3 strategies (pick-best, synthesize, debate), all 12 prompts

## Deliverables

### 1. Shared Bedrock Client (`shared/bedrock_client.py`)
Create a shared HTTP-based Bedrock client used by all 3 experiments:
- Uses `requests` library with the bearer token from env
- Handles Converse API format for all model families
- Returns response text, input_tokens, output_tokens, latency_ms
- Includes retry logic (exponential backoff) for throttling (429s)
- Supports async execution (use `concurrent.futures.ThreadPoolExecutor` since we can't guarantee asyncio compatibility)
- Rate limiting: don't hammer the API. Add a small delay between calls (0.5s minimum)

### 2. Unified Runner (`run_all.py`)
A single script that:
- Runs all 3 experiments sequentially
- Saves raw results to `results/` in each experiment dir (JSON)
- Generates a consolidated report (`RESULTS.md`) with:
  - Per-experiment tables matching the blog format
  - Real costs (calculated from actual token usage × published pricing)
  - Real latencies
  - Quality assessments (use Haiku as judge where applicable — cheap but capable)
  - Convergence rates
  - Model substitution notes
- Estimates remaining cost before each experiment and prints it

### 3. Keep Mock Mode
Don't delete mock mode. Add a `--live` flag to the runner. Default should be `--live` but `--mock` should still work for testing without credentials.

## Cost Controls
- Use Haiku as judge/evaluator wherever possible (cheapest Claude model)
- Don't run Opus more than necessary (10 prompts × 1 call each + 3 self-consistency = 13 Opus calls max)
- Print running cost total after each experiment
- If any single API call fails, log the error and continue (don't abort the whole run)

## Important Notes
- Python 3.x is available at `/usr/bin/python3`
- `requests` is available (`import requests` works)
- No pip available — use only pre-installed packages
- The bearer token env var is `AWS_BEARER_TOKEN_BEDROCK`
- All work stays within `/root/projects/protoGen/`
- Test the Bedrock client with a simple Haiku call before running the full suite

When completely finished, run this command to notify me:
openclaw system event --text "Done: Ensemble experiments refactored for live Bedrock. Results in /root/projects/protoGen/RESULTS.md" --mode now

## UPDATE: No Mock Mode

Remove all mock mode code entirely. Live mode only. No --mock flag, no MockBedrockClient, no MockResponseGenerator, no MOCK_MODE flags. Clean it all out. The experiments should only run against real Bedrock.
