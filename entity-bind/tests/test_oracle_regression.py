"""
Oracle Regression Test

This test verifies that the reference implementation's CSV oracle
matches the exact counts reported in the paper:
- 1800 total rows (5 models × 6 methods × 60 tasks)
- 305 wrong-entity rows
- 0 wrong-tool rows
- 0 over-clarification rows
- 0 error rows

If this test fails, either:
1. The reference data has changed (unlikely - it's versioned)
2. Our understanding of the metrics is incorrect

This is the FIRST test to write and the LAST test to break.
"""

import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def oracle_csv():
    """Load the reference implementation's result CSV."""
    csv_path = Path(__file__).parent.parent / "reference" / "results" / "final_60_5models.csv"
    if not csv_path.exists():
        pytest.skip(f"Reference CSV not found at {csv_path}")
    return pd.read_csv(csv_path)


def test_oracle_row_count(oracle_csv):
    """Verify total row count: 5 models × 6 methods × 60 tasks = 1800."""
    assert len(oracle_csv) == 1800, (
        f"Expected 1800 rows in oracle CSV, got {len(oracle_csv)}"
    )


def test_oracle_dimensions(oracle_csv):
    """Verify the expected number of models, methods, and tasks."""
    n_models = oracle_csv['model'].nunique()
    n_methods = oracle_csv['method'].nunique()
    n_tasks = oracle_csv['task_id'].nunique()

    assert n_models == 5, f"Expected 5 models, got {n_models}"
    assert n_methods == 6, f"Expected 6 methods, got {n_methods}"
    assert n_tasks == 60, f"Expected 60 tasks, got {n_tasks}"

    # Verify cartesian product
    expected = n_models * n_methods * n_tasks
    actual = len(oracle_csv)
    assert actual == expected, (
        f"Expected {n_models} × {n_methods} × {n_tasks} = {expected} rows, "
        f"got {actual}"
    )


def test_oracle_wrong_entity_count(oracle_csv):
    """
    Verify wrong-entity count: 305 rows.

    This is the paper's headline finding: 24-26% wrong-entity rate
    across action-oriented baselines (direct, semantic_filter, cmtf_only,
    entity_retrieval) and 0% for entity-aware methods (confidence_gate,
    entity_cmtf_provenance).
    """
    wrong_entity_rows = (oracle_csv['wrong_entity'] == 1).sum()
    assert wrong_entity_rows == 305, (
        f"Expected exactly 305 wrong-entity rows, got {wrong_entity_rows}"
    )

    # Verify wrong-entity rate is ~24-26% (305/1800 ≈ 16.9% overall,
    # but concentrated in 4 of 6 methods)
    wrong_entity_rate = wrong_entity_rows / len(oracle_csv)
    assert 0.16 < wrong_entity_rate < 0.18, (
        f"Expected wrong-entity rate ~16.9%, got {wrong_entity_rate:.2%}"
    )


def test_oracle_wrong_tool_count(oracle_csv):
    """
    Verify wrong-tool count: 0 rows.

    This is the paper's key orthogonality insight: 0% wrong-tool errors
    yet 24-26% wrong-entity actions. Tool selection is solved; entity
    binding is not.
    """
    wrong_tool_rows = (oracle_csv['wrong_tool'] == 1).sum()
    assert wrong_tool_rows == 0, (
        f"Expected 0 wrong-tool rows, got {wrong_tool_rows}"
    )


def test_oracle_over_clarification_count(oracle_csv):
    """
    Verify over-clarification count: 0 rows.

    This validates that entity-aware methods (confidence_gate,
    entity_cmtf_provenance) did not nag on unambiguous tasks.
    The completion drop (74% → 32%) came from refusing genuinely
    ambiguous tasks, not from over-clarifying clear ones.
    """
    over_clarification_rows = (oracle_csv['over_clarification'] == 1).sum()
    assert over_clarification_rows == 0, (
        f"Expected 0 over-clarification rows, got {over_clarification_rows}"
    )


def test_oracle_methods_present(oracle_csv):
    """Verify all 6 expected methods are present."""
    expected_methods = {
        'direct',
        'semantic_filter',
        'cmtf_only',
        'entity_retrieval',
        'confidence_gate',
        'entity_cmtf_provenance'
    }
    actual_methods = set(oracle_csv['method'].unique())

    assert actual_methods == expected_methods, (
        f"Method mismatch. Expected {expected_methods}, got {actual_methods}"
    )


def test_oracle_entity_aware_methods_zero_wrong_entity(oracle_csv):
    """
    Verify entity-aware methods achieve 0% wrong-entity rate.

    This is the paper's main result: confidence_gate and
    entity_cmtf_provenance both achieve 0.0 wrong-entity actions
    by deferring/clarifying under ambiguity.
    """
    entity_aware_methods = ['confidence_gate', 'entity_cmtf_provenance']

    for method in entity_aware_methods:
        method_df = oracle_csv[oracle_csv['method'] == method]
        wrong_entity_count = (method_df['wrong_entity'] == 1).sum()

        assert wrong_entity_count == 0, (
            f"Method '{method}' should have 0 wrong-entity actions, "
            f"got {wrong_entity_count}"
        )


def test_oracle_baseline_methods_have_wrong_entity(oracle_csv):
    """
    Verify action-oriented baselines have wrong-entity failures.

    All four baselines (direct, semantic_filter, cmtf_only,
    entity_retrieval) should have wrong-entity rates in the
    24-26% range (72-78 errors per method out of 300 runs).
    """
    baseline_methods = ['direct', 'semantic_filter', 'cmtf_only', 'entity_retrieval']

    for method in baseline_methods:
        method_df = oracle_csv[oracle_csv['method'] == method]
        wrong_entity_count = (method_df['wrong_entity'] == 1).sum()
        wrong_entity_rate = wrong_entity_count / len(method_df)

        # Each method has 300 runs (5 models × 60 tasks)
        assert len(method_df) == 300, f"Expected 300 rows for {method}"

        # Wrong-entity rate should be in [0.22, 0.28] range
        # (allowing for some variance across methods)
        assert 0.20 < wrong_entity_rate < 0.30, (
            f"Method '{method}' should have ~24-26% wrong-entity rate, "
            f"got {wrong_entity_rate:.2%} ({wrong_entity_count}/300)"
        )


def test_oracle_summary_statistics(oracle_csv):
    """
    Verify summary statistics match Table II from the paper.

    This is a sanity check that we're reading the same data the
    paper reports.
    """
    # Group by method and compute metrics
    summary = oracle_csv.groupby('method').agg({
        'task_success': 'mean',
        'safe_success': 'mean',
        'wrong_tool': 'mean',
        'wrong_entity': 'mean',
        'entity_correct': 'mean',
        'ambiguity_detected': 'mean',
        'over_clarification': 'mean',
        'risk_weighted_wrong_entity': 'mean'
    }).round(4)

    # Spot-check a few values from Table II
    # (allowing for minor floating-point differences)

    # Direct method
    direct = summary.loc['direct']
    assert abs(direct['task_success'] - 0.74) < 0.01
    assert abs(direct['wrong_entity'] - 0.26) < 0.01
    assert direct['wrong_tool'] == 0.0
    assert direct['over_clarification'] == 0.0

    # Confidence gate method
    conf_gate = summary.loc['confidence_gate']
    assert abs(conf_gate['safe_success'] - 0.40) < 0.01
    assert conf_gate['wrong_entity'] == 0.0
    assert abs(conf_gate['ambiguity_detected'] - 0.68) < 0.02


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
