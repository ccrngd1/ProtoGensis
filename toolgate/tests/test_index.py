"""Tests for tool indexing."""

import pytest
import numpy as np

from toolgate.config import IndexConfig
from toolgate.index import ToolIndex
from toolgate.schemas import MCPTool


def test_index_initialization():
    """Test ToolIndex initialization."""
    config = IndexConfig()
    index = ToolIndex(config)

    assert index.config == config
    assert index.model is None
    assert index.index is None
    assert len(index.tools) == 0


def test_build_index_basic(sample_tools):
    """Test building a basic index."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    assert index.size == len(sample_tools)
    assert index.index is not None
    assert len(index.tools) == len(sample_tools)


def test_build_index_cosine_similarity(sample_tools):
    """Test building index with cosine similarity."""
    config = IndexConfig(similarity_metric="cosine")
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    assert index.size == len(sample_tools)


def test_build_index_euclidean(sample_tools):
    """Test building index with euclidean distance."""
    config = IndexConfig(similarity_metric="euclidean")
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    assert index.size == len(sample_tools)


def test_build_index_empty_tools():
    """Test that building index with empty tools raises error."""
    config = IndexConfig()
    index = ToolIndex(config)

    with pytest.raises(ValueError):
        index.build_index([], [])


def test_build_index_mismatched_lengths(sample_tools):
    """Test error on mismatched tools and server_names."""
    config = IndexConfig()
    index = ToolIndex(config)

    with pytest.raises(ValueError):
        index.build_index(sample_tools, ["server1"])  # Wrong length


def test_search_basic(sample_tools):
    """Test basic search functionality."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    # Search for file operations
    tool_names, scores = index.search("read a file", k=3)

    assert len(tool_names) <= 3
    assert len(scores) == len(tool_names)
    assert "read_file" in tool_names


def test_search_git_tools(sample_tools):
    """Test searching for git-related tools."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    tool_names, scores = index.search("git status and commits", k=5)

    assert "git_status" in tool_names or "git_commit" in tool_names


def test_search_no_index():
    """Test search with no index built."""
    config = IndexConfig()
    index = ToolIndex(config)

    tool_names, scores = index.search("test query", k=5)

    assert tool_names == []
    assert scores == {}


def test_search_k_exceeds_tools(sample_tools):
    """Test search when k exceeds number of tools."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    tool_names, scores = index.search("test", k=100)

    # Should return all tools, not more
    assert len(tool_names) <= len(sample_tools)


def test_get_tool(sample_tools):
    """Test getting tool by name."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    tool = index.get_tool("read_file")

    assert tool is not None
    assert tool.name == "read_file"


def test_get_tool_not_found(sample_tools):
    """Test getting non-existent tool."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    tool = index.get_tool("nonexistent")

    assert tool is None


def test_get_all_tool_names(sample_tools):
    """Test getting all tool names."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    names = index.get_all_tool_names()

    assert len(names) == len(sample_tools)
    assert "read_file" in names


def test_get_all_tools(sample_tools):
    """Test getting all tools."""
    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["test"] * len(sample_tools)
    index.build_index(sample_tools, server_names)

    tools = index.get_all_tools()

    assert len(tools) == len(sample_tools)
    assert all(isinstance(tool, MCPTool) for tool in tools)
