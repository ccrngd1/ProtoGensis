"""Shared Bedrock HTTP client for ensemble experiments."""

import os
import time
import json
import requests
from typing import Dict, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Global rate limiter
_last_call_time = 0
_rate_limit_lock = threading.Lock()

class BedrockClient:
    """HTTP-based Bedrock client using bearer token authentication."""

    def __init__(self, region: str = "us-east-1", min_delay_between_calls: float = 0.1):
        """Initialize Bedrock client.

        Args:
            region: AWS region for Bedrock endpoint
            min_delay_between_calls: Minimum seconds between API calls (rate limiting)
                                     Default 0.1s allows ~10 QPS, safe for parallel calls
        """
        self.region = region
        self.min_delay = min_delay_between_calls
        self.token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK')

        if not self.token:
            raise ValueError("AWS_BEARER_TOKEN_BEDROCK environment variable not set")

    def _rate_limit(self):
        """Enforce minimum delay between API calls."""
        global _last_call_time
        with _rate_limit_lock:
            now = time.time()
            time_since_last = now - _last_call_time
            if time_since_last < self.min_delay:
                time.sleep(self.min_delay - time_since_last)
            _last_call_time = time.time()

    def call_model(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: Optional[float] = 0.7,
        extended_thinking: bool = False,
        thinking_budget: int = 10000,
        max_retries: int = 3
    ) -> Tuple[str, int, int, int]:
        """Call a Bedrock model via HTTP.

        Args:
            model_id: Bedrock model ID (e.g., "us.anthropic.claude-haiku-4-5-20251001-v1:0")
            prompt: User prompt text
            system_prompt: Optional system prompt (persona)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (None for extended thinking)
            extended_thinking: Enable Claude extended thinking
            thinking_budget: Token budget for thinking (if extended_thinking=True)
            max_retries: Maximum retry attempts for throttling

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, latency_ms)
        """
        url = f"https://bedrock-runtime.{self.region}.amazonaws.com/model/{model_id}/converse"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Build request body
        body: Dict = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens if not extended_thinking else max(max_tokens, thinking_budget)
            }
        }

        # Add temperature if not using extended thinking
        if not extended_thinking and temperature is not None:
            body["inferenceConfig"]["temperature"] = temperature

        # Add system prompt if provided
        if system_prompt:
            body["system"] = [{"text": system_prompt}]

        # Add extended thinking config if enabled
        if extended_thinking:
            body["additionalModelRequestFields"] = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": thinking_budget
                }
            }

        # Retry loop with exponential backoff
        for attempt in range(max_retries):
            try:
                # Rate limit before call
                self._rate_limit()

                # Make API call
                start_time = time.time()
                response = requests.post(url, headers=headers, json=body, timeout=120)
                latency_ms = int((time.time() - start_time) * 1000)

                # Handle throttling
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        backoff = (2 ** attempt) * 1.0  # 1s, 2s, 4s
                        print(f"Throttled (429), retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue
                    else:
                        raise Exception(f"Throttled after {max_retries} retries")

                # Handle other errors
                if response.status_code != 200:
                    error_msg = response.text
                    raise Exception(f"API error {response.status_code}: {error_msg}")

                # Parse successful response
                data = response.json()

                # Debug: Save raw response for extended thinking models
                if extended_thinking and os.environ.get('DEBUG_BEDROCK'):
                    debug_file = f"/tmp/bedrock_response_{int(time.time())}.json"
                    with open(debug_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"DEBUG: Saved raw response to {debug_file}")

                # Extract response text from all content blocks
                # For extended thinking, there may be multiple blocks (thinking + answer)
                content = data.get('output', {}).get('message', {}).get('content', [])

                if not content:
                    print(f"WARNING: No content blocks in response. Full response keys: {data.keys()}")
                    print(f"Output keys: {data.get('output', {}).keys()}")
                    print(f"Message keys: {data.get('output', {}).get('message', {}).keys()}")

                # Collect all text from all content blocks
                text_parts = []
                for i, block in enumerate(content):
                    if 'text' in block:
                        text_parts.append(block['text'])
                    elif 'reasoningContent' in block:
                        # Extended thinking models return reasoningContent (internal reasoning)
                        # This is separate from the answer text, which comes in another block
                        # We can skip this block as it's internal reasoning, not the final answer
                        pass
                    elif extended_thinking:
                        # Debug unexpected block structure
                        print(f"WARNING: Content block {i} has unexpected structure. Keys: {block.keys()}")

                # Join all text parts (thinking + answer)
                response_text = '\n\n'.join(text_parts) if text_parts else ''

                if extended_thinking and not response_text:
                    print(f"WARNING: Extended thinking enabled but no text extracted from {len(content)} content blocks")

                # Extract token usage
                usage = data.get('usage', {})
                input_tokens = usage.get('inputTokens', 0)
                output_tokens = usage.get('outputTokens', 0)

                return response_text, input_tokens, output_tokens, latency_ms

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"Timeout, retrying...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise Exception(f"Timeout after {max_retries} retries")

            except Exception as e:
                if attempt < max_retries - 1 and "503" in str(e):
                    print(f"Service unavailable (503), retrying...")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise

        raise Exception("Max retries exceeded")

    def call_batch(
        self,
        calls: List[Dict],
        max_workers: int = 5
    ) -> List[Tuple[str, int, int, int]]:
        """Execute multiple model calls in parallel.

        Args:
            calls: List of dicts with keys: model_id, prompt, system_prompt (optional),
                   max_tokens (optional), temperature (optional), extended_thinking (optional)
            max_workers: Maximum parallel threads

        Returns:
            List of (response_text, input_tokens, output_tokens, latency_ms) tuples
        """
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all calls
            future_to_idx = {}
            for idx, call in enumerate(calls):
                future = executor.submit(
                    self.call_model,
                    call['model_id'],
                    call['prompt'],
                    call.get('system_prompt'),
                    call.get('max_tokens', 2048),
                    call.get('temperature', 0.7),
                    call.get('extended_thinking', False),
                    call.get('thinking_budget', 10000)
                )
                future_to_idx[future] = idx

            # Collect results in order
            results = [None] * len(calls)
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"Call {idx} failed: {e}")
                    results[idx] = ("", 0, 0, 0)  # Return empty result on failure

        return results


