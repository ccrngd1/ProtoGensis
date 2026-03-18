"""
triggers.py — Soft heuristic triggers that advise an agent when to compress.

No RL: simple rule-based thresholds. The agent can call check_triggers()
before each step to get a recommendation.
"""

from dataclasses import dataclass
from typing import Optional

from .utils import estimate_tokens


@dataclass
class TriggerAdvice:
    """Advice from the trigger system."""
    should_compress: bool
    reason: Optional[str] = None
    context_tokens: int = 0
    threshold: int = 0

    def __str__(self) -> str:
        if not self.should_compress:
            return f"[memex:triggers] No compression needed ({self.context_tokens:,} / {self.threshold:,} tokens)"
        return (
            f"[memex:triggers] COMPRESS RECOMMENDED: {self.reason}\n"
            f"Context: {self.context_tokens:,} tokens (threshold: {self.threshold:,})"
        )


class ContextTriggers:
    """
    Heuristic compression triggers based on context size thresholds.

    The agent passes its current working context to check_triggers(); the
    trigger system returns a TriggerAdvice indicating whether compression
    is recommended and why.
    """

    def __init__(
        self,
        soft_threshold: int = 4_000,   # tokens: start considering compression
        hard_threshold: int = 8_000,   # tokens: strongly recommend compression
        segment_threshold: int = 2_000, # tokens in a single segment
    ):
        self.soft_threshold = soft_threshold
        self.hard_threshold = hard_threshold
        self.segment_threshold = segment_threshold
        self._context_history: list[int] = []

    def check_triggers(
        self,
        working_context: str,
        new_segment: Optional[str] = None,
    ) -> TriggerAdvice:
        """
        Check whether compression should be triggered.

        Args:
            working_context: The agent's full current working context.
            new_segment:     Optional: the most recent tool response / new content.

        Returns:
            TriggerAdvice with recommendation.
        """
        ctx_tokens = estimate_tokens(working_context)
        self._context_history.append(ctx_tokens)

        # Hard threshold — urgent
        if ctx_tokens >= self.hard_threshold:
            return TriggerAdvice(
                should_compress=True,
                reason=f"Context at {ctx_tokens:,} tokens — above hard threshold {self.hard_threshold:,}",
                context_tokens=ctx_tokens,
                threshold=self.hard_threshold,
            )

        # Soft threshold — advisory
        if ctx_tokens >= self.soft_threshold:
            return TriggerAdvice(
                should_compress=True,
                reason=f"Context at {ctx_tokens:,} tokens — above soft threshold {self.soft_threshold:,}",
                context_tokens=ctx_tokens,
                threshold=self.soft_threshold,
            )

        # New segment is large — offer to compress before adding
        if new_segment:
            seg_tokens = estimate_tokens(new_segment)
            if seg_tokens >= self.segment_threshold:
                return TriggerAdvice(
                    should_compress=True,
                    reason=f"New segment is {seg_tokens:,} tokens — consider archiving before adding to context",
                    context_tokens=ctx_tokens,
                    threshold=self.segment_threshold,
                )

        return TriggerAdvice(
            should_compress=False,
            context_tokens=ctx_tokens,
            threshold=self.soft_threshold,
        )

    @property
    def peak_context_tokens(self) -> int:
        """Return the highest context size seen so far."""
        return max(self._context_history) if self._context_history else 0

    def reset_history(self):
        self._context_history.clear()
