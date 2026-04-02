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

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost, PRICING


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
    # Tier 1: Premium thinking models
    "opus": ModelConfig(
        name="Claude Opus 4.6 (Extended Thinking)",
        model_id="us.anthropic.claude-opus-4-6-v1",
        supports_thinking=True,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        extended_thinking_multiplier=1.0
    ),

    # Tier 2: Mid-tier models
    "nova-pro": ModelConfig(
        name="Amazon Nova Pro",
        model_id="us.amazon.nova-pro-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.0032,
        extended_thinking_multiplier=1.0
    ),
    "mistral-large": ModelConfig(
        name="Mistral Large",
        model_id="mistral.mistral-large-2402-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.004,
        cost_per_1k_output=0.012,
        extended_thinking_multiplier=1.0
    ),
    "llama-3-1-70b": ModelConfig(
        name="Meta Llama 3.1 70B",
        model_id="us.meta.llama3-1-70b-instruct-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.00072,
        cost_per_1k_output=0.00072,
        extended_thinking_multiplier=1.0
    ),

    # Tier 3: Budget models
    "haiku": ModelConfig(
        name="Claude Haiku 4.5",
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004,
        extended_thinking_multiplier=1.0
    ),
    "llama-3-1-8b": ModelConfig(
        name="Meta Llama 3.1 8B",
        model_id="us.meta.llama3-1-8b-instruct-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.00022,
        cost_per_1k_output=0.00022,
        extended_thinking_multiplier=1.0
    ),

    # Tier 4: Micro/Nano models
    "nova-2-lite": ModelConfig(
        name="Amazon Nova 2 Lite",
        model_id="global.amazon.nova-2-lite-v1:0",  # Using global inference profile
        supports_thinking=False,
        cost_per_1k_input=0.00006,
        cost_per_1k_output=0.00024,
        extended_thinking_multiplier=1.0
    ),
    "nova-lite": ModelConfig(
        name="Amazon Nova Lite",
        model_id="us.amazon.nova-lite-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.00006,
        cost_per_1k_output=0.00024,
        extended_thinking_multiplier=1.0
    ),
    "nova-micro": ModelConfig(
        name="Amazon Nova Micro",
        model_id="us.amazon.nova-micro-v1:0",
        supports_thinking=False,
        cost_per_1k_input=0.000035,
        cost_per_1k_output=0.00014,
        extended_thinking_multiplier=1.0
    ),
    # "llama-3-2-3b": ModelConfig(
    #     name="Meta Llama 3.2 3B",
    #     model_id="us.meta.llama3-2-3b-instruct-v1:0",
    #     supports_thinking=False,
    #     cost_per_1k_input=0.00015,
    #     cost_per_1k_output=0.00015,
    #     extended_thinking_multiplier=1.0
    # ),  # DISABLED: Legacy model, not used in 15 days, cannot activate
    # "llama-3-2-1b": ModelConfig(
    #     name="Meta Llama 3.2 1B",
    #     model_id="us.meta.llama3-2-1b-instruct-v1:0",
    #     supports_thinking=False,
    #     cost_per_1k_input=0.0001,
    #     cost_per_1k_output=0.0001,
    #     extended_thinking_multiplier=1.0
    # ),  # DISABLED: Legacy model, not used in 15 days, cannot activate
    "nemotron-nano": ModelConfig(
        name="Nvidia Nemotron Nano 12B",
        model_id="nvidia.nemotron-nano-12b-v2",
        supports_thinking=False,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.00015,
        extended_thinking_multiplier=1.0
    ),
    "gpt-oss": ModelConfig(
        name="OpenAI GPT OSS 120B",
        model_id="openai.gpt-oss-120b-1:0",
        supports_thinking=False,
        cost_per_1k_input=0.004,
        cost_per_1k_output=0.016,
        extended_thinking_multiplier=1.0
    ),
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
    confidence: float = 0.5  # Confidence score 0-1
    error: Optional[str] = None


