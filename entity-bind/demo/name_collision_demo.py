"""
EntityBind Demo: Name Collision

Demonstrates EntityBind catching a wrong-entity action on a name collision.

Scenario:
- Company has two "Alex" employees: Alex Chen (engineering) and Alex Kumar (customer success)
- Agent is asked to "email Alex about the launch update"
- WITHOUT EntityBind: Agent picks wrong Alex (50/50 chance)
- WITH EntityBind: Detects ambiguity and asks for clarification

This is the paper's core failure mode: right tool (send_email), wrong target (wrong Alex).
"""

from entity_bind.catalog import StaticCatalog, Entity, ToolSpec, Precondition, RiskLevel
from entity_bind.core import gate, GateDecision


def mock_send_email(recipient: str, message: str) -> str:
    """Mock email sender (real tool would call SMTP/API)."""
    return f"✉ Email sent to {recipient}: '{message}'"


def setup_catalog():
    """Create a catalog with two people named Alex."""
    return StaticCatalog(entities=[
        Entity(
            id="person_alex_chen",
            type="person",
            name="Alex Chen",
            email="alex.chen@company.com",
            metadata="Engineering team; leads launch program; works on backend systems"
        ),
        Entity(
            id="person_alex_kumar",
            type="person",
            name="Alex Kumar",
            email="alex.kumar@company.com",
            metadata="Customer success manager; handles customer escalations"
        ),
        Entity(
            id="person_priya",
            type="person",
            name="Priya Shah",
            email="priya@company.com",
            metadata="Product manager; coordinates launch milestones"
        )
    ])


def setup_tool_spec():
    """Create tool specification for send_email."""
    return ToolSpec(
        name="send_email",
        description="Send an email to a recipient",
        preconditions=[
            Precondition(slot="recipient", entity_type="person", required=True)
        ],
        risk=RiskLevel.HIGH  # Sending email is high-risk (visible to recipient)
    )


def run_without_entitybind(catalog):
    """
    Simulate agent WITHOUT EntityBind.

    Agent picks the wrong Alex (simulating typical LLM behavior with ambiguity).
    This is the wrong-entity failure mode.
    """
    print("\n" + "=" * 80)
    print("WITHOUT ENTITYBIND (baseline)")
    print("=" * 80)

    instruction = "Email Alex about the launch update"
    print(f"\n📝 Instruction: {instruction}")
    print(f"   Context: User wants to email Alex Chen (launch team)")

    # Naive resolution: agent picks an Alex, but gets it wrong
    all_entities = catalog.all()
    alex_candidates = [e for e in all_entities if "alex" in e.name.lower()]

    print(f"\n🔍 Found {len(alex_candidates)} people named Alex:")
    for i, entity in enumerate(alex_candidates, 1):
        print(f"   {i}. {entity.name} ({entity.email})")

    # Agent picks wrong one (Alex Kumar instead of Alex Chen)
    # Simulates 50/50 chance - in this case it guessed wrong
    intended = [e for e in alex_candidates if "chen" in e.name.lower()][0]
    chosen = [e for e in alex_candidates if "kumar" in e.name.lower()][0]

    print(f"\n🤖 Agent chose: {chosen.name}")

    # Execute
    result = mock_send_email(chosen.id, "Here's the launch update...")
    print(f"\n{result}")

    # Outcome
    print(f"\n❌ WRONG-ENTITY ACTION:")
    print(f"   User intended to email {intended.name} (launch team)")
    print(f"   but agent actually emailed {chosen.name} (customer success)")
    print(f"   Conventional metrics show: 0% wrong-tool, 100% 'successful' execution")
    print(f"   Reality: wrong target, confusing email sent to wrong person")


