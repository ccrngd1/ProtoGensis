"""Configuration management with Pydantic v2."""

from typing import Dict, List, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, field_validator


class UpstreamServer(BaseModel):
    """Configuration for an upstream MCP server."""
    name: str
    command: str
    args: List[str] = Field(default_factory=list)
    env: Optional[Dict[str, str]] = None


class GatingConfig(BaseModel):
    """Gating rules configuration."""
    top_k: int = Field(default=10, gt=0)
    always_include: List[str] = Field(default_factory=list)
    always_exclude: List[str] = Field(default_factory=list)
    session_boost: float = Field(default=0.15, ge=0.0, le=1.0)
    session_window: int = Field(default=5, ge=1)  # last N turns
    description_max_length: int = Field(default=200, gt=0)

    @field_validator("always_include", "always_exclude")
    @classmethod
    def validate_patterns(cls, v: List[str]) -> List[str]:
        """Ensure patterns are valid strings."""
        return [str(pattern).strip() for pattern in v if pattern]


class IndexConfig(BaseModel):
    """Tool index configuration."""
    model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    cache_dir: Optional[str] = None
    similarity_metric: str = Field(default="cosine")

    @field_validator("similarity_metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        """Validate similarity metric."""
        if v not in ["cosine", "euclidean", "dot"]:
            raise ValueError(f"Invalid similarity metric: {v}")
        return v


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""
    enabled: bool = True
    db_path: str = Field(default="~/.toolgate/metrics.db")
    token_model: str = Field(default="cl100k_base")  # tiktoken encoding


class ToolGateConfig(BaseModel):
    """Main ToolGate configuration."""
    upstream_servers: List[UpstreamServer]
    gating: GatingConfig = Field(default_factory=GatingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "ToolGateConfig":
        """Load configuration from YAML file."""
        config_path = Path(path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict) -> "ToolGateConfig":
        """Create configuration from dictionary."""
        return cls(**data)

    def expand_paths(self) -> None:
        """Expand user paths in configuration."""
        if self.metrics.db_path:
            expanded = Path(self.metrics.db_path).expanduser()
            self.metrics.db_path = str(expanded)
            # Ensure parent directory exists
            expanded.parent.mkdir(parents=True, exist_ok=True)

        if self.index.cache_dir:
            expanded = Path(self.index.cache_dir).expanduser()
            self.index.cache_dir = str(expanded)
            expanded.mkdir(parents=True, exist_ok=True)
