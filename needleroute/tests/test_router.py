"""Tests for NeedleRouter."""

import pytest

from needleroute.config import NeedleRouteConfig, GatingRules
from needleroute.schemas import MCPTool
from needleroute.router import NeedleRouter


@pytest.fixture
def sample_config():
    """Create sample config for testing."""
    return NeedleRouteConfig(
        upstream_servers=[],
        toolgate={"top_k": 5, "session_window": 3},
        needle={"confidence_threshold": 0.7, "model_path": None},
        escalation={"provider": "mock"},
    )


@pytest.fixture
def sample_tools():
    """Create sample tools for testing."""
    return [
        MCPTool(name="read_file", description="Read a file"),
        MCPTool(name="write_file", description="Write to a file"),
        MCPTool(name="delete_file", description="Delete a file"),
        MCPTool(name="web_search", description="Search the web"),
        MCPTool(name="execute_shell", description="Execute shell command"),
    ]


def test_router_initialization(sample_config):
    """Test router initialization."""
    router = NeedleRouter(sample_config)

    assert router.config == sample_config
    assert router.needle is not None
    assert router.escalation is not None
    assert len(router.session_history) == 0


def test_router_pre_encode_tools(sample_config, sample_tools):
    """Test pre-encoding tools."""
    router = NeedleRouter(sample_config)

    router.pre_encode_tools(sample_tools)

    # Should have embeddings for all tools
    assert len(router.tool_embeddings) == len(sample_tools)

    for tool in sample_tools:
        assert tool.name in router.tool_embeddings


def test_router_session_tracking(sample_config):
    """Test session history tracking."""
    router = NeedleRouter(sample_config)

    router.record_tool_call("tool1")
    router.record_tool_call("tool2")
    router.record_tool_call("tool1")

    assert len(router.session_history) == 3
    assert "tool1" in router.session_history
    assert "tool2" in router.session_history


def test_router_session_window_limit(sample_config):
    """Test session window size limit."""
    router = NeedleRouter(sample_config)

    # Add more than window size
    for i in range(10):
        router.record_tool_call(f"tool{i}")

    # Should only keep last 3 (window size)
    assert len(router.session_history) <= sample_config.toolgate.session_window


def test_router_is_destructive_tool(sample_config):
    """Test destructive tool detection."""
    router = NeedleRouter(sample_config)

    # Destructive tools
    assert router._is_destructive_tool("delete_file") is True
    assert router._is_destructive_tool("remove_data") is True
    assert router._is_destructive_tool("write_config") is True
    assert router._is_destructive_tool("create_user") is True

    # Non-destructive tools
    assert router._is_destructive_tool("read_file") is False
    assert router._is_destructive_tool("list_directory") is False
    assert router._is_destructive_tool("search_web") is False


def test_router_matches_pattern(sample_config):
    """Test pattern matching."""
    router = NeedleRouter(sample_config)

    # Exact match
    assert router._matches_pattern("read_file", "read_file") is True

    # Glob patterns
    assert router._matches_pattern("read_file", "read_*") is True
    assert router._matches_pattern("read_file", "*_file") is True
    assert router._matches_pattern("read_file", "*file*") is True

    # No match
    assert router._matches_pattern("read_file", "write_*") is False


def test_router_gating_rules(sample_config, sample_tools):
    """Test gating rule application."""
    router = NeedleRouter(sample_config)

    scores = {
        "read_file": 0.9,
        "write_file": 0.8,
        "delete_file": 0.7,
        "web_search": 0.6,
        "execute_shell": 0.5,
    }

    gating_rules = GatingRules(
        always_include=["web_search"],
        always_exclude=["execute_shell"]
    )

    tool_names = list(scores.keys())
    result = router._apply_gating_rules(scores, tool_names, gating_rules)

    # Should include forced include
    assert "web_search" in result.tools

    # Should exclude forced exclude
    assert "execute_shell" not in result.tools

    # Should track forced includes/excludes
    assert "web_search" in result.forced_include
    assert "execute_shell" in result.forced_exclude


@pytest.mark.asyncio
async def test_router_route_high_confidence(sample_config, sample_tools):
    """Test routing with high confidence (no escalation)."""
    router = NeedleRouter(sample_config)
    router.pre_encode_tools(sample_tools)

    scores = {tool.name: 0.8 for tool in sample_tools}

    decision = await router.route(
        query="Read the config file",
        available_tools=sample_tools,
        similarity_scores=scores,
        destructive_hint=False
    )

    # Should not escalate with high confidence
    # (actual tool selection depends on embeddings, but should get a valid tool)
    assert decision.selected_tool in [t.name for t in sample_tools]


@pytest.mark.asyncio
async def test_router_route_destructive_hint(sample_config, sample_tools):
    """Test routing with destructive hint (always escalates)."""
    router = NeedleRouter(sample_config)
    router.pre_encode_tools(sample_tools)

    scores = {tool.name: 0.9 for tool in sample_tools}

    decision = await router.route(
        query="Delete all files",
        available_tools=sample_tools,
        similarity_scores=scores,
        destructive_hint=True
    )

    # Should escalate due to destructive hint
    assert decision.escalated is True
    assert decision.escalation_reason == "destructive_hint"
    assert decision.destructive_hint is True


@pytest.mark.asyncio
async def test_router_route_no_tools(sample_config):
    """Test routing with no available tools."""
    router = NeedleRouter(sample_config)

    decision = await router.route(
        query="Do something",
        available_tools=[],
        similarity_scores={},
        destructive_hint=False
    )

    # Should escalate with no tools
    assert decision.escalated is True
    assert "no tools" in decision.escalation_reason.lower()


def test_router_get_session_stats(sample_config):
    """Test session statistics."""
    router = NeedleRouter(sample_config)

    router.record_tool_call("read_file")
    router.record_tool_call("write_file")
    router.record_tool_call("read_file")

    stats = router.get_session_stats()

    assert stats["total_calls"] == 3
    assert stats["unique_tools"] == 2
    assert "read_file" in stats["most_common"]
    assert stats["most_common"]["read_file"] == 2
