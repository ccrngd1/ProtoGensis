"""Tests for Needle model abstraction."""

import pytest
import numpy as np

from needleroute.schemas import MCPTool, NeedleScore
from needleroute.needle_model import (
    MockNeedleModel,
    create_needle_model,
)


def test_mock_needle_model_available():
    """Test mock model is always available."""
    model = MockNeedleModel()
    assert model.is_available() is True


def test_mock_needle_encode_tool():
    """Test mock model tool encoding."""
    model = MockNeedleModel()

    tool = MCPTool(
        name="test_tool",
        description="A test tool for testing",
        inputSchema={}
    )

    embedding = model.encode_tool(tool)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)  # MiniLM dimension

    # Encoding same tool should give same result (deterministic)
    embedding2 = model.encode_tool(tool)
    np.testing.assert_array_equal(embedding, embedding2)


def test_mock_needle_encode_query():
    """Test mock model query encoding."""
    model = MockNeedleModel()

    query = "What is the weather?"
    embedding = model.encode_query(query)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (384,)

    # Same query should give same embedding
    embedding2 = model.encode_query(query)
    np.testing.assert_array_equal(embedding, embedding2)


def test_mock_needle_score_tools():
    """Test mock model tool scoring."""
    model = MockNeedleModel()

    # Create tools
    tools = [
        MCPTool(name="read_file", description="Read a file"),
        MCPTool(name="write_file", description="Write to a file"),
        MCPTool(name="web_search", description="Search the web"),
    ]

    # Encode query and tools
    query_embedding = model.encode_query("Show me the file contents")
    tool_embeddings = {
        tool.name: model.encode_tool(tool) for tool in tools
    }

    # Score tools
    scores = model.score_tools(query_embedding, tool_embeddings)

    assert len(scores) == 3
    assert all(isinstance(s, NeedleScore) for s in scores)

    # Scores should be sorted descending
    for i in range(len(scores) - 1):
        assert scores[i].score >= scores[i+1].score

    # Top tool should have confidence set
    assert scores[0].confidence > 0


def test_mock_needle_confidence_calculation():
    """Test confidence calculation as gap between top-1 and top-2."""
    model = MockNeedleModel()

    tools = [
        MCPTool(name="tool1", description="First tool"),
        MCPTool(name="tool2", description="Second tool"),
    ]

    query_embedding = model.encode_query("test query")
    tool_embeddings = {
        tool.name: model.encode_tool(tool) for tool in tools
    }

    scores = model.score_tools(query_embedding, tool_embeddings)

    # Confidence should be gap between top scores
    expected_confidence = scores[0].score - scores[1].score
    assert abs(scores[0].confidence - expected_confidence) < 0.001


def test_mock_needle_single_tool():
    """Test scoring with single tool."""
    model = MockNeedleModel()

    tool = MCPTool(name="only_tool", description="The only tool")

    query_embedding = model.encode_query("test")
    tool_embeddings = {tool.name: model.encode_tool(tool)}

    scores = model.score_tools(query_embedding, tool_embeddings)

    assert len(scores) == 1
    assert scores[0].confidence == 1.0  # Full confidence with only one tool


def test_create_needle_model_force_mock():
    """Test factory function with force_mock."""
    model = create_needle_model(force_mock=True)

    assert isinstance(model, MockNeedleModel)
    assert model.is_available() is True


def test_needle_model_interface():
    """Test that mock model implements required interface."""
    model = MockNeedleModel()

    # Should have all required methods
    assert hasattr(model, 'encode_tool')
    assert hasattr(model, 'encode_query')
    assert hasattr(model, 'score_tools')
    assert hasattr(model, 'is_available')

    # Methods should be callable
    assert callable(model.encode_tool)
    assert callable(model.encode_query)
    assert callable(model.score_tools)
    assert callable(model.is_available)


def test_needle_scoring_normalized():
    """Test that scores use normalized vectors."""
    model = MockNeedleModel()

    tools = [
        MCPTool(name="tool1", description="First"),
        MCPTool(name="tool2", description="Second"),
    ]

    query_embedding = model.encode_query("test")
    tool_embeddings = {
        tool.name: model.encode_tool(tool) for tool in tools
    }

    scores = model.score_tools(query_embedding, tool_embeddings)

    # Cosine similarity should be in [-1, 1]
    for score in scores:
        assert -1.0 <= score.score <= 1.0
