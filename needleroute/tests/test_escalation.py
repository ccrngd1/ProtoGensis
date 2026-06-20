"""Tests for escalation system."""

import pytest

from needleroute.config import EscalationConfig
from needleroute.schemas import MCPTool, EscalationRequest
from needleroute.escalation import MockEscalationProvider, create_escalation_provider


@pytest.fixture
def sample_tools():
    """Create sample tools for testing."""
    return [
        MCPTool(name="read_file", description="Read a file"),
        MCPTool(name="write_file", description="Write to a file"),
        MCPTool(name="web_search", description="Search the web"),
    ]


def test_mock_escalation_provider_initialization():
    """Test mock provider initialization."""
    config = EscalationConfig(provider="mock")
    provider = MockEscalationProvider(config)

    assert provider.config == config


@pytest.mark.asyncio
async def test_mock_escalation_basic(sample_tools):
    """Test basic mock escalation."""
    config = EscalationConfig(provider="mock")
    provider = MockEscalationProvider(config)

    request = EscalationRequest(
        query="Read the config file",
        available_tools=sample_tools,
        reason="test"
    )

    response = await provider.escalate(request)

    # Should return a tool from available tools
    assert response.selected_tool in [t.name for t in sample_tools]
    assert response.model_used == "mock"
    assert response.tokens_used > 0


@pytest.mark.asyncio
async def test_mock_escalation_keyword_matching(sample_tools):
    """Test mock escalation uses keyword matching."""
    config = EscalationConfig(provider="mock")
    provider = MockEscalationProvider(config)

    # Query mentions "read_file" directly
    request = EscalationRequest(
        query="Use read_file to show the contents",
        available_tools=sample_tools,
        reason="test"
    )

    response = await provider.escalate(request)

    # Should pick read_file because it's mentioned in query
    assert response.selected_tool == "read_file"


@pytest.mark.asyncio
async def test_mock_escalation_no_tools():
    """Test mock escalation with no available tools."""
    config = EscalationConfig(provider="mock")
    provider = MockEscalationProvider(config)

    request = EscalationRequest(
        query="Do something",
        available_tools=[],
        reason="test"
    )

    response = await provider.escalate(request)

    assert response.selected_tool == "error"
    assert response.reasoning is not None


@pytest.mark.asyncio
async def test_mock_escalation_reasoning(sample_tools):
    """Test mock escalation provides reasoning."""
    config = EscalationConfig(provider="mock")
    provider = MockEscalationProvider(config)

    request = EscalationRequest(
        query="Search for information",
        available_tools=sample_tools,
        reason="low_confidence"
    )

    response = await provider.escalate(request)

    assert response.reasoning is not None
    assert len(response.reasoning) > 0


def test_create_escalation_provider_mock():
    """Test factory function creates mock provider."""
    config = EscalationConfig(provider="mock")
    provider = create_escalation_provider(config)

    assert isinstance(provider, MockEscalationProvider)


def test_create_escalation_provider_bedrock():
    """Test factory function creates Bedrock provider."""
    config = EscalationConfig(provider="bedrock")
    provider = create_escalation_provider(config)

    # Should create BedrockEscalationProvider
    # (may not be available, but should create instance)
    assert provider is not None


def test_create_escalation_provider_invalid():
    """Test factory function with invalid provider."""
    from pydantic import ValidationError

    # Pydantic validates at config creation time
    with pytest.raises(ValidationError):
        config = EscalationConfig(provider="invalid")


def test_escalation_config_defaults():
    """Test escalation config defaults."""
    config = EscalationConfig(provider="mock")

    assert config.max_tokens == 1024
    assert config.temperature == 0.0
    assert config.region == "us-east-1"
