#!/usr/bin/env python3
"""
Ensemble Thinking Models Harness

Orchestrates calls to three reasoning models via AWS Bedrock:
- Claude Opus (extended thinking)
- Amazon Nova Premier (deep reasoning)
- Mistral Large (reasoning variant)

Captures full responses, reasoning traces, cost, and latency.
"""

import json
import sys
import os
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path to import shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.bedrock_client import BedrockClient, calculate_cost, PRICING


@dataclass
class ModelConfig:
    """Configuration for a reasoning model"""
    name: str
    model_id: str
    supports_thinking: bool
    cost_per_1k_input: float  # USD
    cost_per_1k_output: float  # USD
    extended_thinking_multiplier: float = 1.0  # Cost multiplier for thinking tokens


# Model configurations based on AWS Bedrock pricing
MODELS = {
    "opus": ModelConfig(
        name="Claude Opus 4.6 (Extended Thinking)",
        model_id="us.anthropic.claude-opus-4-6-v1",
        supports_thinking=True,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        extended_thinking_multiplier=1.0
    ),
    "nova": ModelConfig(
        name="Amazon Nova Pro",
        model_id="us.amazon.nova-pro-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.0032,
        extended_thinking_multiplier=1.0
    ),
    "mistral": ModelConfig(
        name="Mistral Large",
        model_id="mistral.mistral-large-2402-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.004,
        cost_per_1k_output=0.012,
        extended_thinking_multiplier=1.0
    )
}


@dataclass
class ModelResponse:
    """Response from a single model"""
    model_key: str
    model_name: str
    prompt_id: str
    answer: str
    reasoning_trace: Optional[str]
    latency_ms: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: float
    timestamp: str
    error: Optional[str] = None


class BedrockHarness:
    """Orchestrates calls to reasoning models via AWS Bedrock"""

    def __init__(self):
        try:
            self.client = BedrockClient()
            print("✓ Bedrock client initialized")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Set AWS_BEARER_TOKEN_BEDROCK environment variable")
            raise

    def _call_claude_opus(self, prompt: str, prompt_id: str) -> ModelResponse:
        """Call Claude Opus with extended thinking"""
        model_config = MODELS["opus"]

        try:
            response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=model_config.model_id,
                prompt=prompt,
                max_tokens=16000,
                temperature=None,  # Must be None for extended thinking
                extended_thinking=True,
                thinking_budget=10000
            )

            # For extended thinking, the thinking content is embedded in the response
            # We'll just return the full response as answer (thinking is internal)
            cost_usd = calculate_cost(model_config.model_id, input_tokens, output_tokens)

            return ModelResponse(
                model_key="opus",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=response_text,
                reasoning_trace="Extended thinking enabled (thinking tokens included in output)",
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,  # Included in output_tokens
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"  ⚠️  Error calling Opus: {e}")
            return ModelResponse(
                model_key="opus",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer="",
                reasoning_trace="",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                cost_usd=0.0,
                timestamp=datetime.now().isoformat(),
                error=str(e)
            )

    def _call_nova_pro(self, prompt: str, prompt_id: str) -> ModelResponse:
        """Call Amazon Nova Pro"""
        model_config = MODELS["nova"]

        try:
            response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=model_config.model_id,
                prompt=prompt,
                max_tokens=4096,
                temperature=0.7
            )

            cost_usd = calculate_cost(model_config.model_id, input_tokens, output_tokens)

            return ModelResponse(
                model_key="nova",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=response_text,
                reasoning_trace="Nova Premier deep reasoning (embedded in response)",
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"  ⚠️  Error calling Nova: {e}")
            return ModelResponse(
                model_key="nova",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer="",
                reasoning_trace="",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                cost_usd=0.0,
                timestamp=datetime.now().isoformat(),
                error=str(e)
            )

    def _call_mistral(self, prompt: str, prompt_id: str) -> ModelResponse:
        """Call Claude Sonnet (substituting for Mistral Large)"""
        model_config = MODELS["mistral"]

        try:
            response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=model_config.model_id,
                prompt=prompt,
                max_tokens=4096,
                temperature=0.7
            )

            cost_usd = calculate_cost(model_config.model_id, input_tokens, output_tokens)

            return ModelResponse(
                model_key="mistral",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=response_text,
                reasoning_trace="Sonnet reasoning (embedded in response)",
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"  ⚠️  Error calling Sonnet: {e}")
            return ModelResponse(
                model_key="mistral",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer="",
                reasoning_trace="",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                cost_usd=0.0,
                timestamp=datetime.now().isoformat(),
                error=str(e)
            )

    def run_prompt(self, prompt_id: str, prompt_text: str) -> Dict[str, ModelResponse]:
        """Run a single prompt through all three models"""
        print(f"\n{'='*80}")
        print(f"Running prompt: {prompt_id}")
        print(f"{'='*80}")

        responses = {}

        for model_key, model_func in [
            ("opus", self._call_claude_opus),
            ("nova", self._call_nova_pro),
            ("mistral", self._call_mistral)
        ]:
            print(f"\nCalling {MODELS[model_key].name}...")
            response = model_func(prompt_text, prompt_id)
            responses[model_key] = response

            if response.error:
                print(f"  ❌ Error: {response.error}")
            else:
                print(f"  ✓ Completed in {response.latency_ms}ms")
                print(f"  💰 Cost: ${response.cost_usd:.6f}")
                print(f"  📊 Tokens: {response.input_tokens} in / {response.output_tokens} out")

        return responses

    def run_all_prompts(self, prompts_file: str = "prompts/prompts.json") -> List[Dict[str, Any]]:
        """Run all prompts through all models"""
        with open(prompts_file, 'r') as f:
            data = json.load(f)

        all_results = []

        for prompt_data in data['prompts']:
            prompt_id = prompt_data['id']
            prompt_text = prompt_data['text']

            responses = self.run_prompt(prompt_id, prompt_text)

            result = {
                'prompt': prompt_data,
                'responses': {k: asdict(v) for k, v in responses.items()},
                'timestamp': datetime.now().isoformat()
            }

            all_results.append(result)

        return all_results

    def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Save results to JSON file"""
        # Ensure results directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to {output_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Ensemble Thinking Models Harness")
    parser.add_argument("--prompts", default="prompts/prompts.json",
                       help="Path to prompts JSON file")
    parser.add_argument("--output", default="results/responses.json",
                       help="Output file for results")

    args = parser.parse_args()

    print("="*80)
    print("Ensemble Thinking Models Harness")
    print("="*80)
    print(f"Mode: LIVE (AWS Bedrock)")
    print(f"Prompts: {args.prompts}")
    print(f"Output: {args.output}")
    print("="*80)

    harness = BedrockHarness()
    results = harness.run_all_prompts(args.prompts)
    harness.save_results(results, args.output)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_cost = sum(
        r['responses'][model]['cost_usd']
        for r in results
        for model in ['opus', 'nova', 'mistral']
        if not r['responses'][model].get('error')
    )

    total_time = sum(
        r['responses'][model]['latency_ms']
        for r in results
        for model in ['opus', 'nova', 'mistral']
        if not r['responses'][model].get('error')
    ) / 1000

    print(f"Prompts processed: {len(results)}")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Total time: {total_time:.1f}s")
    if len(results) > 0:
        print(f"Average per prompt: ${total_cost/len(results):.6f}, {total_time/len(results):.1f}s")

    print("\n✓ Experiment complete!")


if __name__ == "__main__":
    main()
