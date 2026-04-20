"""AWS Bedrock provider implementation."""

import json
import os
from typing import Optional, Dict
import boto3

from .base import BaseProvider


class BedrockProvider(BaseProvider):
    """AWS Bedrock provider (instruction-level, token-level where supported)."""

    def __init__(
        self,
        model_name: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        **kwargs
    ):
        """Initialize Bedrock provider.

        Args:
            model_name: Bedrock model ARN
            **kwargs: Additional config (region, aws_access_key_id, etc.)
        """
        super().__init__(model_name, **kwargs)

        session_kwargs = {}
        if "region" in kwargs:
            session_kwargs["region_name"] = kwargs["region"]
        if "aws_access_key_id" in kwargs:
            session_kwargs["aws_access_key_id"] = kwargs["aws_access_key_id"]
        if "aws_secret_access_key" in kwargs:
            session_kwargs["aws_secret_access_key"] = kwargs["aws_secret_access_key"]

        self.client = boto3.client("bedrock-runtime", **session_kwargs)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 2000,
        logit_bias: Optional[Dict[int, float]] = None,
    ) -> str:
        """Generate response using Bedrock API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            logit_bias: Optional token-level constraints (model-dependent)

        Returns:
            Generated text
        """
        # Bedrock uses different formats for different model families
        # This implementation assumes Claude models via Bedrock

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            body["system"] = system_prompt

        response = self.client.invoke_model(
            modelId=self.model_name,
            body=json.dumps(body),
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    def supports_logit_bias(self) -> bool:
        """Bedrock support depends on underlying model.

        Most Bedrock models (Claude, Titan) use instruction-level only.
        Return False by default.
        """
        return False
