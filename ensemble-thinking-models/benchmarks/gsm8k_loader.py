#!/usr/bin/env python3
"""
GSM8K Benchmark Loader

Downloads and converts GSM8K (Grade School Math 8K) problems to our prompt format.
GSM8K contains 8,500 grade school math word problems with natural language solutions.

Source: https://github.com/openai/grade-school-math
Dataset: https://huggingface.co/datasets/gsm8k
"""

import json
import argparse
import sys
from typing import List, Dict, Any
import re


def download_gsm8k_from_url():
    """
    Download GSM8K dataset from GitHub
    Returns list of problems
    """
    import urllib.request

    url = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"

    print(f"Downloading GSM8K test set from {url}...")

    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')

        problems = []
        for line in content.strip().split('\n'):
            if line.strip():
                problems.append(json.loads(line))

        print(f"✓ Downloaded {len(problems)} GSM8K problems")
        return problems

    except Exception as e:
        print(f"❌ Failed to download from GitHub: {e}")
        return None


def try_datasets_library():
    """
    Try to use HuggingFace datasets library
    """
    try:
        from datasets import load_dataset
        print("Attempting to load GSM8K from HuggingFace datasets...")
        dataset = load_dataset("gsm8k", "main", split="test")
        problems = [{"question": item["question"], "answer": item["answer"]}
                   for item in dataset]
        print(f"✓ Loaded {len(problems)} GSM8K problems via datasets library")
        return problems
    except ImportError:
        print("📦 datasets library not installed, trying direct download...")
        return None
    except Exception as e:
        print(f"⚠️  datasets library failed: {e}, trying direct download...")
        return None


def extract_answer_number(answer_text: str) -> str:
    """
    Extract the final numeric answer from GSM8K answer format.
    GSM8K answers end with #### followed by the number.

    Example: "Natalia sold 48+24 = <<48+24=72>>72 clips.\n#### 72"
    Returns: "72"
    """
    # Look for #### pattern
    match = re.search(r'####\s*(-?\d+(?:,\d+)*(?:\.\d+)?)', answer_text)
    if match:
        # Remove commas from numbers like "1,000"
        return match.group(1).replace(',', '')

    # Fallback: try to find last number in text
    numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', answer_text)
    if numbers:
        return numbers[-1].replace(',', '')

    return "PARSE_ERROR"


def convert_to_prompt_format(problems: List[Dict[str, Any]], count: int = 100) -> Dict[str, Any]:
    """
    Convert GSM8K problems to our prompt format

    Args:
        problems: List of GSM8K problems with 'question' and 'answer' fields
        count: Number of problems to convert (default 100)

    Returns:
        Dictionary in our prompt format
    """
    # Take first 'count' problems
    selected = problems[:count]

    prompts = []
    for i, problem in enumerate(selected):
        question = problem['question']
        answer_text = problem['answer']
        answer_number = extract_answer_number(answer_text)

        prompt = {
            "id": f"gsm8k_{i+1:03d}",
            "category": "math_word_problem",
            "difficulty": "grade_school",
            "text": question,
            "ground_truth": answer_number,
            "full_solution": answer_text,
            "evaluation_criteria": "numeric_match",
            "benchmark": "gsm8k",
            "rationale": "GSM8K grade school math problem requiring multi-step arithmetic reasoning"
        }
        prompts.append(prompt)

    return {
        "benchmark": "gsm8k",
        "description": "Grade School Math 8K - Multi-step math word problems",
        "source": "https://github.com/openai/grade-school-math",
        "total_problems": len(prompts),
        "prompts": prompts
    }


def main():
    parser = argparse.ArgumentParser(description="Download and convert GSM8K benchmark")
    parser.add_argument("--count", type=int, default=100,
                       help="Number of problems to convert (default: 100)")
    parser.add_argument("--output", type=str, default="prompts/gsm8k_100.json",
                       help="Output file path")
    parser.add_argument("--show-sample", action="store_true",
                       help="Show a sample problem and exit")
    args = parser.parse_args()

    print("="*70)
    print("GSM8K Benchmark Loader")
    print("="*70)
    print()

    # Try multiple sources
    problems = try_datasets_library()
    if not problems:
        problems = download_gsm8k_from_url()

    if not problems:
        print("❌ Failed to download GSM8K from all sources")
        print("Please install datasets library: pip install datasets")
        print("Or check internet connection for GitHub download")
        sys.exit(1)

    print(f"\n✓ Successfully loaded {len(problems)} total GSM8K problems")

    # Show sample if requested
    if args.show_sample:
        print("\n" + "="*70)
        print("SAMPLE PROBLEM:")
        print("="*70)
        sample = problems[0]
        print(f"Question: {sample['question']}")
        print(f"\nFull Answer: {sample['answer']}")
        print(f"\nExtracted Answer: {extract_answer_number(sample['answer'])}")
        return

    # Convert to our format
    print(f"\nConverting {args.count} problems to prompt format...")
    prompt_data = convert_to_prompt_format(problems, args.count)

    # Save to file
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, 'w') as f:
        json.dump(prompt_data, f, indent=2)

    print(f"✓ Saved {args.count} problems to {args.output}")
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
