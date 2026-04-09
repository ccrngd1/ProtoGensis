#!/usr/bin/env python3
"""
GPQA Benchmark Loader

Downloads and converts GPQA (Graduate-Level Google-Proof Q&A) to our prompt format.
GPQA contains PhD-level science questions designed to challenge frontier models.

Source: https://github.com/idavidrein/gpqa
Dataset: https://huggingface.co/datasets/Idavidrein/gpqa
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
        print("Attempting to load GPQA from HuggingFace datasets...")

        # GPQA has multiple subsets - use 'gpqa_main' which is the standard benchmark
        dataset = load_dataset("Idavidrein/gpqa", "gpqa_main", split="train")

        problems = []
        for item in dataset:
            problems.append({
                "question": item["Question"],
                "choices": [
                    item["Correct Answer"],
                    item["Incorrect Answer 1"],
                    item["Incorrect Answer 2"],
                    item["Incorrect Answer 3"]
                ],
                "correct_answer": item["Correct Answer"],
                "explanation": item.get("Explanation", ""),
            })

        print(f"✓ Loaded {len(problems)} GPQA problems via datasets library")
        return problems
    except ImportError:
        print("📦 datasets library not installed")
        print("   Install with: pip install datasets")
        return None
    except Exception as e:
        print(f"⚠️  datasets library failed: {e}")
        return None


def convert_to_prompt_format(problems: List[Dict[str, Any]], count: int = 20) -> Dict[str, Any]:
    """
    Convert GPQA problems to our prompt format

    Args:
        problems: List of GPQA problems
        count: Number of problems to convert

    Returns:
        Dictionary in our prompt format
    """

    # Shuffle to get random sample
    shuffled = problems.copy()
    random.shuffle(shuffled)
    selected = shuffled[:count]

    prompts = []
    for i, problem in enumerate(selected):
        question = problem['question']
        choices = problem['choices'].copy()
        correct_answer = problem['correct_answer']

        # Shuffle choices to randomize answer position
        random.shuffle(choices)

        # Find which letter corresponds to correct answer
        correct_letter = None
        for j, choice in enumerate(choices):
            if choice == correct_answer:
                correct_letter = chr(65 + j)  # A=0, B=1, etc.
                break

        # Format question with choices
        formatted_question = f"{question}\n\n"
        for j, choice in enumerate(choices):
            letter = chr(65 + j)  # Convert to A, B, C, D
            formatted_question += f"{letter}) {choice}\n"

        prompt = {
            "id": f"gpqa_{i+1:03d}",
            "category": "graduate_science",
            "difficulty": "phd_level",
            "text": formatted_question.strip(),
            "ground_truth": correct_letter,
            "choices": ['A', 'B', 'C', 'D'],
            "evaluation_criteria": "multiple_choice",
            "benchmark": "gpqa",
            "rationale": "GPQA graduate-level science question requiring deep reasoning"
        }
        prompts.append(prompt)

    return {
        "benchmark": "gpqa",
        "description": "Graduate-Level Google-Proof Q&A - PhD-level science questions",
        "source": "https://github.com/idavidrein/gpqa",
        "total_problems": len(prompts),
        "note": "Designed to challenge frontier models - reported ~60% for Claude Opus",
        "prompts": prompts
    }


def main():
    parser = argparse.ArgumentParser(description="Download and convert GPQA benchmark")
    parser.add_argument("--count", type=int, default=20,
                       help="Number of problems to convert (default: 20)")
    parser.add_argument("--output", type=str, default="prompts/gpqa_20.json",
                       help="Output file path")
    parser.add_argument("--show-sample", action="store_true",
                       help="Show a sample problem and exit")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for shuffling (default: 42)")
    args = parser.parse_args()

    print("="*70)
    print("GPQA Benchmark Loader")
    print("="*70)
    print()

    # Set random seed for reproducibility
    random.seed(args.seed)

    # Try to load dataset
    problems = try_datasets_library()

    if not problems:
        print("❌ Failed to download GPQA")
        print("Please install datasets library: pip install datasets")
        sys.exit(1)

    print(f"\n✓ Successfully loaded {len(problems)} total GPQA problems")

    # Show sample if requested
    if args.show_sample:
        print("\n" + "="*70)
        print("SAMPLE PROBLEM:")
        print("="*70)
        sample = problems[0]
        print(f"Question: {sample['question'][:200]}...")
        print(f"\nChoices:")
        for j, choice in enumerate(sample['choices']):
            letter = chr(65 + j)
            print(f"  {letter}) {choice[:100]}...")
        print(f"\nCorrect: {sample['correct_answer'][:100]}...")
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
    print(json.dumps(prompt_data['prompts'][0], indent=2)[:500] + "...")
    print()
    print("="*70)
    print("Expected Performance (reported):")
    print("  - Claude Opus: ~60%")
    print("  - Claude Sonnet: ~50%")
    print("  - Random guess: 25%")
    print("="*70)
    print("Next steps:")
    print(f"  1. Run: python3 harness.py --prompts {args.output} --models opus-fast opus-thinking")
    print(f"  2. Evaluate: python3 benchmarks/evaluate_ensemble.py ...")
    print("="*70)


if __name__ == "__main__":
    main()
