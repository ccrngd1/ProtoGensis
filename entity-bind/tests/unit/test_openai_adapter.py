"""Unit tests for OpenAI adapter."""

import pytest
from unittest.mock import Mock, MagicMock
from entity_bind.catalog import StaticCatalog, Entity, ToolSpec, Precondition, RiskLevel
from entity_bind.adapters.openai import OpenAIEntityBind


@pytest.fixture
def sample_catalog():
    """Create a sample catalog."""
    return StaticCatalog(entities=[
        Entity(
            id="person_alice",
            type="person",
            name="Alice Johnson",
            email="alice@company.com",
            metadata="Engineering team lead"
        ),
        Entity(
            id="person_bob",
            type="person",
            name="Bob Smith",
            email="bob@company.com",
            metadata="Product manager"
        ),
        Entity(
            id="person_alex_1",
            type="person",
            name="Alex Chen",
            email="alex.chen@company.com",
            metadata="Backend engineer"
        ),
        Entity(
            id="person_alex_2",
            type="person",
            name="Alex Kumar",
            email="alex.kumar@company.com",
            metadata="Frontend engineer"
        )
    ])


@pytest.fixture
def tool_specs():
    """Create sample tool specifications."""
    return {
        "send_email": ToolSpec(
            name="send_email",
            description="Send an email",
            preconditions=[
                Precondition(slot="recipient", entity_type="person", required=True)
            ],
            risk=RiskLevel.HIGH
        ),
        "get_weather": ToolSpec(
            name="get_weather",
            description="Get weather",
            preconditions=[],
            risk=RiskLevel.LOW
        )
    }


def test_gate_tool_call_act(sample_catalog, tool_specs):
    """Test gating a tool call that should ACT."""
    adapter = OpenAIEntityBind(
        catalog=sample_catalog,
        tool_specs=tool_specs
    )

    # Mock tool call
    tool_call = Mock()
    tool_call.id = "call_123"
    tool_call.function.name = "send_email"
    tool_call.function.arguments = '{"recipient": "Alice", "message": "Hello"}'

    def mock_send_email(recipient, message):
        return f"Email sent to {recipient}"

    tools = {"send_email": mock_send_email}

    result = adapter.process_tool_call(tool_call, tools)

    # Should execute successfully with rewritten args
    assert result["role"] == "tool"
    assert "person_alice" in result["content"] or "Email sent" in result["content"]


def test_gate_tool_call_clarify(sample_catalog, tool_specs):
    """Test gating a tool call that should CLARIFY."""
    adapter = OpenAIEntityBind(
        catalog=sample_catalog,
        tool_specs=tool_specs
    )

    # Mock tool call with ambiguous reference
    tool_call = Mock()
    tool_call.id = "call_456"
    tool_call.function.name = "send_email"
    tool_call.function.arguments = '{"recipient": "Alex", "message": "Hello"}'

    tools = {}

    result = adapter.process_tool_call(tool_call, tools)

    # Should clarify
    assert result["role"] == "tool"
    assert "CLARIFICATION" in result["content"] or "clarify" in result["content"].lower()
    # Should mention Alex
    assert "Alex" in result["content"]


def test_gate_tool_call_no_preconditions(sample_catalog, tool_specs):
    """Test gating a tool call with no entity preconditions."""
    adapter = OpenAIEntityBind(
        catalog=sample_catalog,
        tool_specs=tool_specs
    )

    # Tool with no entity preconditions
    tool_call = Mock()
    tool_call.id = "call_789"
    tool_call.function.name = "get_weather"
    tool_call.function.arguments = '{"location": "San Francisco"}'

    def mock_get_weather(location):
        return f"Weather for {location}"

    tools = {"get_weather": mock_get_weather}

    result = adapter.process_tool_call(tool_call, tools)

    # Should execute immediately (no entity preconditions)
    assert result["role"] == "tool"
    assert "San Francisco" in result["content"]


