"""
LLM client helper — wraps boto3 bedrock-runtime for both Haiku and Sonnet calls.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional


# Default model IDs
HAIKU_MODEL = "amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET_MODEL = "amazon-bedrock/global.anthropic.claude-sonnet-4-6"

# Bedrock requires the bare model ID (strip the provider prefix)
_HAIKU_BARE = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_SONNET_BARE = "us.anthropic.claude-sonnet-4-6-20250514-v1:0"

_MODEL_MAP: Dict[str, str] = {
    HAIKU_MODEL: _HAIKU_BARE,
    SONNET_MODEL: _SONNET_BARE,
}


def _call_with_retry(fn: Callable, max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry a function call with exponential backoff on transient errors.

    Handles ThrottlingException and ServiceUnavailable errors from AWS Bedrock.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err = str(e)
            if "ThrottlingException" in err or "ServiceUnavailable" in err:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
            raise
    raise RuntimeError("Max retries exceeded")


def _get_client():
    import boto3  # lazy import so tests can mock easily
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def call_llm(
    prompt: str,
    model: str = HAIKU_MODEL,
    max_tokens: int = 1024,
    system: Optional[str] = None,
    client=None,
) -> str:
    """
    Call an Anthropic model via AWS Bedrock and return the response text.

    Args:
        prompt:     The user-turn content.
        model:      Full model identifier (with or without provider prefix).
        max_tokens: Maximum tokens to generate.
        system:     Optional system prompt.
        client:     Optional pre-built boto3 client (for testing).

    Returns:
        The assistant's response as a string.
    """
    if client is None:
        client = _get_client()

    bare_model = _MODEL_MAP.get(model, model)

    messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]

    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        body["system"] = system

    def _invoke():
        response = client.invoke_model(
            modelId=bare_model,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    return _call_with_retry(_invoke)
