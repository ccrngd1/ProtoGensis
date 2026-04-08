"""
Automated quality assessment using Opus as judge model.
"""

import asyncio
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

from .bedrock_client import BedrockClient
from .models import get_model_pricing


@dataclass
class JudgeScore:
    """Quality score from judge model."""

    correctness: float  # 0-40 points
    completeness: float  # 0-30 points
    clarity: float  # 0-30 points
    total: float  # 0-100 points
    justification: str


class QualityJudge:
    """
    Automated quality judge using Opus.

    Scores responses on:
    - Correctness (40%): Is the answer accurate?
    - Completeness (30%): Does it address all parts?
    - Clarity (30%): Is it well-explained?
    """

    def __init__(self, judge_model: str = "opus"):
        """Initialize judge with specified model."""
        self.judge_model = judge_model
        self.client = BedrockClient()

    async def score_response(
        self,
        prompt: str,
        response: str,
        expected_answer: str = None
    ) -> JudgeScore:
        """
        Score a single response.

        Args:
            prompt: Original prompt
            response: Model response to score
            expected_answer: Optional expected answer for reference

        Returns:
            JudgeScore with breakdown
        """
        judge_prompt = self._build_judge_prompt(prompt, response, expected_answer)

        pricing = get_model_pricing(self.judge_model)
        result = await self.client.invoke_model(
            model_id=pricing.model_id,
            prompt=judge_prompt,
            max_tokens=500,
            temperature=0.3  # Lower temp for consistent judging
        )

        # Parse judge response
        score = self._parse_judge_response(result["response"])
        return score

    def _build_judge_prompt(
        self,
        prompt: str,
        response: str,
        expected_answer: str = None
    ) -> str:
        """Build prompt for judge model."""

        base_prompt = f"""You are an expert judge evaluating the quality of an AI response.

Original Prompt:
{prompt}

Response to Evaluate:
{response}
"""

        if expected_answer:
            base_prompt += f"""
Expected Answer (for reference):
{expected_answer}
"""

        base_prompt += """

Score this response on three dimensions:

1. CORRECTNESS (0-40 points)
   - Is the information accurate?
   - Are there factual errors or hallucinations?
   - Does it address the right question?

2. COMPLETENESS (0-30 points)
   - Does it cover all parts of the prompt?
   - Are there missing elements?
   - Is sufficient detail provided?

3. CLARITY (0-30 points)
   - Is it well-structured and easy to follow?
   - Is the explanation clear?
   - Is the language appropriate?

Provide your evaluation in this exact format:

CORRECTNESS: [score]/40
[brief justification]

COMPLETENESS: [score]/30
[brief justification]

CLARITY: [score]/30
[brief justification]

TOTAL: [sum]/100

SUMMARY: [1-2 sentence overall assessment]
"""
        return base_prompt

    def _parse_judge_response(self, response: str) -> JudgeScore:
        """Parse judge model output into structured score."""

        # Extract scores using regex
        correctness_match = re.search(r'CORRECTNESS:\s*(\d+(?:\.\d+)?)/40', response)
        completeness_match = re.search(r'COMPLETENESS:\s*(\d+(?:\.\d+)?)/30', response)
        clarity_match = re.search(r'CLARITY:\s*(\d+(?:\.\d+)?)/30', response)
        total_match = re.search(r'TOTAL:\s*(\d+(?:\.\d+)?)/100', response)
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?:\n|$)', response, re.DOTALL)

        correctness = float(correctness_match.group(1)) if correctness_match else 0.0
        completeness = float(completeness_match.group(1)) if completeness_match else 0.0
        clarity = float(clarity_match.group(1)) if clarity_match else 0.0
        total = float(total_match.group(1)) if total_match else correctness + completeness + clarity
        summary = summary_match.group(1).strip() if summary_match else "No summary provided"

        return JudgeScore(
            correctness=correctness,
            completeness=completeness,
            clarity=clarity,
            total=total,
            justification=summary
        )

    async def score_batch(
        self,
        evaluations: List[Dict]
    ) -> List[JudgeScore]:
        """
        Score multiple responses in parallel.

        Args:
            evaluations: List of dicts with 'prompt', 'response', 'expected_answer'

        Returns:
            List of JudgeScore objects
        """
        tasks = [
            self.score_response(
                prompt=eval_dict['prompt'],
                response=eval_dict['response'],
                expected_answer=eval_dict.get('expected_answer')
            )
            for eval_dict in evaluations
        ]

        return await asyncio.gather(*tasks)
