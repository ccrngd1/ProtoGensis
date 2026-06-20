"""NeedleRouter - orchestrates ToolGate + Needle + Escalation."""

import re
from typing import Dict, List, Optional, Set
from collections import deque
import numpy as np

from needleroute.config import NeedleRouteConfig, GatingRules
from needleroute.schemas import (
    MCPTool,
    IndexedTool,
    GatingResult,
    RoutingDecision,
    EscalationRequest,
    NeedleScore,
)
from needleroute.needle_model import NeedleModel, create_needle_model
from needleroute.escalation import EscalationProvider, create_escalation_provider


class NeedleRouter:
    """
    Orchestrates tool routing pipeline:
    1. ToolGate filtering (top-K selection)
    2. Needle model scoring
    3. Confidence-based escalation
    """

    def __init__(self, config: NeedleRouteConfig):
        """
        Initialize router.

        Args:
            config: NeedleRoute configuration
        """
        self.config = config

        # Initialize Needle model
        self.needle = create_needle_model(config.needle.model_path)

        # Initialize escalation provider
        self.escalation = create_escalation_provider(config.escalation)

        # Session history for continuity boost
        self.session_history: deque = deque(maxlen=config.toolgate.session_window)

        # Pre-encoded tool embeddings cache
        self.tool_embeddings: Dict[str, np.ndarray] = {}

        # Destructive tools patterns (tools that modify state)
        self.destructive_patterns = [
            r".*delete.*",
            r".*remove.*",
            r".*rm.*",
            r".*destroy.*",
            r".*drop.*",
            r".*write.*",
            r".*create.*",
            r".*modify.*",
            r".*update.*",
        ]

    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches a pattern."""
        regex_pattern = pattern.replace(".", r"\.")
        regex_pattern = regex_pattern.replace("*", ".*")
        regex_pattern = regex_pattern.replace("?", ".")
        regex_pattern = f"^{regex_pattern}$"

        try:
            return bool(re.match(regex_pattern, tool_name, re.IGNORECASE))
        except Exception:
            return tool_name.lower() == pattern.lower()

    def _is_destructive_tool(self, tool_name: str) -> bool:
        """Check if tool is potentially destructive."""
        tool_lower = tool_name.lower()
        for pattern in self.destructive_patterns:
            if re.match(pattern, tool_lower):
                return True
        return False

    def _apply_gating_rules(
        self,
        scores: Dict[str, float],
        all_tools: List[str],
        gating_rules: GatingRules,
    ) -> GatingResult:
        """
        Apply ToolGate filtering rules.

        Args:
            scores: Tool similarity scores
            all_tools: All available tool names
            gating_rules: Gating configuration

        Returns:
            GatingResult with filtered tools
        """
        # Get forced include/exclude
        forced_include = set()
        for pattern in gating_rules.always_include:
            for tool in all_tools:
                if self._matches_pattern(tool, pattern):
                    forced_include.add(tool)

        forced_exclude = set()
        for pattern in gating_rules.always_exclude:
            for tool in all_tools:
                if self._matches_pattern(tool, pattern):
                    forced_exclude.add(tool)

        # Get session-boosted tools
        session_boosted = set(self.session_history)

        # Apply session boost
        boosted_scores = scores.copy()
        for tool in session_boosted:
            if tool in boosted_scores:
                boosted_scores[tool] += self.config.toolgate.session_boost

        # Sort by score descending
        sorted_tools = sorted(
            boosted_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Filter: exclude forced_exclude, take top-K
        filtered = []
        for tool_name, score in sorted_tools:
            if tool_name in forced_exclude:
                continue
            filtered.append(tool_name)

        # Take top-K
        top_k_tools = filtered[:self.config.toolgate.top_k]

        # Add forced includes
        final_tools = list(set(top_k_tools) | forced_include)

        # Build final scores
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

    def pre_encode_tools(self, tools: List[MCPTool]) -> None:
        """
        Pre-encode tool definitions for fast scoring.

        Args:
            tools: List of tools to encode
        """
        if not self.needle.is_available():
            print("Warning: Needle model unavailable, skipping tool encoding")
            return

        self.tool_embeddings.clear()

        for tool in tools:
            try:
                embedding = self.needle.encode_tool(tool)
                self.tool_embeddings[tool.name] = embedding
            except Exception as e:
                print(f"Warning: Failed to encode tool {tool.name}: {e}")

    async def route(
        self,
        query: str,
        available_tools: List[MCPTool],
        similarity_scores: Dict[str, float],
        destructive_hint: bool = False,
    ) -> RoutingDecision:
        """
        Route a query to the best tool.

        Pipeline:
        1. ToolGate filtering (already done via similarity_scores)
        2. Apply gating rules
        3. Needle model scoring
        4. Confidence check
        5. Escalation if needed

        Args:
            query: User query
            available_tools: Tools after ToolGate filtering
            similarity_scores: Similarity scores from ToolGate
            destructive_hint: Hint that this operation may be destructive

        Returns:
            RoutingDecision with selected tool and confidence
        """
        # Apply gating rules
        tool_names = [t.name for t in available_tools]
        gating_result = self._apply_gating_rules(
            similarity_scores,
            tool_names,
            self.config.gating
        )

        # Filter available_tools to only gated tools
        filtered_tools = [t for t in available_tools if t.name in gating_result.tools]

        if not filtered_tools:
            # No tools available after gating
            return RoutingDecision(
                selected_tool="error",
                confidence=0.0,
                needle_scores=[],
                escalated=True,
                escalation_reason="No tools available after gating"
            )

        # Check if we should escalate due to destructive hint
        if destructive_hint and self.config.needle.always_escalate_destructive:
            # Escalate to frontier model
            request = EscalationRequest(
                query=query,
                available_tools=filtered_tools,
                reason="destructive_hint"
            )
            response = await self.escalation.escalate(request)

            return RoutingDecision(
                selected_tool=response.selected_tool,
                confidence=1.0,
                needle_scores=[],
                escalated=True,
                escalation_reason="destructive_hint",
                destructive_hint=True
            )

        # Check if Needle model is available
        if not self.needle.is_available():
            # Escalate all calls when Needle unavailable
            request = EscalationRequest(
                query=query,
                available_tools=filtered_tools,
                reason="needle_unavailable"
            )
            response = await self.escalation.escalate(request)

            return RoutingDecision(
                selected_tool=response.selected_tool,
                confidence=1.0,
                needle_scores=[],
                escalated=True,
                escalation_reason="needle_unavailable"
            )

        # Use Needle model to score tools
        try:
            # Encode query
            query_embedding = self.needle.encode_query(query)

            # Get tool embeddings for filtered tools
            tool_embeds = {}
            for tool in filtered_tools:
                if tool.name in self.tool_embeddings:
                    tool_embeds[tool.name] = self.tool_embeddings[tool.name]
                else:
                    # Encode on-the-fly if not cached
                    tool_embeds[tool.name] = self.needle.encode_tool(tool)

            # Score tools
            needle_scores = self.needle.score_tools(query_embedding, tool_embeds)

            if not needle_scores:
                # No scores, escalate
                request = EscalationRequest(
                    query=query,
                    available_tools=filtered_tools,
                    reason="no_scores"
                )
                response = await self.escalation.escalate(request)

                return RoutingDecision(
                    selected_tool=response.selected_tool,
                    confidence=0.0,
                    needle_scores=[],
                    escalated=True,
                    escalation_reason="no_scores"
                )

            # Get top tool
            top_tool = needle_scores[0]

            # Check confidence threshold
            if top_tool.confidence < self.config.needle.confidence_threshold:
                # Low confidence, escalate
                request = EscalationRequest(
                    query=query,
                    available_tools=filtered_tools,
                    reason=f"low_confidence ({top_tool.confidence:.3f} < {self.config.needle.confidence_threshold})"
                )
                response = await self.escalation.escalate(request)

                return RoutingDecision(
                    selected_tool=response.selected_tool,
                    confidence=top_tool.confidence,
                    needle_scores=needle_scores,
                    escalated=True,
                    escalation_reason="low_confidence"
                )

            # Check if top tool is destructive
            if self._is_destructive_tool(top_tool.tool_name) and self.config.needle.always_escalate_destructive:
                request = EscalationRequest(
                    query=query,
                    available_tools=filtered_tools,
                    reason="destructive_tool_detected"
                )
                response = await self.escalation.escalate(request)

                return RoutingDecision(
                    selected_tool=response.selected_tool,
                    confidence=top_tool.confidence,
                    needle_scores=needle_scores,
                    escalated=True,
                    escalation_reason="destructive_tool_detected",
                    destructive_hint=True
                )

            # High confidence, use Needle's selection
            return RoutingDecision(
                selected_tool=top_tool.tool_name,
                confidence=top_tool.confidence,
                needle_scores=needle_scores,
                escalated=False
            )

        except Exception as e:
            print(f"Error during Needle routing: {e}")
            # Fallback: escalate
            request = EscalationRequest(
                query=query,
                available_tools=filtered_tools,
                reason=f"needle_error: {e}"
            )
            response = await self.escalation.escalate(request)

            return RoutingDecision(
                selected_tool=response.selected_tool,
                confidence=0.0,
                needle_scores=[],
                escalated=True,
                escalation_reason=f"needle_error: {e}"
            )

    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool call for session continuity."""
        self.session_history.append(tool_name)

    def get_session_stats(self) -> Dict:
        """Get session statistics."""
        from collections import Counter
        counts = Counter(self.session_history)
        return {
            "total_calls": len(self.session_history),
            "unique_tools": len(set(self.session_history)),
            "most_common": dict(counts.most_common(5)),
        }
