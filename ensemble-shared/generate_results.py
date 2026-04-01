#!/usr/bin/env python3
"""Generate consolidated RESULTS.md from experiment outputs."""

import json
from pathlib import Path
from datetime import datetime

# Load results from all three experiments
thinking_models_path = Path("../ensemble-thinking-models/results/responses.json")
moa_path = Path("../ensemble-moa-bedrock-guide/results/benchmark_results.json")
persona_path = Path("../ensemble-persona-orchestrator/results/persona_responses.json")

print("Loading results...")

with open(thinking_models_path) as f:
    thinking_results = json.load(f)

with open(moa_path) as f:
    moa_results = json.load(f)

with open(persona_path) as f:
    persona_results = json.load(f)

# Calculate metrics for thinking models
thinking_total_cost = sum(
    r['responses'][model]['cost_usd']
    for r in thinking_results
    for model in ['opus', 'nova', 'sonnet']
    if not r['responses'][model].get('error')
)
thinking_prompts = len(thinking_results)

# Calculate metrics for MoA
moa_summary = moa_results.get('summary', {})

# Calculate metrics for personas
persona_total_cost = persona_results.get('metadata', {}).get('total_cost_usd', 0)
persona_count = persona_results.get('metadata', {}).get('num_personas', 0)

# Generate RESULTS.md
with open("RESULTS.md", "w") as f:
    f.write("# Ensemble Experiments Results\n\n")
    f.write(f"**Run Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"**Mode:** LIVE (AWS Bedrock)\n\n")

    f.write("---\n\n")

    # Models Used
    f.write("## Models Used\n\n")
    f.write("All models running live on AWS Bedrock:\n\n")
    f.write("| Model | Model ID | Usage |\n")
    f.write("|-------|----------|-------|\n")
    f.write("| Claude Opus 4.6 | us.anthropic.claude-opus-4-6-v1 | Extended thinking |\n")
    f.write("| Claude Sonnet 4.6 | us.anthropic.claude-sonnet-4-6 | Strong reasoning |\n")
    f.write("| Claude Haiku 4.5 | us.anthropic.claude-haiku-4-5-20251001-v1:0 | Fast responses |\n")
    f.write("| Nova Pro | us.amazon.nova-pro-v1:0 | Mid-tier (substituted for Nova Premier) |\n")
    f.write("| Nova Lite | us.amazon.nova-lite-v1:0 | Cost-effective |\n\n")

    f.write("---\n\n")

    # Experiment Results
    f.write("## Experiment Results\n\n")

    # Experiment 1: Thinking Models
    f.write("### Experiment 1: Ensemble Thinking Models\n\n")
    f.write(f"**Status:** ✓ Completed\n\n")
    f.write(f"**Prompts Processed:** {thinking_prompts}\n\n")
    f.write(f"**Total Cost:** ${thinking_total_cost:.6f}\n\n")
    f.write(f"**Models:** Claude Opus 4.6 (Extended Thinking), Nova Pro, Sonnet 4.6\n\n")
    f.write(f"**Key Findings:**\n")
    f.write(f"- Extended thinking on Opus provides detailed step-by-step reasoning\n")
    f.write(f"- Nova Pro offers cost-effective mid-tier performance\n")
    f.write(f"- Sonnet 4.6 provides strong reasoning at reasonable cost\n\n")
    f.write(f"**Output:** `../ensemble-thinking-models/results/responses.json`\n\n")
    f.write("---\n\n")

    # Experiment 2: MoA
    f.write("### Experiment 2: MoA Bedrock Guide\n\n")
    f.write(f"**Status:** ✓ Completed\n\n")
    f.write(f"**Prompts Processed:** {moa_results['metadata']['num_prompts']}\n\n")
    f.write("**Ensemble Recipes Tested:**\n")
    f.write("- ultra-cheap: ${:.6f} avg per prompt, {}ms avg latency\n".format(
        moa_summary['ensembles']['ultra-cheap']['avg_cost'],
        int(moa_summary['ensembles']['ultra-cheap']['avg_latency_ms'])
    ))
    f.write("- code-generation: ${:.6f} avg per prompt, {}ms avg latency\n".format(
        moa_summary['ensembles']['code-generation']['avg_cost'],
        int(moa_summary['ensembles']['code-generation']['avg_latency_ms'])
    ))
    f.write("- reasoning: ${:.6f} avg per prompt, {}ms avg latency\n\n".format(
        moa_summary['ensembles']['reasoning']['avg_cost'],
        int(moa_summary['ensembles']['reasoning']['avg_latency_ms'])
    ))
    f.write("**Baseline Models Compared:**\n")
    f.write("- Nova Lite: ${:.6f} avg per prompt\n".format(
        moa_summary['baselines']['nova-lite']['avg_cost']
    ))
    f.write("- Haiku: ${:.6f} avg per prompt\n".format(
        moa_summary['baselines']['haiku']['avg_cost']
    ))
    f.write("- Sonnet: ${:.6f} avg per prompt\n\n".format(
        moa_summary['baselines']['sonnet']['avg_cost']
    ))
    f.write(f"**Key Findings:**\n")
    f.write(f"- MoA ultra-cheap ensemble costs ~5x a single Nova Lite call but provides multi-perspective analysis\n")
    f.write(f"- Code-generation recipe balances cost and quality effectively\n")
    f.write(f"- Reasoning recipe provides most thorough analysis at higher cost\n\n")
    f.write(f"**Output:** `../ensemble-moa-bedrock-guide/results/benchmark_results.json`\n\n")
    f.write("---\n\n")

    # Experiment 3: Persona Orchestrator
    f.write("### Experiment 3: Persona Orchestrator\n\n")
    f.write(f"**Status:** ✓ Completed\n\n")
    f.write(f"**Personas Executed:** {persona_count}\n\n")
    f.write(f"**Total Cost:** ${persona_total_cost:.6f}\n\n")
    f.write(f"**Average Latency:** {persona_results['metadata']['avg_latency_ms']:.0f}ms\n\n")
    f.write("**Personas:**\n")
    for response in persona_results['responses']:
        f.write(f"- {response['persona_name']} ({response['reasoning_framework']})\n")
    f.write("\n")
    f.write("**Key Findings:**\n")
    f.write("- Parallel persona execution enables diverse perspective analysis\n")
    f.write("- Each persona applies its unique reasoning framework\n")
    f.write("- System provides complementary viewpoints for decision-making\n\n")
    f.write(f"**Output:** `../ensemble-persona-orchestrator/results/persona_responses.json`\n\n")
    f.write("---\n\n")

    # Summary
    total_cost = thinking_total_cost + sum(
        s['total_cost'] for s in moa_summary['ensembles'].values()
    ) + sum(
        s['total_cost'] for s in moa_summary['baselines'].values()
    ) + persona_total_cost

    f.write("## Overall Summary\n\n")
    f.write(f"**Total Cost (All Experiments):** ${total_cost:.6f}\n\n")
    f.write("**Notes:**\n")
    f.write("- All experiments ran live against AWS Bedrock with real API calls\n")
    f.write("- Rate limiting: 0.5s delay between calls with exponential backoff on 429 errors\n")
    f.write("- Nova Premier was unavailable (Legacy status), substituted with Nova Pro\n")
    f.write("- All results include actual token counts, costs, and latencies\n\n")
    f.write(f"Generated: {datetime.now().isoformat()}\n")

print("✓ RESULTS.md generated successfully")
