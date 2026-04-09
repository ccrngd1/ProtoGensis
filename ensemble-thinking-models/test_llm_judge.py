#!/usr/bin/env python3
"""
Test script for LLM-as-judge evaluation

Tests that:
1. Judge correctly identifies correct answers
2. Judge correctly identifies incorrect answers
3. Judge is lenient with wording differences
4. Judge logs decisions properly
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluate import Evaluator

def test_llm_judge():
    """Test LLM judge with sample questions"""

    print("="*70)
    print("LLM JUDGE TEST")
    print("="*70)
    print()

    # Initialize evaluator with LLM judge
    evaluator = Evaluator(
        use_llm_judge=True,
        judge_log_file="test_judge_log.jsonl"
    )

    # Test cases
    test_cases = [
        {
            "name": "Correct answer (exact match)",
            "question": "What is 2 + 2?",
            "answer": "The answer is 4.",
            "ground_truth": "4",
            "expected": True
        },
        {
            "name": "Correct answer (different wording)",
            "question": "What is the probability of getting heads on a fair coin flip?",
            "answer": "The probability is 50% or one half (0.5).",
            "ground_truth": "50% or 0.5",
            "expected": True
        },
        {
            "name": "Incorrect answer",
            "question": "What is 2 + 2?",
            "answer": "The answer is 5.",
            "ground_truth": "4",
            "expected": False
        },
        {
            "name": "Correct with extra explanation",
            "question": "Should you switch doors in the Monty Hall problem?",
            "answer": "Yes, you should switch. The probability of winning by switching is 2/3, while staying gives you only 1/3 chance. This is because the host reveals information when opening a door.",
            "ground_truth": "Yes, switch. Probability of winning by switching is 2/3.",
            "expected": True
        },
        {
            "name": "Partially correct (missing key detail)",
            "question": "What causes seasons on Earth?",
            "answer": "Seasons are caused by the distance from the sun changing throughout the year.",
            "ground_truth": "Seasons are caused by the tilt of Earth's axis (23.5 degrees), not distance from sun.",
            "expected": False
        }
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"Question: {test['question']}")
        print(f"Answer: {test['answer'][:80]}...")
        print(f"Expected: {'CORRECT' if test['expected'] else 'INCORRECT'}")

        # Create mock prompt dict
        prompt = {"text": test['question']}

        # Run evaluation
        is_correct = evaluator._evaluate_against_ground_truth(
            answer=test['answer'],
            ground_truth=test['ground_truth'],
            prompt_id=f"test_{i}",
            prompt=prompt
        )

        # Check result
        if is_correct == test['expected']:
            print(f"✓ PASSED")
            passed += 1
        else:
            print(f"✗ FAILED - Got: {'CORRECT' if is_correct else 'INCORRECT'}")
            failed += 1

        print()

    print("="*70)
    print(f"RESULTS: {passed}/{len(test_cases)} tests passed")
    print(f"Total judge cost: ${evaluator.total_judge_cost:.4f}")
    print(f"Judge log saved to: test_judge_log.jsonl")
    print("="*70)

    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_llm_judge()
    sys.exit(0 if success else 1)