def test_format_clarification_as_tool_result():
    """Test formatting a clarification as OpenAI tool result."""
    adapter = OpenAIEntityBind(
        catalog=StaticCatalog(entities=[]),
        tool_specs={}
    )

    tool_call_id = "call_123"
    clarification = "Which Alex do you mean: Alex Chen or Alex Kumar?"

    # This is tested via the process_tool_call method
    # Just verify adapter initializes correctly
    assert adapter.catalog is not None
    assert adapter.tool_specs is not None


def test_execute_tool_call():
    """Test executing a tool call with real tool function."""
    def mock_send_email(recipient, message):
        return f"Email sent to {recipient}: {message}"

    tools = {
        "send_email": mock_send_email
    }

    adapter = OpenAIEntityBind(
        catalog=StaticCatalog(entities=[]),
        tool_specs={}
    )

    tool_call = Mock()
    tool_call.id = "call_999"
    tool_call.function.name = "send_email"
    tool_call.function.arguments = '{"recipient": "alice@test.com", "message": "Hi"}'

    result = adapter.process_tool_call(tool_call, tools)

    assert result["tool_call_id"] == "call_999"
    assert result["role"] == "tool"
    assert "alice@test.com" in result["content"]


def test_process_tool_calls_mixed():
    """Test processing a mix of tool calls (ACT + CLARIFY)."""
    catalog = StaticCatalog(entities=[
        Entity(id="person_alice", type="person", name="Alice"),
        Entity(id="person_alex_1", type="person", name="Alex Chen"),
        Entity(id="person_alex_2", type="person", name="Alex Kumar")
    ])

    tool_specs = {
        "send_email": ToolSpec(
            name="send_email",
            description="Send email",
            preconditions=[
                Precondition(slot="recipient", entity_type="person", required=True)
            ],
            risk=RiskLevel.HIGH
        )
    }

    def mock_send_email(recipient, message):
        return f"Sent to {recipient}"

    tools = {"send_email": mock_send_email}

    adapter = OpenAIEntityBind(
        catalog=catalog,
        tool_specs=tool_specs
    )

    # Two tool calls: one clear, one ambiguous
    tool_call_1 = Mock()
    tool_call_1.id = "call_1"
    tool_call_1.function.name = "send_email"
    tool_call_1.function.arguments = '{"recipient": "Alice", "message": "Hi"}'

    tool_call_2 = Mock()
    tool_call_2.id = "call_2"
    tool_call_2.function.name = "send_email"
    tool_call_2.function.arguments = '{"recipient": "Alex", "message": "Hi"}'

    tool_calls = [tool_call_1, tool_call_2]
    results = adapter.intercept_tool_calls(tool_calls, tools)

    assert len(results) == 2

    # First should execute
    assert results[0]["role"] == "tool"

    # Second should clarify
    assert results[1]["role"] == "tool"


def test_invalid_json_arguments():
    """Test handling invalid JSON in tool arguments."""
    adapter = OpenAIEntityBind(
        catalog=StaticCatalog(entities=[]),
        tool_specs={}
    )

    tool_call = Mock()
    tool_call.id = "call_bad"
    tool_call.function.name = "send_email"
    tool_call.function.arguments = 'invalid json {{'

    tools = {}
    result = adapter.process_tool_call(tool_call, tools)

    assert result["role"] == "tool"
    assert "error" in result["content"].lower()


def test_missing_tool_function():
    """Test handling missing tool function."""
    adapter = OpenAIEntityBind(
        catalog=StaticCatalog(entities=[]),
        tool_specs={}
    )

    tool_call = Mock()
    tool_call.id = "call_missing"
    tool_call.function.name = "nonexistent_tool"
    tool_call.function.arguments = '{}'

    tools = {}
    result = adapter.process_tool_call(tool_call, tools)

    assert result["role"] == "tool"
    assert "not found" in result["content"].lower() or "nonexistent" in result["content"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
