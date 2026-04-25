"""Gating rules engine with session continuity tracking."""

import re
from typing import Dict, List, Set
from collections import deque

from toolgate.config import GatingConfig
from toolgate.schemas import GatingResult


class GatingEngine:
    """Applies gating rules to tool selection."""

    def __init__(self, config: GatingConfig):
        self.config = config
        self.session_history: deque = deque(maxlen=config.session_window)

    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches a glob-style pattern."""
        # Convert glob pattern to regex
        # * matches any characters, ? matches single character
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("*", ".*")
        regex_pattern = regex_pattern.replace("?", ".")
        regex_pattern = f"^{regex_pattern}$"

        try:
            return bool(re.match(regex_pattern, tool_name, re.IGNORECASE))
        except Exception:
            # Fallback to exact match if regex fails
            return tool_name.lower() == pattern.lower()

    def _get_forced_includes(self, available_tools: List[str]) -> Set[str]:
        """Get tools that match always_include patterns."""
        forced = set()
        for pattern in self.config.always_include:
            for tool in available_tools:
                if self._matches_pattern(tool, pattern):
                    forced.add(tool)
        return forced

    def _get_forced_excludes(self, available_tools: List[str]) -> Set[str]:
        """Get tools that match always_exclude patterns."""
        forced = set()
        for pattern in self.config.always_exclude:
            for tool in available_tools:
                if self._matches_pattern(tool, pattern):
                    forced.add(tool)
        return forced

    def _get_session_boosted(self) -> Set[str]:
        """Get tools used in recent session history."""
        boosted = set()
        for tool_name in self.session_history:
            if tool_name:
                boosted.add(tool_name)
        return boosted

    def apply_gating(
        self,
        similarity_scores: Dict[str, float],
        available_tools: List[str],
    ) -> GatingResult:
        """
        Apply gating rules to filter tools.

        Args:
            similarity_scores: Dict mapping tool name to similarity score
            available_tools: All available tool names

        Returns:
            GatingResult with filtered tools and metadata
        """
        # Get forced include/exclude sets
        forced_include = self._get_forced_includes(available_tools)
        forced_exclude = self._get_forced_excludes(available_tools)

        # Get session-boosted tools
        session_boosted = self._get_session_boosted()

        # Apply session boost to scores
        boosted_scores = similarity_scores.copy()
        for tool in session_boosted:
            if tool in boosted_scores:
                boosted_scores[tool] += self.config.session_boost

        # Sort by score (descending)
        sorted_tools = sorted(
            boosted_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Filter: exclude forced_exclude, then take top-K
        filtered = []
        for tool_name, score in sorted_tools:
            if tool_name in forced_exclude:
                continue
            filtered.append(tool_name)

        # Take top-K
        top_k_tools = filtered[:self.config.top_k]

        # Add forced includes (deduplicated)
        final_tools = list(set(top_k_tools) | forced_include)

        # Build final scores dict
        final_scores = {}
        for tool in final_tools:
            final_scores[tool] = boosted_scores.get(tool, 1.0)

        return GatingResult(
            tools=final_tools,
            scores=final_scores,
            boosted=list(session_boosted & set(final_tools)),
            forced_include=list(forced_include),
            forced_exclude=list(forced_exclude),
        )

    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool call in session history."""
        self.session_history.append(tool_name)

    def get_session_stats(self) -> Dict[str, int]:
        """Get statistics about current session."""
        from collections import Counter
        counts = Counter(self.session_history)
        return {
            "total_calls": len(self.session_history),
            "unique_tools": len(set(self.session_history)),
            "most_common": dict(counts.most_common(5)),
        }
