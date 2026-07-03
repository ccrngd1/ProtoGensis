"""
Entity-Aware Action Gate

Implements Algorithm 1 from the paper (complete):
1. Select tool and extract entity mentions from args
2. Check preconditions P_E(t)
3. Resolve mentions (retrieve candidates → score → gate)
4. Action gate: execute OR clarify/defer
5. Log provenance

This is the main entry point for middleware.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from entity_bind.catalog.base import Catalog
from entity_bind.catalog.schema import RiskLevel, ToolSpec
from entity_bind.core.resolver import BindingResult, EntityResolver


class GateDecision(str, Enum):
    """Action gate decision."""

    ACT = "act"  # Execute tool with resolved bindings
    CLARIFY = "clarify"  # Ask user to disambiguate
    DEFER = "defer"  # Cannot resolve - defer to user/human


@dataclass
class GateResult:
    """
    Result of the action gate.

    Contains everything needed to either execute the tool (with rewritten
    args) or return a clarification to the user.
    """

    # Decision
    decision: GateDecision
    tool_name: str

    # Rewritten args (if ACT)
    bound_args: Optional[Dict[str, Any]] = None

    # Clarification (if CLARIFY/DEFER)
    clarification: Optional[str] = None

    # Binding provenance (for all slots)
    bindings: Optional[Dict[str, BindingResult]] = None

    # Metadata
    risk: RiskLevel = RiskLevel.MEDIUM
    all_resolved: bool = False
    unresolved_slots: List[str] = None

    def __post_init__(self):
        if self.unresolved_slots is None:
            self.unresolved_slots = []


class EntityGate:
    """
    Entity-aware action gate.

    Intercepts tool calls, resolves entity references, and makes the
    ACT/CLARIFY/DEFER decision based on confidence + margin thresholds.
    """

    def __init__(
        self,
        catalog: Catalog,
        resolver: Optional[EntityResolver] = None
    ):
        """
        Initialize gate.

        Args:
            catalog: Entity catalog
            resolver: Entity resolver (created if not provided)
        """
        self.catalog = catalog
        self.resolver = resolver or EntityResolver(catalog)

    def gate(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_spec: ToolSpec,
        context: Optional[Dict] = None
    ) -> GateResult:
        """
        Main gate function (Algorithm 1).

        Args:
            tool_name: Name of the tool being called
            tool_args: Tool arguments (may contain natural-language entity references)
            tool_spec: Tool specification with preconditions
            context: Optional context (user, session, etc.)

        Returns:
            GateResult with decision and rewritten args or clarification
        """
        context = context or {}

        # 1. Extract entity mentions from args based on preconditions
        mentions = self._extract_mentions(tool_args, tool_spec)

        if not mentions:
            # No entity preconditions - execute directly
            return GateResult(
                decision=GateDecision.ACT,
                tool_name=tool_name,
                bound_args=tool_args,
                bindings={},
                all_resolved=True
            )

        # 2. Build expected types mapping
        expected_types = {
            slot: precond.entity_type
            for precond in tool_spec.preconditions
            for slot, _ in mentions.items()
            if precond.slot == slot
        }

        # 3. Resolve all mentions
        binding_results = self.resolver.resolve_many(
            mentions,
            expected_types=expected_types,
            risk=tool_spec.risk,
            context=context
        )

        # 4. Check if all required slots resolved
        all_resolved = self.resolver.all_resolved(binding_results)
        unresolved_slots = [
            slot for slot, result in binding_results.items()
            if not result.resolved
        ]

        # 5. Action gate decision
        if all_resolved:
            # All slots resolved → ACT
            bound_args = self._rewrite_args(tool_args, binding_results)
            return GateResult(
                decision=GateDecision.ACT,
                tool_name=tool_name,
                bound_args=bound_args,
                bindings=binding_results,
                risk=tool_spec.risk,
                all_resolved=True
            )
        else:
            # Some slots unresolved → CLARIFY or DEFER
            clarification = self._generate_multi_slot_clarification(
                binding_results,
                unresolved_slots
            )

            # CLARIFY if we have candidate suggestions, DEFER if truly stuck
            decision = GateDecision.CLARIFY
            if all(not r.candidates for r in binding_results.values() if not r.resolved):
                decision = GateDecision.DEFER

            return GateResult(
                decision=decision,
                tool_name=tool_name,
                clarification=clarification,
                bindings=binding_results,
                risk=tool_spec.risk,
                all_resolved=False,
                unresolved_slots=unresolved_slots
            )

    def _extract_mentions(
        self,
        tool_args: Dict[str, Any],
        tool_spec: ToolSpec
    ) -> Dict[str, str]:
        """
        Extract entity mentions from tool args based on preconditions.

        Args:
            tool_args: Tool arguments
            tool_spec: Tool specification with preconditions

        Returns:
            {slot: mention} mapping
        """
        mentions = {}

        for precond in tool_spec.preconditions:
            slot = precond.slot
            if slot in tool_args:
                value = tool_args[slot]
                # Only extract string mentions (entity references)
                # Skip if already resolved to an ID (e.g., "person_priya")
                if isinstance(value, str) and not value.startswith(precond.entity_type + "_"):
                    mentions[slot] = value

        return mentions

    def _rewrite_args(
        self,
        tool_args: Dict[str, Any],
        binding_results: Dict[str, BindingResult]
    ) -> Dict[str, Any]:
        """
        Rewrite tool args with resolved canonical entity IDs.

        Args:
            tool_args: Original tool arguments
            binding_results: Binding results for each slot

        Returns:
            Rewritten args with canonical entity IDs
        """
        bound_args = tool_args.copy()

        for slot, result in binding_results.items():
            if result.resolved and result.entity:
                bound_args[slot] = result.entity.id

        return bound_args

    def _generate_multi_slot_clarification(
        self,
        binding_results: Dict[str, BindingResult],
        unresolved_slots: List[str]
    ) -> str:
        """
        Generate clarification for multiple unresolved slots.

        Handles both single-slot and multi-slot clarifications.
        """
        if len(unresolved_slots) == 1:
            # Single slot unresolved - use its clarification
            slot = unresolved_slots[0]
            return binding_results[slot].clarification or f"Could not resolve '{binding_results[slot].mention}'."

        # Multiple slots unresolved - combine clarifications
        clarifications = []
        for slot in unresolved_slots:
            result = binding_results[slot]
            clarifications.append(f"- {slot}: {result.clarification or 'unresolved'}")

        return "Multiple entities need clarification:\n" + "\n".join(clarifications)


# ============================================================================
# Convenience Functions
# ============================================================================


def gate(
    tool_name: str,
    tool_args: Dict[str, Any],
    catalog: Catalog,
    tool_spec: ToolSpec,
    resolver: Optional[EntityResolver] = None,
    context: Optional[Dict] = None
) -> GateResult:
    """
    Standalone gate function (convenience wrapper).

    This is the main public API for using EntityBind as a library.

    Args:
        tool_name: Name of the tool being called
        tool_args: Tool arguments
        catalog: Entity catalog
        tool_spec: Tool specification with preconditions
        resolver: Entity resolver (created if not provided)
        context: Optional context

    Returns:
        GateResult with decision and rewritten args or clarification

    Example:
        ```python
        from entity_bind import gate, StaticCatalog, ToolSpec, RiskLevel

        catalog = StaticCatalog(entities=[
            {"id": "person_alex_chen", "type": "person", "name": "Alex Chen", ...},
            {"id": "person_alex_kumar", "type": "person", "name": "Alex Kumar", ...}
        ])

        tool_spec = ToolSpec(
            name="send_email",
            preconditions=[Precondition(slot="recipient", entity_type="person", required=True)],
            risk=RiskLevel.HIGH
        )

        result = gate(
            tool_name="send_email",
            tool_args={"recipient": "Alex", "message": "Launch update"},
            catalog=catalog,
            tool_spec=tool_spec
        )

        if result.decision == "act":
            # Execute with rewritten args
            send_email(**result.bound_args)
        else:
            # Return clarification to user
            print(result.clarification)
        ```
    """
    entity_gate = EntityGate(catalog, resolver)
    return entity_gate.gate(tool_name, tool_args, tool_spec, context)
