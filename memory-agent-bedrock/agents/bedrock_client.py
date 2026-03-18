"""Shared boto3 Bedrock client helper."""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

import boto3

MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon-bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
)

# Strip the "amazon-bedrock/" prefix if present — boto3 wants the raw model ID.
_RAW_MODEL_ID = MODEL_ID.removeprefix("amazon-bedrock/")

_client: Optional[Any] = None
_client_lock = threading.Lock()


def get_client() -> Any:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # Double-check inside lock
                region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
                _client = boto3.client("bedrock-runtime", region_name=region)
    return _client


def invoke(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """Call Haiku 4.5 via bedrock-runtime and return the text response."""
    client = get_client()

    messages = [{"role": "user", "content": prompt}]
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        body["system"] = system

    response = client.invoke_model(
        modelId=_RAW_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]
