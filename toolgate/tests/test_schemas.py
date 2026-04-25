"""Tests for Pydantic schemas."""

import pytest
from toolgate.schemas import (
    ToolInputSchema, MCPTool, ToolStub, IndexedTool,
    GatingResult, MetricsRecord
)


def test_tool_input_schema():
    """Test ToolInputSchema creation."""
    schema = ToolInputSchema(
        type="object",
        properties={"name": {"type": "string"}},
        required=["name"]
    )

    assert schema.type == "object"
    assert "name" in schema.properties
    assert schema.required == ["name"]


def test_mcp_tool():
    """Test MCPTool creation."""
    tool = MCPTool(
        name="test_tool",
        description="A test tool",
        inputSchema=ToolInputSchema(type="object")
    )

    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.inputSchema.type == "object"


def test_tool_stub_from_tool():
    """Test creating ToolStub from MCPTool."""
    tool = MCPTool(
        name="test_tool",
        description="Short description"
    )

    stub = ToolStub.from_tool(tool)

    assert stub.name == "test_tool"
    assert stub.description == "Short description"


def test_tool_stub_truncation():
    """Test description truncation in ToolStub."""
    long_desc = "A" * 300
    tool = MCPTool(
        name="test_tool",
        description=long_desc
    )

    stub = ToolStub.from_tool(tool, max_desc_len=200)

    assert stub.name == "test_tool"
    assert len(stub.description) == 203  # 200 + "..."
    assert stub.description.endswith("...")


def test_indexed_tool():
    """Test IndexedTool creation."""
    tool = MCPTool(name="test", description="Test tool")
    embedding = [0.1, 0.2, 0.3]

    indexed = IndexedTool(
        name="test",
        description="Test tool",
        embedding=embedding,
        server_name="test_server",
        full_tool=tool
    )

    assert indexed.name == "test"
    assert indexed.embedding == embedding
    assert indexed.server_name == "test_server"
    assert indexed.full_tool == tool


def test_gating_result():
    """Test GatingResult creation."""
    result = GatingResult(
        tools=["tool1", "tool2"],
        scores={"tool1": 0.9, "tool2": 0.8},
        boosted=["tool1"],
        forced_include=["tool2"],
        forced_exclude=["tool3"]
    )

    assert len(result.tools) == 2
    assert result.scores["tool1"] == 0.9
    assert "tool1" in result.boosted
    assert "tool2" in result.forced_include


def test_metrics_record():
    """Test MetricsRecord creation."""
    record = MetricsRecord(
        timestamp=1234567890.0,
        event_type="list_tools",
        tools_returned=5,
        tokens_saved=1000,
        latency_ms=50.5
    )

    assert record.timestamp == 1234567890.0
    assert record.event_type == "list_tools"
    assert record.tools_returned == 5
    assert record.tokens_saved == 1000
    assert record.latency_ms == 50.5
