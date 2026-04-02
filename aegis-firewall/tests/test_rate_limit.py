"""Tests for rate limiting."""

import pytest
import time
from aegis.rate_limit import RateLimiter


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_allows_under_limit(self):
        limiter = RateLimiter(default_limit=5, window_seconds=10)

        for i in range(5):
            result = limiter.check_limit('agent1', 'tool1')
            assert result['allowed'] is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(default_limit=3, window_seconds=10)

        # First 3 should succeed
        for i in range(3):
            result = limiter.check_limit('agent1', 'tool1')
            assert result['allowed'] is True

        # 4th should fail
        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is False
        assert result['retry_after'] > 0

    def test_per_tool_limits(self):
        limiter = RateLimiter(
            default_limit=10,
            window_seconds=10,
            per_tool_limits={'exec': 2}
        )

        # exec should have limit of 2
        for i in range(2):
            result = limiter.check_limit('agent1', 'exec')
            assert result['allowed'] is True

        result = limiter.check_limit('agent1', 'exec')
        assert result['allowed'] is False

        # Other tools should have default limit
        for i in range(10):
            result = limiter.check_limit('agent1', 'read_file')
            assert result['allowed'] is True

    def test_sliding_window(self):
        limiter = RateLimiter(default_limit=2, window_seconds=1)

        # Use up limit
        limiter.check_limit('agent1', 'tool1')
        limiter.check_limit('agent1', 'tool1')

        # Should be blocked
        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is False

        # Wait for window to slide
        time.sleep(1.1)

        # Should be allowed again
        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is True

    def test_separate_agent_tracking(self):
        limiter = RateLimiter(default_limit=2, window_seconds=10)

        # Agent1 uses limit
        limiter.check_limit('agent1', 'tool1')
        limiter.check_limit('agent1', 'tool1')

        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is False

        # Agent2 should have separate limit
        result = limiter.check_limit('agent2', 'tool1')
        assert result['allowed'] is True

    def test_reset(self):
        limiter = RateLimiter(default_limit=2, window_seconds=10)

        limiter.check_limit('agent1', 'tool1')
        limiter.check_limit('agent1', 'tool1')

        # Should be at limit
        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is False

        # Reset
        limiter.reset('agent1', 'tool1')

        # Should be allowed again
        result = limiter.check_limit('agent1', 'tool1')
        assert result['allowed'] is True

    def test_get_stats(self):
        limiter = RateLimiter(default_limit=10, window_seconds=60)

        limiter.check_limit('agent1', 'tool1')
        limiter.check_limit('agent1', 'tool2')
        limiter.check_limit('agent2', 'tool1')

        stats = limiter.get_stats()

        assert stats['tracked_combinations'] == 3
        assert stats['total_calls_in_windows'] == 3
        assert 'agent1' in stats['agents']
        assert 'tool1' in stats['tools']
