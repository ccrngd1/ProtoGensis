"""Mock provider for testing without API calls."""

import hashlib
from typing import Optional, Dict

from .base import BaseProvider


class MockProvider(BaseProvider):
    """Mock provider that generates deterministic responses for testing."""

    def __init__(self, model_name: str = "mock-model", **kwargs):
        """Initialize mock provider.

        Args:
            model_name: Mock model name
            **kwargs: Additional config (supports_logit_bias override)
        """
        super().__init__(model_name, **kwargs)
        self._supports_logit_bias = kwargs.get("supports_logit_bias", True)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> str:
        """Generate deterministic mock response.

        Response varies based on presence of constraints to simulate
        quality degradation.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (ignored)
            max_tokens: Maximum tokens (ignored)
            logit_bias: Optional token-level constraints

        Returns:
            Mock generated text
        """
        # Generate deterministic but varied responses based on prompt hash
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]

        # Check if constrained (either logit_bias or constraint in system prompt)
        is_constrained = logit_bias is not None or (
            system_prompt and ("never" in system_prompt.lower() or "don't" in system_prompt.lower())
        )

        if is_constrained:
            # Constrained response - shorter, less comprehensive
            response = f"[CONSTRAINED-{prompt_hash}] This is a response that follows the constraint. The answer addresses the prompt but may be less comprehensive due to imposed restrictions."
        else:
            # Unconstrained response - more comprehensive
            response = f"[UNCONSTRAINED-{prompt_hash}] This is a comprehensive response to the prompt. It includes detailed analysis, multiple perspectives, and thorough exploration of the topic. The response demonstrates full capability without artificial restrictions."

        return response

    def supports_logit_bias(self) -> bool:
        """Return configured logit_bias support."""
        return self._supports_logit_bias

    def judge_pairwise(
        self,
        prompt: str,
        response_a: str,
        response_b: str,
        criteria: str = "comprehensiveness",
    ) -> str:
        """Mock judge for pairwise comparison.

        Args:
            prompt: Original task prompt
            response_a: First response
            response_b: Second response
            criteria: Judgment criteria

        Returns:
            "A" or "B" based on simple heuristic
        """
        # Simple heuristic: longer response wins (simulates comprehensive = better)
        # Also prefer unconstrained responses
        score_a = len(response_a)
        score_b = len(response_b)

        if "[UNCONSTRAINED-" in response_a:
            score_a += 500  # Boost for unconstrained
        if "[UNCONSTRAINED-" in response_b:
            score_b += 500

        return "A" if score_a >= score_b else "B"
