#!/usr/bin/env python3
"""
HumanEval Benchmark Loader

Downloads and converts HumanEval to our prompt format.
HumanEval contains 164 hand-written programming problems with function signatures,
docstrings, function bodies, and test cases.

Source: https://github.com/openai/human-eval
Dataset: https://huggingface.co/datasets/openai_humaneval
"""

import json
import argparse
import sys
from typing import List, Dict, Any
import random


def try_datasets_library():
    """
    Try to use HuggingFace datasets library
    """
    try:
        from datasets import load_dataset
        print("Attempting to load HumanEval from HuggingFace datasets...")

        dataset = load_dataset("openai_humaneval", split="test")

        problems = []
        for item in dataset:
            problems.append({
                "task_id": item["task_id"],
                "prompt": item["prompt"],  # Function signature + docstring
                "canonical_solution": item["canonical_solution"],
                "test": item["test"],  # Test cases
                "entry_point": item["entry_point"],  # Function name to test
            })

        print(f"✓ Loaded {len(problems)} HumanEval problems via datasets library")
        return problems
    except ImportError:
        print("📦 datasets library not installed")
        print("   Install with: pip install datasets")
        return None
    except Exception as e:
        print(f"⚠️  datasets library failed: {e}")
        return None


def convert_to_prompt_format(problems: List[Dict[str, Any]], count: int = 100) -> Dict[str, Any]:
    """
    Convert HumanEval problems to our prompt format

    Args:
        problems: List of HumanEval problems
        count: Number of problems to convert

    Returns:
        Dictionary in our prompt format
    """

    # Take first 'count' problems or sample randomly
    if len(problems) > count:
        selected = problems[:count]
    else:
        selected = problems

    prompts = []
    for i, problem in enumerate(selected):
        task_id = problem['task_id']
        prompt_text = problem['prompt']

        # Format the prompt to ask for code completion
        formatted_prompt = f"""Complete the following Python function:

{prompt_text}

Provide ONLY the complete function implementation. Do not include test cases or example usage."""

        prompt_obj = {
            "id": f"humaneval_{i+1:03d}",
            "original_task_id": task_id,
            "category": "code_generation",
            "difficulty": "programming",
            "text": formatted_prompt,
            "ground_truth": {
                "canonical_solution": problem['canonical_solution'],
                "test": problem['test'],
                "entry_point": problem['entry_point'],
                "prompt": problem['prompt']  # Need this to prepend to model solution
            },
            "evaluation_criteria": "code_execution",
            "benchmark": "humaneval",
            "rationale": f"HumanEval {task_id} - Python function implementation with test cases"
        }
        prompts.append(prompt_obj)

    return {
        "benchmark": "humaneval",
        "description": "HumanEval - Hand-written programming problems with test cases",
        "source": "https://github.com/openai/human-eval",
        "total_problems": len(prompts),
        "note": "Evaluation requires code execution - see evaluate_humaneval() in evaluators.py",
        "prompts": prompts
    }


def main():
    parser = argparse.ArgumentParser(description="Download and convert HumanEval benchmark")
    parser.add_argument("--count", type=int, default=20,
                       help="Number of problems to convert (default: 20, max: 164)")
    parser.add_argument("--output", type=str, default="prompts/humaneval_20.json",
                       help="Output file path")
    parser.add_argument("--show-sample", action="store_true",
                       help="Show a sample problem and exit")
    args = parser.parse_args()

    print("="*70)
    print("HumanEval Benchmark Loader")
    print("="*70)
    print()

    # Try to load dataset
    problems = try_datasets_library()

    if not problems:
        print("❌ Failed to download HumanEval")
        print("Please install datasets library: pip install datasets")
        sys.exit(1)

    print(f"\n✓ Successfully loaded {len(problems)} total HumanEval problems")

    # Show sample if requested
    if args.show_sample:
        print("\n" + "="*70)
        print("SAMPLE PROBLEM:")
        print("="*70)
        sample = problems[0]
        print(f"Task ID: {sample['task_id']}")
        print(f"\nPrompt:\n{sample['prompt']}")
        print(f"\nCanonical Solution:\n{sample['canonical_solution']}")
        print(f"\nEntry Point: {sample['entry_point']}")
        print(f"\nTest Preview:\n{sample['test'][:200]}...")
        return

    # Convert to our format
    print(f"\nConverting {min(args.count, len(problems))} problems to prompt format...")
    prompt_data = convert_to_prompt_format(problems, args.count)

    # Save to file
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w') as f:
        json.dump(prompt_data, f, indent=2)

    print(f"✓ Saved {len(prompt_data['prompts'])} problems to {args.output}")
    print()
    print("="*70)
    print("SAMPLE CONVERTED PROMPT:")
    print("="*70)
    sample_prompt = prompt_data['prompts'][0]
    # Print without full ground_truth to keep it readable
    display_prompt = sample_prompt.copy()
    display_prompt['ground_truth'] = "<test_cases_and_solution>"
    print(json.dumps(display_prompt, indent=2))
    print()
    print("="*70)
    print("IMPORTANT: HumanEval requires code execution for evaluation")
    print("="*70)
    print("Next steps:")
    print(f"  1. Run: python3 harness.py --prompts {args.output} --models opus-fast opus-thinking")
    print(f"  2. Note: Full evaluation requires implementing code execution sandbox")
    print(f"     Currently evaluate_humaneval() in evaluators.py is a placeholder")
    print("="*70)


if __name__ == "__main__":
    main()
