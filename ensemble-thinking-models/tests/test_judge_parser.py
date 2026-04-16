#!/usr/bin/env python3
"""
Test suite for judge_parser.py

Tests all parsing strategies and edge cases to ensure robust judge response parsing.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from aggregators.judge_parser import JudgeParser, ParseStrategy, get_parser_stats


def test_structured_format():
    """Test parsing of structured format (highest confidence)"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # Perfect structured format
    response = """
SELECTED: opus-fast
FINAL_ANSWER: 42
REASONING: Opus provides the most accurate calculation with clear step-by-step work.
"""
    result = parser.parse_selection(response)

    assert result.selected_model == 'opus-fast', f"Expected opus-fast, got {result.selected_model}"
    assert result.final_answer == '42', f"Expected '42', got {result.final_answer}"
    assert result.confidence == 1.0, f"Expected confidence 1.0, got {result.confidence}"
    assert result.strategy == ParseStrategy.STRUCTURED
    print("✓ Structured format parsing")


def test_explicit_selection():
    """Test parsing of explicit selection phrases"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    test_cases = [
        ("SELECTING opus-fast because it has the best reasoning.", 'opus-fast'),
        ("After analysis, CHOICE: sonnet-fast", 'sonnet-fast'),
        ("I SELECT haiku-fast for its clarity.", 'haiku-fast'),
        ("SELECTED MODEL: opus-fast", 'opus-fast'),
    ]

    for response, expected in test_cases:
        result = parser.parse_selection(response)
        assert result.selected_model == expected, \
            f"Expected {expected}, got {result.selected_model} for: {response}"
        assert result.confidence == 0.9
        assert result.strategy == ParseStrategy.EXPLICIT_SELECTION

    print("✓ Explicit selection parsing")


def test_standalone_line():
    """Test parsing of model name on standalone line"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # First line pattern
    response = """opus-fast

**Reasoning:**
Opus provides the clearest explanation with proper step-by-step work.
"""
    result = parser.parse_selection(response)
    assert result.selected_model == 'opus-fast'
    assert result.confidence == 0.8
    assert result.strategy == ParseStrategy.STANDALONE_LINE

    # Last line pattern
    response = """
After careful analysis of all three responses, considering correctness,
clarity, and completeness, the best answer is:

sonnet-fast
"""
    result = parser.parse_selection(response)
    assert result.selected_model == 'sonnet-fast'

    print("✓ Standalone line parsing")


def test_positive_phrases():
    """Test parsing of positive selection phrases"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    test_cases = [
        ("All three are good, but opus-fast's clear reasoning makes opus-fast the best choice.", 'opus-fast'),
        ("sonnet-fast is the best answer here.", 'sonnet-fast'),
        ("The analysis makes haiku-fast the best option.", 'haiku-fast'),
        ("opus-fast provides the most accurate solution.", 'opus-fast'),
    ]

    for response, expected in test_cases:
        result = parser.parse_selection(response)
        assert result.selected_model == expected, \
            f"Expected {expected}, got {result.selected_model} for: {response}"
        assert result.confidence == 0.7
        assert result.strategy == ParseStrategy.POSITIVE_PHRASES

    print("✓ Positive phrases parsing")


def test_sentiment_scoring():
    """Test sentiment scoring fallback"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # Response where opus is mentioned positively but without clear selection phrases
    # Use possessive form which gives weak signal (0.5 weight)
    response = """
After reviewing all responses, here's my analysis:

haiku-fast provides no real depth here.
sonnet-fast fails to address the nuances completely.

In the final section, opus-fast's approach demonstrates better understanding.
Looking at opus-fast's methodology, it's more thorough.
"""
    result = parser.parse_selection(response)

    assert result.selected_model == 'opus-fast', \
        f"Expected opus-fast from sentiment, got {result.selected_model}"
    # Should use sentiment scoring or positive phrases (both acceptable)
    assert result.confidence <= 0.7, f"Expected confidence <= 0.7, got {result.confidence}"
    assert result.strategy in [ParseStrategy.SENTIMENT_SCORING, ParseStrategy.POSITIVE_PHRASES]

    print("✓ Sentiment scoring parsing")


def test_fuzzy_matching():
    """Test fuzzy matching of model names"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # Response uses shortened model name
    response = "SELECTED: opus"  # Should match opus-fast

    result = parser.parse_selection(response)

    # Should fuzzy match "opus" to "opus-fast"
    assert result.selected_model == 'opus-fast', \
        f"Expected opus-fast from fuzzy match, got {result.selected_model}"
    assert len(result.warnings) > 0  # Should warn about fuzzy matching

    print("✓ Fuzzy matching")


def test_case_insensitivity():
    """Test that parsing is case-insensitive"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    test_cases = [
        "SELECTED: OPUS-FAST",
        "selected: Opus-Fast",
        "Selected: opus-fast",
        "SELECTING OPUS-FAST",
    ]

    for response in test_cases:
        result = parser.parse_selection(response)
        assert result.selected_model == 'opus-fast', \
            f"Case-insensitive parsing failed for: {response}"

    print("✓ Case insensitivity")


