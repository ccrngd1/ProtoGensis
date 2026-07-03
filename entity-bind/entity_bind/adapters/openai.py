"""
OpenAI Function-Calling Adapter

Intercepts OpenAI tool_calls before dispatch and applies EntityBind gating.

Usage pattern:
1. Call OpenAI API as normal, get response with tool_calls
2. For each tool_call, run entity_bind.gate()
3. If ACT: dispatch with rewritten args
4. If CLARIFY/DEFER: return clarification as tool_result

This works with any OpenAI-compatible endpoint (LiteLLM, Bedrock-via-proxy, local).
"""

import json
from typing import Any, Callable, Dict, List, Optional, Union

from entity_bind.catalog.base import Catalog
from entity_bind.catalog.schema import ToolSpec
from entity_bind.core.gate import EntityGate, GateDecision, GateResult
from entity_bind.core.resolver import EntityResolver
from entity_bind.provenance.store import ProvenanceStore


class OpenAIEntityBind:
    """
    OpenAI adapter for EntityBind.

    Wraps the manual tool dispatch loop with entity binding gate.
    """

    def __init__(
        self,
        catalog: Catalog,
        tool_specs: Dict[str, ToolSpec],
        resolver: Optional[EntityResolver] = None,
        provenance_store: Optional[ProvenanceStore] = None
    ):
        """
        Initialize OpenAI adapter.

        Args:
            catalog: Entity catalog
            tool_specs: {tool_name: ToolSpec} mapping
            resolver: Entity resolver (created if not provided)
            provenance_store: Provenance store for logging (optional)
        """
        self.catalog = catalog
        self.tool_specs = tool_specs
        self.gate = EntityGate(catalog, resolver)
        self.provenance_store = provenance_store

    def intercept_tool_calls(
        self,
        tool_calls: List[Any],
        tools: Dict[str, Callable],
        context: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Intercept and process OpenAI tool_calls with entity binding.

        Args:
            tool_calls: List of tool_call objects from OpenAI response
            tools: {tool_name: callable} mapping of actual tool functions
            context: Optional context for resolution

        Returns:
            List of tool results to feed back to the model
        """
        results = []

        for tool_call in tool_calls:
            result = self.process_tool_call(tool_call, tools, context)
            results.append(result)

        return results

    def process_tool_call(
        self,
        tool_call: Any,
        tools: Dict[str, Callable],
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process a single tool_call through the entity binding gate.

        Args:
            tool_call: Single tool_call object from OpenAI response
            tools: {tool_name: callable} mapping
            context: Optional context

        Returns:
            Tool result dict with tool_call_id, role, content
        """
        tool_name = tool_call.function.name

        # Parse tool arguments with error handling
        try:
            tool_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            return self._format_error(tool_call.id, f"Invalid JSON in arguments: {e}")

        # Check if tool has entity preconditions
        if tool_name not in self.tool_specs:
            # No preconditions - execute directly
            if tool_name in tools:
                try:
                    output = tools[tool_name](**tool_args)
                    return self._format_result(tool_call.id, output)
                except Exception as e:
                    return self._format_error(tool_call.id, str(e))
            else:
                return self._format_error(tool_call.id, f"Tool '{tool_name}' not found")

        # Run entity binding gate
        tool_spec = self.tool_specs[tool_name]
        gate_result = self.gate.gate(tool_name, tool_args, tool_spec, context)

        # Log provenance
        if self.provenance_store:
            self.provenance_store.record(gate_result)

        # Handle decision
        if gate_result.decision == GateDecision.ACT:
            # Execute with rewritten args
            if tool_name in tools:
                try:
                    output = tools[tool_name](**gate_result.bound_args)
                    return self._format_result(tool_call.id, output)
                except Exception as e:
                    return self._format_error(tool_call.id, str(e))
            else:
                return self._format_error(tool_call.id, f"Tool '{tool_name}' not found")

        else:
            # CLARIFY or DEFER - return clarification as tool result
            # The model will see this and can either ask the user or try again
            return self._format_clarification(tool_call.id, gate_result.clarification)

    def _format_result(self, tool_call_id: str, output: Any) -> Dict[str, Any]:
        """Format successful tool result."""
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": str(output)
        }

    def _format_error(self, tool_call_id: str, error: str) -> Dict[str, Any]:
        """Format error result."""
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": f"Error: {error}"
        }

    def _format_clarification(self, tool_call_id: str, clarification: str) -> Dict[str, Any]:
        """
        Format clarification as tool result.

        The model will receive this as the tool's response and can
        either ask the user for clarification or try to resolve it.
        """
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": f"[EntityBind] {clarification}"
        }


