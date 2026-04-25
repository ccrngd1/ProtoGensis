"""Tests for benchmark suite."""

import pytest
import json
import sys
from pathlib import Path

from toolgate.config import IndexConfig, GatingConfig
from toolgate.index import ToolIndex
from toolgate.gating import GatingEngine
from toolgate.schemas import MCPTool

# Add benchmark directory to path
benchmark_dir = Path(__file__).parent.parent / "benchmark"
sys.path.insert(0, str(benchmark_dir))


def test_benchmark_tools_json_exists():
    """Test that tools.json exists."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    tools_file = benchmark_dir / "tools.json"

    assert tools_file.exists()


def test_benchmark_tools_json_valid():
    """Test that tools.json is valid JSON."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    tools_file = benchmark_dir / "tools.json"

    with open(tools_file) as f:
        tools = json.load(f)

    assert isinstance(tools, list)
    assert len(tools) == 50  # Should have 50 tools


def test_benchmark_tools_structure():
    """Test tool structure in tools.json."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    tools_file = benchmark_dir / "tools.json"

    with open(tools_file) as f:
        tools = json.load(f)

    for tool in tools[:5]:  # Check first 5
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


def test_benchmark_queries_json_exists():
    """Test that queries.json exists."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    queries_file = benchmark_dir / "queries.json"

    assert queries_file.exists()


def test_benchmark_queries_json_valid():
    """Test that queries.json is valid JSON."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    queries_file = benchmark_dir / "queries.json"

    with open(queries_file) as f:
        queries = json.load(f)

    assert isinstance(queries, list)
    assert len(queries) == 20  # Should have 20 queries


def test_benchmark_queries_structure():
    """Test query structure in queries.json."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    queries_file = benchmark_dir / "queries.json"

    with open(queries_file) as f:
        queries = json.load(f)

    for query in queries:
        assert "query" in query
        assert "relevant_tools" in query
        assert isinstance(query["relevant_tools"], list)


def test_benchmark_run_script_exists():
    """Test that run.py exists."""
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    run_file = benchmark_dir / "run.py"

    assert run_file.exists()


def test_benchmark_precision_calculation():
    """Test precision@k calculation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    calculate_precision_at_k = run.calculate_precision_at_k

    returned = ["tool1", "tool2", "tool3", "tool4", "tool5"]
    relevant = ["tool1", "tool3", "tool6"]

    precision = calculate_precision_at_k(returned, relevant, k=5)

    # 2 out of 5 match
    assert precision == 0.4


def test_benchmark_precision_perfect():
    """Test precision with perfect match."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    calculate_precision_at_k = run.calculate_precision_at_k

    returned = ["tool1", "tool2", "tool3"]
    relevant = ["tool1", "tool2", "tool3"]

    precision = calculate_precision_at_k(returned, relevant, k=3)

    assert precision == 1.0


def test_benchmark_precision_no_match():
    """Test precision with no matches."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    calculate_precision_at_k = run.calculate_precision_at_k

    returned = ["tool1", "tool2", "tool3"]
    relevant = ["tool4", "tool5", "tool6"]

    precision = calculate_precision_at_k(returned, relevant, k=3)

    assert precision == 0.0


def test_benchmark_load_data():
    """Test loading benchmark data."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    load_benchmark_data = run.load_benchmark_data

    tools, queries = load_benchmark_data()

    assert len(tools) == 50
    assert len(queries) == 20


def test_benchmark_token_reduction():
    """Test token reduction calculation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    calculate_token_reduction = run.calculate_token_reduction
    from toolgate.metrics import MetricsCollector
    from toolgate.config import MetricsConfig

    # Create simple tools
    tools = [
        MCPTool(name=f"tool{i}", description=f"Description {i}" * 10)
        for i in range(10)
    ]

    returned = ["tool0", "tool1"]  # Only 2 of 10

    metrics = MetricsCollector(MetricsConfig(enabled=False))
    total, returned_tokens, reduction = calculate_token_reduction(
        tools, returned, metrics
    )

    assert total > returned_tokens
    assert reduction > 0
    assert reduction < 100


def test_benchmark_index_build():
    """Test that benchmark can build an index."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    load_benchmark_data = run.load_benchmark_data

    tools, queries = load_benchmark_data()

    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["benchmark"] * len(tools)
    index.build_index(tools, server_names)

    assert index.size == 50


def test_benchmark_search_relevance():
    """Test search finds relevant tools."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run", benchmark_dir / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    load_benchmark_data = run.load_benchmark_data

    tools, queries = load_benchmark_data()

    config = IndexConfig()
    index = ToolIndex(config)

    server_names = ["benchmark"] * len(tools)
    index.build_index(tools, server_names)

    # Test first query
    query_data = queries[0]
    query = query_data["query"]
    relevant = query_data["relevant_tools"]

    tool_names, scores = index.search(query, k=10)

    # At least one relevant tool should be in top 10
    matches = [t for t in tool_names if t in relevant]
    assert len(matches) > 0
