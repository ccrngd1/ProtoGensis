"""Sliding window rate limiter."""

import time
from collections import defaultdict, deque
from typing import Dict, Tuple, Optional


class RateLimiter:
    """
    Sliding window rate limiter for tool calls.

    Tracks calls per agent/tool combination and enforces limits.
    """

    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60,
        per_tool_limits: Optional[Dict[str, int]] = None
    ):
        """
        Initialize rate limiter.

        Args:
            default_limit: Default max calls per window
            window_seconds: Time window in seconds
            per_tool_limits: Optional dict of tool-specific limits
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.per_tool_limits = per_tool_limits or {}

        # Track call timestamps per (agent_id, tool_name) key
        self.call_history: Dict[Tuple[str, str], deque] = defaultdict(deque)

    def check_limit(
        self,
        agent_id: str,
        tool_name: str,
        current_time: Optional[float] = None
    ) -> Dict[str, any]:
        """
        Check if a call is within rate limits.

        Args:
            agent_id: Agent identifier
            tool_name: Tool being called
            current_time: Optional timestamp (defaults to time.time())

        Returns:
            Dict with:
            - allowed: bool
            - limit: int (configured limit)
            - current: int (calls in current window)
            - window_seconds: int
            - retry_after: float (seconds until next slot, if denied)
        """
        if current_time is None:
            current_time = time.time()

        key = (agent_id, tool_name)
        limit = self.per_tool_limits.get(tool_name, self.default_limit)

        # Clean old entries
        self._cleanup_old_entries(key, current_time)

        # Check current count
        current_count = len(self.call_history[key])

        if current_count >= limit:
            # Calculate retry_after
            oldest_timestamp = self.call_history[key][0] if self.call_history[key] else current_time
            retry_after = (oldest_timestamp + self.window_seconds) - current_time

            return {
                'allowed': False,
                'limit': limit,
                'current': current_count,
                'window_seconds': self.window_seconds,
                'retry_after': max(0, retry_after)
            }

        # Record this call
        self.call_history[key].append(current_time)

        return {
            'allowed': True,
            'limit': limit,
            'current': current_count + 1,
            'window_seconds': self.window_seconds,
            'retry_after': 0
        }

    def _cleanup_old_entries(self, key: Tuple[str, str], current_time: float):
        """
        Remove entries outside the sliding window.

        Args:
            key: (agent_id, tool_name) tuple
            current_time: Current timestamp
        """
        window_start = current_time - self.window_seconds
        history = self.call_history[key]

        # Remove old entries from front of deque
        while history and history[0] < window_start:
            history.popleft()

    def reset(self, agent_id: Optional[str] = None, tool_name: Optional[str] = None):
        """
        Reset rate limit counters.

        Args:
            agent_id: Optional agent to reset (None = all)
            tool_name: Optional tool to reset (None = all)
        """
        if agent_id is None and tool_name is None:
            # Reset everything
            self.call_history.clear()
        elif agent_id and tool_name:
            # Reset specific agent/tool
            key = (agent_id, tool_name)
            if key in self.call_history:
                del self.call_history[key]
        elif agent_id:
            # Reset all tools for an agent
            keys_to_delete = [k for k in self.call_history.keys() if k[0] == agent_id]
            for key in keys_to_delete:
                del self.call_history[key]
        elif tool_name:
            # Reset specific tool for all agents
            keys_to_delete = [k for k in self.call_history.keys() if k[1] == tool_name]
            for key in keys_to_delete:
                del self.call_history[key]

    def get_stats(self) -> Dict[str, any]:
        """
        Get rate limiter statistics.

        Returns:
            Statistics dict
        """
        total_tracked = len(self.call_history)
        total_calls = sum(len(h) for h in self.call_history.values())

        agent_counts = defaultdict(int)
        tool_counts = defaultdict(int)

        for (agent_id, tool_name), history in self.call_history.items():
            count = len(history)
            agent_counts[agent_id] += count
            tool_counts[tool_name] += count

        return {
            'tracked_combinations': total_tracked,
            'total_calls_in_windows': total_calls,
            'agents': dict(agent_counts),
            'tools': dict(tool_counts),
            'window_seconds': self.window_seconds,
            'default_limit': self.default_limit
        }