def run_with_entitybind(catalog, tool_spec):
    """
    Run agent WITH EntityBind.

    EntityBind detects ambiguity and asks for clarification.
    """
    print("\n" + "=" * 80)
    print("WITH ENTITYBIND")
    print("=" * 80)

    instruction = "Email Alex about the launch update"
    print(f"\n📝 Instruction: {instruction}")

    # Tool call (simulating LLM output)
    tool_name = "send_email"
    tool_args = {
        "recipient": "Alex",  # Ambiguous mention
        "message": "Here's the launch update..."
    }

    print(f"\n🤖 Agent calls: {tool_name}({tool_args})")

    # Run EntityBind gate
    gate_result = gate(
        tool_name=tool_name,
        tool_args=tool_args,
        catalog=catalog,
        tool_spec=tool_spec
    )

    print(f"\n🛡  EntityBind decision: {gate_result.decision.value.upper()}")

    if gate_result.decision == GateDecision.ACT:
        # Resolved - execute
        result = mock_send_email(**gate_result.bound_args)
        print(f"\n{result}")
        print(f"\n✅ SAFE ACTION: Entity resolved to {gate_result.bound_args['recipient']}")

    else:
        # Ambiguous - ask for clarification
        print(f"\n❓ Clarification needed:")
        print(f"   {gate_result.clarification}")
        print(f"\n✅ SAFE OUTCOME: Detected ambiguity, prevented wrong-entity action")

        # Show what bindings were considered
        if gate_result.bindings:
            for slot, binding in gate_result.bindings.items():
                if binding.candidates:
                    print(f"\n   Candidates for '{binding.mention}':")
                    for entity, score in binding.top_candidates:
                        print(f"      - {entity.name} ({entity.email}): score={score:.3f}")
                    print(f"   Top-1 score: {binding.confidence:.3f}, tau={binding.tau:.3f}")
                    print(f"   Margin: {binding.margin:.3f}, delta={binding.delta:.3f}")
                    print(f"   Passed tau: {binding.passed_tau}, Passed delta: {binding.passed_delta}")


def run_unambiguous_case(catalog, tool_spec):
    """
    Run an unambiguous case to show EntityBind doesn't over-clarify.

    "Email Priya" is unambiguous - EntityBind should ACT.
    """
    print("\n" + "=" * 80)
    print("UNAMBIGUOUS CASE (should ACT, not over-clarify)")
    print("=" * 80)

    instruction = "Email Priya about the launch update"
    print(f"\n📝 Instruction: {instruction}")

    tool_args = {
        "recipient": "Priya",
        "message": "Here's the launch update..."
    }

    gate_result = gate(
        tool_name="send_email",
        tool_args=tool_args,
        catalog=catalog,
        tool_spec=tool_spec
    )

    print(f"\n🛡  EntityBind decision: {gate_result.decision.value.upper()}")

    if gate_result.decision == GateDecision.ACT:
        result = mock_send_email(**gate_result.bound_args)
        print(f"\n{result}")
        print(f"\n✅ CORRECT: Acted on unambiguous input (no over-clarification)")

        # Show resolution details
        if gate_result.bindings:
            for slot, binding in gate_result.bindings.items():
                print(f"\n   Resolved '{binding.mention}' to {binding.entity.name}")
                print(f"   Score: {binding.confidence:.3f}, Margin: {binding.margin:.3f}")
    else:
        print(f"\n❌ OVER-CLARIFICATION: Asked for clarification on unambiguous input")


def main():
    """Run all demo scenarios."""
    print("\n" + "=" * 80)
    print("EntityBind Demo: Name Collision")
    print("=" * 80)
    print("\nThis demo shows EntityBind catching a wrong-entity action.")
    print("Scenario: Two employees named 'Alex' - which one should receive the email?")

    # Setup
    catalog = setup_catalog()
    tool_spec = setup_tool_spec()

    # Demo 1: WITHOUT EntityBind (wrong-entity failure)
    run_without_entitybind(catalog)

    # Demo 2: WITH EntityBind (detects ambiguity)
    run_with_entitybind(catalog, tool_spec)

    # Demo 3: Unambiguous case (no over-clarification)
    run_unambiguous_case(catalog, tool_spec)

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)
    print("\nKey takeaways:")
    print("1. Conventional metrics miss wrong-entity actions (right tool, wrong target)")
    print("2. EntityBind detects ambiguity and prevents wrong-entity actions")
    print("3. EntityBind doesn't over-clarify on unambiguous inputs")
    print("4. This is a safety-completion tradeoff controlled by tau/delta thresholds")
    print()


if __name__ == "__main__":
    main()
