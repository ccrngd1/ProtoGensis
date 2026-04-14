#!/usr/bin/env python3
"""
Test script for QualityJudge module.
"""

import asyncio
import sys
from moa import QualityJudge


async def test_judge():
    """Test judge on sample responses."""

    print("="*60)
    print("TESTING QUALITY JUDGE")
    print("="*60)

    # Check bearer token
    import os
    if not os.environ.get('AWS_BEARER_TOKEN_BEDROCK'):
        print("\n❌ AWS_BEARER_TOKEN_BEDROCK not set")
        print("Run: export AWS_BEARER_TOKEN_BEDROCK=your_token")
        return False

    try:
        judge = QualityJudge(judge_model="opus")
        print("\n✓ QualityJudge initialized")

        # Test case 1: Good response
        print("\n" + "-"*60)
        print("Test 1: Good Response")
        print("-"*60)

        prompt1 = "What is 2+2? Explain your answer."
        response1 = "2+2 equals 4. This is a basic arithmetic operation where we add two units to two other units, resulting in a total of four units."
        expected1 = "4"

        print(f"Prompt: {prompt1}")
        print(f"Response: {response1}")
        print("\nScoring...")

        score1 = await judge.score_response(prompt1, response1, expected1)

        print(f"\n✓ Score received:")
        print(f"  Correctness: {score1.correctness}/40")
        print(f"  Completeness: {score1.completeness}/30")
        print(f"  Clarity: {score1.clarity}/30")
        print(f"  TOTAL: {score1.total}/100")
        print(f"  Summary: {score1.justification}")

        # Test case 2: Poor response
        print("\n" + "-"*60)
        print("Test 2: Poor Response")
        print("-"*60)

        prompt2 = "Explain the CAP theorem in distributed systems."
        response2 = "CAP is about computers."
        expected2 = "Consistency, Availability, Partition tolerance - can only have 2 of 3"

        print(f"Prompt: {prompt2}")
        print(f"Response: {response2}")
        print("\nScoring...")

        score2 = await judge.score_response(prompt2, response2, expected2)

        print(f"\n✓ Score received:")
        print(f"  Correctness: {score2.correctness}/40")
        print(f"  Completeness: {score2.completeness}/30")
        print(f"  Clarity: {score2.clarity}/30")
        print(f"  TOTAL: {score2.total}/100")
        print(f"  Summary: {score2.justification}")

        # Test case 3: Batch scoring
        print("\n" + "-"*60)
        print("Test 3: Batch Scoring")
        print("-"*60)

        evaluations = [
            {
                'prompt': 'What is Python?',
                'response': 'Python is a high-level programming language known for its readability and versatility.',
                'expected_answer': 'A programming language'
            },
            {
                'prompt': 'What is HTTP?',
                'response': 'HTTP stands for HyperText Transfer Protocol. It is the foundation of data communication on the web.',
                'expected_answer': 'Protocol for web communication'
            }
        ]

        print(f"Scoring {len(evaluations)} responses in batch...")

        scores = await judge.score_batch(evaluations)

        print(f"\n✓ Batch scoring complete:")
        for i, score in enumerate(scores):
            print(f"  Response {i+1}: {score.total}/100")

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nJudge is working correctly and ready for benchmark integration.")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_judge())
    sys.exit(0 if success else 1)
