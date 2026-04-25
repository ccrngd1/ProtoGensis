"""Pytest fixtures for ToolGate tests."""

import tempfile
from pathlib import Path
from typing import List
import pytest

from toolgate.config import (
    ToolGateConfig, UpstreamServer, GatingConfig,
    IndexConfig, MetricsConfig
)
from toolgate.schemas import MCPTool, ToolInputSchema


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_tools() -> List[MCPTool]:
    """Create sample tools for testing."""
    return [
        MCPTool(
            name="read_file",
            description="Read contents of a file",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"path": {"type": "string"}},
                required=["path"]
            )
        ),
        MCPTool(
            name="write_file",
            description="Write content to a file",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                required=["path", "content"]
            )
        ),
        MCPTool(
            name="list_directory",
            description="List files in a directory",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"path": {"type": "string"}},
                required=["path"]
            )
        ),
        MCPTool(
            name="git_status",
            description="Get git repository status",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        ),
        MCPTool(
            name="git_commit",
            description="Create a git commit",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"message": {"type": "string"}},
                required=["message"]
            )
        ),
        MCPTool(
            name="http_get",
            description="Make HTTP GET request",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"url": {"type": "string"}},
                required=["url"]
            )
        ),
        MCPTool(
            name="parse_json",
            description="Parse JSON string",
            inputSchema=ToolInputSchema(
                type="object",
                properties={"json_string": {"type": "string"}},
                required=["json_string"]
            )
        ),
        MCPTool(
            name="calculate_hash",
            description="Calculate cryptographic hash",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "data": {"type": "string"},
                    "algorithm": {"type": "string"}
                },
                required=["data"]
            )
        ),
    ]


@pytest.fixture
def sample_config(temp_dir: Path) -> ToolGateConfig:
    """Create a sample configuration."""
    db_path = temp_dir / "metrics.db"

    return ToolGateConfig(
        upstream_servers=[
            UpstreamServer(
                name="test_server",
                command="test",
                args=["--stdio"]
            )
        ],
        gating=GatingConfig(
            top_k=5,
            always_include=["git_*"],
            always_exclude=["dangerous_*"],
            session_boost=0.15,
            session_window=5
        ),
        index=IndexConfig(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            similarity_metric="cosine"
        ),
        metrics=MetricsConfig(
            enabled=True,
            db_path=str(db_path)
        )
    )


@pytest.fixture
def sample_config_dict(temp_dir: Path) -> dict:
    """Create a sample configuration dictionary."""
    return {
        "upstream_servers": [
            {
                "name": "filesystem",
                "command": "mcp-server-filesystem",
                "args": ["--stdio"]
            }
        ],
        "gating": {
            "top_k": 10,
            "always_include": ["read_*", "write_*"],
            "always_exclude": ["delete_*"],
            "session_boost": 0.2,
            "session_window": 3
        },
        "index": {
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "similarity_metric": "cosine"
        },
        "metrics": {
            "enabled": True,
            "db_path": str(temp_dir / "test_metrics.db")
        }
    }
