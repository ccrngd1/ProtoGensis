#!/usr/bin/env python3
"""
Test for race condition fix in cost/latency trackers.

Verifies that calling start_pipeline() or start_layer() twice
raises RuntimeError instead of silently overwriting data.
"""

import sys
from moa.cost_tracker import CostTracker
from moa.latency_tracker import LatencyTracker


def test_cost_tracker_race_condition():
    """Test that CostTracker raises error on double start_pipeline()."""
    print("Testing CostTracker race condition fix...")

    tracker = CostTracker()

    # First start should work
    tracker.start_pipeline()
    print("  ✓ First start_pipeline() succeeded")

    # Second start should raise RuntimeError
    try:
        tracker.start_pipeline()
        print("  ✗ FAIL: Second start_pipeline() should have raised RuntimeError")
        return False
    except RuntimeError as e:
        if "already in progress" in str(e):
            print(f"  ✓ Second start_pipeline() correctly raised: {e}")
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False

    # Clean up properly
    tracker.end_pipeline()
    print("  ✓ end_pipeline() succeeded")

    # After ending, should be able to start again
    tracker.start_pipeline()
    print("  ✓ start_pipeline() after end_pipeline() succeeded")
    tracker.end_pipeline()

    print("  ✓ CostTracker race condition test PASSED\n")
    return True


def test_latency_tracker_pipeline_race_condition():
    """Test that LatencyTracker raises error on double start_pipeline()."""
    print("Testing LatencyTracker pipeline race condition fix...")

    tracker = LatencyTracker()

    # First start should work
    tracker.start_pipeline()
    print("  ✓ First start_pipeline() succeeded")

    # Second start should raise RuntimeError
    try:
        tracker.start_pipeline()
        print("  ✗ FAIL: Second start_pipeline() should have raised RuntimeError")
        return False
    except RuntimeError as e:
        if "already in progress" in str(e):
            print(f"  ✓ Second start_pipeline() correctly raised: {e}")
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False

    # Clean up properly
    tracker.end_pipeline()
    print("  ✓ end_pipeline() succeeded")

    # After ending, should be able to start again
    tracker.start_pipeline()
    print("  ✓ start_pipeline() after end_pipeline() succeeded")
    tracker.end_pipeline()

    print("  ✓ LatencyTracker pipeline race condition test PASSED\n")
    return True


def test_latency_tracker_layer_race_condition():
    """Test that LatencyTracker raises error on double start_layer()."""
    print("Testing LatencyTracker layer race condition fix...")

    tracker = LatencyTracker()

    # Start pipeline first (required)
    tracker.start_pipeline()

    # First start_layer should work
    tracker.start_layer(0)
    print("  ✓ First start_layer(0) succeeded")

    # Second start_layer should raise RuntimeError
    try:
        tracker.start_layer(1)
        print("  ✗ FAIL: Second start_layer() should have raised RuntimeError")
        return False
    except RuntimeError as e:
        if "already in progress" in str(e):
            print(f"  ✓ Second start_layer() correctly raised: {e}")
        else:
            print(f"  ✗ FAIL: Wrong error message: {e}")
            return False

    # Clean up properly
    tracker.end_layer()
    print("  ✓ end_layer() succeeded")

    # After ending, should be able to start next layer
    tracker.start_layer(1)
    print("  ✓ start_layer(1) after end_layer() succeeded")
    tracker.end_layer()

    # Clean up
    tracker.end_pipeline()

    print("  ✓ LatencyTracker layer race condition test PASSED\n")
    return True


def test_reset_clears_state():
    """Test that reset() allows starting fresh pipeline."""
    print("Testing reset() functionality...")

    cost_tracker = CostTracker()
    latency_tracker = LatencyTracker()

    # Start pipeline without ending
    cost_tracker.start_pipeline()
    latency_tracker.start_pipeline()

    # Reset should clear state
    cost_tracker.reset()
    latency_tracker.reset()
    print("  ✓ reset() called")

    # Should be able to start again after reset
    cost_tracker.start_pipeline()
    latency_tracker.start_pipeline()
    print("  ✓ start_pipeline() after reset() succeeded")

    # Clean up
    cost_tracker.end_pipeline()
    latency_tracker.end_pipeline()

    print("  ✓ reset() functionality test PASSED\n")
    return True


def main():
    """Run all race condition tests."""
    print("=" * 80)
    print("RACE CONDITION FIX TESTS")
    print("=" * 80)
    print()

    tests = [
        test_cost_tracker_race_condition,
        test_latency_tracker_pipeline_race_condition,
        test_latency_tracker_layer_race_condition,
        test_reset_clears_state
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"  ✗ UNEXPECTED ERROR: {e}\n")
            results.append(False)

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Race condition fix verified!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
