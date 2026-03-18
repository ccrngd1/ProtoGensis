"""
tests/test_triggers.py — Tests for the ContextTriggers class.
Covers threshold detection, context tracking, and trigger advice.
"""

import pytest
from memex.triggers import ContextTriggers, TriggerAdvice


# Sample content strings of varying lengths
SMALL_CONTENT = "a" * 100  # ~25 tokens
MEDIUM_CONTENT = "a" * 1600  # ~400 tokens
LARGE_CONTENT = "a" * 8000  # ~2000 tokens
HUGE_CONTENT = "a" * 16000  # ~4000 tokens


def test_no_compression_below_soft_threshold():
    """Should not recommend compression when context is below soft threshold."""
    triggers = ContextTriggers(soft_threshold=4000, hard_threshold=8000)
    advice = triggers.check_triggers(MEDIUM_CONTENT)

    assert advice.should_compress is False
    assert advice.context_tokens < 4000
    assert advice.threshold == 4000


def test_soft_threshold_triggers_compression():
    """Should recommend compression when context exceeds soft threshold."""
    triggers = ContextTriggers(soft_threshold=1000, hard_threshold=8000)
    # HUGE_CONTENT is ~4000 tokens, well above 1000
    advice = triggers.check_triggers(HUGE_CONTENT)

    assert advice.should_compress is True
    assert "soft threshold" in advice.reason
    assert advice.context_tokens >= 1000
    assert advice.threshold == 1000


def test_hard_threshold_triggers_compression():
    """Should recommend compression when context exceeds hard threshold."""
    triggers = ContextTriggers(soft_threshold=4000, hard_threshold=3000)
    advice = triggers.check_triggers(HUGE_CONTENT)

    assert advice.should_compress is True
    assert "hard threshold" in advice.reason
    assert advice.context_tokens >= 3000
    assert advice.threshold == 3000


def test_hard_threshold_takes_precedence():
    """Hard threshold should take precedence over soft threshold in reason."""
    triggers = ContextTriggers(soft_threshold=1000, hard_threshold=2000)
    advice = triggers.check_triggers(HUGE_CONTENT)

    assert advice.should_compress is True
    # Should mention hard threshold, not soft
    assert "hard threshold" in advice.reason
    assert "soft threshold" not in advice.reason


def test_segment_threshold_triggers_compression():
    """Should recommend compression when new segment exceeds segment threshold."""
    triggers = ContextTriggers(soft_threshold=10000, hard_threshold=20000, segment_threshold=1500)
    # Working context is small, but new segment is large
    advice = triggers.check_triggers(SMALL_CONTENT, new_segment=LARGE_CONTENT)

    assert advice.should_compress is True
    assert "New segment" in advice.reason
    assert advice.threshold == 1500


def test_context_history_tracking():
    """Should track context size history across multiple checks."""
    triggers = ContextTriggers(soft_threshold=10000, hard_threshold=20000)

    # First check
    triggers.check_triggers(SMALL_CONTENT)
    assert len(triggers._context_history) == 1

    # Second check
    triggers.check_triggers(MEDIUM_CONTENT)
    assert len(triggers._context_history) == 2

    # Third check
    triggers.check_triggers(HUGE_CONTENT)
    assert len(triggers._context_history) == 3


def test_peak_context_tokens():
    """Should correctly calculate peak context from history."""
    triggers = ContextTriggers(soft_threshold=10000, hard_threshold=20000)

    # Initially no history
    assert triggers.peak_context_tokens == 0

    # Add varying context sizes
    triggers.check_triggers(SMALL_CONTENT)  # ~25 tokens
    triggers.check_triggers(HUGE_CONTENT)   # ~4000 tokens
    triggers.check_triggers(MEDIUM_CONTENT) # ~400 tokens

    # Peak should be from HUGE_CONTENT
    peak = triggers.peak_context_tokens
    assert peak > 3500  # Approximate, depends on token estimation
    assert peak < 5000


def test_reset_history():
    """Should clear context history when reset is called."""
    triggers = ContextTriggers(soft_threshold=10000, hard_threshold=20000)

    # Build up history
    triggers.check_triggers(SMALL_CONTENT)
    triggers.check_triggers(MEDIUM_CONTENT)
    triggers.check_triggers(HUGE_CONTENT)

    assert len(triggers._context_history) == 3
    assert triggers.peak_context_tokens > 0

    # Reset
    triggers.reset_history()

    assert len(triggers._context_history) == 0
    assert triggers.peak_context_tokens == 0


def test_trigger_advice_string_representation_no_compression():
    """TriggerAdvice should format correctly when compression not needed."""
    advice = TriggerAdvice(
        should_compress=False,
        reason=None,
        context_tokens=2500,
        threshold=4000
    )

    result = str(advice)
    assert "[memex:triggers]" in result
    assert "No compression needed" in result
    assert "2,500" in result  # Formatted with commas
    assert "4,000" in result


def test_trigger_advice_string_representation_with_compression():
    """TriggerAdvice should format correctly when compression is recommended."""
    advice = TriggerAdvice(
        should_compress=True,
        reason="Context at 5,000 tokens — above soft threshold 4,000",
        context_tokens=5000,
        threshold=4000
    )

    result = str(advice)
    assert "[memex:triggers]" in result
    assert "COMPRESS RECOMMENDED" in result
    assert "Context at 5,000 tokens" in result
    assert "5,000 tokens" in result


def test_custom_thresholds():
    """Should respect custom threshold values."""
    triggers = ContextTriggers(
        soft_threshold=2000,
        hard_threshold=5000,
        segment_threshold=1000
    )

    assert triggers.soft_threshold == 2000
    assert triggers.hard_threshold == 5000
    assert triggers.segment_threshold == 1000


def test_segment_threshold_only_checks_new_segment():
    """Segment threshold should only trigger when new_segment is provided."""
    triggers = ContextTriggers(soft_threshold=10000, hard_threshold=20000, segment_threshold=500)

    # Without new_segment, even if context is large, segment threshold shouldn't trigger
    advice = triggers.check_triggers(LARGE_CONTENT)  # ~2000 tokens
    assert advice.should_compress is False

    # With new_segment that's large, should trigger
    advice = triggers.check_triggers(SMALL_CONTENT, new_segment=LARGE_CONTENT)
    assert advice.should_compress is True
    assert "New segment" in advice.reason
