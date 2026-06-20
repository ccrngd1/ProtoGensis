"""Configuration management with Pydantic v2."""

from typing import Dict, List, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, field_validator


class UpstreamServer(BaseModel):
    """Configuration for an upstream MCP server."""
    name: str
    transport: str = "stdio"
    command: List[str]
    env: Optional[Dict[str, str]] = None


class ToolGateConfig(BaseModel):
    """ToolGate filtering configuration."""
    top_k: int = Field(default=10, gt=0)
    phase1_max_desc: int = Field(default=200, gt=0)
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    session_boost: float = Field(default=0.15, ge=0.0, le=1.0)
    session_window: int = Field(default=5, ge=1)


class NeedleConfig(BaseModel):
    """Needle model configuration."""
    model_path: Optional[str] = None  # HuggingFace path or local path
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    always_escalate_destructive: bool = True

    @field_validator("model_path")
    @classmethod
    def validate_model_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate model path if provided."""
        if v and v != "null":
            return v
        return None


class EscalationConfig(BaseModel):
    """Frontier model escalation configuration."""
    provider: str = Field(default="bedrock")
    model: str = Field(default="anthropic.claude-haiku-4-5-20251001-v1:0")
    region: str = Field(default="us-east-1")
    max_tokens: int = Field(default=1024, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate escalation provider."""
        if v not in ["bedrock", "mock"]:
            raise ValueError(f"Invalid provider: {v}. Must be 'bedrock' or 'mock'")
        return v


class GatingRules(BaseModel):
    """Tool gating rules."""
    always_include: List[str] = Field(default_factory=list)
    always_exclude: List[str] = Field(default_factory=list)


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""
    enabled: bool = True
    db_path: str = Field(default="~/.needleroute/metrics.sqlite")


class NeedleRouteConfig(BaseModel):
    """Main NeedleRoute configuration."""
    transport: str = "stdio"
    toolgate: ToolGateConfig = Field(default_factory=ToolGateConfig)
    needle: NeedleConfig = Field(default_factory=NeedleConfig)
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)
    upstream_servers: List[UpstreamServer]
    gating: GatingRules = Field(default_factory=GatingRules)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    @classmethod
    def from_yaml(cls, path: str) -> "NeedleRouteConfig":
        """Load configuration from YAML file."""
        config_path = Path(path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict) -> "NeedleRouteConfig":
        """Create configuration from dictionary."""
        return cls(**data)

    def expand_paths(self) -> None:
        """Expand user paths in configuration."""
        if self.metrics.db_path:
            expanded = Path(self.metrics.db_path).expanduser()
            self.metrics.db_path = str(expanded)
            # Ensure parent directory exists
            expanded.parent.mkdir(parents=True, exist_ok=True)

        # Expand model path if it's a local path
        if self.needle.model_path and not self.needle.model_path.startswith("Cactus-Compute/"):
            expanded = Path(self.needle.model_path).expanduser()
            if expanded.exists():
                self.needle.model_path = str(expanded)
