"""Anthropic/Claude provider implementation."""

import os
from typing import Optional, Dict
from anthropic import Anthropic

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Anthropic/Claude API provider (instruction-level only)."""

    def __init__(self, model_name: str = "claude-3-opus-20240229", **kwargs):
        """Initialize Anthropic provider.

        Args:
            model_name: Claude model name
            **kwargs: Additional config (api_key, etc.)
        """
        super().__init__(model_name, **kwargs)
        api_key = kwargs.get("api_key", os.getenv("ANTHROPIC_API_KEY"))
        self.client = Anthropic(api_key=api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> str:
        """Generate response using Anthropic API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            logit_bias: Ignored (not supported by Anthropic)

        Returns:
            Generated text
        """
        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def supports_logit_bias(self) -> bool:
        """Anthropic does not support logit_bias."""
        return False
