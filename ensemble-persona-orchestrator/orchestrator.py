"""
Orchestrator - Synthesize final output from multiple persona responses

Three strategies:
1. Pick-Best: Judge selects the strongest individual response
2. Synthesize: Combine strongest elements from all responses
3. Debate: Feed disagreements back for one round, then resolve
"""
import asyncio
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

try:
    import boto3
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


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

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        mock_mode: bool = False
    ):
        """
        Initialize orchestrator

        Args:
            model_id: Bedrock model ID for orchestration
            mock_mode: If True, generate mock orchestrated responses
        """
        self.model_id = model_id
        self.mock_mode = mock_mode or not BEDROCK_AVAILABLE

        if not self.mock_mode:
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        else:
            print("Orchestrator running in MOCK MODE")

    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 3000
    ) -> str:
        """Call LLM for orchestration (lower temperature for more consistent judging)"""
        if self.mock_mode:
            # Simulate processing time
            await asyncio.sleep(0.3)
            return self._generate_mock_orchestration(prompt, system_prompt)

        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": messages
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def _generate_mock_orchestration(self, prompt: str, system_prompt: str) -> str:
        """Generate mock orchestrated response based on strategy"""
        if "Pick the strongest" in system_prompt or "judge" in system_prompt.lower():
            return """
**Selected Response: Domain Expert**

**Rationale:**
The Domain Expert's response provides the most pragmatic and actionable guidance. While other personas raised valuable concerns (Skeptical Analyst's risk assessment, Devil's Advocate's questioning of the premise), the Domain Expert balanced theoretical considerations with practical implementation reality.

Key strengths of the selected response:
1. Referenced specific best practices and precedents
2. Acknowledged common failure modes to avoid
3. Provided concrete next steps rather than just analysis
4. Balanced innovation with proven patterns

The First Principles Thinker's axiom-based approach was intellectually rigorous but perhaps over-engineered for a 3-month timeline. The Creative Problem Solver offered novel approaches but lacked consideration of implementation constraints.

**Final Answer:** [Domain Expert's complete response would be included here]
"""
        elif "Synthesize" in system_prompt or "combine" in system_prompt.lower():
            return """
**Synthesized Response:**

Drawing the strongest elements from all personas:

**Foundation (from First Principles Thinker):**
The core question is: what authentication capabilities must we have, vs. what's conventional overhead? Essential: user identity, session management, password security. Not essential initially: SSO, multi-factor auth (can add later).

**Risk Assessment (from Skeptical Analyst & Devil's Advocate):**
Building auth in-house carries significant risks:
- Security vulnerabilities from inexperienced implementation
- Ongoing maintenance burden (password resets, token refresh, edge cases)
- Regulatory compliance (GDPR, data breach notification)
- Opportunity cost—3 engineers for 3 months, but how much goes to auth vs. core product?

**Pragmatic Solution (from Domain Expert):**
Industry consensus for small teams: use Auth0 or similar. Historical data shows in-house auth is a common startup mistake. The "not invented here" syndrome is costly.

**Creative Middle Ground (from Creative Problem Solver):**
Consider: start with Auth0, but design your system with an auth abstraction layer. If you outgrow it (scale or cost), you can swap implementations later. This inverts the risk—you get speed now, keep flexibility later.

**Validation Approach (from Empiricist):**
Metrics to decide: (1) time-to-market impact, (2) security incident rate, (3) developer hours spent on auth vs. features. Run a spike: spend 1 week prototyping both approaches, measure complexity.

**Systems View (from Systems Thinker):**
Second-order effects: if you build auth, every new feature has auth implications (permissions, roles, API security). This compounds over time. But if Auth0 pricing scales with MAU, there's a future cost curve to model.

**Recommendation:**
Use Auth0 (or similar) with an abstraction layer. Your constraint is time and team size, and auth is a solved problem. Invest your scarce engineering resources in your unique value proposition, not in reimplementing OAuth flows. Revisit if you reach 100K+ MAU or have specific compliance needs that commodity auth can't meet.
"""
        else:  # Debate strategy
            return """
**Debate Resolution:**

**Round 1 - Key Disagreements Identified:**

1. **Build vs. Buy Trade-off:**
   - First Principles: "From axioms, auth is just cryptographic identity verification—not complex"
   - Domain Expert: "Historical precedent shows small teams underestimate auth complexity"
   - **Tension:** Theoretical simplicity vs. implementation reality

2. **Risk Assessment:**
   - Skeptical Analyst: "Security vulnerabilities are the primary risk"
   - Devil's Advocate: "Vendor lock-in and pricing risk are overlooked"
   - **Tension:** Implementation risk vs. dependency risk

3. **Timeline Feasibility:**
   - Creative Solver: "Could we do hybrid—use Auth0 for MVP, plan migration path?"
   - Empiricist: "No data provided on actual implementation time for either approach"

**Round 2 - Consensus Building:**

After debate round, personas converged on:
- **Agreement:** Time constraint (3 months, 3 engineers) is the binding factor
- **Agreement:** Auth is necessary but not differentiating for most startups
- **Agreement:** Need to validate assumptions with time-boxed exploration

**Remaining Disagreement:**
- Whether abstraction layer adds valuable flexibility or premature architecture

**Final Resolution:**

**Recommended approach:** Use third-party auth (Auth0/Clerk/Supabase Auth) for MVP

**Rationale from debate:**
The First Principles Thinker's challenge to build from fundamentals is intellectually valid but conflicts with the Empiricist's observation that we lack data on actual implementation complexity. The Domain Expert's pattern-matching shows this is a known solved problem. The Devil's Advocate's vendor risk concern is real but manageable (abstraction layer addresses this without over-engineering).

The Systems Thinker's insight closes the debate: auth creates ongoing feedback loops (every feature touches auth). Starting with a well-tested service reduces that system complexity during the critical early phase.

**Debate outcome:** 5 personas leaning toward third-party, 2 suggesting build-with-abstraction. The conditional recommendations (validate with spike, design for optionality) represent the synthesis of the disagreement.
"""

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


