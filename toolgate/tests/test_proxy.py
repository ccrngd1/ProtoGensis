"""Tests for proxy server (simplified, without live MCP connections)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from toolgate.config import ToolGateConfig, UpstreamServer
from toolgate.proxy import ToolGateProxy


def test_proxy_initialization(sample_config):
    """Test proxy initialization."""
    proxy = ToolGateProxy(sample_config)

    assert proxy.config == sample_config
    assert proxy.index is not None
    assert proxy.gating is not None
    assert proxy.metrics is not None


def test_proxy_has_server():
    """Test that proxy creates MCP server."""
    config = ToolGateConfig(
        upstream_servers=[
            UpstreamServer(name="test", command="test", args=[])
        ]
    )

    proxy = ToolGateProxy(config)

    assert proxy.server is not None
    assert proxy.server.name == "toolgate"


def test_proxy_initializes_components(sample_config):
    """Test that proxy initializes all components."""
    proxy = ToolGateProxy(sample_config)

    # Check components are initialized
    assert proxy.index is not None
    assert proxy.gating is not None
    assert proxy.metrics is not None
    assert proxy.server is not None


def test_proxy_empty_upstream_sessions():
    """Test proxy starts with empty upstream sessions."""
    config = ToolGateConfig(
        upstream_servers=[
            UpstreamServer(name="test", command="test", args=[])
        ]
    )

    proxy = ToolGateProxy(config)

    assert len(proxy.upstream_sessions) == 0


def test_proxy_schema_cache_empty():
    """Test proxy starts with empty schema cache."""
    config = ToolGateConfig(
        upstream_servers=[
            UpstreamServer(name="test", command="test", args=[])
        ]
    )

    proxy = ToolGateProxy(config)

    assert len(proxy.schema_cache) == 0


def test_proxy_last_user_message_none():
    """Test proxy starts with no last user message."""
    config = ToolGateConfig(
        upstream_servers=[
            UpstreamServer(name="test", command="test", args=[])
        ]
    )

    proxy = ToolGateProxy(config)

    assert proxy.last_user_message is None


@pytest.mark.asyncio
async def test_proxy_create_tool_stubs(sample_config, sample_tools):
    """Test creating tool stubs."""
    proxy = ToolGateProxy(sample_config)

    # Build index first
    server_names = ["test"] * len(sample_tools)
    proxy.index.build_index(sample_tools, server_names)

    # Create stubs
    tool_names = ["read_file", "write_file"]
    stubs = await proxy._create_tool_stubs(tool_names)

    assert len(stubs) == 2
    assert stubs[0].name == "read_file"


@pytest.mark.asyncio
async def test_proxy_cleanup_empty():
    """Test cleanup with no sessions."""
    config = ToolGateConfig(
        upstream_servers=[
            UpstreamServer(name="test", command="test", args=[])
        ]
    )

    proxy = ToolGateProxy(config)

    # Should not raise error
    await proxy._cleanup()
