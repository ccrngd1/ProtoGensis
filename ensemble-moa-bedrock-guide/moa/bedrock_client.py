"""
Bedrock API integration with async support.

Provides both real and mock implementations for testing without live Bedrock.
"""

import asyncio
import json
import random
from abc import ABC, abstractmethod
from typing import Dict, List


class BaseBedrockClient(ABC):
    """Abstract base class for Bedrock clients."""

    @abstractmethod
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

        Returns:
            Dict with keys: 'response', 'input_tokens', 'output_tokens'
        """
        pass


class BedrockClient(BaseBedrockClient):
    """
    Real Bedrock API client using boto3.

    Requires AWS credentials configured via environment or ~/.aws/credentials
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize Bedrock client.

        Args:
            region: AWS region for Bedrock API
        """
        try:
            import boto3
            self.region = region
            self.client = boto3.client(
                service_name="bedrock-runtime",
                region_name=region
            )
        except ImportError:
            raise ImportError(
                "boto3 is required for BedrockClient. "
                "Install with: pip install boto3"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Bedrock client: {e}. "
                "Ensure AWS credentials are configured."
            )

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
            **kwargs: Additional model-specific parameters

        Returns:
            Dict with 'response', 'input_tokens', 'output_tokens'
        """
        # Run the blocking boto3 call in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._invoke_sync,
            model_id,
            prompt,
            max_tokens,
            temperature,
            kwargs
        )
        return result

    def _invoke_sync(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        extra_params: dict
    ) -> Dict:
        """Synchronous invoke call (run in thread pool)."""
        # Build request body based on model family
        if "anthropic" in model_id:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                **extra_params
            }
        elif "amazon" in model_id:  # Nova models
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                }
            }
        elif "meta.llama" in model_id:
            body = {
                "prompt": prompt,
                "max_gen_len": max_tokens,
                "temperature": temperature,
                **extra_params
            }
        elif "mistral" in model_id:
            body = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **extra_params
            }
        else:
            raise ValueError(f"Unsupported model family: {model_id}")

        # Invoke the model
        response = self.client.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )

        # Parse response based on model family
        response_body = json.loads(response["body"].read())

        if "anthropic" in model_id:
            text = response_body["content"][0]["text"]
            input_tokens = response_body["usage"]["input_tokens"]
            output_tokens = response_body["usage"]["output_tokens"]
        elif "amazon" in model_id:
            text = response_body["output"]["message"]["content"][0]["text"]
            input_tokens = response_body["usage"]["inputTokens"]
            output_tokens = response_body["usage"]["outputTokens"]
        elif "meta.llama" in model_id:
            text = response_body["generation"]
            input_tokens = response_body.get("prompt_token_count", 0)
            output_tokens = response_body.get("generation_token_count", 0)
        elif "mistral" in model_id:
            text = response_body["outputs"][0]["text"]
            # Mistral doesn't always return token counts
            input_tokens = len(prompt.split()) * 1.3  # Rough estimate
            output_tokens = len(text.split()) * 1.3
        else:
            raise ValueError(f"Unsupported model family: {model_id}")

        return {
            "response": text,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens)
        }


class MockBedrockClient(BaseBedrockClient):
    """
    Mock Bedrock client for testing without live API calls.

    Generates synthetic responses with realistic latency and token counts.
    """

    def __init__(self, response_delay_ms: int = 500):
        """
        Initialize mock client.

        Args:
            response_delay_ms: Simulated API latency in milliseconds
        """
        self.response_delay_ms = response_delay_ms
        self.call_count = 0

    async def invoke_model(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict:
        """
        Mock model invocation with synthetic response.

        Generates a response that includes the model name and a summary
        of the input prompt, simulating how models might respond differently.
        """
        self.call_count += 1

        # Simulate API latency
        await asyncio.sleep(self.response_delay_ms / 1000)

        # Extract model name for response generation
        model_name = model_id.split("/")[-1].split(":")[-1]

        # Generate mock response based on model characteristics
        if "nova" in model_id.lower():
            response = f"[Nova Model Response]\n\nBased on the prompt, here's my analysis: {self._generate_mock_content(prompt, 'concise')}"
        elif "anthropic" in model_id.lower() or "claude" in model_id.lower():
            response = f"[Claude Model Response]\n\n{self._generate_mock_content(prompt, 'detailed')}"
        elif "llama" in model_id.lower():
            response = f"[Llama Model Response]\n\n{self._generate_mock_content(prompt, 'technical')}"
        elif "mistral" in model_id.lower():
            response = f"[Mistral Model Response]\n\n{self._generate_mock_content(prompt, 'balanced')}"
        else:
            response = f"[{model_name} Response]\n\n{self._generate_mock_content(prompt, 'generic')}"

        # Estimate token counts
        input_tokens = len(prompt.split()) * 1.3  # Rough approximation
        output_tokens = len(response.split()) * 1.3

        return {
            "response": response,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens)
        }

    def _generate_mock_content(self, prompt: str, style: str) -> str:
        """Generate mock content based on style."""
        templates = {
            "concise": [
                "The key insight is that {topic}. This approach offers efficiency.",
                "In summary: {topic}. Consider the practical implications.",
                "Quick analysis: {topic}. The solution is straightforward.",
            ],
            "detailed": [
                "Let me provide a comprehensive analysis. {topic} This requires careful consideration of multiple factors including context, constraints, and objectives.",
                "I'll break this down systematically. First, {topic}. Second, we should examine the underlying assumptions. Third, consider the broader implications.",
                "Here's a thorough examination: {topic}. The nuances here are important to understand for making informed decisions.",
            ],
            "technical": [
                "From a technical perspective: {topic}. The implementation details matter significantly here.",
                "Analyzing the system: {topic}. Performance and scalability are key considerations.",
                "Technical breakdown: {topic}. The architecture should support these requirements.",
            ],
            "balanced": [
                "Considering both aspects: {topic}. There are trade-offs to evaluate.",
                "A balanced view suggests {topic}. Both approaches have merit.",
                "Evaluating the options: {topic}. The optimal choice depends on context.",
            ],
            "generic": [
                "Based on the input: {topic}. This is the recommended approach.",
                "In response to your query: {topic}. Further details can be provided as needed.",
                "Analysis: {topic}. This addresses the core question.",
            ]
        }

        # Extract a topic summary from the prompt
        words = prompt.split()
        topic_summary = " ".join(words[:10]) + ("..." if len(words) > 10 else "")

        template = random.choice(templates.get(style, templates["generic"]))
        return template.format(topic=topic_summary)
