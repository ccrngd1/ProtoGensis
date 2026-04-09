#!/usr/bin/env python3
"""
MMLU Benchmark Loader

Downloads and converts MMLU (Massive Multitask Language Understanding) to our prompt format.
MMLU contains 57 subjects across STEM, humanities, social sciences, and more.
Each question is multiple choice (4 options).

Source: https://github.com/hendrycks/test
Dataset: https://huggingface.co/datasets/cais/mmlu
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
        print("Attempting to load MMLU from HuggingFace datasets...")

        # MMLU has multiple splits and subjects, load test split
        dataset = load_dataset("cais/mmlu", "all", split="test")

        problems = []
        for item in dataset:
            problems.append({
                "question": item["question"],
                "choices": item["choices"],
                "answer": item["answer"],  # Index 0-3
                "subject": item.get("subject", "unknown")
            })

        print(f"✓ Loaded {len(problems)} MMLU problems via datasets library")
        return problems
    except ImportError:
        print("📦 datasets library not installed")
        print("   Install with: pip install datasets")
        return None
    except Exception as e:
        print(f"⚠️  datasets library failed: {e}")
        return None


def convert_answer_index_to_letter(index: int) -> str:
    """Convert 0-3 index to A-D letter"""
    return ['A', 'B', 'C', 'D'][index]


def convert_to_prompt_format(problems: List[Dict[str, Any]], count: int = 100, sample_diverse: bool = True) -> Dict[str, Any]:
    """
    Convert MMLU problems to our prompt format

    Args:
        problems: List of MMLU problems
        count: Number of problems to convert
        sample_diverse: If True, sample evenly across subjects

    Returns:
        Dictionary in our prompt format
    """

    # Optionally sample diverse subjects
    if sample_diverse and len(problems) > count:
        # Group by subject
        by_subject = {}
        for p in problems:
            subject = p.get('subject', 'unknown')
            if subject not in by_subject:
                by_subject[subject] = []
            by_subject[subject].append(p)

        # Sample evenly
        subjects = list(by_subject.keys())
        per_subject = max(1, count // len(subjects))
        selected = []

        for subject in subjects:
            sample_count = min(per_subject, len(by_subject[subject]))
            selected.extend(random.sample(by_subject[subject], sample_count))
            if len(selected) >= count:
                break

        selected = selected[:count]
        print(f"Sampled {count} problems from {len(subjects)} subjects")
    else:
        selected = problems[:count]

    prompts = []
    for i, problem in enumerate(selected):
        question = problem['question']
        choices = problem['choices']
        answer_idx = problem['answer']
        answer_letter = convert_answer_index_to_letter(answer_idx)
        subject = problem.get('subject', 'unknown')

        # Format question with choices
        formatted_question = f"{question}\n\n"
        for j, choice in enumerate(choices):
            letter = convert_answer_index_to_letter(j)
            formatted_question += f"{letter}) {choice}\n"

        prompt = {
            "id": f"mmlu_{i+1:03d}",
            "category": "multiple_choice",
            "difficulty": "college_level",
            "text": formatted_question.strip(),
            "ground_truth": answer_letter,
            "subject": subject,
            "choices": ['A', 'B', 'C', 'D'],
            "evaluation_criteria": "multiple_choice",
            "benchmark": "mmlu",
            "rationale": f"MMLU {subject} question testing multitask language understanding"
        }
        prompts.append(prompt)

    return {
        "benchmark": "mmlu",
        "description": "Massive Multitask Language Understanding - Multiple choice across 57 subjects",
        "source": "https://github.com/hendrycks/test",
        "total_problems": len(prompts),
        "subjects": list(set(p.get('subject', 'unknown') for p in selected)),
        "prompts": prompts
    }


def main():
    parser = argparse.ArgumentParser(description="Download and convert MMLU benchmark")
    parser.add_argument("--count", type=int, default=100,
                       help="Number of problems to convert (default: 100)")
    parser.add_argument("--output", type=str, default="prompts/mmlu_100.json",
                       help="Output file path")
    parser.add_argument("--show-sample", action="store_true",
                       help="Show a sample problem and exit")
    parser.add_argument("--no-diverse", action="store_true",
                       help="Don't sample diverse subjects, just take first N")
    args = parser.parse_args()

    print("="*70)
    print("MMLU Benchmark Loader")
    print("="*70)
    print()

    # Try to load dataset
    problems = try_datasets_library()

    if not problems:
        print("❌ Failed to download MMLU")
        print("Please install datasets library: pip install datasets")
        sys.exit(1)

    print(f"\n✓ Successfully loaded {len(problems)} total MMLU problems")

    # Show sample if requested
    if args.show_sample:
        print("\n" + "="*70)
        print("SAMPLE PROBLEM:")
        print("="*70)
        sample = problems[0]
        print(f"Subject: {sample.get('subject', 'unknown')}")
        print(f"Question: {sample['question']}")
        print(f"\nChoices:")
        for j, choice in enumerate(sample['choices']):
            letter = convert_answer_index_to_letter(j)
            print(f"  {letter}) {choice}")
        print(f"\nAnswer: {convert_answer_index_to_letter(sample['answer'])}")
        return

    # Convert to our format
    print(f"\nConverting {args.count} problems to prompt format...")
    prompt_data = convert_to_prompt_format(
        problems,
        args.count,
        sample_diverse=not args.no_diverse
    )

    # Save to file
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w') as f:
        json.dump(prompt_data, f, indent=2)

    print(f"✓ Saved {args.count} problems to {args.output}")
    print(f"  Subjects covered: {', '.join(prompt_data['subjects'][:10])}...")
    print()
    print("="*70)
    print("SAMPLE CONVERTED PROMPT:")
    print("="*70)
    print(json.dumps(prompt_data['prompts'][0], indent=2))
    print()
    print("="*70)
    print("Next steps:")
    print(f"  1. Run: python3 harness.py --prompts {args.output} --models opus-fast opus-thinking")
    print(f"  2. Evaluate: python3 evaluate.py --responses results/... --prompts {args.output}")
    print("="*70)


if __name__ == "__main__":
    main()
