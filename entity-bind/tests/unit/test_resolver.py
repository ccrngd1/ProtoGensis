"""Unit tests for resolver and gate."""

import pytest
from entity_bind.catalog import StaticCatalog, Entity, ToolSpec, Precondition, RiskLevel
from entity_bind.core import EntityResolver, gate, GateDecision


@pytest.fixture
def sample_catalog():
    """Create a sample catalog with name collision."""
    return StaticCatalog(entities=[
        Entity(
            id="person_alex_chen",
            type="person",
            name="Alex Chen",
            email="alex.chen@company.com",
            metadata="Engineering team"
        ),
        Entity(
            id="person_alex_kumar",
            type="person",
            name="Alex Kumar",
            email="alex.kumar@company.com",
            metadata="Customer success"
        ),
        Entity(
            id="person_priya",
            type="person",
            name="Priya Shah",
            email="priya@company.com",
            metadata="Product manager"
        )
    ])


@pytest.fixture
def send_email_spec():
    """Create send_email tool spec."""
    return ToolSpec(
        name="send_email",
        description="Send an email",
        preconditions=[
            Precondition(slot="recipient", entity_type="person", required=True)
        ],
        risk=RiskLevel.HIGH
    )


def test_resolver_unambiguous(sample_catalog):
    """Test resolver on unambiguous mention."""
    resolver = EntityResolver(sample_catalog)

    result = resolver.resolve(
        mention="Priya",
        expected_type="person",
        risk=RiskLevel.MEDIUM
    )

    assert result.resolved
    assert result.entity.id == "person_priya"
    assert result.confidence > 0.7
    assert result.passed_tau
    assert result.passed_delta


def test_resolver_name_collision(sample_catalog):
    """Test resolver on ambiguous name collision."""
    resolver = EntityResolver(sample_catalog)

    result = resolver.resolve(
        mention="Alex",
        expected_type="person",
        risk=RiskLevel.HIGH  # High risk = strict thresholds
    )

    # Should NOT resolve due to ambiguity
    assert not result.resolved
    assert len(result.candidates) >= 2
    assert result.clarification is not None
    assert "Alex Chen" in result.clarification or "Alex Kumar" in result.clarification


def test_gate_act_on_unambiguous(sample_catalog, send_email_spec):
    """Test gate ACTs on unambiguous input."""
    gate_result = gate(
        tool_name="send_email",
        tool_args={"recipient": "Priya", "message": "Hello"},
        catalog=sample_catalog,
        tool_spec=send_email_spec
    )

    assert gate_result.decision == GateDecision.ACT
    assert gate_result.bound_args["recipient"] == "person_priya"
    assert gate_result.all_resolved


def test_gate_clarify_on_ambiguous(sample_catalog, send_email_spec):
    """Test gate CLARIFIES on ambiguous input."""
    gate_result = gate(
        tool_name="send_email",
        tool_args={"recipient": "Alex", "message": "Hello"},
        catalog=sample_catalog,
        tool_spec=send_email_spec
    )

    assert gate_result.decision == GateDecision.CLARIFY
    assert not gate_result.all_resolved
    assert gate_result.clarification is not None
    assert "recipient" in gate_result.unresolved_slots


def test_gate_no_preconditions(sample_catalog):
    """Test gate with tool that has no entity preconditions."""
    # Tool with no entity preconditions
    spec = ToolSpec(
        name="get_time",
        description="Get current time",
        preconditions=[],
        risk=RiskLevel.LOW
    )

    gate_result = gate(
        tool_name="get_time",
        tool_args={},
        catalog=sample_catalog,
        tool_spec=spec
    )

    # Should ACT immediately (no preconditions to check)
    assert gate_result.decision == GateDecision.ACT
    assert gate_result.all_resolved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
