"""Two-pass recovery tester for constraint mitigation."""

from dataclasses import dataclass
from typing import List, Optional
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .providers.base import BaseProvider
from .constraints.engine import Constraint
from .tasks.loader import Task


@dataclass
class RecoveryResult:
    """Result of two-pass recovery test."""

    task_name: str
    constraint_name: str
    single_pass_response: str  # Generated with constraint from start
    two_pass_response: str  # Unconstrained then rewritten
    two_pass_better: bool  # True if two-pass recovered quality
    recovery_rate: float  # 0.0 to 1.0

    def get_recommendation(self) -> str:
        """Get recommendation based on recovery rate.

        Returns:
            Recommendation string
        """
        if self.recovery_rate > 0.8:
            return "USE TWO-PASS"
        elif self.recovery_rate > 0.5:
            return "TWO-PASS HELPS"
        else:
            return "DROP CONSTRAINT"


class RecoveryTester:
    """Test whether two-pass generation recovers quality loss from constraints.

    Two-pass approach:
    1. Generate unconstrained baseline
    2. Rewrite baseline with constraint applied

    Compare against single-pass constrained generation.
    """

    def __init__(
        self,
        provider: BaseProvider,
        judge_provider: Optional[BaseProvider] = None,
    ):
        """Initialize recovery tester.

        Args:
            provider: LLM provider for generating responses
            judge_provider: Optional separate provider for judging
        """
        self.provider = provider
        self.judge_provider = judge_provider or provider

    def test_recovery(
        self,
        task: Task,
        constraint: Constraint,
        use_logit_bias: bool = False,
    ) -> RecoveryResult:
        """Test two-pass recovery for a task-constraint pair.

        Args:
            task: Task to test
            constraint: Constraint to apply
            use_logit_bias: Use token-level constraints if supported

        Returns:
            RecoveryResult with comparison
        """
        # Single-pass: generate with constraint from start
        single_pass = self._generate_constrained(
            task.get_prompt(),
            constraint,
            use_logit_bias,
        )

        # Two-pass: generate unconstrained, then rewrite
        unconstrained = self.provider.generate(
            prompt=task.get_prompt(),
            temperature=1.0,
            max_tokens=2000,
        )

        # Rewrite with constraint
        rewrite_prompt = self._create_rewrite_prompt(
            task.get_prompt(),
            unconstrained,
            constraint,
        )

        two_pass = self._generate_constrained(
            rewrite_prompt,
            constraint,
            use_logit_bias,
        )

        # Judge which is better
        two_pass_better = self._judge_recovery(
            task.get_prompt(),
            single_pass,
            two_pass,
        )

        # Calculate recovery rate (simplified: 1.0 if recovered, 0.0 if not)
        recovery_rate = 1.0 if two_pass_better else 0.0

        return RecoveryResult(
            task_name=task.name,
            constraint_name=constraint.name,
            single_pass_response=single_pass,
            two_pass_response=two_pass,
            two_pass_better=two_pass_better,
            recovery_rate=recovery_rate,
        )

    def _generate_constrained(
        self,
        prompt: str,
        constraint: Constraint,
        use_logit_bias: bool,
    ) -> str:
        """Generate with constraint applied.

        Args:
            prompt: Prompt
            constraint: Constraint to apply
            use_logit_bias: Use token-level if supported

        Returns:
            Generated text
        """
        if use_logit_bias and self.provider.supports_logit_bias():
            token_ids = self.provider.get_token_ids(constraint.tokens or [])
            logit_bias = constraint.get_logit_bias(token_ids)

            return self.provider.generate(
                prompt=prompt,
                temperature=1.0,
                max_tokens=2000,
                logit_bias=logit_bias,
            )
        else:
            _, system_prompt = self.provider.apply_constraint_instruction(
                base_prompt=prompt,
                constraint_instruction=constraint.get_instruction(),
            )

            return self.provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=1.0,
                max_tokens=2000,
            )

    def _create_rewrite_prompt(
        self,
        original_task: str,
        unconstrained_response: str,
        constraint: Constraint,
    ) -> str:
        """Create prompt for rewriting with constraint.

        Args:
            original_task: Original task prompt
            unconstrained_response: Unconstrained response to rewrite
            constraint: Constraint to apply

        Returns:
            Rewrite prompt
        """
        return f"""Rewrite the following response to maintain its quality and comprehensiveness while applying this constraint: {constraint.get_instruction()}

ORIGINAL TASK:
{original_task}

RESPONSE TO REWRITE:
{unconstrained_response}

Provide the rewritten version:"""

    def _judge_recovery(
        self,
        task_prompt: str,
        single_pass: str,
        two_pass: str,
    ) -> bool:
        """Judge if two-pass is better than single-pass.

        Args:
            task_prompt: Original task
            single_pass: Single-pass constrained response
            two_pass: Two-pass constrained response

        Returns:
            True if two-pass is better
        """
        # Check if provider has built-in judge
        if hasattr(self.judge_provider, "judge_pairwise"):
            winner = self.judge_provider.judge_pairwise(
                task_prompt, single_pass, two_pass
            )
            return winner == "B"  # Two-pass is position B

        # Use LLM judge
        judge_prompt = f"""You are evaluating two responses to the same task. Both responses follow a constraint, but were generated differently. Judge which is MORE COMPREHENSIVE and COMPLETE.

TASK:
{task_prompt}

RESPONSE A (single-pass):
{single_pass}

RESPONSE B (two-pass):
{two_pass}

Which response is more comprehensive and thorough?
Output only 'A' or 'B'."""

        judgment = self.judge_provider.generate(
            prompt=judge_prompt,
            system_prompt="You are an impartial judge. Output only 'A' or 'B'.",
            temperature=0.0,
            max_tokens=10,
        )

        judgment = judgment.strip().upper()
        return "B" in judgment

    def test_multiple(
        self,
        tasks: List[Task],
        constraint: Constraint,
        use_logit_bias: bool = False,
        progress: bool = True,
    ) -> List[RecoveryResult]:
        """Test recovery across multiple tasks.

        Args:
            tasks: List of tasks
            constraint: Constraint to test
            use_logit_bias: Use token-level if supported
            progress: Show progress bar

        Returns:
            List of recovery results
        """
        results = []

        if progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            ) as prog:
                task_prog = prog.add_task(
                    f"Testing recovery for {constraint.name}...",
                    total=len(tasks),
                )

                for task in tasks:
                    result = self.test_recovery(task, constraint, use_logit_bias)
                    results.append(result)
                    prog.advance(task_prog)
        else:
            for task in tasks:
                result = self.test_recovery(task, constraint, use_logit_bias)
                results.append(result)

        return results

    def calculate_recovery_rate(
        self,
        results: List[RecoveryResult],
    ) -> float:
        """Calculate aggregate recovery rate.

        Args:
            results: List of recovery results

        Returns:
            Overall recovery rate (0.0 to 1.0)
        """
        if not results:
            return 0.0

        successes = sum(1 for r in results if r.two_pass_better)
        return successes / len(results)
