"""Google Gemini provider (google-genai SDK)."""

from __future__ import annotations

import os

from .base import Provider, ProviderError


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-pro", temperature: float | None = 0.7):
        super().__init__(model, temperature)
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("google-genai package not installed") from exc
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set")
        self._client = genai.Client(api_key=api_key)

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        )
        if self.temperature is not None:
            config.temperature = self.temperature
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )
        except Exception as exc:  # google-genai raises assorted exception types
            raise ProviderError(f"{self.label}: {exc}") from exc
        return response.text or ""
