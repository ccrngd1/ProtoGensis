"""OpenAI provider implementation."""

import os
from typing import Optional, Dict, List
from openai import OpenAI

from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI API provider with logit_bias support."""

    def __init__(self, model_name: str = "gpt-4", **kwargs):
        """Initialize OpenAI provider.

        Args:
            model_name: OpenAI model name (default: gpt-4)
            **kwargs: Additional config (api_key, etc.)
        """
        super().__init__(model_name, **kwargs)
        api_key = kwargs.get("api_key", os.getenv("OPENAI_API_KEY"))
        self.client = OpenAI(api_key=api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> str:
        """Generate response using OpenAI API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            logit_bias: Optional token-level constraints

        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if logit_bias:
            kwargs["logit_bias"] = logit_bias

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def supports_logit_bias(self) -> bool:
        """OpenAI supports logit_bias."""
        return True

    def get_token_ids(self, tokens: List[str]) -> Optional[List[int]]:
        """Get token IDs for OpenAI tokenizer.

        Note: This is a simplified implementation. Production code should
        use tiktoken for accurate tokenization.

        Args:
            tokens: List of token strings

        Returns:
            List of token IDs (placeholder implementation)
        """
        # Placeholder - real implementation would use tiktoken
        # For now, return None to indicate we should use instruction-level
        return None
