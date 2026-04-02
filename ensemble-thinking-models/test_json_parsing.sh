#!/usr/bin/env bash
# Quick test of JSON parsing with 2-3 models on 1 prompt
# Cost: ~$0.05-0.10 instead of $3-5

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

cd "$PROJECT_DIR"

echo "========================================"
echo "JSON Parsing Test"
echo "========================================"
echo "Models: haiku, nova-lite, mistral-large (3 models)"
echo "Prompts: prompts_limited.json (3 prompts)"
echo "Cost: ~$0.10-0.20"
echo ""

# Test with 3 diverse models (cheap + mid-tier)
# Use prompts_limited.json but only process first prompt
PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models haiku nova-lite mistral-large \
  --prompts prompts/prompts_limited.json \
  --output results/test_responses.json

# Check if confidence scores were extracted
echo ""
echo "Checking JSON parsing results..."
python3 -c "
import json

with open('results/test_responses.json') as f:
    data = json.load(f)

print(f\"Total prompts: {len(data)}\")
print()

for i, prompt_result in enumerate(data):
    prompt_id = prompt_result['prompt']['id']
    print(f\"Prompt {i+1}: {prompt_id}\")

    for model, response in prompt_result['responses'].items():
        conf = response.get('confidence', 'MISSING')
        answer_len = len(response.get('answer', ''))
        print(f\"  {model:20} | confidence: {conf:4} | answer: {answer_len} chars\")
    print()

# Check all have confidence
all_have_conf = all(
    r.get('confidence') is not None
    for prompt_result in data
    for r in prompt_result['responses'].values()
)

if all_have_conf:
    print('✓ All models returned confidence scores')
else:
    print('⚠️  Some models missing confidence scores')
"

# Test vote with confidence weighting
echo ""
echo "Testing confidence-weighted vote..."
cp results/test_responses.json results/responses.json
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py results/responses.json --live

# Show vote result
echo ""
echo "Vote results:"
python3 -c "
import json

with open('results/vote_results.json') as f:
    data = json.load(f)

for result in data['results']:
    prompt_id = result['prompt_id']
    print(f\"\nPrompt: {prompt_id}\")
    print(f\"  Selected: {', '.join(result['models_agreeing'])}\")
    print(f\"  Strategy: {result['strategy']}\")
    print(f\"  Convergence: {result['convergence']}\")
    print(f\"  Judge reasoning (first 150 chars):\")
    print(f\"    {result['judge_reasoning'][:150]}...\")
"

echo ""
echo "✓ Test complete! Check results above for:"
echo "  1. All models have confidence scores"
echo "  2. Vote aggregator uses confidence weighting"
echo "  3. Selected answer makes sense"
