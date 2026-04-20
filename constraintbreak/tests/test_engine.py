"""Tests for pairwise comparison engine."""

import pytest
from constraintbreak.engine import PairwiseEngine, ComparisonResult
from constraintbreak.providers import MockProvider
from constraintbreak.constraints import Constraint
from constraintbreak.tasks import Task


class TestPairwiseEngine:
    """Test PairwiseEngine."""

    @pytest.fixture
    def provider(self):
        """Create mock provider."""
        return MockProvider()

    @pytest.fixture
    def engine(self, provider):
        """Create pairwise engine."""
        return PairwiseEngine(provider)

    @pytest.fixture
    def test_constraint(self):
        """Create test constraint."""
        return Constraint(
            name="test_constraint",
            description="Test constraint",
            instruction="Never use the letter X in your response.",
            tokens=["X"],
            category="test",
        )

    @pytest.fixture
    def test_task(self):
        """Create test task."""
        return Task(
            name="test_task",
            category="test",
            prompt="Write a short essay about testing.",
        )

    def test_engine_initialization(self, provider):
        """Test engine initialization."""
        engine = PairwiseEngine(provider)
        assert engine.provider == provider
        assert engine.judge_provider == provider

    def test_run_comparison(self, engine, test_task, test_constraint):
        """Test running a single comparison."""
        result = engine.run_comparison(
            task=test_task,
            constraint=test_constraint,
            use_logit_bias=False,
        )

        assert isinstance(result, ComparisonResult)
        assert result.task_name == test_task.name
        assert result.constraint_name == test_constraint.name
        assert result.unconstrained_response
        assert result.constrained_response
        assert result.winner_ab in ["A", "B"]
        assert result.winner_ba in ["A", "B"]
        assert 0.0 <= result.win_rate <= 1.0

    def test_comparison_detects_degradation(self, engine, test_task, test_constraint):
        """Test that comparison detects quality degradation."""
        result = engine.run_comparison(
            task=test_task,
            constraint=test_constraint,
            use_logit_bias=False,
        )

        # MockProvider should show unconstrained is better
        assert result.degradation_detected
        assert result.win_rate > 0.0

    def test_severity_levels(self, test_task, test_constraint):
        """Test severity level calculation."""
        # Test each severity level
        result_none = ComparisonResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="B",
            winner_ba="A",
            degradation_detected=False,
            win_rate=0.0,
        )
        assert result_none.get_severity() == "none"

        result_low = ComparisonResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="A",
            winner_ba="A",
            degradation_detected=True,
            win_rate=0.1,
        )
        assert result_low.get_severity() == "low"

        result_medium = ComparisonResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="A",
            winner_ba="B",
            degradation_detected=True,
            win_rate=0.2,
        )
        assert result_medium.get_severity() == "medium"

        result_high = ComparisonResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="A",
            winner_ba="B",
            degradation_detected=True,
            win_rate=0.5,
        )
        assert result_high.get_severity() == "high"

    def test_position_bias_correction(self, engine):
        """Test position bias correction in win rate calculation."""
        # Both positions favor unconstrained
        win_rate = engine._calculate_win_rate("A", "B")
        assert win_rate == 1.0

        # Both positions favor constrained
        win_rate = engine._calculate_win_rate("B", "A")
        assert win_rate == 0.0

        # Split decision
        win_rate = engine._calculate_win_rate("A", "A")
        assert win_rate == 0.5

        win_rate = engine._calculate_win_rate("B", "B")
        assert win_rate == 0.5

    def test_scan_full_matrix(self, engine, test_constraint):
        """Test scanning full task x constraint matrix."""
        from constraintbreak.tasks import TaskLoader

        loader = TaskLoader()
        tasks = loader.get_tasks()[:2]  # Use first 2 tasks for speed
        constraints = [test_constraint]

        results = engine.scan_full_matrix(
            tasks=tasks,
            constraints=constraints,
            use_logit_bias=False,
            progress=False,
        )

        assert len(results) == len(tasks) * len(constraints)
        assert all(isinstance(r, ComparisonResult) for r in results)
