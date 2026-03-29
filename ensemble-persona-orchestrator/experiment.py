"""
Main experiment runner - ties together runner, orchestrator, and diversity measurement

Usage:
    python experiment.py --prompt "Your question here"
    python experiment.py --benchmark  # Run all benchmark prompts
    python experiment.py --benchmark --prompt-id strategy_001  # Run specific prompt
"""
import argparse
import json
import time
from pathlib import Path
from runner import PersonaRunner
from orchestrator import Orchestrator
from diversity import measure_diversity, print_diversity_report


def run_full_experiment(prompt: str, mock_mode: bool = True, output_file: str = None):
    """
    Run complete experiment: personas → orchestration → diversity analysis

    Args:
        prompt: The question to analyze
        mock_mode: If True, use mock responses (no Bedrock calls)
        output_file: Optional path to save results JSON
    """
    print("\n" + "="*80)
    print("ENSEMBLE PERSONA ORCHESTRATOR - FULL EXPERIMENT")
    print("="*80 + "\n")

    start_time = time.time()

    # Step 1: Run prompt through all personas
    print("STEP 1: Running prompt through all personas...")
    runner = PersonaRunner(mock_mode=mock_mode)
    ensemble_result = runner.run_ensemble_sync(prompt)

    # Step 2: Measure diversity
    print("\nSTEP 2: Measuring response diversity...")
    diversity_metrics = measure_diversity(ensemble_result['responses'])
    print_diversity_report(diversity_metrics)

    # Step 3: Orchestrate with all strategies
    print("\nSTEP 3: Orchestrating responses with all strategies...")
    orchestrator = Orchestrator(mock_mode=mock_mode)
    orchestration_result = orchestrator.orchestrate_all_strategies_sync(
        prompt,
        ensemble_result['responses']
    )

    total_time = time.time() - start_time

    # Compile full result
    full_result = {
        "experiment": {
            "prompt": prompt,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_time_seconds": total_time,
            "mock_mode": mock_mode
        },
        "persona_responses": ensemble_result,
        "diversity_metrics": {
            "diversity_score": diversity_metrics.diversity_score,
            "avg_pairwise_similarity": diversity_metrics.avg_pairwise_similarity,
            "conclusion_agreement": diversity_metrics.conclusion_agreement,
            "lexical_overlap": diversity_metrics.lexical_overlap,
            "unique_concepts_per_persona": diversity_metrics.unique_concepts_per_persona,
            "pairwise_similarities": diversity_metrics.pairwise_similarities,
            "analysis": diversity_metrics.analysis
        },
        "orchestration": orchestration_result
    }

    # Print summary
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80 + "\n")

    print(f"Total experiment time: {total_time:.2f}s")
    print(f"Personas: {len(ensemble_result['responses'])}")
    print(f"Diversity score: {diversity_metrics.diversity_score:.3f}")
    print(f"Conclusion agreement: {diversity_metrics.conclusion_agreement:.3f}")
    print(f"Orchestration strategies: {len(orchestration_result['strategies'])}")

    # Print orchestration previews
    print("\n" + "="*80)
    print("ORCHESTRATION STRATEGY COMPARISON")
    print("="*80 + "\n")

    for strategy_name, strategy_result in orchestration_result['strategies'].items():
        print(f"### {strategy_name.replace('_', ' ').title()}")
        print(f"Latency: {strategy_result['latency_ms']:.0f}ms")
        print("-" * 80)
        output_preview = strategy_result['final_output'][:400]
        print(output_preview + "...\n")

    # Save to file if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(full_result, f, indent=2)
        print(f"\n✓ Results saved to: {output_file}")

    return full_result