# ============================================================================
# Convenience Wrapper
# ============================================================================


class EntityBoundToolRegistry:
    """
    Registry pattern for entity-bound tools.

    Simplifies the common pattern: define tools → define specs → intercept calls.
    """

    def __init__(
        self,
        catalog: Catalog,
        resolver: Optional[EntityResolver] = None,
        provenance_store: Optional[ProvenanceStore] = None
    ):
        """
        Initialize tool registry.

        Args:
            catalog: Entity catalog
            resolver: Entity resolver (created if not provided)
            provenance_store: Provenance store for logging (optional)
        """
        self.catalog = catalog
        self.resolver = resolver
        self.provenance_store = provenance_store

        self.tools: Dict[str, Callable] = {}
        self.tool_specs: Dict[str, ToolSpec] = {}

    def register(
        self,
        func: Callable,
        spec: ToolSpec,
        name: Optional[str] = None
    ) -> None:
        """
        Register a tool with its entity spec.

        Args:
            func: Tool function
            spec: ToolSpec with preconditions
            name: Tool name (defaults to func.__name__)
        """
        tool_name = name or func.__name__
        self.tools[tool_name] = func
        self.tool_specs[tool_name] = spec

    def call(
        self,
        tool_calls: List[Any],
        context: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute tool_calls with entity binding.

        Args:
            tool_calls: List of tool_call objects from OpenAI response
            context: Optional context

        Returns:
            List of tool results
        """
        adapter = OpenAIEntityBind(
            catalog=self.catalog,
            tool_specs=self.tool_specs,
            resolver=self.resolver,
            provenance_store=self.provenance_store
        )
        return adapter.intercept_tool_calls(tool_calls, self.tools, context)

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        Generate OpenAI tools schema from registered tools.

        Returns tools in the format expected by OpenAI API.
        """
        tools_schema = []

        for name, spec in self.tool_specs.items():
            # Build parameters from preconditions
            properties = {}
            required = []

            for precond in spec.preconditions:
                properties[precond.slot] = {
                    "type": "string",
                    "description": f"{precond.entity_type} entity (name or ID)"
                }
                if precond.required:
                    required.append(precond.slot)

            tools_schema.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec.description or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })

        return tools_schema


# ============================================================================
# Example Usage
# ============================================================================


def example_openai_integration():
    """
    Example: Full OpenAI integration with EntityBind.

    Shows the complete pattern from tool definition to execution.
    """
    from entity_bind.catalog import StaticCatalog, Entity, Precondition, RiskLevel

    # 1. Define entity catalog
    catalog = StaticCatalog(entities=[
        Entity(
            id="person_alex_chen",
            type="person",
            name="Alex Chen",
            email="alex.chen@company.com",
            metadata="Launch team engineer"
        ),
        Entity(
            id="person_alex_kumar",
            type="person",
            name="Alex Kumar",
            email="alex.kumar@company.com",
            metadata="Customer success manager"
        ),
    ])

    # 2. Define tools
    def send_email(recipient: str, message: str) -> str:
        """Send an email (mock)."""
        return f"Email sent to {recipient}: {message}"

    # 3. Create tool spec
    send_email_spec = ToolSpec(
        name="send_email",
        description="Send an email to a recipient",
        preconditions=[
            Precondition(slot="recipient", entity_type="person", required=True)
        ],
        risk=RiskLevel.HIGH
    )

    # 4. Create registry and register tool
    registry = EntityBoundToolRegistry(catalog)
    registry.register(send_email, send_email_spec)

    # 5. Simulate OpenAI response with tool_calls
    # In real usage, this comes from: response = client.chat.completions.create(...)
    class MockToolCall:
        def __init__(self, id, name, args):
            self.id = id
            self.function = type('obj', (object,), {
                'name': name,
                'arguments': json.dumps(args)
            })

    tool_calls = [
        MockToolCall(
            id="call_1",
            name="send_email",
            args={"recipient": "Alex", "message": "Launch update"}
        )
    ]

    # 6. Process tool_calls with entity binding
    results = registry.call(tool_calls)

    # 7. Results contain either execution output or clarification
    for result in results:
        print(result['content'])
        # Expected output (if ambiguous):
        # "[EntityBind] Multiple entities match 'Alex'. Do you mean Alex Chen
        #  (alex.chen@company.com) or Alex Kumar (alex.kumar@company.com)?"
        #
        # Or (if clear):
        # "Email sent to person_alex_chen: Launch update"


if __name__ == "__main__":
    example_openai_integration()
