#!/usr/bin/env python3
"""Test that the README quickstart example works"""

from entity_bind import StaticCatalog, Entity, ToolSpec, Precondition, RiskLevel, gate

# 1. Define catalog
catalog = StaticCatalog(entities=[
    Entity(
        id="person_alex_chen",
        type="person",
        name="Alex Chen",
        email="alex.chen@company.com",
        metadata="Engineering team; leads launch program"
    ),
    Entity(
        id="person_alex_kumar",
        type="person",
        name="Alex Kumar",
        email="alex.kumar@company.com",
        metadata="Customer success manager"
    ),
    Entity(
        id="person_priya",
        type="person",
        name="Priya Shah",
        email="priya@company.com",
        metadata="Product manager"
    )
])

# 2. Define tool spec
send_email_spec = ToolSpec(
    name="send_email",
    description="Send an email to a recipient",
    preconditions=[
        Precondition(slot="recipient", entity_type="person", required=True)
    ],
    risk=RiskLevel.HIGH
)

# 3. Test ambiguous case
print("Testing ambiguous case (Alex)...")
result_ambiguous = gate(
    tool_name="send_email",
    tool_args={"recipient": "Alex", "message": "Launch update"},
    catalog=catalog,
    tool_spec=send_email_spec
)
print(f"  Decision: {result_ambiguous.decision}")
print(f"  Has clarification: {result_ambiguous.clarification is not None}")
from entity_bind import GateDecision
assert result_ambiguous.decision != GateDecision.ACT, "Should not act on ambiguous mention"
assert result_ambiguous.clarification is not None, "Should provide clarification"
print("  ✅ Correctly blocked ambiguous mention")

# 4. Test unambiguous case
print("\nTesting unambiguous case (Priya)...")
result_unambiguous = gate(
    tool_name="send_email",
    tool_args={"recipient": "Priya", "message": "Launch update"},
    catalog=catalog,
    tool_spec=send_email_spec
)
print(f"  Decision: {result_unambiguous.decision}")
print(f"  Bound args: {result_unambiguous.bound_args}")
assert result_unambiguous.decision == GateDecision.ACT, "Should act on unambiguous mention"
assert result_unambiguous.bound_args["recipient"] == "person_priya", "Should bind to correct entity"
print("  ✅ Correctly acted on unambiguous mention")

print("\n✅ README quickstart example works correctly!")
