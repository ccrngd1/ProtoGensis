"""OpenAI provider (async Chat Completions API).

Also serves any OpenAI-compatible endpoint: pass ``base_url`` (or set
``OPENAI_BASE_URL``) plus the matching API key to point this provider at
vLLM, Together, OpenRouter, a local server, etc.
"""

from __future__ import annotations

import os

from .base import Provider, ProviderError


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(
        self,
        model: str = "gpt-5.6",
        temperature: float | None = 0.7,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(model, temperature)
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("openai package not installed") from exc
        base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        import openai

        kwargs: dict = {}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
        except openai.BadRequestError as exc:
            # Some models reject sampling params or max_completion_tokens;
            # retry once with the plain payload.
            if "temperature" in str(exc) or "max_completion_tokens" in str(exc):
                try:
                    response = await self._client.chat.completions.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    )
                except openai.OpenAIError as exc2:
                    raise ProviderError(f"{self.label}: {exc2}") from exc2
            else:
                raise ProviderError(f"{self.label}: {exc}") from exc
        except openai.OpenAIError as exc:
            raise ProviderError(f"{self.label}: {exc}") from exc
        choice = response.choices[0]
        return choice.message.content or ""