def run_benchmark_suite(mock_mode: bool = True, prompt_id: str = None):
    """
    Run all benchmark prompts and generate comparison report

    Args:
        mock_mode: If True, use mock responses
        prompt_id: If provided, run only this specific prompt
    """
    # Load benchmark prompts
    benchmark_path = Path("benchmark/test_prompts.json")
    with open(benchmark_path, 'r') as f:
        benchmark_data = json.load(f)

    prompts = benchmark_data['prompts']

    # Filter to specific prompt if requested
    if prompt_id:
        prompts = [p for p in prompts if p['id'] == prompt_id]
        if not prompts:
            print(f"Error: Prompt ID '{prompt_id}' not found in benchmark")
            return

    print("\n" + "="*80)
    print(f"BENCHMARK SUITE: Running {len(prompts)} prompts")
    print("="*80 + "\n")

    results = []

    for i, prompt_data in enumerate(prompts, 1):
        print(f"\n{'='*80}")
        print(f"Benchmark {i}/{len(prompts)}: {prompt_data['id']} ({prompt_data['category']})")
        print("="*80 + "\n")

        output_file = f"results/benchmark_{prompt_data['id']}.json"

        result = run_full_experiment(
            prompt=prompt_data['prompt'],
            mock_mode=mock_mode,
            output_file=output_file
        )

        # Add metadata
        result['benchmark_metadata'] = {
            "id": prompt_data['id'],
            "category": prompt_data['category'],
            "difficulty": prompt_data['difficulty'],
            "expected_diversity": prompt_data['expected_diversity']
        }

        results.append({
            "id": prompt_data['id'],
            "category": prompt_data['category'],
            "diversity_score": result['diversity_metrics']['diversity_score'],
            "conclusion_agreement": result['diversity_metrics']['conclusion_agreement'],
            "expected_diversity": prompt_data['expected_diversity']
        })

        print("\n" + "="*80)
        print(f"✓ Completed {prompt_data['id']}")
        print("="*80 + "\n")

    # Generate benchmark summary
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80 + "\n")

    print(f"{'ID':<20} {'Category':<25} {'Diversity':<12} {'Agreement':<12} {'Expected':<12}")
    print("-" * 80)

    for result in results:
        print(
            f"{result['id']:<20} "
            f"{result['category']:<25} "
            f"{result['diversity_score']:<12.3f} "
            f"{result['conclusion_agreement']:<12.3f} "
            f"{result['expected_diversity']:<12}"
        )

    # Save summary
    summary_path = Path("results/benchmark_summary.json")
    with open(summary_path, 'w') as f:
        json.dump({
            "benchmark_run": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_prompts": len(results),
            "results": results,
            "avg_diversity": sum(r['diversity_score'] for r in results) / len(results),
            "avg_agreement": sum(r['conclusion_agreement'] for r in results) / len(results)
        }, f, indent=2)

    print(f"\n✓ Benchmark summary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Ensemble Persona Orchestrator - Experiment Runner"
    )

    parser.add_argument(
        '--prompt',
        type=str,
        help='Question to analyze with ensemble personas'
    )

    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run full benchmark suite instead of single prompt'
    )

    parser.add_argument(
        '--prompt-id',
        type=str,
        help='Specific benchmark prompt ID to run (use with --benchmark)'
    )

    parser.add_argument(
        '--live',
        action='store_true',
        help='Use live Bedrock API calls instead of mock mode'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output file path for results JSON'
    )

    args = parser.parse_args()

    mock_mode = not args.live

    if args.benchmark:
        run_benchmark_suite(mock_mode=mock_mode, prompt_id=args.prompt_id)
    elif args.prompt:
        output_file = args.output or f"results/experiment_{int(time.time())}.json"
        run_full_experiment(
            prompt=args.prompt,
            mock_mode=mock_mode,
            output_file=output_file
        )
    else:
        # Interactive mode
        print("\n" + "="*80)
        print("ENSEMBLE PERSONA ORCHESTRATOR")
        print("="*80 + "\n")
        print("Interactive mode. Enter a prompt to analyze.")
        print("(Or use --help to see CLI options)\n")

        prompt = input("Enter your prompt: ").strip()

        if prompt:
            run_full_experiment(
                prompt=prompt,
                mock_mode=mock_mode,
                output_file="results/interactive_result.json"
            )
        else:
            print("No prompt provided. Exiting.")


if __name__ == "__main__":
    main()