class BedrockHarness:
    """Orchestrates calls to reasoning models via AWS Bedrock"""

    def __init__(self, models_to_run: List[str] = None):
        """
        Initialize harness.

        Args:
            models_to_run: List of model keys to run. If None, runs all models.
        """
        try:
            self.client = BedrockClient()
            print("✓ Bedrock client initialized")

            # Determine which models to run
            if models_to_run:
                self.active_models = {k: MODELS[k] for k in models_to_run if k in MODELS}
            else:
                self.active_models = MODELS

            print(f"✓ Running {len(self.active_models)} models: {', '.join(self.active_models.keys())}")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Set AWS_BEARER_TOKEN_BEDROCK environment variable")
            raise

    def _build_json_prompt(self, question: str) -> str:
        """Build a prompt that requests JSON output with answer and confidence."""
        return f"""{question}

IMPORTANT: You must respond in valid JSON format with exactly this structure:
{{
  "answer": "Your detailed answer here, with full reasoning and explanation",
  "confidence": 0.85
}}

Where:
- "answer" is your complete response to the question
- "confidence" is a number between 0 and 1 indicating how confident you are in your answer
  - 0.0 = no confidence, complete uncertainty
  - 0.5 = moderate confidence, could go either way
  - 0.8 = high confidence, quite certain
  - 0.95+ = very high confidence, nearly certain

Provide your best reasoning in the "answer" field, then honestly assess your confidence."""

    def _parse_json_response(self, text: str) -> tuple[str, float]:
        """
        Parse JSON response to extract answer and confidence.
        Returns (answer, confidence). If parsing fails, returns (raw_text, 0.5).
        """
        try:
            # Try to find JSON in the response (model might add text before/after)
            import re

            # Look for JSON object
            json_match = re.search(r'\{[^}]*"answer"[^}]*"confidence"[^}]*\}', text, re.DOTALL)
            if not json_match:
                # Try alternate order
                json_match = re.search(r'\{[^}]*"confidence"[^}]*"answer"[^}]*\}', text, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                answer = data.get('answer', text)
                confidence = float(data.get('confidence', 0.5))
                # Clamp confidence to 0-1
                confidence = max(0.0, min(1.0, confidence))
                return answer, confidence
            else:
                # No JSON found, return raw text with default confidence
                return text, 0.5

        except Exception as e:
            print(f"  ⚠️  JSON parsing failed: {e}, using raw response")
            return text, 0.5

    def _call_model_generic(self, model_key: str, prompt: str, prompt_id: str) -> ModelResponse:
        """Call any model with JSON output format."""
        model_config = MODELS[model_key]

        # Build JSON-formatted prompt
        json_prompt = self._build_json_prompt(prompt)

        try:
            # Check if this is a thinking model
            if model_config.supports_thinking:
                response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                    model_id=model_config.model_id,
                    prompt=json_prompt,
                    max_tokens=16000,
                    temperature=None,
                    extended_thinking=True,
                    thinking_budget=10000
                )
            else:
                response_text, input_tokens, output_tokens, latency_ms = self.client.call_model(
                    model_id=model_config.model_id,
                    prompt=json_prompt,
                    max_tokens=4096,
                    temperature=0.7
                )

            # Parse JSON response
            answer, confidence = self._parse_json_response(response_text)

            # Calculate cost
            cost_usd = calculate_cost(model_config.model_id, input_tokens, output_tokens)

            return ModelResponse(
                model_key=model_key,
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=answer,
                reasoning_trace=f"Confidence: {confidence:.2f}" + (
                    " (extended thinking)" if model_config.supports_thinking else ""
                ),
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat(),
                confidence=confidence  # Add confidence to response
            )

        except Exception as e:
            print(f"  ⚠️  Error calling {model_key}: {e}")
            return ModelResponse(
                model_key=model_key,
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
                error=str(e),
                confidence=0.0
            )

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
        """Run a single prompt through all active models (in parallel)"""
        print(f"\n{'='*80}")
        print(f"Running prompt: {prompt_id}")
        print(f"{'='*80}")
        print(f"Calling {len(self.active_models)} models in parallel...")

        # Build JSON-formatted prompt once
        json_prompt = self._build_json_prompt(prompt_text)

        # Build batch of calls for all models
        calls = []
        model_keys = list(self.active_models.keys())

        for model_key in model_keys:
            model_config = self.active_models[model_key]

            if model_config.supports_thinking:
                calls.append({
                    'model_id': model_config.model_id,
                    'prompt': json_prompt,
                    'max_tokens': 16000,
                    'temperature': None,
                    'extended_thinking': True,
                    'thinking_budget': 10000
                })
            else:
                calls.append({
                    'model_id': model_config.model_id,
                    'prompt': json_prompt,
                    'max_tokens': 4096,
                    'temperature': 0.7,
                    'extended_thinking': False
                })

        # Execute all calls in parallel
        print(f"⚡ Parallel execution starting...")
        batch_results = self.client.call_batch(calls, max_workers=len(self.active_models))

        # Parse results into ModelResponse objects
        responses = {}
        for idx, model_key in enumerate(model_keys):
            model_config = self.active_models[model_key]
            response_text, input_tokens, output_tokens, latency_ms = batch_results[idx]

            # Handle empty responses (errors)
            if not response_text and input_tokens == 0:
                responses[model_key] = ModelResponse(
                    model_key=model_key,
                    model_name=model_config.name,
                    prompt_id=prompt_id,
                    answer="",
                    reasoning_trace="",
                    latency_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    thinking_tokens=0,
                    cost_usd=0.0,
                    confidence=0.0,
                    timestamp=datetime.now().isoformat(),
                    error="API call failed"
                )
                print(f"\n  ❌ {model_config.name}: Error")
                continue

            # Parse JSON response
            answer, confidence = self._parse_json_response(response_text)

            # Calculate cost
            cost_usd = calculate_cost(model_config.model_id, input_tokens, output_tokens)

            responses[model_key] = ModelResponse(
                model_key=model_key,
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=answer,
                reasoning_trace=f"Confidence: {confidence:.2f}" + (
                    " (extended thinking)" if model_config.supports_thinking else ""
                ),
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                confidence=confidence,
                timestamp=datetime.now().isoformat()
            )

            # Print result
            print(f"\n  ✓ {model_config.name}: {latency_ms}ms | ${cost_usd:.6f} | {input_tokens}→{output_tokens} tokens | conf={confidence:.2f}")

        print(f"\n⚡ All models completed!")
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
    parser.add_argument("--models", nargs='+',
                       help="Specific models to run (e.g., --models opus haiku nova-pro)")
    parser.add_argument("--exclude-opus", action="store_true",
                       help="Exclude Opus from the model list")

    args = parser.parse_args()

    # Determine which models to run
    if args.models:
        models_to_run = args.models
    elif args.exclude_opus:
        models_to_run = [k for k in MODELS.keys() if k != "opus"]
    else:
        models_to_run = None  # Run all

    print("="*80)
    print("Ensemble Thinking Models Harness")
    print("="*80)
    print(f"Mode: LIVE (AWS Bedrock)")
    print(f"Prompts: {args.prompts}")
    print(f"Output: {args.output}")
    if args.models:
        print(f"Models: {', '.join(args.models)}")
    elif args.exclude_opus:
        print(f"Models: ALL EXCEPT OPUS")
    else:
        print(f"Models: ALL ({len(MODELS)} models)")
    print("="*80)

    harness = BedrockHarness(models_to_run=models_to_run)
    results = harness.run_all_prompts(args.prompts)
    harness.save_results(results, args.output)

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    # Calculate stats across all models that were run
    model_keys = list(harness.active_models.keys())

    total_cost = sum(
        r['responses'][model]['cost_usd']
        for r in results
        for model in model_keys
        if model in r['responses'] and not r['responses'][model].get('error')
    )

    total_time = sum(
        r['responses'][model]['latency_ms']
        for r in results
        for model in model_keys
        if model in r['responses'] and not r['responses'][model].get('error')
    ) / 1000

    print(f"Prompts processed: {len(results)}")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Total time: {total_time:.1f}s")
    if len(results) > 0:
        print(f"Average per prompt: ${total_cost/len(results):.6f}, {total_time/len(results):.1f}s")

    print("\n✓ Experiment complete!")


if __name__ == "__main__":
    main()
