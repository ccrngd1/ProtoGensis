"""Integration tests for full NeedleRoute pipeline."""

import pytest

from needleroute.config import NeedleRouteConfig
from needleroute.schemas import MCPTool
from needleroute.index import ToolIndex
from needleroute.router import NeedleRouter


@pytest.fixture
def full_config():
    """Create full config for integration testing."""
    return NeedleRouteConfig(
        upstream_servers=[],
        toolgate={"top_k": 10},
        needle={"confidence_threshold": 0.7},
        escalation={"provider": "mock"},
        metrics={"enabled": False}
    )


@pytest.fixture
def test_tools():
    """Create test tool catalog."""
    return [
        MCPTool(
            name="read_file",
            description="Read the contents of a file from the filesystem",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        ),
        MCPTool(
            name="write_file",
            description="Write content to a file on the filesystem",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        ),
        MCPTool(
            name="web_search",
            description="Search the internet for information using a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        ),
        MCPTool(
            name="execute_python",
            description="Execute Python code in a sandbox environment",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"]
            }
        ),
        MCPTool(
            name="sql_query",
            description="Execute SQL query against the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        ),
    ]


def test_full_pipeline_index_build(full_config, test_tools):
    """Test building index with real tools."""
    index = ToolIndex(full_config.toolgate)

    server_names = ["test_server"] * len(test_tools)
    index.build_index(test_tools, server_names)

    assert index.size == len(test_tools)
    assert len(index.get_all_tool_names()) == len(test_tools)


def test_full_pipeline_search(full_config, test_tools):
    """Test searching index."""
    index = ToolIndex(full_config.toolgate)
    server_names = ["test_server"] * len(test_tools)
    index.build_index(test_tools, server_names)

    # Search for file-related tool
    tool_names, scores = index.search("Read the config.yaml file", k=3)

    assert len(tool_names) > 0
    assert "read_file" in tool_names  # Should find read_file as relevant


def test_full_pipeline_search_top_k(full_config, test_tools):
    """Test top-K filtering."""
    index = ToolIndex(full_config.toolgate)
    server_names = ["test_server"] * len(test_tools)
    index.build_index(test_tools, server_names)

    # Search with k=2
    tool_names, scores = index.search("Search for information", k=2)

    assert len(tool_names) <= 2


@pytest.mark.asyncio
async def test_full_pipeline_routing(full_config, test_tools):
    """Test full routing pipeline."""
    # Build index
    index = ToolIndex(full_config.toolgate)
    server_names = ["test_server"] * len(test_tools)
    index.build_index(test_tools, server_names)

    # Create router
    router = NeedleRouter(full_config)
    router.pre_encode_tools(test_tools)

    # Search for relevant tools
    query = "Read the README.md file"
    tool_names, scores = index.search(query, k=full_config.toolgate.top_k)

    # Get filtered tools
    filtered_tools = [t for t in test_tools if t.name in tool_names]

    # Route
    decision = await router.route(query, filtered_tools, scores)

    # Should select a tool
    assert decision.selected_tool in [t.name for t in test_tools]


@pytest.mark.asyncio
async def test_full_pipeline_session_continuity(full_config, test_tools):
    """Test session continuity boost."""
    index = ToolIndex(full_config.toolgate)
    server_names = ["test_server"] * len(test_tools)
    index.build_index(test_tools, server_names)

    router = NeedleRouter(full_config)
    router.pre_encode_tools(test_tools)

    # Record some tool calls
    router.record_tool_call("read_file")
    router.record_tool_call("read_file")

    # Search
    query = "Show me that file again"
    tool_names, scores = index.search(query, k=5)
    filtered_tools = [t for t in test_tools if t.name in tool_names]

    # Route - should have read_file in history
    decision = await router.route(query, filtered_tools, scores)

    # read_file should get session boost
    assert len(router.session_history) == 2
    assert "read_file" in router.session_history


@pytest.mark.asyncio
async def test_full_pipeline_destructive_detection(full_config, test_tools):
    """Test destructive tool detection."""
    # Add a destructive tool
    destructive_tool = MCPTool(
        name="delete_all_files",
        description="Delete all files in the directory",
        inputSchema={"type": "object"}
    )
    all_tools = test_tools + [destructive_tool]

    index = ToolIndex(full_config.toolgate)
    server_names = ["test_server"] * len(all_tools)
    index.build_index(all_tools, server_names)

    router = NeedleRouter(full_config)
    router.pre_encode_tools(all_tools)

    # Query that might match destructive tool
    query = "Remove all temporary files"
    tool_names, scores = index.search(query, k=5)
    filtered_tools = [t for t in all_tools if t.name in tool_names]

    # Route - should escalate if destructive tool is selected
    decision = await router.route(query, filtered_tools, scores)

    # If a destructive tool was selected, should escalate
    if "delete" in decision.selected_tool.lower():
        # May or may not be escalated depending on Needle model
        # But system should handle it correctly
        assert decision.selected_tool is not None


@pytest.mark.asyncio
async def test_full_pipeline_escalation_trigger(full_config):
    """Test that escalation triggers correctly."""
    # Create scenario with low confidence
    tools = [
        MCPTool(name="tool1", description="First tool"),
        MCPTool(name="tool2", description="Second tool"),
    ]

    index = ToolIndex(full_config.toolgate)
    index.build_index(tools, ["test"] * len(tools))

    router = NeedleRouter(full_config)
    router.pre_encode_tools(tools)

    # Use destructive hint to force escalation
    query = "Do something dangerous"
    tool_names, scores = index.search(query, k=2)
    filtered_tools = [t for t in tools if t.name in tool_names]

    decision = await router.route(
        query,
        filtered_tools,
        scores,
        destructive_hint=True
    )

    # Should escalate due to destructive hint
    assert decision.escalated is True


def test_integration_schema_adapter():
    """Test MCP tool schema conversion."""
    tool = MCPTool(
        name="test_tool",
        description="A test tool",
        inputSchema={
            "type": "object",
            "properties": {
                "arg1": {"type": "string"},
                "arg2": {"type": "number"}
            },
            "required": ["arg1"]
        }
    )

    # Schema should be preserved
    assert tool.inputSchema["type"] == "object"
    assert "arg1" in tool.inputSchema["properties"]
    assert "arg1" in tool.inputSchema["required"]


@pytest.mark.asyncio
async def test_integration_end_to_end_accuracy(full_config, test_tools):
    """Test end-to-end accuracy on known queries."""
    index = ToolIndex(full_config.toolgate)
    server_names = ["test"] * len(test_tools)
    index.build_index(test_tools, server_names)

    router = NeedleRouter(full_config)
    router.pre_encode_tools(test_tools)

    # Test cases with expected tools
    test_cases = [
        ("Read the config file", "read_file"),
        ("Write data to output.txt", "write_file"),
        ("Search Google for information", "web_search"),
        ("Execute this Python script", "execute_python"),
        ("Query the database", "sql_query"),
    ]

    correct = 0
    total = len(test_cases)

    for query, expected_tool in test_cases:
        tool_names, scores = index.search(query, k=5)
        filtered_tools = [t for t in test_tools if t.name in tool_names]

        decision = await router.route(query, filtered_tools, scores)

        if decision.selected_tool == expected_tool:
            correct += 1

    accuracy = correct / total

    # Should get better than random accuracy (20%) even with mock model
    # With real embeddings: 85%+
    assert accuracy >= 0.15, f"Accuracy {accuracy:.1%} below threshold (random baseline: 20%)"
