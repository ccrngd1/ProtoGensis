"""LLM provider layer: a thin LiteLLM wrapper.

The model is configured exclusively via the COBALT_MODEL environment
variable; no command or prompt logic ever names a model. DEFAULT_MODEL is
the single place a model string appears, used only when COBALT_MODEL is
unset.

Examples:
    COBALT_MODEL=bedrock/anthropic.claude-sonnet-4-6   # AWS Bedrock (default family)
    COBALT_MODEL=litellm/sonnet45                       # local LiteLLM proxy at :4000
    COBALT_MODEL=anthropic/claude-sonnet-4-6            # direct Anthropic API

For the local proxy also set:
    COBALT_API_BASE=http://localhost:4000
    COBALT_API_KEY=sk-...            # whatever key the proxy expects
"""

from __future__ import annotations

import os

# The only model string in the codebase. Overridden by COBALT_MODEL.
DEFAULT_MODEL = "bedrock/anthropic.claude-sonnet-4-6"


class ProviderError(RuntimeError):
    pass


def get_model() -> str:
    return os.environ.get("COBALT_MODEL", DEFAULT_MODEL)


def complete(system: str, user: str, max_tokens: int = 8000) -> str:
    """One-shot completion. Returns the assistant text.

    Imports litellm lazily so tests (which monkeypatch this function) and
    parser-only usage never pay the import or require credentials.
    """
    try:
        import litellm
    except ImportError as e:  # pragma: no cover
        raise ProviderError(
            "litellm is not installed; run `pip install -e .` from cobol-agent/"
        ) from e

    kwargs: dict = {
        "model": get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    api_base = os.environ.get("COBALT_API_BASE")
    if api_base:
        kwargs["api_base"] = api_base
    api_key = os.environ.get("COBALT_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key

    try:
        response = litellm.completion(**kwargs)
    except Exception as e:
        raise ProviderError(f"LLM call failed ({get_model()}): {e}") from e

    content = response.choices[0].message.content
    if not content:
        raise ProviderError(f"empty completion from {get_model()}")
    return content
