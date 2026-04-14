#!/usr/bin/env python3
"""
Test judge response parsing validation.

Verifies that _parse_judge_response properly validates input
and raises clear errors instead of silently returning 0.
"""

import sys
import os
from unittest.mock import Mock, patch

# Mock AWS credentials for testing
os.environ['AWS_BEARER_TOKEN_BEDROCK'] = 'test_token_for_unit_tests'

from moa.judge import QualityJudge


def get_judge():
    """Helper to create judge instance with mocked client."""
    with patch('moa.judge.BedrockClient'):
        return QualityJudge()


def test_valid_format():
    """Test parsing of correctly formatted response."""
    print("Testing valid format...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
The answer is factually accurate.

COMPLETENESS: 25/30
Covers most key points but missing some details.

CLARITY: 28/30
Well-structured and clear.

TOTAL: 88/100

SUMMARY: Good response overall with minor room for improvement.
"""

    try:
        score = judge._parse_judge_response(response)
        assert score.correctness == 35, f"Expected 35, got {score.correctness}"
        assert score.completeness == 25, f"Expected 25, got {score.completeness}"
        assert score.clarity == 28, f"Expected 28, got {score.clarity}"
        assert score.total == 88, f"Expected 88, got {score.total}"
        assert "Good response" in score.justification
        print("  ✓ Valid format parsed correctly")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def test_case_insensitive():
    """Test parsing with lowercase field names."""
    print("Testing case-insensitive parsing...")

    judge = get_judge()
    response = """
correctness: 30/40
Some minor inaccuracies.

completeness: 20/30
Missing several key points.

clarity: 25/30
Generally clear.

total: 75/100

SUMMARY: Acceptable response with gaps.
"""

    try:
        score = judge._parse_judge_response(response)
        assert score.correctness == 30, f"Expected 30, got {score.correctness}"
        assert score.completeness == 20, f"Expected 20, got {score.completeness}"
        assert score.clarity == 25, f"Expected 25, got {score.clarity}"
        print("  ✓ Case-insensitive parsing works")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def test_flexible_spacing():
    """Test parsing with variable spacing around slashes."""
    print("Testing flexible spacing...")

    judge = get_judge()
    response = """
CORRECTNESS: 32 / 40
Good accuracy.

COMPLETENESS: 22 / 30
Mostly complete.

CLARITY: 26 / 30
Clear enough.

TOTAL: 80 / 100

SUMMARY: Solid response.
"""

    try:
        score = judge._parse_judge_response(response)
        assert score.correctness == 32, f"Expected 32, got {score.correctness}"
        assert score.completeness == 22, f"Expected 22, got {score.completeness}"
        assert score.clarity == 26, f"Expected 26, got {score.clarity}"
        print("  ✓ Flexible spacing handled correctly")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def test_missing_correctness():
    """Test that missing CORRECTNESS raises ValueError."""
    print("Testing missing CORRECTNESS detection...")

    judge = get_judge()
    response = """
COMPLETENESS: 25/30
Good coverage.

CLARITY: 28/30
Very clear.

TOTAL: 88/100

SUMMARY: Missing correctness score.
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError, got score: {score}")
        return False
    except ValueError as e:
        if "Failed to parse CORRECTNESS" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False
    except Exception as e:
        print(f"  ✗ FAIL: Wrong exception type: {e}")
        return False


def test_missing_completeness():
    """Test that missing COMPLETENESS raises ValueError."""
    print("Testing missing COMPLETENESS detection...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
Accurate.

CLARITY: 28/30
Clear.

TOTAL: 88/100

SUMMARY: Missing completeness score.
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError, got score: {score}")
        return False
    except ValueError as e:
        if "Failed to parse COMPLETENESS" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False


def test_missing_clarity():
    """Test that missing CLARITY raises ValueError."""
    print("Testing missing CLARITY detection...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
Accurate.

COMPLETENESS: 25/30
Complete.

TOTAL: 88/100

SUMMARY: Missing clarity score.
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError, got score: {score}")
        return False
    except ValueError as e:
        if "Failed to parse CLARITY" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False


def test_score_out_of_range():
    """Test that out-of-range scores raise ValueError."""
    print("Testing out-of-range score detection...")

    judge = get_judge()
    response = """
CORRECTNESS: 50/40
This is too high!

COMPLETENESS: 25/30
Normal.

CLARITY: 28/30
Normal.

TOTAL: 103/100

SUMMARY: Correctness score exceeds maximum.
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError for score=50/40, got: {score}")
        return False
    except ValueError as e:
        if "out of valid range" in str(e) and "50" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False


def test_negative_score():
    """Test that negative scores raise ValueError."""
    print("Testing negative score detection...")

    judge = get_judge()
    response = """
CORRECTNESS: -5/40
Negative score!

COMPLETENESS: 25/30
Normal.

CLARITY: 28/30
Normal.

TOTAL: 48/100

SUMMARY: Negative correctness score.
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError for negative score, got: {score}")
        return False
    except ValueError as e:
        if "out of valid range" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False


def test_total_mismatch():
    """Test that mismatched TOTAL raises ValueError."""
    print("Testing TOTAL mismatch detection...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
Good.

COMPLETENESS: 25/30
Good.

CLARITY: 28/30
Good.

TOTAL: 50/100

SUMMARY: Total doesn't match (should be 88, not 50).
"""

    try:
        score = judge._parse_judge_response(response)
        print(f"  ✗ FAIL: Should have raised ValueError for total mismatch, got: {score}")
        return False
    except ValueError as e:
        if "doesn't match sum" in str(e):
            print(f"  ✓ Correctly raised ValueError: {str(e)[:80]}...")
            return True
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False


def test_missing_total():
    """Test that missing TOTAL is calculated from components."""
    print("Testing missing TOTAL calculation...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
Good accuracy.

COMPLETENESS: 25/30
Mostly complete.

CLARITY: 28/30
Very clear.

SUMMARY: Missing total, should be calculated as 88.
"""

    try:
        score = judge._parse_judge_response(response)
        expected_total = 35 + 25 + 28
        assert score.total == expected_total, f"Expected {expected_total}, got {score.total}"
        print(f"  ✓ Missing TOTAL correctly calculated as {score.total}")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def test_missing_summary():
    """Test that missing SUMMARY uses default."""
    print("Testing missing SUMMARY handling...")

    judge = get_judge()
    response = """
CORRECTNESS: 35/40
Good.

COMPLETENESS: 25/30
Good.

CLARITY: 28/30
Good.

TOTAL: 88/100
"""

    try:
        score = judge._parse_judge_response(response)
        assert score.justification == "No summary provided", \
            f"Expected default summary, got: {score.justification}"
        print("  ✓ Missing SUMMARY uses default value")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def test_decimal_scores():
    """Test parsing of decimal scores."""
    print("Testing decimal score parsing...")

    judge = get_judge()
    response = """
CORRECTNESS: 35.5/40
Very good.

COMPLETENESS: 25.7/30
Excellent coverage.

CLARITY: 28.3/30
Crystal clear.

TOTAL: 89.5/100

SUMMARY: Excellent response with minor improvements possible.
"""

    try:
        score = judge._parse_judge_response(response)
        assert abs(score.correctness - 35.5) < 0.01, f"Expected 35.5, got {score.correctness}"
        assert abs(score.completeness - 25.7) < 0.01, f"Expected 25.7, got {score.completeness}"
        assert abs(score.clarity - 28.3) < 0.01, f"Expected 28.3, got {score.clarity}"
        print("  ✓ Decimal scores parsed correctly")
        return True
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        return False


def main():
    """Run all parsing validation tests."""
    print("=" * 80)
    print("JUDGE PARSING VALIDATION TESTS")
    print("=" * 80)
    print()

    tests = [
        test_valid_format,
        test_case_insensitive,
        test_flexible_spacing,
        test_missing_correctness,
        test_missing_completeness,
        test_missing_clarity,
        test_score_out_of_range,
        test_negative_score,
        test_total_mismatch,
        test_missing_total,
        test_missing_summary,
        test_decimal_scores,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ UNEXPECTED ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            results.append(False)

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Judge parsing properly validates input!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
