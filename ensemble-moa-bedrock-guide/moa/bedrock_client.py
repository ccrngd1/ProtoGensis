"""
Bedrock API integration with async support.
Uses shared Bedrock client for HTTP-based API calls.
"""

import asyncio
import sys
import os
from typing import Dict

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from ensemble_shared.bedrock_client import BedrockClient as SharedBedrockClient, calculate_cost


class BedrockClient:
    """
    Bedrock API client using shared HTTP-based client.
    Wraps shared client's synchronous calls in async for compatibility with MoA.
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize Bedrock client."""
        try:
            self.region = region
            self.client = SharedBedrockClient(region=region)
        except ValueError as e:
            raise RuntimeError(f"Failed to initialize Bedrock client: {e}")

    async def invoke_model(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """
        Invoke a Bedrock model asynchronously.

        Args:
            model_id: Bedrock model ID (e.g., 'us.amazon.nova-lite-v1:0')
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model-specific parameters (ignored for now)

        Returns:
            Dict with 'response', 'input_tokens', 'output_tokens'
        """
        # Run the synchronous shared client call in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._invoke_sync,
            model_id,
            prompt,
            max_tokens,
            temperature
        )
        return result

    def _invoke_sync(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict:
        """Synchronous invoke call (run in thread pool)."""
        try:
            response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=model_id,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return {
                "response": response_text,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens)
            }
        except Exception as e:
            raise RuntimeError(f"Bedrock API call failed for {model_id}: {e}")
