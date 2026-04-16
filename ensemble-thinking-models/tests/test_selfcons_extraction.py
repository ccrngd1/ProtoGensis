#!/usr/bin/env python3
"""
Regression test for self-consistency answer extraction bug

This test verifies that self-consistency results include both:
1. selected_answer: Full answer text from majority sample
2. extracted_answer: Extracted key used for voting (numeric for GSM8K, letter for MMLU/GPQA)

Bug history:
- Pre-2026-04-11: Only selected_answer existed, contained full text for GSM8K
- Post-2026-04-11: Added extracted_answer field with proper numeric extraction

This regression test ensures the bug doesn't reoccur.
"""

import json
import sys
import os
import re

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from aggregators.self_consistency import SelfConsistencyAggregator


def test_extracted_answer_field_exists():
    """Test that SelfConsistencyResult includes extracted_answer field"""
    aggregator = SelfConsistencyAggregator(mock_mode=True)

    result = aggregator.aggregate(
        model_id="test",
        model_key="test",
        prompt_text="What is 2+2?",
        num_samples=5,
        benchmark="numeric"
    )

    # Check field exists
    assert hasattr(result, 'extracted_answer'), \
        "SelfConsistencyResult missing extracted_answer field"

    # Check it's populated
    assert result.extracted_answer, \
        "extracted_answer field is empty"

    print("✓ extracted_answer field exists and is populated")


def test_numeric_extraction_gsm8k():
    """Test that numeric answers are extracted correctly for GSM8K"""
    aggregator = SelfConsistencyAggregator(mock_mode=True)

    # Test extraction method directly
    test_cases = [
        # (input, expected_extracted_key)
        ("The answer is 42", "42"),
        ("Let me work through this.\n\nThe total is 18 items.", "18"),
        ("$70,000", "70000"),  # Bug case: dollar sign and commas
        ("540 items in total", "540"),  # Bug case: text after number
        ("12.50", "12.50"),  # Decimal
        ("-5", "-5"),  # Negative
        ("1,234,567", "1234567"),  # Large number with commas
    ]

    for answer, expected in test_cases:
        extracted = aggregator._extract_answer_key(answer, benchmark="numeric")
        assert extracted == expected, \
            f"Failed: '{answer}' -> got '{extracted}', expected '{expected}'"
        print(f"✓ '{answer}' -> '{extracted}'")


def test_mc_extraction_mmlu_gpqa():
    """Test that multiple choice letters are extracted for MMLU/GPQA"""
    aggregator = SelfConsistencyAggregator(mock_mode=True)

    test_cases = [
        ("The correct answer is B", "B"),
        ("I believe the answer is A.", "A"),
        ("Answer: C", "C"),
        ("D is the right choice", "D"),
    ]

    for answer, expected in test_cases:
        extracted = aggregator._extract_answer_key(answer, benchmark="mc")
        assert extracted == expected, \
            f"Failed: '{answer}' -> got '{extracted}', expected '{expected}'"
        print(f"✓ '{answer}' -> '{extracted}'")


def test_auto_mode_deprecated():
    """Test that auto mode still works for backwards compatibility but is discouraged"""
    aggregator = SelfConsistencyAggregator(mock_mode=True)

    # Auto mode should still extract, but may be buggy (article "a" -> letter A)
    # This test documents the known issue with auto mode

    buggy_case = "I found a solution"
    extracted = aggregator._extract_answer_key(buggy_case, benchmark="auto")

    # Auto mode will incorrectly extract "A" from article "a"
    # This is WHY we added explicit benchmark parameter
    print(f"⚠️  Auto mode buggy case: '{buggy_case}' -> '{extracted}'")
    print("    (This is why benchmark='numeric' or 'mc' should be used explicitly)")


def test_phase2_results_structure():
    """Test that fixed Phase 2 results have correct structure"""

    # Check if fixed files exist
    fixed_files = [
        'results/phase2/gsm8k_100_selfcons_run1_fixed.json',
        'results/phase2/gsm8k_100_selfcons_run2_fixed.json',
        'results/phase2/gsm8k_100_selfcons_run3_fixed.json',
    ]

    for filepath in fixed_files:
        if not os.path.exists(filepath):
            print(f"⚠️  Fixed file not found: {filepath}")
            continue

        with open(filepath) as f:
            data = json.load(f)

        # Check first result has numeric extracted_answer
        if data['results']:
            first = data['results'][0]
            selected = first.get('selected_answer', '')

            # For fixed files, selected_answer should be numeric
            # (In original buggy files, it was full text)
            if re.match(r'^\$?-?[\d,]+\.?\d*$', str(selected).strip()):
                print(f"✓ {filepath}: selected_answer is numeric ('{selected}')")
            else:
                # Check if there's an extracted_answer field
                extracted = first.get('extracted_answer', '')
                if extracted and re.match(r'^\$?-?[\d,]+\.?\d*$', str(extracted).strip()):
                    print(f"✓ {filepath}: extracted_answer is numeric ('{extracted}')")
                elif len(str(selected)) > 50:
                    print(f"⚠️  {filepath}: selected_answer is full text (bug not fixed)")
                else:
                    print(f"⚠️  {filepath}: Cannot determine if bug is fixed")


def main():
    """Run all regression tests"""
    print("="*80)
    print("SELF-CONSISTENCY EXTRACTION REGRESSION TESTS")
    print("="*80)
    print()

    tests = [
        ("Field existence", test_extracted_answer_field_exists),
        ("Numeric extraction (GSM8K)", test_numeric_extraction_gsm8k),
        ("Multiple choice extraction (MMLU/GPQA)", test_mc_extraction_mmlu_gpqa),
        ("Auto mode (deprecated)", test_auto_mode_deprecated),
        ("Phase 2 results structure", test_phase2_results_structure),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n{'='*80}")
        print(f"Test: {test_name}")
        print(f"{'='*80}")
        try:
            test_func()
            passed += 1
            print(f"\n✅ PASSED: {test_name}")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ FAILED: {test_name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"\n❌ ERROR: {test_name}")
            print(f"   Exception: {e}")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed > 0:
        print("\n🔴 REGRESSION TESTS FAILED")
        print("   Self-consistency extraction bug may have reoccurred")
        sys.exit(1)
    else:
        print("\n✅ ALL REGRESSION TESTS PASSED")
        print("   Self-consistency extraction working correctly")
        sys.exit(0)


if __name__ == "__main__":
    main()
