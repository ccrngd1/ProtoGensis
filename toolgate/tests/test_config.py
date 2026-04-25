"""Tests for configuration management."""

import pytest
import yaml
from pathlib import Path

from toolgate.config import (
    ToolGateConfig, UpstreamServer, GatingConfig,
    IndexConfig, MetricsConfig
)


def test_upstream_server_creation():
    """Test creating an upstream server config."""
    server = UpstreamServer(
        name="test",
        command="test-cmd",
        args=["--flag"],
        env={"KEY": "value"}
    )

    assert server.name == "test"
    assert server.command == "test-cmd"
    assert server.args == ["--flag"]
    assert server.env == {"KEY": "value"}


def test_gating_config_defaults():
    """Test gating config default values."""
    config = GatingConfig()

    assert config.top_k == 10
    assert config.always_include == []
    assert config.always_exclude == []
    assert config.session_boost == 0.15
    assert config.session_window == 5
    assert config.description_max_length == 200


def test_gating_config_validation():
    """Test gating config validation."""
    config = GatingConfig(
        top_k=5,
        always_include=["tool1", "tool2"],
        always_exclude=["tool3"],
        session_boost=0.2
    )

    assert config.top_k == 5
    assert "tool1" in config.always_include
    assert "tool3" in config.always_exclude


def test_gating_config_invalid_boost():
    """Test that invalid session_boost is rejected."""
    with pytest.raises(ValueError):
        GatingConfig(session_boost=1.5)  # > 1.0


def test_index_config_defaults():
    """Test index config default values."""
    config = IndexConfig()

    assert config.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.similarity_metric == "cosine"


def test_index_config_invalid_metric():
    """Test that invalid similarity metric is rejected."""
    with pytest.raises(ValueError):
        IndexConfig(similarity_metric="invalid")


def test_metrics_config_defaults():
    """Test metrics config default values."""
    config = MetricsConfig()

    assert config.enabled is True
    assert config.db_path == "~/.toolgate/metrics.db"
    assert config.token_model == "cl100k_base"


def test_toolgate_config_from_dict(sample_config_dict):
    """Test creating config from dictionary."""
    config = ToolGateConfig.from_dict(sample_config_dict)

    assert len(config.upstream_servers) == 1
    assert config.upstream_servers[0].name == "filesystem"
    assert config.gating.top_k == 10
    assert config.index.similarity_metric == "cosine"
    assert config.metrics.enabled is True


def test_toolgate_config_from_yaml(temp_dir):
    """Test loading config from YAML file."""
    config_path = temp_dir / "config.yaml"

    config_data = {
        "upstream_servers": [
            {
                "name": "test",
                "command": "test-cmd",
                "args": ["--stdio"]
            }
        ],
        "gating": {
            "top_k": 5
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    config = ToolGateConfig.from_yaml(str(config_path))

    assert len(config.upstream_servers) == 1
    assert config.gating.top_k == 5


def test_config_expand_paths(temp_dir):
    """Test path expansion in config."""
    config = ToolGateConfig(
        upstream_servers=[],
        metrics=MetricsConfig(
            db_path=str(temp_dir / "metrics.db")
        ),
        index=IndexConfig(
            cache_dir=str(temp_dir / "cache")
        )
    )

    config.expand_paths()

    assert Path(config.metrics.db_path).parent.exists()
    assert Path(config.index.cache_dir).exists()


def test_config_file_not_found():
    """Test error handling for missing config file."""
    with pytest.raises(FileNotFoundError):
        ToolGateConfig.from_yaml("nonexistent.yaml")