# Pricing table (per 1M tokens)
PRICING = {
    # Claude models
    "us.anthropic.claude-opus-4-6-v1": {"input": 15.00, "output": 75.00},
    "us.anthropic.claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 0.80, "output": 4.00},

    # Nova models
    "us.amazon.nova-micro-v1:0": {"input": 0.035, "output": 0.14},
    "us.amazon.nova-lite-v1:0": {"input": 0.06, "output": 0.24},
    "amazon.nova-2-lite-v1:0": {"input": 0.06, "output": 0.24},
    "global.amazon.nova-2-lite-v1:0": {"input": 0.06, "output": 0.24},  # Global inference profile
    "us.amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},
    "us.amazon.nova-premier-v1:0": {"input": 2.00, "output": 8.00},

    # Mistral models
    "mistral.mistral-7b-instruct-v0:2": {"input": 0.15, "output": 0.20},
    "mistral.mixtral-8x7b-instruct-v0:1": {"input": 0.45, "output": 0.70},
    "mistral.mistral-large-2402-v1:0": {"input": 4.00, "output": 12.00},

    # Llama models
    "us.meta.llama3-2-1b-instruct-v1:0": {"input": 0.10, "output": 0.10},
    "us.meta.llama3-2-3b-instruct-v1:0": {"input": 0.15, "output": 0.15},
    "us.meta.llama3-1-8b-instruct-v1:0": {"input": 0.22, "output": 0.22},
    "us.meta.llama3-1-70b-instruct-v1:0": {"input": 0.72, "output": 0.72},

    # Nvidia models
    "nvidia.nemotron-nano-12b-v2": {"input": 0.15, "output": 0.15},

    # OpenAI models
    "openai.gpt-oss-120b-1:0": {"input": 4.00, "output": 16.00},
}

def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in dollars for a model call.

    Args:
        model_id: Bedrock model ID
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in dollars
    """
    if model_id not in PRICING:
        print(f"Warning: No pricing data for {model_id}, returning $0")
        return 0.0

    pricing = PRICING[model_id]
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost
