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
        """Parse judge model output into structured score.

        Raises:
            ValueError: If required scores cannot be parsed or are out of valid range
        """

        # Try multiple patterns for robustness (case-insensitive, flexible spacing)
        # Note: Allow optional negative sign to parse negative scores (will validate range after)
        correctness_patterns = [
            r'CORRECTNESS:\s*(-?\d+(?:\.\d+)?)\s*/\s*40',  # Standard format
            r'correctness:\s*(-?\d+(?:\.\d+)?)\s*/\s*40',  # Lowercase
            r'CORRECTNESS\s*[:=-]\s*(-?\d+(?:\.\d+)?)',    # Flexible separator
        ]
        completeness_patterns = [
            r'COMPLETENESS:\s*(-?\d+(?:\.\d+)?)\s*/\s*30',
            r'completeness:\s*(-?\d+(?:\.\d+)?)\s*/\s*30',
            r'COMPLETENESS\s*[:=-]\s*(-?\d+(?:\.\d+)?)',
        ]
        clarity_patterns = [
            r'CLARITY:\s*(-?\d+(?:\.\d+)?)\s*/\s*30',
            r'clarity:\s*(-?\d+(?:\.\d+)?)\s*/\s*30',
            r'CLARITY\s*[:=-]\s*(-?\d+(?:\.\d+)?)',
        ]
        total_patterns = [
            r'TOTAL:\s*(-?\d+(?:\.\d+)?)\s*/\s*100',
            r'total:\s*(-?\d+(?:\.\d+)?)\s*/\s*100',
            r'TOTAL\s*[:=-]\s*(-?\d+(?:\.\d+)?)',
        ]

        # Extract scores with fallback patterns
        correctness_match = None
        for pattern in correctness_patterns:
            correctness_match = re.search(pattern, response, re.IGNORECASE)
            if correctness_match:
                break

        completeness_match = None
        for pattern in completeness_patterns:
            completeness_match = re.search(pattern, response, re.IGNORECASE)
            if completeness_match:
                break

        clarity_match = None
        for pattern in clarity_patterns:
            clarity_match = re.search(pattern, response, re.IGNORECASE)
            if clarity_match:
                break

        # Validate all required fields are present
        if not correctness_match:
            raise ValueError(
                f"Failed to parse CORRECTNESS from judge response. "
                f"Response preview:\n{response[:300]}"
            )
        if not completeness_match:
            raise ValueError(
                f"Failed to parse COMPLETENESS from judge response. "
                f"Response preview:\n{response[:300]}"
            )
        if not clarity_match:
            raise ValueError(
                f"Failed to parse CLARITY from judge response. "
                f"Response preview:\n{response[:300]}"
            )

        # Parse numeric values
        correctness = float(correctness_match.group(1))
        completeness = float(completeness_match.group(1))
        clarity = float(clarity_match.group(1))

        # Validate score ranges
        if not (0 <= correctness <= 40):
            raise ValueError(
                f"CORRECTNESS score {correctness} out of valid range [0, 40]. "
                f"Response preview:\n{response[:300]}"
            )
        if not (0 <= completeness <= 30):
            raise ValueError(
                f"COMPLETENESS score {completeness} out of valid range [0, 30]. "
                f"Response preview:\n{response[:300]}"
            )
        if not (0 <= clarity <= 30):
            raise ValueError(
                f"CLARITY score {clarity} out of valid range [0, 30]. "
                f"Response preview:\n{response[:300]}"
            )

        # Parse total (optional, can be calculated)
        total_match = None
        for pattern in total_patterns:
            total_match = re.search(pattern, response, re.IGNORECASE)
            if total_match:
                break

        if total_match:
            total = float(total_match.group(1))
            # Validate total is reasonable (within ±2 of sum for rounding)
            expected_total = correctness + completeness + clarity
            if abs(total - expected_total) > 2:
                raise ValueError(
                    f"TOTAL score {total} doesn't match sum of components "
                    f"({expected_total:.1f}). Difference: {abs(total - expected_total):.1f}. "
                    f"Response preview:\n{response[:300]}"
                )
        else:
            # Calculate from components if not provided
            total = correctness + completeness + clarity

        # Extract summary (optional, provide default if missing)
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?:\n|$)', response, re.DOTALL)
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
