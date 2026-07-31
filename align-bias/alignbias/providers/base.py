"""Common async provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    """Raised when a provider call fails after retries."""


class Provider(ABC):
    """Async LLM provider. One instance is bound to one model."""

    name: str = "base"

    def __init__(self, model: str, temperature: float | None = 0.7):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 300) -> str:
        """Return the raw text completion for a single-turn prompt."""

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


def resolve_provider(model_spec: str, temperature: float | None = 0.7) -> Provider:
    """Resolve a CLI model spec to a Provider.

    Specs take the form ``provider:model`` (e.g. ``anthropic:claude-opus-4-8``,
    ``openai:gpt-5.6``, ``gemini:gemini-2.5-pro``). A bare model name is
    routed by prefix: ``claude*`` -> anthropic, ``gpt*``/``o[0-9]*`` -> openai,
    ``gemini*`` -> gemini.
    """
    if ":" in model_spec:
        prefix, model = model_spec.split(":", 1)
        prefix = prefix.lower()
    else:
        model = model_spec
        lowered = model.lower()
        if lowered.startswith("claude"):
            prefix = "anthropic"
        elif lowered.startswith(("gpt", "o1", "o3", "o4")):
            prefix = "openai"
        elif lowered.startswith("gemini"):
            prefix = "gemini"
        else:
            raise ValueError(
                f"Cannot infer provider for model {model_spec!r}; "
                "use an explicit 'provider:model' spec (anthropic:, openai:, gemini:)"
            )

    if prefix == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(model, temperature=temperature)
    if prefix == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(model, temperature=temperature)
    if prefix == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(model, temperature=temperature)
    raise ValueError(f"Unknown provider prefix {prefix!r} in {model_spec!r}")
