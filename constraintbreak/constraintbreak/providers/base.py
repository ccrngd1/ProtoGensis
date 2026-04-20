"""Base provider abstraction for LLM backends."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model_name: str, **kwargs):
        """Initialize provider with model name and optional config.

        Args:
            model_name: The model identifier (e.g., "gpt-4", "claude-3-opus")
            **kwargs: Provider-specific configuration
        """
        self.model_name = model_name
        self.config = kwargs

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> str:
        """Generate a response from the model.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            logit_bias: Optional token-level constraints (token_id -> bias)

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def supports_logit_bias(self) -> bool:
        """Check if provider supports token-level constraints.

        Returns:
            True if logit_bias is supported
        """
        pass

    def apply_constraint_instruction(
        self,
        base_prompt: str,
        constraint_instruction: str,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Apply instruction-level constraint to prompts.

        Args:
            base_prompt: Original user prompt
            constraint_instruction: Constraint instruction (e.g., "Never use em dashes")
            system_prompt: Optional existing system prompt

        Returns:
            Tuple of (modified_prompt, modified_system_prompt)
        """
        # Default: prepend constraint to system prompt
        if system_prompt:
            modified_system = f"{constraint_instruction}\n\n{system_prompt}"
        else:
            modified_system = constraint_instruction

        return base_prompt, modified_system

    def get_token_ids(self, tokens: List[str]) -> Optional[List[int]]:
        """Get token IDs for given strings (for logit_bias).

        Args:
            tokens: List of token strings

        Returns:
            List of token IDs, or None if not supported
        """
        return None
