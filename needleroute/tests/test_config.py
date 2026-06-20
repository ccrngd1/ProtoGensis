"""Tests for configuration management."""

import pytest
import tempfile
from pathlib import Path

from needleroute.config import (
    NeedleRouteConfig,
    ToolGateConfig,
    NeedleConfig,
    EscalationConfig,
    UpstreamServer,
)


def test_toolgate_config_defaults():
    """Test ToolGate config defaults."""
    config = ToolGateConfig()
    assert config.top_k == 10
    assert config.phase1_max_desc == 200
    assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.session_boost == 0.15
    assert config.session_window == 5


def test_needle_config_defaults():
    """Test Needle config defaults."""
    config = NeedleConfig()
    assert config.model_path is None
    assert config.confidence_threshold == 0.7
    assert config.always_escalate_destructive is True


def test_escalation_config_defaults():
    """Test escalation config defaults."""
    config = EscalationConfig()
    assert config.provider == "bedrock"
    assert config.model == "anthropic.claude-haiku-4-5-20251001-v1:0"
    assert config.region == "us-east-1"
    assert config.max_tokens == 1024


def test_needleroute_config_from_dict():
    """Test config creation from dictionary."""
    config_dict = {
        "transport": "stdio",
        "upstream_servers": [
            {
                "name": "test",
                "command": ["echo", "test"]
            }
        ],
        "toolgate": {"top_k": 5},
        "needle": {"confidence_threshold": 0.8},
        "escalation": {"provider": "mock"},
    }

    config = NeedleRouteConfig.from_dict(config_dict)
    assert config.transport == "stdio"
    assert len(config.upstream_servers) == 1
    assert config.toolgate.top_k == 5
    assert config.needle.confidence_threshold == 0.8
    assert config.escalation.provider == "mock"


def test_needleroute_config_from_yaml():
    """Test config loading from YAML file."""
    yaml_content = """
needleroute:
  transport: stdio
  toolgate:
    top_k: 15
  needle:
    confidence_threshold: 0.6
  escalation:
    provider: bedrock
upstream_servers:
  - name: filesystem
    transport: stdio
    command: ["ls"]
gating:
  always_include: []
  always_exclude: []
metrics:
  enabled: true
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        temp_path = f.name

    try:
        config = NeedleRouteConfig.from_yaml(temp_path)
        assert len(config.upstream_servers) == 1
        assert config.upstream_servers[0].name == "filesystem"
    finally:
        Path(temp_path).unlink()


def test_config_expand_paths():
    """Test path expansion."""
    config = NeedleRouteConfig(
        upstream_servers=[],
        metrics={"db_path": "~/.needleroute/test.db"}
    )

    config.expand_paths()

    # Should expand tilde
    assert "~" not in config.metrics.db_path
    assert str(Path.home()) in config.metrics.db_path


def test_upstream_server_config():
    """Test upstream server configuration."""
    server = UpstreamServer(
        name="test_server",
        command=["python", "-m", "server"],
        env={"KEY": "value"}
    )

    assert server.name == "test_server"
    assert server.command == ["python", "-m", "server"]
    assert server.env == {"KEY": "value"}


def test_escalation_provider_validation():
    """Test escalation provider validation."""
    # Valid provider
    config = EscalationConfig(provider="bedrock")
    assert config.provider == "bedrock"

    config = EscalationConfig(provider="mock")
    assert config.provider == "mock"

    # Invalid provider should raise error
    with pytest.raises(Exception):
        EscalationConfig(provider="invalid")


def test_confidence_threshold_bounds():
    """Test confidence threshold validation."""
    # Valid thresholds
    config = NeedleConfig(confidence_threshold=0.0)
    assert config.confidence_threshold == 0.0

    config = NeedleConfig(confidence_threshold=1.0)
    assert config.confidence_threshold == 1.0

    config = NeedleConfig(confidence_threshold=0.5)
    assert config.confidence_threshold == 0.5


def test_session_boost_bounds():
    """Test session boost validation."""
    # Valid boosts
    config = ToolGateConfig(session_boost=0.0)
    assert config.session_boost == 0.0

    config = ToolGateConfig(session_boost=1.0)
    assert config.session_boost == 1.0

    config = ToolGateConfig(session_boost=0.2)
    assert config.session_boost == 0.2
