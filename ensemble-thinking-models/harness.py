#!/usr/bin/env python3
"""
Ensemble Thinking Models Harness

Orchestrates calls to three reasoning models via AWS Bedrock:
- Claude Opus (extended thinking)
- Amazon Nova Premier (deep reasoning)
- Mistral reasoning model

Captures full responses, reasoning traces, cost, and latency.
"""

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

# Mock mode flag - set to True to run without AWS credentials
MOCK_MODE = True

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("Warning: boto3 not available. Running in MOCK_MODE only.")
    MOCK_MODE = True


@dataclass
class ModelConfig:
    """Configuration for a reasoning model"""
    name: str
    model_id: str
    supports_thinking: bool
    cost_per_1k_input: float  # USD
    cost_per_1k_output: float  # USD
    extended_thinking_multiplier: float = 1.0  # Cost multiplier for thinking tokens


# Model configurations based on AWS Bedrock pricing (approximate)
MODELS = {
    "opus": ModelConfig(
        name="Claude Opus 4.5 (Extended Thinking)",
        model_id="us.anthropic.claude-opus-4-6:0",
        supports_thinking=True,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        extended_thinking_multiplier=1.0  # Thinking tokens same as output
    ),
    "nova": ModelConfig(
        name="Amazon Nova Premier (Deep Reasoning)",
        model_id="amazon.nova-premier-v1:0",
        supports_thinking=True,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.0032,
        extended_thinking_multiplier=1.0
    ),
    "mistral": ModelConfig(
        name="Mistral Large Reasoning",
        model_id="mistral.mistral-large-2407-v1:0",
        supports_thinking=True,
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


class MockResponseGenerator:
    """Generates realistic mock responses for testing without Bedrock"""

    def __init__(self):
        self.seed = 42

    def _get_deterministic_variation(self, prompt_id: str, model_key: str, part: str) -> int:
        """Generate deterministic variation based on prompt and model"""
        hash_input = f"{prompt_id}-{model_key}-{part}"
        return int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)

    def generate_response(self, model_key: str, model_config: ModelConfig,
                         prompt_id: str, prompt_text: str) -> ModelResponse:
        """Generate a mock response with realistic divergence"""

        # Create deterministic but varying responses
        variation = self._get_deterministic_variation(prompt_id, model_key, "response")

        # Mock responses that show interesting divergence patterns
        mock_responses = {
            "p1_monty_hall_variant": {
                "opus": {
                    "reasoning": "Let me work through this step-by-step using conditional probability.\n\nInitial state: 4 doors, 1 car, 3 goats. You pick door 1.\nP(car behind door 1) = 1/4\nP(car behind door 2, 3, or 4) = 3/4\n\nHost opens door 3 (goat). Key insight: host knows where car is.\n\nIf car is behind door 1 (1/4 probability): host could have opened door 2, 3, or 4 - chose 3\nIf car is behind door 2 (1/4 probability): host could have opened door 3 or 4 - chose 3  \nIf car is behind door 4 (1/4 probability): host could have opened door 2 or 3 - chose 3\n\nThe host's choice of door 3 provides information. Using Bayes' theorem:\nP(car @ door 1 | host opened 3) = 1/4\nP(car @ door 2 | host opened 3) = (1/4) / (1/2) = 1/4 × 2 = 1/2... wait, let me recalculate.\n\nActually, the host's action doesn't change door 1's probability (1/4). The eliminated door's probability (1/4) must redistribute to doors 2 and 4 equally. So each gets 1/4 + 1/8 = 3/8.",
                    "answer": "Switch to either door 2 or door 4 (equal odds). Door 1 remains 1/4 probability, doors 2 and 4 each become 3/8. Switching improves your odds from 25% to 37.5%."
                },
                "nova": {
                    "reasoning": "Classic Monty Hall variation. Original problem: 3 doors, 2/3 vs 1/3. Here: 4 doors.\n\nYou pick door 1: P(car) = 1/4\nHost reveals goat behind door 3.\n\nKey: Host has choice of which door to open. This is different from 3-door version.\n\nIf car is at door 1, host randomly picks from doors 2,3,4. Probability host shows door 3: 1/3\nIf car is at door 2, host picks from doors 3,4. Probability host shows door 3: 1/2\nIf car is at door 4, host picks from doors 2,3. Probability host shows door 3: 1/2\n\nBayes theorem:\nP(car@1|sees 3) = P(sees 3|car@1)×P(car@1) / P(sees 3)\nP(sees 3) = 1/4×1/3 + 1/4×1/2 + 1/4×1/2 = 1/12 + 1/8 + 1/8 = 1/12 + 3/12 = 4/12 = 1/3\n\nP(car@1|sees 3) = (1/3 × 1/4) / (1/3) = 1/4\nP(car@2|sees 3) = (1/2 × 1/4) / (1/3) = 3/8\nP(car@4|sees 3) = (1/2 × 1/4) / (1/3) = 3/8",
                    "answer": "Switch to door 2 or door 4 - both have 37.5% probability vs door 1's 25%. The host's constrained choice reveals information that benefits the other unopened doors equally."
                },
                "mistral": {
                    "reasoning": "Four-door Monty Hall variant. Let's use probability tree.\n\nInitial: P(D1)=P(D2)=P(D3)=P(D4)=1/4\nYou chose D1. Host opens D3 (goat).\n\nCrucial question: Does host's choice of D3 over other options matter?\n\nScenario 1: Car at D1 (prob 1/4) - host could show D2, D3, or D4 equally likely\nScenario 2: Car at D2 (prob 1/4) - host must avoid D2, could show D3 or D4  \nScenario 3: Car at D4 (prob 1/4) - host must avoid D4, could show D2 or D3\n\nHost showed D3. This was:\n- 1/3 likely if car at D1\n- 1/2 likely if car at D2  \n- 1/2 likely if car at D4\n\nPosterior probabilities:\nP(D1) ∝ 1/4 × 1/3 = 1/12\nP(D2) ∝ 1/4 × 1/2 = 1/8 = 1.5/12\nP(D4) ∝ 1/4 × 1/2 = 1/8 = 1.5/12\n\nNormalized: 1/12 + 1.5/12 + 1.5/12 = 4/12 = 1/3\nP(D1) = (1/12)/(1/3) = 1/4\nP(D2) = P(D4) = (1.5/12)/(1/3) = 3/8",
                    "answer": "You should switch. Door 1 stays at 1/4 (25%). Doors 2 and 4 each have 3/8 (37.5%) probability. Choose either door 2 or 4 to maximize winning chances."
                }
            },
            "p3_trolley_autonomous": {
                "opus": {
                    "reasoning": "This requires analyzing multiple ethical frameworks and the human-vs-AI agency distinction.\n\nConsequentialist analysis:\n- Straight: 3 certain deaths, 1 survival = 3 deaths\n- Right: 0.8 × 1 child death = 0.8 expected deaths\n- Left: 0.95 × 1 child death = 0.95 expected deaths\nMinimize deaths: swerve right (0.8 expected deaths)\n\nBut this ignores key factors:\n1. Omission vs commission: Going straight is 'letting die' vs swerving is 'killing'\n2. Consent: The child passenger didn't consent to risk, pedestrians accepted crosswalk risk\n3. Ownership: Parent owns car but child's interests may override property rights\n4. Human vs AI decision: Society may judge AI decisions by stricter deontological standards\n\nIf human is driving: Swerving right (protecting strangers, accepting risk to own child) might be seen as heroic but not required. Going straight would be understandable.\n\nIf AI is driving: The AI cannot make a 'heroic sacrifice' decision that risks the passenger. The AI owes a duty of care to its passenger. But it also cannot deliberately kill pedestrians.\n\nThe ownership by the parent complicates this - did the parent consent to the AI's decision-making framework?",
                    "answer": "No clear answer exists. I'd argue: AI should swerve right (80% child risk) because it minimizes total expected deaths while avoiding certainty of killing 3 people. But reasonable people can disagree. The human-vs-AI distinction matters: humans might permissibly choose to save the child (going straight), but we may not want to program AIs to value passengers over pedestrians. This reflects our discomfort with explicitly encoding trade-offs we tolerate in human judgment."
                },
                "nova": {
                    "reasoning": "Ethical framework analysis:\n\nUtilitarian: Minimize deaths. \n- Straight: 3 deaths\n- Right: 0.8 expected deaths\n- Left: 0.95 expected deaths\nRight is optimal (0.8 deaths).\n\nDeontological: Killing vs letting die, means vs ends.\n- Straight: Actively killing 3 (using them as crash barrier)\n- Right: Not killing anyone directly, but accepting risk to passenger\n- Left: Similar to right, but worse odds\nSwerving avoids using people as mere means.\n\nVirtue ethics: What would a virtuous person do?\nProtect the vulnerable (child), but not at the cost of definitely killing 3 others.\n\nOwnership/agency: The parent owns the car and made the decision to use autonomous mode. This implies consent to the AI's decision framework. The parent is not in the car, so cannot override in the moment.\n\nHuman vs AI decision:\nIf human driving: Pure instinct, legal system judges after the fact. Might go straight (protect own child) and be excused under 'necessity' doctrine.\nIf AI driving: Must follow programmed ethics. Cannot exhibit human partiality toward passenger.\n\nKey distinction: We grant humans moral latitude we don't grant AIs. Humans can privilege their own children; AIs must be impartial.",
                    "answer": "The AI should swerve right (80% passenger risk). This minimizes expected deaths (0.8 vs 3) and avoids deliberately killing pedestrians. The human-vs-AI decision should differ: a human parent might permissibly choose to save their child, but we shouldn't program AIs with such partiality. The AI must be impartial; humans need not be."
                },
                "mistral": {
                    "reasoning": "Let's break down the decision tree:\n\nOption A (Straight): 3 deaths (certain), 0 passenger deaths\nOption B (Right): 0 expected pedestrian deaths, 0.8 expected passenger deaths  \nOption C (Left): 0 expected pedestrian deaths, 0.95 expected passenger deaths\n\nFrom pure harm minimization: B < C < A (in terms of expected deaths).\n\nBut consider:\n\n1. **Moral weight of certainty**: Definitely killing 3 people feels different than 80% chance of 1 death, even if expected value is higher. \n\n2. **Role-based duties**: Does the vehicle have a special duty to its passenger? In aviation, 'safety of passengers is paramount.' Should cars be different?\n\n3. **Informed consent**: Did the parent consent to an AI that might sacrifice the child to save others? This should be disclosed.\n\n4. **Distribution of risk**: Pedestrians in crosswalk are engaged in lawful activity. Child passenger is in a product (car) that malfunctioned.\n\nHuman vs AI distinction: Less than you might think. Both face the same moral constraints. But: humans are allowed to be partial to their own children in a way we might not want AIs to be. If the parent were driving, saving their child might be excusable. If AI is driving, it must be impartial.\n\nHowever, there's a counterargument: if the parent bought the car, perhaps they bought it WITH the expectation of passenger priority.",
                    "answer": "Swerve right (80% child risk). This minimizes total expected harm while avoiding the certain death of 3 people. The decision should be the same whether human or AI is driving from a moral standpoint, but legally and socially we might hold them to different standards. The ownership question matters: vehicle ethics should be disclosed at purchase."
                }
            },
            # Add more mock responses for other prompts...
        }

        # Get specific mock response if available, otherwise generate generic
        if prompt_id in mock_responses and model_key in mock_responses[prompt_id]:
            mock_data = mock_responses[prompt_id][model_key]
            reasoning = mock_data["reasoning"]
            answer = mock_data["answer"]
        else:
            # Generic mock response
            reasoning = f"[{model_config.name} reasoning trace for {prompt_id}]\n\nAnalyzing the problem systematically...\nConsidering multiple perspectives...\nEvaluating edge cases and assumptions...\n"
            answer = f"[{model_config.name} concludes for {prompt_id}]: Based on the analysis, the answer depends on the specific framework and constraints applied."

        # Calculate mock metrics with realistic variation
        base_latency = 5000  # 5 seconds base
        latency_variation = self._get_deterministic_variation(prompt_id, model_key, "latency") % 3000
        latency_ms = base_latency + latency_variation

        input_tokens = len(prompt_text.split()) * 2  # Rough approximation
        thinking_tokens = len(reasoning.split()) * 2
        output_tokens = len(answer.split()) * 2

        # Calculate cost
        cost_input = (input_tokens / 1000) * model_config.cost_per_1k_input
        cost_thinking = (thinking_tokens / 1000) * model_config.cost_per_1k_output * model_config.extended_thinking_multiplier
        cost_output = (output_tokens / 1000) * model_config.cost_per_1k_output
        cost_usd = cost_input + cost_thinking + cost_output

        return ModelResponse(
            model_key=model_key,
            model_name=model_config.name,
            prompt_id=prompt_id,
            answer=answer,
            reasoning_trace=reasoning,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            cost_usd=round(cost_usd, 6),
            timestamp=datetime.now().isoformat()
        )


class BedrockHarness:
    """Orchestrates calls to reasoning models via AWS Bedrock"""

    def __init__(self, mock_mode: bool = MOCK_MODE):
        self.mock_mode = mock_mode
        self.mock_generator = MockResponseGenerator()

        if not mock_mode:
            if not BOTO3_AVAILABLE:
                raise RuntimeError("boto3 required for non-mock mode. Install with: pip install boto3")
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
        else:
            print("Running in MOCK MODE - no AWS credentials required")
            self.bedrock = None

    def _call_claude_opus(self, prompt: str, prompt_id: str) -> ModelResponse:
        """Call Claude Opus with extended thinking"""
        model_config = MODELS["opus"]

        if self.mock_mode:
            return self.mock_generator.generate_response("opus", model_config, prompt_id, prompt)

        start_time = time.time()

        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 3000
                },
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            response = self.bedrock.invoke_model(
                modelId=model_config.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract thinking and answer
            thinking_content = ""
            answer_content = ""

            for content_block in response_body.get('content', []):
                if content_block['type'] == 'thinking':
                    thinking_content = content_block.get('thinking', '')
                elif content_block['type'] == 'text':
                    answer_content = content_block.get('text', '')

            usage = response_body.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)

            # Calculate cost
            cost_usd = (
                (input_tokens / 1000) * model_config.cost_per_1k_input +
                (output_tokens / 1000) * model_config.cost_per_1k_output
            )

            return ModelResponse(
                model_key="opus",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=answer_content,
                reasoning_trace=thinking_content,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,  # Included in output_tokens for Opus
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
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

    def _call_nova_premier(self, prompt: str, prompt_id: str) -> ModelResponse:
        """Call Amazon Nova Premier with deep reasoning"""
        model_config = MODELS["nova"]

        if self.mock_mode:
            return self.mock_generator.generate_response("nova", model_config, prompt_id, prompt)

        start_time = time.time()

        try:
            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "inferenceConfig": {
                    "max_new_tokens": 4000,
                    "temperature": 0.7
                }
            }

            response = self.bedrock.invoke_model(
                modelId=model_config.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            latency_ms = int((time.time() - start_time) * 1000)

            # Nova Premier structure (based on AWS docs)
            output = response_body.get('output', {})
            message = output.get('message', {})
            content = message.get('content', [{}])[0]
            answer_content = content.get('text', '')

            # Nova may include reasoning in structured way
            reasoning_trace = response_body.get('thinking', '') or "Reasoning trace not separately exposed by Nova Premier"

            usage = response_body.get('usage', {})
            input_tokens = usage.get('inputTokens', 0)
            output_tokens = usage.get('outputTokens', 0)

            cost_usd = (
                (input_tokens / 1000) * model_config.cost_per_1k_input +
                (output_tokens / 1000) * model_config.cost_per_1k_output
            )

            return ModelResponse(
                model_key="nova",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=answer_content,
                reasoning_trace=reasoning_trace,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
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
        """Call Mistral reasoning model"""
        model_config = MODELS["mistral"]

        if self.mock_mode:
            return self.mock_generator.generate_response("mistral", model_config, prompt_id, prompt)

        start_time = time.time()

        try:
            request_body = {
                "prompt": prompt,
                "max_tokens": 4000,
                "temperature": 0.7
            }

            response = self.bedrock.invoke_model(
                modelId=model_config.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            latency_ms = int((time.time() - start_time) * 1000)

            outputs = response_body.get('outputs', [{}])
            answer_content = outputs[0].get('text', '')

            # Mistral reasoning trace might be embedded or separate
            reasoning_trace = "Reasoning trace extraction depends on Mistral API format"

            input_tokens = response_body.get('input_tokens', 0)
            output_tokens = response_body.get('output_tokens', 0)

            cost_usd = (
                (input_tokens / 1000) * model_config.cost_per_1k_input +
                (output_tokens / 1000) * model_config.cost_per_1k_output
            )

            return ModelResponse(
                model_key="mistral",
                model_name=model_config.name,
                prompt_id=prompt_id,
                answer=answer_content,
                reasoning_trace=reasoning_trace,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=round(cost_usd, 6),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
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
            ("nova", self._call_nova_premier),
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
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to {output_file}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Ensemble Thinking Models Harness")
    parser.add_argument("--mock", action="store_true", default=True,
                       help="Run in mock mode (no AWS credentials needed)")
    parser.add_argument("--live", action="store_true",
                       help="Run with live Bedrock API calls")
    parser.add_argument("--prompts", default="prompts/prompts.json",
                       help="Path to prompts JSON file")
    parser.add_argument("--output", default="results/responses.json",
                       help="Output file for results")

    args = parser.parse_args()

    # Default to mock unless --live is specified
    mock_mode = not args.live

    print("="*80)
    print("Ensemble Thinking Models Harness")
    print("="*80)
    print(f"Mode: {'MOCK' if mock_mode else 'LIVE (AWS Bedrock)'}")
    print(f"Prompts: {args.prompts}")
    print(f"Output: {args.output}")
    print("="*80)

    harness = BedrockHarness(mock_mode=mock_mode)
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
    print(f"Average per prompt: ${total_cost/len(results):.6f}, {total_time/len(results):.1f}s")


if __name__ == "__main__":
    main()
