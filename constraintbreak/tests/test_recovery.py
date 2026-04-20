"""Tests for two-pass recovery tester."""

import pytest
from constraintbreak.recovery import RecoveryTester, RecoveryResult
from constraintbreak.providers import MockProvider
from constraintbreak.constraints import Constraint
from constraintbreak.tasks import Task


class TestRecoveryTester:
    """Test RecoveryTester."""

    @pytest.fixture
    def provider(self):
        """Create mock provider."""
        return MockProvider()

    @pytest.fixture
    def tester(self, provider):
        """Create recovery tester."""
        return RecoveryTester(provider)

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

    def test_tester_initialization(self, provider):
        """Test tester initialization."""
        tester = RecoveryTester(provider)
        assert tester.provider == provider
        assert tester.judge_provider == provider

    def test_test_recovery(self, tester, test_task, test_constraint):
        """Test recovery testing."""
        result = tester.test_recovery(
            task=test_task,
            constraint=test_constraint,
            use_logit_bias=False,
        )

        assert isinstance(result, RecoveryResult)
        assert result.task_name == test_task.name
        assert result.constraint_name == test_constraint.name
        assert result.single_pass_response
        assert result.two_pass_response
        assert isinstance(result.two_pass_better, bool)
        assert 0.0 <= result.recovery_rate <= 1.0

    def test_recovery_recommendations(self, test_task, test_constraint):
        """Test recovery recommendation logic."""
        # High recovery rate
        result_high = RecoveryResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            single_pass_response="test",
            two_pass_response="test",
            two_pass_better=True,
            recovery_rate=0.9,
        )
        assert result_high.get_recommendation() == "USE TWO-PASS"

        # Medium recovery rate
        result_medium = RecoveryResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            single_pass_response="test",
            two_pass_response="test",
            two_pass_better=True,
            recovery_rate=0.6,
        )
        assert result_medium.get_recommendation() == "TWO-PASS HELPS"

        # Low recovery rate
        result_low = RecoveryResult(
            task_name=test_task.name,
            constraint_name=test_constraint.name,
            single_pass_response="test",
            two_pass_response="test",
            two_pass_better=False,
            recovery_rate=0.3,
        )
        assert result_low.get_recommendation() == "DROP CONSTRAINT"

    def test_test_multiple(self, tester, test_constraint):
        """Test recovery across multiple tasks."""
        from constraintbreak.tasks import TaskLoader

        loader = TaskLoader()
        tasks = loader.get_tasks()[:2]  # Use first 2 tasks for speed

        results = tester.test_multiple(
            tasks=tasks,
            constraint=test_constraint,
            use_logit_bias=False,
            progress=False,
        )

        assert len(results) == len(tasks)
        assert all(isinstance(r, RecoveryResult) for r in results)

    def test_calculate_recovery_rate(self, tester, test_task, test_constraint):
        """Test aggregate recovery rate calculation."""
        results = [
            RecoveryResult(
                task_name=f"task_{i}",
                constraint_name=test_constraint.name,
                single_pass_response="test",
                two_pass_response="test",
                two_pass_better=(i % 2 == 0),
                recovery_rate=1.0 if (i % 2 == 0) else 0.0,
            )
            for i in range(4)
        ]

        recovery_rate = tester.calculate_recovery_rate(results)
        assert recovery_rate == 0.5  # 2 out of 4

    def test_calculate_recovery_rate_empty(self, tester):
        """Test recovery rate with empty results."""
        recovery_rate = tester.calculate_recovery_rate([])
        assert recovery_rate == 0.0
