"""
Persona Runner - Execute same prompt with multiple personas in parallel
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import hashlib
import random

try:
    import boto3
    from botocore.exceptions import ClientError
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False
    print("Warning: boto3 not available. Running in mock mode.")


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


class PersonaRunner:
    """Runs same prompt through multiple personas in parallel"""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        personas_dir: str = "personas",
        mock_mode: bool = False,
        mock_delay: float = 0.5
    ):
        """
        Initialize the runner

        Args:
            model_id: Bedrock model ID to use
            personas_dir: Directory containing persona JSON files
            mock_mode: If True, generate mock responses instead of calling Bedrock
            mock_delay: Simulated latency for mock responses (seconds)
        """
        self.model_id = model_id
        self.personas_dir = Path(personas_dir)
        self.mock_mode = mock_mode or not BEDROCK_AVAILABLE
        self.mock_delay = mock_delay

        if not self.mock_mode:
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        else:
            print("Running in MOCK MODE - responses will be simulated")

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
    ) -> tuple[str, int, str]:
        """
        Make async call to Bedrock API

        Returns:
            tuple of (response_text, token_count, finish_reason)
        """
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": messages
        }

        # Bedrock API is synchronous, so run in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
        )

        response_body = json.loads(response['body'].read())

        text = response_body['content'][0]['text']
        token_count = response_body['usage']['output_tokens']
        finish_reason = response_body.get('stop_reason', 'end_turn')

        return text, token_count, finish_reason

    async def _generate_mock_response(
        self,
        prompt: str,
        persona: PersonaConfig
    ) -> tuple[str, int, str]:
        """Generate a realistic mock response based on persona framework"""

        # Simulate API latency with some variance
        await asyncio.sleep(self.mock_delay + random.uniform(-0.1, 0.3))

        # Create framework-specific mock responses
        framework_templates = {
            "axiomatic_deduction": (
                "**First Principles Analysis:**\n\n"
                "Let me break this down to fundamental truths:\n\n"
                "1. **Core Axiom**: {assumption1}\n"
                "2. **Immutable Constraint**: {assumption2}\n"
                "3. **Derived Principle**: From these foundations, we can deduce that {conclusion}\n\n"
                "Questioning convention: The typical approach assumes {convention}, "
                "but from first principles, we should actually {alternative}."
            ),
            "critical_empiricism": (
                "**Skeptical Assessment:**\n\n"
                "**Claims to Verify:**\n"
                "- {claim1} - Needs evidence\n"
                "- {claim2} - Assumption requiring validation\n\n"
                "**Potential Flaws:**\n"
                "- Selection bias in {area}\n"
                "- Unexamined premise: {premise}\n"
                "- Correlation vs causation concern\n\n"
                "**What would disprove this?** {falsification}"
            ),
            "adversarial_interrogation": (
                "**Devil's Advocate Position:**\n\n"
                "**Arguing AGAINST the dominant view:**\n\n"
                "The consensus overlooks {overlooked_issue}. Consider:\n\n"
                "1. **Hidden cost**: {cost}\n"
                "2. **Edge case failure**: {failure}\n"
                "3. **Alternative explanation**: {alt_explanation}\n\n"
                "**Stakeholders harmed**: {stakeholders}\n"
                "**Unintended consequence**: {consequence}"
            ),
            "analogical_synthesis": (
                "**Creative Reframing:**\n\n"
                "What if we approached this like {analogy}?\n\n"
                "**Novel perspective**: {reframe}\n\n"
                "**Unconventional approaches:**\n"
                "1. {approach1}\n"
                "2. {approach2}\n"
                "3. Hybrid solution: {hybrid}\n\n"
                "**Relaxing constraints**: What if we challenged {constraint}?"
            ),
            "pattern_recognition": (
                "**Domain Expert View:**\n\n"
                "This is a known pattern in the field. Relevant precedents:\n\n"
                "- **Similar case**: {case_study}\n"
                "- **Best practice**: {best_practice}\n"
                "- **Anti-pattern to avoid**: {anti_pattern}\n\n"
                "**State of the art**: {sota}\n"
                "**Common failure mode**: {failure_mode}\n\n"
                "Implementation considerations: {implementation}"
            ),
            "experimental_validation": (
                "**Empirical Framework:**\n\n"
                "**Testable hypothesis**: {hypothesis}\n\n"
                "**How to measure success:**\n"
                "- Metric 1: {metric1}\n"
                "- Metric 2: {metric2}\n\n"
                "**Experiment design**: {experiment}\n\n"
                "**Data needed**: {data}\n"
                "**Statistical considerations**: Sample size n={n}, power={power}\n\n"
                "**What current evidence shows**: {evidence}"
            ),
            "systems_dynamics": (
                "**Systems Analysis:**\n\n"
                "**System map:**\n"
                "- Components: {components}\n"
                "- Feedback loop: {feedback}\n"
                "- Leverage point: {leverage}\n\n"
                "**Second-order effects**: {second_order}\n"
                "**Delays**: {delays}\n"
                "**Unintended consequences**: {unintended}\n\n"
                "**Root cause vs symptom**: Treating {symptom} vs addressing {root}\n"
                "**Emergent behavior**: {emergent}"
            )
        }

        # Generate a framework-appropriate response
        template = framework_templates.get(
            persona.reasoning_framework,
            "Analysis from {framework} perspective: {generic_response}"
        )

        # Create a hash-based but consistent response for the same prompt+persona
        seed = hashlib.md5(f"{prompt[:50]}{persona.id}".encode()).hexdigest()
        random.seed(seed)

        # Fill in template with plausible placeholders
        response = template.format(
            assumption1="the underlying constraints are X and Y",
            assumption2="we must optimize for Z",
            conclusion="approach A is more fundamental than approach B",
            convention="we should follow standard practice X",
            alternative="optimize for the fundamental constraint Y directly",
            claim1="Performance improves by 50%",
            claim2="Users prefer option A",
            area="the test sample",
            premise="that current metrics capture true value",
            falsification="If we saw metric X decrease while Y increases, this would be refuted",
            overlooked_issue="significant downstream risks",
            cost="Implementation requires resources that could be better allocated",
            failure="When constraint X is violated, system fails catastrophically",
            alt_explanation="The correlation could be explained by confounding factor Z",
            stakeholders="Team B loses autonomy, users in region C face degraded service",
            consequence="Success in metric A may drive perverse incentives in area B",
            analogy="how biological immune systems handle threats",
            reframe="Instead of 'how to scale X', ask 'do we need X at this scale?'",
            approach1="Invert the problem: optimize for minimizing Y instead of maximizing X",
            approach2="Borrow from domain Z: use technique T",
            hybrid="Combine approach A's strength (speed) with approach B's strength (accuracy)",
            constraint="the assumption that we must maintain backward compatibility",
            case_study="Company X faced similar issue in 2023, resolved via strategy Y",
            best_practice="Industry standard is to implement Z pattern with safeguards A and B",
            anti_pattern="Avoid the common mistake of premature optimization in area X",
            sota="Current state-of-the-art uses technique T, achieving benchmark B",
            failure_mode="Watch for symptom S, which indicates underlying issue I",
            implementation="Consider edge cases E1, E2; use library L for handling X",
            hypothesis="If we implement X, then metric Y will improve by Z%",
            metric1="User engagement (DAU/MAU ratio)",
            metric2="Task completion rate",
            experiment="A/B test with n=1000 per cohort, 2-week duration, stratified by user segment",
            data="Need: baseline metrics (✓ available), treatment response (collect via instrumentation), confounders (need user survey)",
            n="500",
            power="0.8",
            evidence="Preliminary data shows correlation r=0.6, but causation unestablished",
            components="Users, API, Database, Cache, External Service",
            feedback="Positive reinforcing loop: more users → more data → better recommendations → more users",
            leverage="Intervene at the cache layer—small change, large impact on system load",
            second_order="Improving speed may increase usage, which increases load, which decreases speed",
            delays="Effect of optimization won't be visible for 2-3 weeks due to cache warming",
            unintended="Optimizing for metric X may cause gaming behavior, degrading actual value",
            symptom="slow response times",
            root="inefficient query patterns in the data access layer",
            emergent="System exhibits scale-dependent behavior not predictable from individual components",
            framework=persona.reasoning_framework,
            generic_response=f"[Mock response for {persona.name} analyzing: {prompt[:100]}...]"
        )

        # Reset random seed
        random.seed()

        token_count = len(response.split())
        finish_reason = "end_turn"

        return response, token_count, finish_reason

    async def _run_single_persona(
        self,
        prompt: str,
        persona: PersonaConfig
    ) -> PersonaResponse:
        """Run prompt through a single persona"""
        start_time = time.time()

        try:
            if self.mock_mode:
                text, token_count, finish_reason = await self._generate_mock_response(prompt, persona)
            else:
                text, token_count, finish_reason = await self._call_bedrock(
                    prompt=prompt,
                    system_prompt=persona.system_prompt,
                    temperature=persona.temperature
                )

            latency_ms = (time.time() - start_time) * 1000

            return PersonaResponse(
                persona_id=persona.id,
                persona_name=persona.name,
                reasoning_framework=persona.reasoning_framework,
                response_text=text,
                latency_ms=latency_ms,
                model_id=self.model_id,
                temperature=persona.temperature,
                token_count=token_count,
                finish_reason=finish_reason
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return PersonaResponse(
                persona_id=persona.id,
                persona_name=persona.name,
                reasoning_framework=persona.reasoning_framework,
                response_text=f"ERROR: {str(e)}",
                latency_ms=latency_ms,
                model_id=self.model_id,
                temperature=persona.temperature,
                token_count=0,
                finish_reason="error"
            )

    async def run_ensemble(
        self,
        prompt: str,
        selected_personas: Optional[List[str]] = None
    ) -> Dict:
        """
        Run prompt through all personas in parallel

        Args:
            prompt: The prompt to send to all personas
            selected_personas: Optional list of persona IDs to use (default: all)

        Returns:
            Dictionary with responses and metadata
        """
        # Filter personas if specific ones requested
        personas_to_run = self.personas
        if selected_personas:
            personas_to_run = [p for p in self.personas if p.id in selected_personas]

        if not personas_to_run:
            raise ValueError(f"No matching personas found for: {selected_personas}")

        print(f"\n{'='*60}")
        print(f"Running prompt through {len(personas_to_run)} personas in parallel...")
        print(f"Model: {self.model_id}")
        print(f"Mode: {'MOCK' if self.mock_mode else 'LIVE'}")
        print(f"{'='*60}\n")

        # Run all personas in parallel
        start_time = time.time()
        tasks = [self._run_single_persona(prompt, persona) for persona in personas_to_run]
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Calculate metrics
        total_tokens = sum(r.token_count or 0 for r in responses)
        avg_latency = sum(r.latency_ms for r in responses) / len(responses)

        result = {
            "prompt": prompt,
            "model_id": self.model_id,
            "mock_mode": self.mock_mode,
            "responses": [asdict(r) for r in responses],
            "metadata": {
                "persona_count": len(responses),
                "total_execution_time_ms": total_time * 1000,
                "avg_persona_latency_ms": avg_latency,
                "total_tokens": total_tokens,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        print(f"\n{'='*60}")
        print(f"✓ Completed in {total_time:.2f}s")
        print(f"  Average persona latency: {avg_latency:.0f}ms")
        print(f"  Total tokens: {total_tokens}")
        print(f"{'='*60}\n")

        return result

    def run_ensemble_sync(
        self,
        prompt: str,
        selected_personas: Optional[List[str]] = None
    ) -> Dict:
        """Synchronous wrapper for run_ensemble"""
        return asyncio.run(self.run_ensemble(prompt, selected_personas))


def main():
    """Demo usage"""
    runner = PersonaRunner(mock_mode=True)

    test_prompt = """
    Our startup is deciding between building our own authentication system
    or using a third-party service like Auth0. We have a small team (3 engineers)
    and need to launch in 3 months. What should we do?
    """

    result = runner.run_ensemble_sync(test_prompt)

    # Print each persona's response
    print("\n" + "="*60)
    print("PERSONA RESPONSES:")
    print("="*60 + "\n")

    for response in result["responses"]:
        print(f"### {response['persona_name']} ({response['reasoning_framework']})")
        print(f"Latency: {response['latency_ms']:.0f}ms | Tokens: {response['token_count']}")
        print("-" * 60)
        print(response['response_text'][:500] + "..." if len(response['response_text']) > 500 else response['response_text'])
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
