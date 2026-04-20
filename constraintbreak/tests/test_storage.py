"""Tests for storage module."""

import pytest
import tempfile
from pathlib import Path
from constraintbreak.storage import ResultStorage
from constraintbreak.engine import ComparisonResult
from constraintbreak.recovery import RecoveryResult


class TestResultStorage:
    """Test ResultStorage."""

    @pytest.fixture
    def storage(self):
        """Create temporary storage."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        storage = ResultStorage(db_path)
        yield storage

        # Cleanup
        Path(db_path).unlink()

    @pytest.fixture
    def sample_comparison_results(self):
        """Create sample comparison results."""
        return [
            ComparisonResult(
                task_name="task1",
                constraint_name="constraint1",
                unconstrained_response="Unconstrained",
                constrained_response="Constrained",
                winner_ab="A",
                winner_ba="B",
                degradation_detected=True,
                win_rate=0.5,
            ),
            ComparisonResult(
                task_name="task2",
                constraint_name="constraint1",
                unconstrained_response="Unconstrained",
                constrained_response="Constrained",
                winner_ab="B",
                winner_ba="A",
                degradation_detected=False,
                win_rate=0.0,
            ),
        ]

    @pytest.fixture
    def sample_recovery_results(self):
        """Create sample recovery results."""
        return [
            RecoveryResult(
                task_name="task1",
                constraint_name="constraint1",
                single_pass_response="Single pass",
                two_pass_response="Two pass",
                two_pass_better=True,
                recovery_rate=1.0,
            ),
            RecoveryResult(
                task_name="task2",
                constraint_name="constraint1",
                single_pass_response="Single pass",
                two_pass_response="Two pass",
                two_pass_better=False,
                recovery_rate=0.0,
            ),
        ]

    def test_storage_initialization(self, storage):
        """Test storage initialization."""
        assert storage.db_path
        assert Path(storage.db_path).exists()

    def test_save_and_get_comparison_results(self, storage, sample_comparison_results):
        """Test saving and retrieving comparison results."""
        run_id = "test_run_1"

        storage.save_comparison_results(
            results=sample_comparison_results,
            run_id=run_id,
            provider="mock",
            model_name="test-model",
        )

        retrieved = storage.get_comparison_results(run_id)

        assert len(retrieved) == len(sample_comparison_results)
        assert all(r["run_id"] == run_id for r in retrieved)
        assert all(r["provider"] == "mock" for r in retrieved)

    def test_save_and_get_recovery_results(self, storage, sample_recovery_results):
        """Test saving and retrieving recovery results."""
        run_id = "test_run_2"

        storage.save_recovery_results(
            results=sample_recovery_results,
            run_id=run_id,
            provider="mock",
            model_name="test-model",
        )

        retrieved = storage.get_recovery_results(run_id)

        assert len(retrieved) == len(sample_recovery_results)
        assert all(r["run_id"] == run_id for r in retrieved)

    def test_save_run_metadata(self, storage):
        """Test saving run metadata."""
        run_id = "test_run_3"

        storage.save_run_metadata(
            run_id=run_id,
            provider="mock",
            model_name="test-model",
            test_type="scan",
            config={"use_logit_bias": True},
        )

        runs = storage.list_runs()
        assert any(r["run_id"] == run_id for r in runs)

    def test_list_runs(self, storage, sample_comparison_results):
        """Test listing all runs."""
        storage.save_run_metadata(
            run_id="run1",
            provider="mock",
            model_name="test-model",
            test_type="scan",
        )

        storage.save_run_metadata(
            run_id="run2",
            provider="mock",
            model_name="test-model",
            test_type="recover",
        )

        runs = storage.list_runs()
        assert len(runs) >= 2

    def test_cache_generation(self, storage):
        """Test caching baseline generations."""
        storage.cache_generation(
            task_name="task1",
            provider="mock",
            model_name="test-model",
            prompt_hash="abc123",
            response="Cached response",
        )

        cached = storage.get_cached_generation(
            task_name="task1",
            provider="mock",
            model_name="test-model",
            prompt_hash="abc123",
        )

        assert cached == "Cached response"

    def test_get_cached_generation_not_found(self, storage):
        """Test getting non-existent cached generation."""
        cached = storage.get_cached_generation(
            task_name="nonexistent",
            provider="mock",
            model_name="test-model",
            prompt_hash="xyz789",
        )

        assert cached is None

    def test_get_all_comparison_results(self, storage, sample_comparison_results):
        """Test getting all comparison results without filter."""
        storage.save_comparison_results(
            results=sample_comparison_results,
            run_id="run1",
            provider="mock",
            model_name="test-model",
        )

        all_results = storage.get_comparison_results()
        assert len(all_results) >= len(sample_comparison_results)
