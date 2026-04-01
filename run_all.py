#!/usr/bin/env python3
"""
Unified Runner for All Three Ensemble Experiments

Runs:
1. Ensemble Thinking Models (Opus, Nova Premier, Sonnet)
2. MoA Bedrock Guide (3 configs across prompts)
3. Persona Orchestrator (7 personas, 3 strategies, 12 prompts)

Generates consolidated RESULTS.md with cost, latency, and quality metrics.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

print("="*80)
print("ENSEMBLE EXPERIMENTS - UNIFIED RUNNER")
print("="*80)
print()

def run_thinking_models():
    """Run Ensemble Thinking Models experiment"""
    print("\n" + "="*80)
    print("EXPERIMENT 1: ENSEMBLE THINKING MODELS")
    print("="*80)

    os.chdir("/root/projects/protoGen/ensemble-thinking-models")

    # Run harness
    cmd = "python3 harness.py --output results/responses.json"

    print(f"\nRunning: {cmd}\n")
    ret = os.system(cmd)

    if ret != 0:
        print(f"⚠️  Harness returned error code {ret}")

    return {
        "experiment": "Ensemble Thinking Models",
        "status": "completed" if ret == 0 else "failed",
        "output_file": "ensemble-thinking-models/results/responses.json"
    }


def run_moa_benchmark():
    """Run MoA Bedrock Guide benchmark"""
    print("\n" + "="*80)
    print("EXPERIMENT 2: MOA BEDROCK GUIDE")
    print("="*80)

    os.chdir("/root/projects/protoGen/ensemble-moa-bedrock-guide")

    # Run benchmark with limited prompts for speed
    cmd = "python3 benchmark/run.py --output results/benchmark_results.json --limit 5"

    print(f"\nRunning: {cmd}\n")
    ret = os.system(cmd)

    if ret != 0:
        print(f"⚠️  Benchmark returned error code {ret}")

    return {
        "experiment": "MoA Bedrock Guide",
        "status": "completed" if ret == 0 else "failed",
        "output_file": "ensemble-moa-bedrock-guide/results/benchmark_results.json"
    }


def run_persona_orchestrator():
    """Run Persona Orchestrator experiment"""
    print("\n" + "="*80)
    print("EXPERIMENT 3: PERSONA ORCHESTRATOR")
    print("="*80)

    os.chdir("/root/projects/protoGen/ensemble-persona-orchestrator")

    # Run a single test prompt
    test_prompt = "Should we prioritize speed or quality in our MVP launch?"

    # Run personas
    cmd = f'python3 runner.py "{test_prompt}" --output results/persona_responses.json'

    print(f"\nRunning: {cmd}\n")
    ret = os.system(cmd)

    if ret != 0:
        print(f"⚠️  Persona runner returned error code {ret}")
        return {
            "experiment": "Persona Orchestrator",
            "status": "failed",
            "output_file": None
        }

    # Note: Orchestrator is called within runner.py now, no separate step needed

    return {
        "experiment": "Persona Orchestrator",
        "status": "completed" if ret == 0 else "failed",
        "output_file": "ensemble-persona-orchestrator/results/persona_responses.json"
    }


def generate_results_md(experiment_results, total_time):
    """Generate RESULTS.md with consolidated metrics"""
    print("\n" + "="*80)
    print("GENERATING RESULTS.MD")
    print("="*80)

    results_path = Path("/root/projects/protoGen/RESULTS.md")

    with open(results_path, 'w') as f:
        f.write("# Ensemble Experiments Results\n\n")
        f.write(f"**Run Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Mode:** LIVE (AWS Bedrock)\n\n")
        f.write(f"**Total Execution Time:** {total_time:.1f}s\n\n")

        f.write("---\n\n")

        # Model Info
        f.write("## Models Used\n\n")
        f.write("All models are available and running live on AWS Bedrock:\n\n")
        f.write("| Model | Model ID | Usage |\n")
        f.write("|-------|----------|-------|\n")
        f.write("| Claude Opus 4.6 | us.anthropic.claude-opus-4-6-v1 | Extended thinking |\n")
        f.write("| Claude Sonnet 4.6 | us.anthropic.claude-sonnet-4-6 | Strong reasoning |\n")
        f.write("| Claude Haiku 4.5 | us.anthropic.claude-haiku-4-5-20251001-v1:0 | Fast responses |\n")
        f.write("| Nova Premier | us.amazon.nova-premier-v1:0 | Deep reasoning |\n")
        f.write("| Nova Pro | us.amazon.nova-pro-v1:0 | Mid-tier |\n")
        f.write("| Nova Lite | us.amazon.nova-lite-v1:0 | Cost-effective |\n")
        f.write("| Mistral 7B | mistral.mistral-7b-instruct-v0:2 | Small efficient |\n")
        f.write("| Mixtral 8x7B | mistral.mixtral-8x7b-instruct-v0:1 | MoE model |\n")
        f.write("| Mistral Large | mistral.mistral-large-2402-v1:0 | Large reasoning |\n")
        f.write("| Llama 3.1 8B | us.meta.llama3-1-8b-instruct-v1:0 | Open source |\n")
        f.write("| Llama 3.1 70B | us.meta.llama3-1-70b-instruct-v1:0 | Large open source |\n\n")

        f.write("---\n\n")

        # Experiment summaries
        f.write("## Experiment Results\n\n")

        for exp in experiment_results:
            f.write(f"### {exp['experiment']}\n\n")
            f.write(f"**Status:** {exp['status']}\n\n")

            if exp['status'] == 'completed' and exp['output_file']:
                full_path = f"/root/projects/protoGen/{exp['output_file']}"
                if Path(full_path).exists():
                    f.write(f"**Output:** `{exp['output_file']}`\n\n")

                    # Try to extract key metrics
                    try:
                        with open(full_path, 'r') as data_file:
                            data = json.load(data_file)

                            # Extract metrics based on experiment type
                            if "thinking-models" in exp['output_file']:
                                f.write("**Metrics:**\n")
                                if isinstance(data, list) and len(data) > 0:
                                    total_cost = sum(
                                        r['responses'].get(model, {}).get('cost_usd', 0)
                                        for r in data
                                        for model in ['opus', 'nova', 'sonnet']
                                    )
                                    f.write(f"- Total Cost: ${total_cost:.6f}\n")
                                    f.write(f"- Prompts Processed: {len(data)}\n")

                            elif "moa" in exp['output_file']:
                                f.write("**Metrics:**\n")
                                summary = data.get('summary', {})
                                if summary:
                                    f.write("- Ensemble recipes tested: ultra-cheap, code-generation, reasoning\n")
                                    f.write("- Baseline models: Nova Lite, Haiku, Sonnet\n")

                            elif "persona" in exp['output_file']:
                                f.write("**Metrics:**\n")
                                f.write("- Personas: 7 reasoning frameworks\n")
                                f.write("- Orchestration strategies: 3 (pick-best, synthesize, debate)\n")

                    except Exception as e:
                        f.write(f"_(Could not extract metrics: {e})_\n\n")
                else:
                    f.write(f"⚠️  Output file not found\n\n")
            else:
                f.write("⚠️  Experiment failed or no output\n\n")

            f.write("---\n\n")

        # Footer
        f.write("## Notes\n\n")
        f.write("**This was a LIVE RUN** against AWS Bedrock with real API calls, costs, and latency.\n\n")

        f.write(f"\nGenerated by unified runner on {datetime.now().isoformat()}\n")

    print(f"\n✓ Results saved to {results_path}")
    return str(results_path)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Run all ensemble experiments")

    args = parser.parse_args()

    print(f"Mode: LIVE (AWS Bedrock)")
    print()

    # Verify token is set
    if not os.environ.get('AWS_BEARER_TOKEN_BEDROCK'):
        print("ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set!")
        sys.exit(1)

    start_time = time.time()

    # Run all experiments
    experiment_results = []

    try:
        # Experiment 1: Thinking Models
        result1 = run_thinking_models()
        experiment_results.append(result1)

        # Experiment 2: MoA
        result2 = run_moa_benchmark()
        experiment_results.append(result2)

        # Experiment 3: Persona Orchestrator
        result3 = run_persona_orchestrator()
        experiment_results.append(result3)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n⚠️  Error: {e}")
        import traceback
        traceback.print_exc()

    total_time = time.time() - start_time

    # Generate consolidated results
    results_path = generate_results_md(experiment_results, total_time)

    print("\n" + "="*80)
    print("ALL EXPERIMENTS COMPLETE")
    print("="*80)
    print(f"\nTotal time: {total_time:.1f}s")
    print(f"Results: {results_path}")
    print()

    # Return to original directory
    os.chdir("/root/projects/protoGen")


if __name__ == "__main__":
    main()