def main():
    """Demo usage"""
    # Simulate persona responses for testing
    mock_responses = [
        {
            "persona_name": "First Principles Thinker",
            "reasoning_framework": "axiomatic_deduction",
            "response_text": "From first principles, authentication is fundamentally about cryptographic proof of identity. The core axiom is: a system must verify that a request comes from who it claims to come from. Building from this foundation, we need: (1) secure storage of credentials, (2) cryptographic hashing, (3) session token generation. These are well-understood problems with standard solutions. The question isn't 'can we build it' but 'should we allocate scarce resources to it'?"
        },
        {
            "persona_name": "Domain Expert",
            "reasoning_framework": "pattern_recognition",
            "response_text": "Industry best practice for teams under 10 people: use established auth providers. Historical precedent: YC companies that built auth in-house spent 2-3x estimated time. Common failure mode: underestimating edge cases (password reset, email verification, session management across devices, token refresh). State of the art: Auth0, Clerk, Supabase Auth. Anti-pattern: 'we're different, we need custom auth.' Unless you have extremely specific compliance requirements, you're not different."
        },
        {
            "persona_name": "Devil's Advocate",
            "reasoning_framework": "adversarial_interrogation",
            "response_text": "Arguing against third-party auth: (1) Vendor lock-in and pricing risk—Auth0 scales with MAU, could become expensive. (2) You're trusting critical infrastructure to external service—outage = your users can't log in. (3) Customization constraints—when you need specific auth flows, you'll fight the provider's abstractions. (4) Learning opportunity cost—your team never learns auth deeply, technical debt accumulates in the abstraction layer. Counter-argument to 'it's a solved problem': if it's so solved, why are there a dozen competing providers?"
        }
    ]

    orchestrator = Orchestrator(mock_mode=True)

    prompt = "Should we build our own auth or use a third-party service?"

    result = orchestrator.orchestrate_all_strategies_sync(prompt, mock_responses)

    # Print results
    print("\n" + "="*60)
    print("ORCHESTRATION RESULTS:")
    print("="*60 + "\n")

    for strategy_name, strategy_result in result["strategies"].items():
        print(f"### Strategy: {strategy_name.replace('_', ' ').title()}")
        print(f"Latency: {strategy_result['latency_ms']:.0f}ms")
        print("-" * 60)
        print(strategy_result['final_output'][:600] + "...")
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
