"""Unit tests for catalog module."""

import pytest
from entity_bind.catalog import (
    StaticCatalog,
    Entity,
    EntityType,
    Precondition,
    ToolSpec,
    RiskLevel,
    ThresholdConfig
)


def test_entity_creation():
    """Test entity creation and properties."""
    entity = Entity(
        id="person_alex",
        type="person",
        name="Alex Chen",
        email="alex@company.com",
        aliases=["A. Chen", "Alex"],
        metadata="Engineering team"
    )

    assert entity.id == "person_alex"
    assert entity.type == "person"
    assert entity.display_name == "Alex Chen"
    assert len(entity.all_names) == 3  # name + 2 aliases
    assert entity.matches_type("person")


def test_static_catalog():
    """Test static catalog operations."""
    entities = [
        Entity(id="person_1", type="person", name="Alice"),
        Entity(id="person_2", type="person", name="Bob"),
        Entity(id="doc_1", type="document", title="Report"),
    ]

    catalog = StaticCatalog(entities=entities)

    # Test get
    assert catalog.get("person_1").name == "Alice"
    assert catalog.get("missing") is None

    # Test find_by_type
    people = catalog.find_by_type("person")
    assert len(people) == 2

    # Test all
    assert len(catalog.all()) == 3

    # Test add
    catalog.add(Entity(id="person_3", type="person", name="Charlie"))
    assert len(catalog.all()) == 4

    # Test remove
    assert catalog.remove("person_1")
    assert len(catalog.all()) == 3
    assert not catalog.remove("missing")


def test_precondition_parsing():
    """Test precondition from string parsing."""
    # Required (default)
    p1 = Precondition.from_string("recipient:person")
    assert p1.slot == "recipient"
    assert p1.entity_type == "person"
    assert p1.required

    # Optional
    p2 = Precondition.from_string("attachment:document:optional")
    assert p2.slot == "attachment"
    assert p2.entity_type == "document"
    assert not p2.required


def test_tool_spec():
    """Test tool specification."""
    spec = ToolSpec(
        name="send_email",
        description="Send an email",
        preconditions=[
            Precondition(slot="recipient", entity_type="person", required=True),
            Precondition(slot="attachment", entity_type="document", required=False)
        ],
        risk=RiskLevel.HIGH
    )

    assert spec.name == "send_email"
    assert len(spec.required_preconditions) == 1
    assert len(spec.optional_preconditions) == 1
    assert spec.get_precondition("recipient").required


def test_threshold_defaults():
    """Test threshold configuration defaults."""
    defaults = ThresholdConfig.defaults()

    assert RiskLevel.LOW in defaults
    assert RiskLevel.CRITICAL in defaults

    # Critical should have higher thresholds than low
    assert defaults[RiskLevel.CRITICAL].tau > defaults[RiskLevel.LOW].tau
    assert defaults[RiskLevel.CRITICAL].delta > defaults[RiskLevel.LOW].delta


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
