#!/usr/bin/env python3
"""
P5: Offline test suite.
MUST pass with NO live LLM (SHACL + P2 numeric + verifier assertions).
"""
import pytest
import json
from pathlib import Path


def test_p2_semantic_layer_reproduces_six_rates():
    """P2 Gate: Six-rate divergence via semantic layer (LLM-free)."""
    from semantic.compiler import MetricCompiler

    compiler = MetricCompiler()

    metrics_to_test = [
        "naive_header_denial_rate_with_rejections",
        "header_denial_rate_adj_only",
        "line_denial_rate_everything_not_paid",
        "line_denial_rate_excl_reversals_dupes_keep_pr",
        "first_pass_line_denial_rate",
        "auth_defect_denial_rate"
    ]

    results = []
    for mid in metrics_to_test:
        result = compiler.query_metric(mid)
        results.append(result)
        assert "rate_pct" in result
        assert result["rate_pct"] > 0

    # Calculate spread
    rates = [r['rate_pct'] for r in results]
    spread_ratio = max(rates) / min(rates) if min(rates) > 0 else 0

    # Expect significant divergence (at least 2x)
    assert spread_ratio >= 2.0, f"Expected spread >=2x, got {spread_ratio:.1f}x"
    print(f"✅ Six-rate spread: {min(rates):.1f}% -> {max(rates):.1f}% ({spread_ratio:.1f}x)")


def test_p3_shacl_validation_passes_clean_data():
    """P3 Gate: SHACL validation passes on clean data."""
    from ontology.graph import PayorGraph

    graph = PayorGraph()
    graph.load_instances()

    conforms = graph.validate_shacl()
    assert conforms, "SHACL validation should pass on clean data"
    print("✅ SHACL validation passes on clean data")


def test_p3_shacl_validation_fails_on_violations():
    """P3 Gate: SHACL validation fails on seeded violations."""
    from ontology.graph import PayorGraph, seed_violations_for_testing

    graph = PayorGraph()
    graph.load_instances()

    # Seed violations
    seed_violations_for_testing(graph)

    conforms = graph.validate_shacl()
    assert not conforms, "SHACL validation should fail on seeded violations"
    print("✅ SHACL correctly fails on seeded violations")


def test_p3_inference_from_absence_finds_hs14_gap():
    """P3 Gate: Inference-from-absence finds HS-14 authorization gap."""
    from ontology.graph import PayorGraph

    graph = PayorGraph()
    graph.load_instances()

    absence_results = graph.traverse_carc_197_to_root_cause()

    # Should find at least one health system with missing auth
    assert len(absence_results) > 0, "Should find at least one authorization gap"

    # Should specifically find HS-14
    hs_ids = [str(row.hs).split("_")[-1] for row in absence_results]
    assert "HS-14" in hs_ids, "Should identify HS-14 notification gap"
    print(f"✅ Found authorization gaps: {hs_ids}")


def test_warehouse_data_exists():
    """Verify warehouse data files exist."""
    assert Path("warehouse/claims.duckdb").exists()
    assert Path("warehouse/schema.txt").exists()
    print("✅ Warehouse data exists")


def test_ground_truth_exists():
    """Verify ground truth exists."""
    assert Path("generate/truth.json").exists()

    with open("generate/truth.json") as f:
        truth = json.load(f)

    assert "governed_answer" in truth
    assert "rate_pct" in truth["governed_answer"]
    assert "at_risk_allowed_dollars" in truth["governed_answer"]
    print("✅ Ground truth loaded")


def test_verification_layer_extracts_facts():
    """Test verification layer extracts structured facts."""
    from eval.verify import extract_structured_answer

    # Mock answer with key facts
    text = """The denial rate is 12.9%. CARC-197 accounts for 61.6% of denials.
    The at-risk allowed amount is $354,110.56. Root cause: HS-14 was omitted from
    notification cohort per UM-RAD-2026 policy (MP-RAD-114 §4.2)."""

    extracted = extract_structured_answer(text)

    assert "rate_pct" in extracted
    assert extracted["rate_pct"] == 12.9

    assert "carc_197_dominance_pct" in extracted
    assert extracted["carc_197_dominance_pct"] == 61.6

    assert "at_risk_allowed_dollars" in extracted
    assert abs(extracted["at_risk_allowed_dollars"] - 354110.56) < 1.0

    assert extracted.get("mentions_hs14") == True
    assert extracted.get("identifies_notification_gap") == True
    assert extracted.get("cites_policy") == True

    print("✅ Verification extracts all key facts")


def test_verification_layer_detects_diffs():
    """Test verification layer detects discrepancies."""
    from eval.verify import verify_governed_answer

    # Mock answer with WRONG facts
    wrong_answer = {
        "answer": "The denial rate is 25.0%. We have no idea why."
    }

    result = verify_governed_answer(wrong_answer)

    # Should have diffs
    assert result["diff_count"] > 0, "Should detect discrepancies"
    assert not result["passed"], "Should fail verification"
    print(f"✅ Verification detects {result['diff_count']} diffs")


def test_ontology_loads():
    """Test ontology RDF file loads."""
    from rdflib import Graph

    g = Graph()
    g.parse("ontology/payor.ttl", format="turtle")

    assert len(g) > 0, "Ontology should have triples"
    print(f"✅ Ontology loaded: {len(g)} triples")


def test_shapes_load():
    """Test SHACL shapes file loads."""
    from rdflib import Graph

    g = Graph()
    g.parse("ontology/shapes/denial_shapes.shacl.ttl", format="turtle")

    assert len(g) > 0, "Shapes should have constraints"
    print(f"✅ SHACL shapes loaded: {len(g)} triples")


def test_semantic_metrics_yaml_valid():
    """Test semantic metrics YAML is valid."""
    import yaml

    with open("semantic/metrics/denials.yml") as f:
        metrics = yaml.safe_load(f)

    assert "metrics" in metrics
    assert len(metrics["metrics"]) > 0

    for metric in metrics["metrics"]:
        assert "id" in metric
        assert "name" in metric
        assert "version" in metric

    print(f"✅ Semantic metrics YAML valid: {len(metrics['metrics'])} metrics")


def test_eval_questions_yaml_valid():
    """Test evaluation questions YAML is valid."""
    import yaml

    with open("eval/questions.yml") as f:
        questions = yaml.safe_load(f)

    assert "questions" in questions
    assert len(questions["questions"]) >= 50

    for q in questions["questions"]:
        assert "id" in q
        assert "text" in q
        assert "category" in q

    print(f"✅ Evaluation questions YAML valid: {len(questions['questions'])} questions")


def test_requirements_installable():
    """Test requirements.txt lists all dependencies."""
    assert Path("requirements.txt").exists()

    with open("requirements.txt") as f:
        reqs = f.read()

    required = ["duckdb", "rdflib", "pyshacl", "litellm", "pytest", "PyYAML"]
    for pkg in required:
        assert pkg in reqs, f"Missing dependency: {pkg}"

    print("✅ Requirements.txt complete")


def test_demo_mock_mode_runs():
    """Test demo.py runs in mock mode (no LLM)."""
    from demo import run_mock_demo

    question = "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?"
    result = run_mock_demo(question)

    assert "ungoverned" in result
    assert "governed" in result
    assert "verification" in result

    # Verification should pass in mock mode
    assert result["verification"]["passed"], "Mock demo verification should pass"

    print("✅ Demo mock mode runs and verifies")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
