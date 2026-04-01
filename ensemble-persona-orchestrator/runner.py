"""
Persona Runner - Execute same prompt with multiple personas in parallel
Refactored to use shared Bedrock HTTP client
"""
import asyncio
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class PersonaConfig:
    """Configuration for a single persona"""
    name: str
    id: str
    description: str
    system_prompt: str
    temperature: float
    reasoning_framework: str


@dataclass
class PersonaResponse:
    """Response from a single persona"""
    persona_id: str
    persona_name: str
    reasoning_framework: str
    response_text: str
    latency_ms: float
    model_id: str
    temperature: float
    token_count: Optional[int] = None
    finish_reason: Optional[str] = None
    cost_usd: float = 0.0


class PersonaRunner:
    """Runs same prompt through multiple personas in parallel"""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-6",
        personas_dir: str = "personas"
    ):
        """
        Initialize the runner

        Args:
            model_id: Bedrock model ID to use (default: Sonnet 4.6)
            personas_dir: Directory containing persona JSON files
        """
        self.model_id = model_id
        self.personas_dir = Path(personas_dir)

        try:
            self.bedrock_client = BedrockClient()
            print("✓ Bedrock client initialized (Sonnet 4.6)")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Set AWS_BEARER_TOKEN_BEDROCK environment variable")
            raise

        self.personas = self._load_personas()
        print(f"Loaded {len(self.personas)} personas: {[p.name for p in self.personas]}")

    def _load_personas(self) -> List[PersonaConfig]:
        """Load all persona configurations from JSON files"""
        personas = []

        if not self.personas_dir.exists():
            raise FileNotFoundError(f"Personas directory not found: {self.personas_dir}")

        for persona_file in self.personas_dir.glob("*.json"):
            with open(persona_file, 'r') as f:
                data = json.load(f)
                persona = PersonaConfig(**data)
                personas.append(persona)

        if not personas:
            raise ValueError(f"No persona files found in {self.personas_dir}")

        return personas

    async def _call_bedrock(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> tuple:
        """
        Make async call to Bedrock API via shared client

        Returns:
            tuple of (response_text, token_count, finish_reason, latency_ms, cost_usd)
        """
        # Run the synchronous shared client call in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._call_bedrock_sync,
            prompt,
            system_prompt,
            temperature,
            max_tokens
        )
        return result

    def _call_bedrock_sync(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> tuple:
        """Synchronous Bedrock call (run in thread pool)"""
        response_text, input_tokens, output_tokens, latency_ms = self.bedrock_client.call_model(
            model_id=self.model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        cost_usd = calculate_cost(self.model_id, input_tokens, output_tokens)

        return response_text, output_tokens, "end_turn", latency_ms, cost_usd

    async def run_persona(
        self,
        prompt: str,
        persona: PersonaConfig
    ) -> PersonaResponse:
        """
        Run a single persona on the prompt

        Args:
            prompt: The question/prompt to analyze
            persona: Persona configuration

        Returns:
            PersonaResponse with the result
        """
        print(f"  Running {persona.name}...")

        try:
            response_text, token_count, finish_reason, latency_ms, cost_usd = await self._call_bedrock(
                prompt=prompt,
                system_prompt=persona.system_prompt,
                temperature=persona.temperature,
                max_tokens=2048
            )
        except Exception as e:
            print(f"    ⚠️  Error: {e}")
            response_text = f"[Error calling Bedrock: {e}]"
            token_count = 0
            finish_reason = "error"
            latency_ms = 0
            cost_usd = 0.0

        return PersonaResponse(
            persona_id=persona.id,
            persona_name=persona.name,
            reasoning_framework=persona.reasoning_framework,
            response_text=response_text,
            latency_ms=latency_ms,
            model_id=self.model_id,
            temperature=persona.temperature,
            token_count=token_count,
            finish_reason=finish_reason,
            cost_usd=cost_usd
        )

    async def run_ensemble(
        self,
        prompt: str,
        personas: Optional[List[PersonaConfig]] = None
    ) -> Dict:
        """
        Run prompt through all personas in parallel

        Args:
            prompt: The question to analyze
            personas: Optional list of specific personas (defaults to all loaded)

        Returns:
            Dict with responses and metadata
        """
        personas_to_run = personas or self.personas

        print(f"\nRunning {len(personas_to_run)} personas in parallel...")
        start_time = time.time()

        # Run all personas concurrently
        tasks = [
            self.run_persona(prompt, persona)
            for persona in personas_to_run
        ]

        responses = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Calculate totals
        total_cost = sum(r.cost_usd for r in responses)
        total_tokens = sum(r.token_count or 0 for r in responses)
        avg_latency = sum(r.latency_ms for r in responses) / len(responses) if responses else 0

        result = {
            "prompt": prompt,
            "responses": [asdict(r) for r in responses],
            "metadata": {
                "num_personas": len(responses),
                "total_time_seconds": total_time,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens,
                "avg_latency_ms": avg_latency
            }
        }

        print(f"✓ Completed in {total_time:.2f}s")
        print(f"  Total cost: ${total_cost:.6f}")
        print(f"  Avg latency: {avg_latency:.0f}ms")

        return result

    def run_ensemble_sync(self, prompt: str) -> Dict:
        """Synchronous wrapper for run_ensemble"""
        return asyncio.run(self.run_ensemble(prompt))


def main():
    """Demo CLI for persona runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run personas on a prompt")
    parser.add_argument("prompt", help="The prompt to analyze")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    runner = PersonaRunner()
    result = runner.run_ensemble_sync(args.prompt)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✓ Results saved to {output_path}")
    else:
        print("\n" + "="*80)
        print("PERSONA RESPONSES")
        print("="*80)
        for response in result['responses']:
            print(f"\n### {response['persona_name']}")
            print(f"Framework: {response['reasoning_framework']}")
            print(f"Latency: {response['latency_ms']:.0f}ms")
            print(f"Cost: ${response['cost_usd']:.6f}")
            print("-" * 80)
            print(response['response_text'][:300] + "...")


if __name__ == "__main__":
    main()