def test_malformed_responses():
    """Test handling of malformed/ambiguous responses"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # No clear selection
    response = "All three models provide different perspectives on the problem."

    result = parser.parse_selection(response)

    # Should default to first valid model with confidence 0.0
    assert result.selected_model in parser.valid_models
    assert result.confidence <= 0.3  # Very low confidence
    assert len(result.warnings) > 0  # Should have warnings

    print("✓ Malformed response handling")


def test_invalid_model_name():
    """Test handling when parsed model not in valid list"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # Response mentions a model not in valid list
    response = "SELECTED: gpt-4"  # Not in valid_models

    result = parser.parse_selection(response)

    # Should still return a valid model (fallback)
    assert result.selected_model in parser.valid_models or result.selected_model is None
    assert len(result.warnings) > 0  # Should warn about invalid model

    print("✓ Invalid model name handling")


def test_parser_stats():
    """Test parser statistics generation"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    responses = [
        "SELECTED: opus-fast\nREASONING: Good answer",  # Structured
        "SELECTING sonnet-fast",  # Explicit
        "haiku-fast",  # Standalone
        "opus-fast is the best",  # Positive phrase
        "This is ambiguous text with no clear selection",  # Fallback
    ]

    results = [parser.parse_selection(r) for r in responses]
    stats = get_parser_stats(results)

    assert stats['total_parses'] == 5
    assert 0.0 <= stats['avg_confidence'] <= 1.0
    assert 'strategy_distribution' in stats
    assert stats['low_confidence_count'] >= 1  # At least the ambiguous one

    print("✓ Parser statistics")
    print(f"  Avg confidence: {stats['avg_confidence']:.1%}")
    print(f"  Strategy distribution: {stats['strategy_distribution']}")


def test_logging_fallbacks():
    """Test that fallback strategies generate appropriate warnings"""
    import logging
    import io

    # Capture log output
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = logging.getLogger('JudgeParser')
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    parser = JudgeParser(
        valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'],
        logger=logger
    )

    # Parse with fallback strategy (should log warning)
    response = "opus-fast is the best choice here"
    result = parser.parse_selection(response)

    log_output = log_stream.getvalue()

    # Should have logged that a fallback was used
    assert 'fallback' in log_output.lower() or 'warning' in log_output.lower(), \
        "Fallback strategy should generate warning log"

    print("✓ Fallback logging")


def test_real_world_examples():
    """Test with real-world judge response patterns"""
    parser = JudgeParser(valid_models=['opus-fast', 'sonnet-fast', 'haiku-fast'])

    # Pattern 1: Verbose reasoning with selection at end
    response1 = """
After analyzing all three responses:

Opus-fast provides a comprehensive explanation with proper citations.
Sonnet-fast gives a good summary but lacks detail.
Haiku-fast's response is too brief.

Based on completeness and accuracy, I'm selecting opus-fast.
"""
    result1 = parser.parse_selection(response1)
    assert result1.selected_model == 'opus-fast'

    # Pattern 2: Selection upfront, reasoning after
    response2 = """
sonnet-fast

**Why:**
- Clear structure
- Addresses all points
- Best balance of brevity and completeness
"""
    result2 = parser.parse_selection(response2)
    assert result2.selected_model == 'sonnet-fast'

    # Pattern 3: Comparative analysis
    response3 = """
Comparing the three:

OPUS-FAST: Strong reasoning, verbose
SONNET-FAST: Good balance
HAIKU-FAST: Too brief

CHOICE: SONNET-FAST
"""
    result3 = parser.parse_selection(response3)
    assert result3.selected_model == 'sonnet-fast'

    print("✓ Real-world examples")


def main():
    """Run all tests"""
    print("="*80)
    print("JUDGE PARSER TEST SUITE")
    print("="*80)
    print()

    tests = [
        ("Structured format", test_structured_format),
        ("Explicit selection", test_explicit_selection),
        ("Standalone line", test_standalone_line),
        ("Positive phrases", test_positive_phrases),
        ("Sentiment scoring", test_sentiment_scoring),
        ("Fuzzy matching", test_fuzzy_matching),
        ("Case insensitivity", test_case_insensitivity),
        ("Malformed responses", test_malformed_responses),
        ("Invalid model names", test_invalid_model_name),
        ("Parser statistics", test_parser_stats),
        ("Fallback logging", test_logging_fallbacks),
        ("Real-world examples", test_real_world_examples),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\nTest: {test_name}")
        print("-"*80)
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: {test_name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {test_name}")
            print(f"   Exception: {e}")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed > 0:
        print("\n🔴 SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
