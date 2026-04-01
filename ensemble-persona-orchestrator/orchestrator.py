"""
Orchestrator - Synthesize final output from multiple persona responses

Three strategies:
1. Pick-Best: Judge selects the strongest individual response
2. Synthesize: Combine strongest elements from all responses
3. Debate: Feed disagreements back for one round, then resolve
"""
import asyncio
import sys
import os
import time
from typing import Dict, List
from dataclasses import dataclass, asdict

# Add parent directory to path to import shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class OrchestrationResult:
    """Result of orchestration process"""
    strategy: str
    final_output: str
    rationale: str
    latency_ms: float
    metadata: Dict


class Orchestrator:
    """Orchestrates multiple persona responses into final output"""

    def __init__(self, model_id: str = "us.anthropic.claude-sonnet-4-6"):
        """
        Initialize orchestrator

        Args:
            model_id: Bedrock model ID for orchestration
        """
        self.model_id = model_id
        try:
            self.bedrock_client = BedrockClient()
            print("✓ Orchestrator initialized with Bedrock client")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Set AWS_BEARER_TOKEN_BEDROCK environment variable")
            raise

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 3000
    ) -> str:
        """Call LLM for orchestration (lower temperature for more consistent judging)"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._call_llm_sync,
            prompt,
            system_prompt,
            max_tokens,
            temperature
        )
        return result

    def _call_llm_sync(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Synchronous LLM call (run in thread pool)"""
        response_text, input_tokens, output_tokens, latency_ms = self.bedrock_client.call_model(
            model_id=self.model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response_text

    def _format_responses_for_orchestration(
        self,
        prompt: str,
        responses: List[Dict]
    ) -> str:
        """Format persona responses for orchestration prompt"""
        formatted = f"**Original Prompt:**\n{prompt}\n\n"
        formatted += "**Persona Responses:**\n\n"

        for i, response in enumerate(responses, 1):
            formatted += f"### Response {i}: {response['persona_name']}\n"
            formatted += f"**Framework:** {response['reasoning_framework']}\n\n"
            formatted += f"{response['response_text']}\n\n"
            formatted += "-" * 60 + "\n\n"

        return formatted

    async def strategy_pick_best(
        self,
        prompt: str,
        responses: List[Dict]
    ) -> OrchestrationResult:
        """
        Strategy 1: Pick the strongest individual response

        A judge LLM evaluates all responses and selects the single best one,
        with detailed rationale for the choice.
        """
        start_time = time.time()

        system_prompt = """You are an expert judge evaluating multiple analytical responses.

Your task: Select the SINGLE STRONGEST response and explain why.

Evaluation criteria:
- Depth of reasoning and insight
- Practical applicability
- Consideration of trade-offs and edge cases
- Clarity and structure
- Originality of perspective

Be specific in your rationale: quote particular strengths from the chosen response and explain why it outperforms the others. This isn't about consensus—it's about identifying excellence."""

        formatted_responses = self._format_responses_for_orchestration(prompt, responses)

        orchestration_prompt = f"""{formatted_responses}

**Your Task:**
1. Evaluate each response against the criteria
2. Select the strongest single response
3. Provide detailed rationale for your selection
4. Include the complete selected response in your output

Format:
**Selected Response:** [Persona Name]

**Rationale:**
[Detailed explanation of why this response is strongest]

**Final Answer:**
[Complete text of the selected response]
"""

        output = await self._call_llm(orchestration_prompt, system_prompt)
        latency_ms = (time.time() - start_time) * 1000

        return OrchestrationResult(
            strategy="pick_best",
            final_output=output,
            rationale="Judge selected strongest individual response based on depth, applicability, and insight",
            latency_ms=latency_ms,
            metadata={
                "response_count": len(responses),
                "personas_evaluated": [r['persona_name'] for r in responses]
            }
        )

    async def strategy_synthesize(
        self,
        prompt: str,
        responses: List[Dict]
    ) -> OrchestrationResult:
        """
        Strategy 2: Synthesize best elements from all responses

        Extract the strongest insights from each response and combine them
        into a coherent, integrated answer that's better than any individual.
        """
        start_time = time.time()

        system_prompt = """You are a master synthesist combining insights from multiple analytical perspectives.

Your task: Create a SYNTHESIZED response that integrates the strongest elements from all inputs.

Your synthesis should:
- Identify unique insights from each perspective
- Resolve contradictions by finding higher-level framework
- Combine complementary strengths
- Produce a coherent answer better than any single input
- Explicitly attribute which insights came from which framework

This is NOT picking a winner. This is NOT averaging. This is integration—the whole should be greater than the parts."""

        formatted_responses = self._format_responses_for_orchestration(prompt, responses)

        orchestration_prompt = f"""{formatted_responses}

**Your Task:**
1. Identify the strongest insight from each persona
2. Find where perspectives complement vs. conflict
3. Synthesize into a unified, integrated response
4. Show your work—attribute which insights came from which personas

Format:
**Synthesized Response:**
[Your integrated answer, with clear attribution like "(from First Principles Thinker)" or "(Systems Thinker's insight)"]

**Synthesis Notes:**
[How you resolved conflicts, what you integrated from each source]
"""

        output = await self._call_llm(orchestration_prompt, system_prompt)
        latency_ms = (time.time() - start_time) * 1000

        return OrchestrationResult(
            strategy="synthesize",
            final_output=output,
            rationale="Combined strongest elements from all personas into integrated response",
            latency_ms=latency_ms,
            metadata={
                "response_count": len(responses),
                "personas_synthesized": [r['persona_name'] for r in responses]
            }
        )

    async def strategy_debate(
        self,
        prompt: str,
        responses: List[Dict],
        runner=None  # Optional: for actual debate round
    ) -> OrchestrationResult:
        """
        Strategy 3: Debate and resolve

        Identify disagreements, simulate one round of debate where personas
        respond to each other's critiques, then synthesize final resolution.

        Note: This is a simplified version that has the orchestrator model
        the debate. A full implementation would use the runner to actually
        re-invoke personas with each other's critiques.
        """
        start_time = time.time()

        system_prompt = """You are facilitating a debate between analytical perspectives.

Your task: Identify key disagreements, model how personas would respond to each other's critiques, then resolve to a final recommendation.

Process:
1. Identify 2-3 core disagreements between perspectives
2. Articulate the tension: what's the fundamental question they disagree on?
3. Model a debate round: how would each persona respond to the others' critiques?
4. Find resolution: where do they converge? What conditional recommendations emerge?
5. Produce final synthesized answer that reflects the debate outcome

Your resolution should be more robust than initial responses—tempered by critique, strengthened by challenge."""

        formatted_responses = self._format_responses_for_orchestration(prompt, responses)

        orchestration_prompt = f"""{formatted_responses}

**Your Task:**
1. Identify key disagreements (2-3 main tensions)
2. Model debate round: how would personas respond to each other?
3. Find areas of convergence and remaining disagreement
4. Synthesize final resolution informed by the debate

Format:
**Key Disagreements:**
[List main tensions]

**Debate Round:**
[Model how personas would engage with each other's critiques]

**Resolution:**
[Final synthesized answer, more robust from being stress-tested]

**Debate Outcome:**
[What the process revealed that individual responses missed]
"""

        output = await self._call_llm(orchestration_prompt, system_prompt, temperature=0.4)
        latency_ms = (time.time() - start_time) * 1000

        return OrchestrationResult(
            strategy="debate",
            final_output=output,
            rationale="Identified disagreements, modeled debate round, resolved to synthesis",
            latency_ms=latency_ms,
            metadata={
                "response_count": len(responses),
                "personas_debated": [r['persona_name'] for r in responses],
                "debate_rounds": 1  # Simplified version
            }
        )

    async def orchestrate_all_strategies(
        self,
        prompt: str,
        responses: List[Dict]
    ) -> Dict:
        """
        Run all three orchestration strategies in parallel and compare

        Returns:
            Dictionary with results from all strategies
        """
        print(f"\n{'='*60}")
        print(f"Running all orchestration strategies...")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Run all strategies in parallel
        results = await asyncio.gather(
            self.strategy_pick_best(prompt, responses),
            self.strategy_synthesize(prompt, responses),
            self.strategy_debate(prompt, responses)
        )

        total_time = time.time() - start_time

        output = {
            "prompt": prompt,
            "persona_count": len(responses),
            "strategies": {
                "pick_best": asdict(results[0]),
                "synthesize": asdict(results[1]),
                "debate": asdict(results[2])
            },
            "metadata": {
                "total_orchestration_time_ms": total_time * 1000,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        print(f"\n{'='*60}")
        print(f"✓ All strategies completed in {total_time:.2f}s")
        print(f"{'='*60}\n")

        return output

    def orchestrate_all_strategies_sync(
        self,
        prompt: str,
        responses: List[Dict]
    ) -> Dict:
        """Synchronous wrapper for orchestrate_all_strategies"""
        return asyncio.run(self.orchestrate_all_strategies(prompt, responses))


if __name__ == "__main__":
    print("Orchestrator module - use via runner.py or experiment.py")
