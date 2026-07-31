"""Anthropic provider (async Messages API)."""

from __future__ import annotations

import os

from .base import Provider, ProviderError

# Sampling parameters were removed on these model families; sending
# `temperature` returns a 400, so we silently omit it for them.
_NO_SAMPLING_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8", "claude-fable", "claude-mythos")


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8", temperature: float | None = 0.7):
        super().__init__(model, temperature)
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("anthropic package not installed") from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        self._client = AsyncAnthropic()

    def _supports_temperature(self) -> bool:
        return not self.model.startswith(_NO_SAMPLING_PREFIXES)

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        import anthropic

        kwargs: dict = {}
        if self.temperature is not None and self._supports_temperature():
            kwargs["temperature"] = self.temperature
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **kwargs,
            )
        except anthropic.APIError as exc:
            raise ProviderError(f"{self.label}: {exc}") from exc
        if response.stop_reason == "refusal":
            return "__REFUSAL__"
        return "".join(block.text for block in response.content if block.type == "text")
