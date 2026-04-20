"""Core pairwise comparison engine with position bias correction."""

from dataclasses import dataclass
from typing import Optional, List, Tuple
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .providers.base import BaseProvider
from .constraints.engine import Constraint
from .tasks.loader import Task


@dataclass
class ComparisonResult:
    """Result of a pairwise comparison."""

    task_name: str
    constraint_name: str
    unconstrained_response: str
    constrained_response: str
    winner_ab: str  # "A" or "B" when unconstrained is position A
    winner_ba: str  # "A" or "B" when unconstrained is position B
    degradation_detected: bool
    win_rate: float  # 0.0 to 1.0, higher means constraint hurt quality

    def get_severity(self) -> str:
        """Get severity level based on win rate.

        Returns:
            Severity string: "none", "low", "medium", or "high"
        """
        if self.win_rate < 0.05:
            return "none"
        elif self.win_rate < 0.15:
            return "low"
        elif self.win_rate < 0.30:
            return "medium"
        else:
            return "high"


class PairwiseEngine:
    """Engine for pairwise comparison with position bias correction.

    This implements the key methodological contribution from the paper:
    comparing constrained vs unconstrained outputs using pairwise judgment
    with position swapping to control for position bias.
    """

    def __init__(
        self,
        provider: BaseProvider,
        judge_provider: Optional[BaseProvider] = None,
    ):
        """Initialize pairwise engine.

        Args:
            provider: LLM provider for generating responses
            judge_provider: Optional separate provider for judging.
                          Uses provider if not specified.
        """
        self.provider = provider
        self.judge_provider = judge_provider or provider

    def run_comparison(
        self,
        task: Task,
        constraint: Constraint,
        use_logit_bias: bool = False,
    ) -> ComparisonResult:
        """Run pairwise comparison for a task-constraint pair.

        Args:
            task: Task to test
            constraint: Constraint to apply
            use_logit_bias: Use token-level constraint if supported

        Returns:
            ComparisonResult with win rates and degradation info
        """
        # Step 1: Generate unconstrained baseline
        unconstrained = self.provider.generate(
            prompt=task.get_prompt(),
            temperature=1.0,
            max_tokens=2000,
        )

        # Step 2: Generate constrained response
        if use_logit_bias and self.provider.supports_logit_bias():
            # Token-level constraint
            token_ids = self.provider.get_token_ids(constraint.tokens or [])
            logit_bias = constraint.get_logit_bias(token_ids)

            constrained = self.provider.generate(
                prompt=task.get_prompt(),
                temperature=1.0,
                max_tokens=2000,
                logit_bias=logit_bias,
            )
        else:
            # Instruction-level constraint
            _, system_prompt = self.provider.apply_constraint_instruction(
                base_prompt=task.get_prompt(),
                constraint_instruction=constraint.get_instruction(),
            )

            constrained = self.provider.generate(
                prompt=task.get_prompt(),
                system_prompt=system_prompt,
                temperature=1.0,
                max_tokens=2000,
            )

        # Step 3: Judge with position A/B (unconstrained first)
        winner_ab = self._judge_pair(
            task.get_prompt(),
            response_a=unconstrained,
            response_b=constrained,
        )

        # Step 4: Judge with position B/A (unconstrained second) - controls for position bias
        winner_ba = self._judge_pair(
            task.get_prompt(),
            response_a=constrained,
            response_b=unconstrained,
        )

        # Step 5: Aggregate results with position bias correction
        win_rate = self._calculate_win_rate(winner_ab, winner_ba)
        degradation_detected = win_rate > 0.05  # 5% threshold

        return ComparisonResult(
            task_name=task.name,
            constraint_name=constraint.name,
            unconstrained_response=unconstrained,
            constrained_response=constrained,
            winner_ab=winner_ab,
            winner_ba=winner_ba,
            degradation_detected=degradation_detected,
            win_rate=win_rate,
        )

    def _judge_pair(
        self,
        task_prompt: str,
        response_a: str,
        response_b: str,
    ) -> str:
        """Judge which response is more comprehensive.

        Args:
            task_prompt: Original task prompt
            response_a: First response
            response_b: Second response

        Returns:
            "A" or "B" indicating winner
        """
        # Check if provider has built-in judge method (like MockProvider)
        if hasattr(self.judge_provider, "judge_pairwise"):
            return self.judge_provider.judge_pairwise(
                task_prompt, response_a, response_b
            )

        # Otherwise, use LLM as judge
        judge_prompt = self._create_judge_prompt(task_prompt, response_a, response_b)

        judgment = self.judge_provider.generate(
            prompt=judge_prompt,
            system_prompt="You are an impartial judge evaluating response quality. Output only 'A' or 'B'.",
            temperature=0.0,  # Deterministic judging
            max_tokens=10,
        )

        # Parse judgment
        judgment = judgment.strip().upper()
        if "A" in judgment and "B" not in judgment:
            return "A"
        elif "B" in judgment and "A" not in judgment:
            return "B"
        else:
            # Fallback: prefer A on ambiguous
            return "A"

    def _create_judge_prompt(
        self,
        task_prompt: str,
        response_a: str,
        response_b: str,
    ) -> str:
        """Create prompt for LLM judge.

        Args:
            task_prompt: Original task
            response_a: First response
            response_b: Second response

        Returns:
            Judge prompt
        """
        return f"""You are evaluating two responses to the same task. Judge which response is MORE COMPREHENSIVE, THOROUGH, and COMPLETE.

TASK:
{task_prompt}

RESPONSE A:
{response_a}

RESPONSE B:
{response_b}

Which response is more comprehensive and thorough? Consider:
- Depth of analysis
- Completeness of coverage
- Detail and examples
- Overall informativeness

Output only the letter 'A' or 'B' for your choice."""

    def _calculate_win_rate(self, winner_ab: str, winner_ba: str) -> float:
        """Calculate win rate with position bias correction.

        When unconstrained is in position A and wins, winner_ab = "A"
        When unconstrained is in position B and wins, winner_ba = "B"

        Args:
            winner_ab: Winner when unconstrained is position A
            winner_ba: Winner when unconstrained is position B

        Returns:
            Win rate for unconstrained (0.0 to 1.0)
        """
        unconstrained_wins = 0

        # Position A/B: unconstrained is A
        if winner_ab == "A":
            unconstrained_wins += 1

        # Position B/A: unconstrained is B
        if winner_ba == "B":
            unconstrained_wins += 1

        # Win rate: 0.0 (constrained always wins) to 1.0 (unconstrained always wins)
        return unconstrained_wins / 2.0

    def scan_full_matrix(
        self,
        tasks: List[Task],
        constraints: List[Constraint],
        use_logit_bias: bool = False,
        progress: bool = True,
    ) -> List[ComparisonResult]:
        """Scan full task x constraint matrix.

        Args:
            tasks: List of tasks to test
            constraints: List of constraints to test
            use_logit_bias: Use token-level constraints if supported
            progress: Show progress bar

        Returns:
            List of all comparison results
        """
        results = []
        total = len(tasks) * len(constraints)

        if progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            ) as prog:
                task_prog = prog.add_task("Scanning...", total=total)

                for constraint in constraints:
                    for task in tasks:
                        result = self.run_comparison(task, constraint, use_logit_bias)
                        results.append(result)
                        prog.advance(task_prog)
        else:
            for constraint in constraints:
                for task in tasks:
                    result = self.run_comparison(task, constraint, use_logit_bias)
                    results.append(result)

        return results
