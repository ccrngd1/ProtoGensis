"""Pytest fixtures for CoherenceProbe tests."""

import pytest
from coherenceprobe.models import AgentOutput, CoherenceConfig


@pytest.fixture
def coherent_outputs():
    """Fixture providing coherent agent outputs (no contradictions)."""
    return [
        AgentOutput(
            agent="summarizer",
            timestamp="2026-06-07T10:00:00Z",
            input="Article about AI safety",
            output="The article discusses AI safety measures. It emphasizes the importance of alignment. Research shows promising results.",
            metadata={}
        ),
        AgentOutput(
            agent="critic",
            timestamp="2026-06-07T10:00:05Z",
            input="Article about AI safety",
            output="The paper covers safety protocols. Alignment is a key focus area. Recent studies demonstrate progress.",
            metadata={}
        ),
    ]


@pytest.fixture
def contradictory_outputs():
    """Fixture providing contradictory agent outputs."""
    return [
        AgentOutput(
            agent="agent_a",
            timestamp="2026-06-07T10:00:00Z",
            input="system status",
            output="The server is running on port 8080. All systems are operational.",
            metadata={}
        ),
        AgentOutput(
            agent="agent_b",
            timestamp="2026-06-07T10:00:05Z",
            input="system status",
            output="The server is running on port 3000. The system is currently down for maintenance.",
            metadata={}
        ),
    ]


@pytest.fixture
def subtle_contradiction_outputs():
    """Fixture providing subtle contradictions that require NLI to detect."""
    return [
        AgentOutput(
            agent="analyst_1",
            timestamp="2026-06-07T10:00:00Z",
            input="market data",
            output="The stock price increased by 15% this quarter. The company reported strong earnings.",
            metadata={}
        ),
        AgentOutput(
            agent="analyst_2",
            timestamp="2026-06-07T10:00:05Z",
            input="market data",
            output="The company's stock declined this quarter. Financial performance was below expectations.",
            metadata={}
        ),
    ]


@pytest.fixture
def single_agent_output():
    """Fixture with output from only one agent (no contradictions possible)."""
    return [
        AgentOutput(
            agent="solo",
            timestamp="2026-06-07T10:00:00Z",
            input="test",
            output="This is a single agent output. No contradictions possible.",
            metadata={}
        ),
    ]


@pytest.fixture
def empty_outputs():
    """Fixture with no outputs."""
    return []


@pytest.fixture
def default_config():
    """Fixture providing default configuration."""
    return CoherenceConfig()


@pytest.fixture
def local_config():
    """Fixture providing local mode configuration."""
    return CoherenceConfig(
        local=True,
        verbose=False
    )


@pytest.fixture
def verbose_config():
    """Fixture providing verbose configuration."""
    return CoherenceConfig(
        verbose=True,
        threshold=0.6
    )
