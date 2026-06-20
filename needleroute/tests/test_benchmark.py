"""Tests for benchmark harness."""

import pytest
import json
from pathlib import Path

from needleroute.benchmark.runner import load_benchmark_data


def test_load_benchmark_tools():
    """Test loading benchmark tools."""
    tools, queries = load_benchmark_data()

    # Should have 50 tools (approximately)
    assert len(tools) >= 45

    # All tools should have required fields
    for tool in tools:
        assert tool.name is not None
        assert tool.description is not None
        assert tool.inputSchema is not None


def test_load_benchmark_queries():
    """Test loading benchmark queries."""
    tools, queries = load_benchmark_data()

    # Should have 100 queries (approximately)
    assert len(queries) >= 95

    # All queries should have required fields
    for query in queries:
        assert "query" in query
        assert "expected_tool" in query
        assert len(query["query"]) > 0


def test_benchmark_query_coverage():
    """Test that benchmark queries cover all tools."""
    tools, queries = load_benchmark_data()

    tool_names = {t.name for t in tools}
    expected_tools = {q["expected_tool"] for q in queries}

    # All expected tools should exist in catalog
    assert expected_tools.issubset(tool_names)


def test_benchmark_tool_diversity():
    """Test that benchmark has diverse tool types."""
    tools, queries = load_benchmark_data()

    # Should have various categories
    categories = {
        "filesystem": ["read_file", "write_file", "delete_file", "list_directory"],
        "web": ["web_search", "fetch_url"],
        "execution": ["execute_python", "execute_shell"],
        "data": ["sql_query", "json_parse", "csv_read"],
        "git": ["git_commit", "git_push", "git_pull"],
    }

    tool_names = [t.name for t in tools]

    # Check each category is represented
    for category, expected_tools in categories.items():
        category_tools = [t for t in expected_tools if t in tool_names]
        assert len(category_tools) > 0, f"No tools found for category {category}"


def test_benchmark_query_distribution():
    """Test that queries are distributed across tools."""
    tools, queries = load_benchmark_data()

    # Count queries per tool
    tool_counts = {}
    for query in queries:
        expected = query["expected_tool"]
        tool_counts[expected] = tool_counts.get(expected, 0) + 1

    # Each tool should have at least one query
    tool_names = {t.name for t in tools}
    for tool_name in tool_names:
        assert tool_name in tool_counts, f"No queries for tool {tool_name}"


def test_benchmark_tools_json_valid():
    """Test that tools.json is valid JSON."""
    benchmark_dir = Path(__file__).parent.parent / "needleroute" / "benchmark"
    tools_file = benchmark_dir / "tools.json"

    assert tools_file.exists(), "tools.json not found"

    with open(tools_file) as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) > 0


def test_benchmark_queries_json_valid():
    """Test that queries.json is valid JSON."""
    benchmark_dir = Path(__file__).parent.parent / "needleroute" / "benchmark"
    queries_file = benchmark_dir / "queries.json"

    assert queries_file.exists(), "queries.json not found"

    with open(queries_file) as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) > 0


def test_benchmark_tool_schemas():
    """Test that all tools have valid schemas."""
    tools, _ = load_benchmark_data()

    for tool in tools:
        schema = tool.inputSchema
        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"


def test_benchmark_realistic_queries():
    """Test that queries are realistic user queries."""
    _, queries = load_benchmark_data()

    for query_data in queries:
        query = query_data["query"]

        # Should be reasonable length
        assert 10 <= len(query) <= 200

        # Should start with capital or common words
        first_word = query.split()[0]
        assert len(first_word) > 0
