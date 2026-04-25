"""Pydantic models for MCP tool objects and internal structures."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolInputSchema(BaseModel):
    """JSON Schema for tool parameters."""
    model_config = ConfigDict(extra="allow")

    type: str = "object"
    properties: Optional[Dict[str, Any]] = None
    required: Optional[List[str]] = None
    additionalProperties: Optional[bool] = None


class MCPTool(BaseModel):
    """Full MCP tool definition with all metadata."""
    model_config = ConfigDict(extra="allow")

    name: str
    description: Optional[str] = None
    inputSchema: Optional[ToolInputSchema] = None


class ToolStub(BaseModel):
    """Truncated tool returned in phase 1 (listTools response)."""
    name: str
    description: Optional[str] = None

    @classmethod
    def from_tool(cls, tool: MCPTool, max_desc_len: int = 200) -> "ToolStub":
        """Create stub from full tool with truncated description."""
        desc = tool.description or ""
        if len(desc) > max_desc_len:
            desc = desc[:max_desc_len] + "..."
        return cls(name=tool.name, description=desc)


class IndexedTool(BaseModel):
    """Tool with embedding vector and metadata for FAISS index."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    embedding: List[float]
    server_name: str
    full_tool: MCPTool


class GatingResult(BaseModel):
    """Result of gating decision with scores and metadata."""
    tools: List[str]  # tool names to return
    scores: Dict[str, float]  # similarity scores
    boosted: List[str] = Field(default_factory=list)  # tools with session boost
    forced_include: List[str] = Field(default_factory=list)  # always_include matches
    forced_exclude: List[str] = Field(default_factory=list)  # always_exclude matches


class MetricsRecord(BaseModel):
    """Single metrics record for logging."""
    timestamp: float
    event_type: str  # "list_tools", "call_tool", "index_build"
    tool_name: Optional[str] = None
    tools_returned: Optional[int] = None
    tokens_saved: Optional[int] = None
    latency_ms: Optional[float] = None
    query_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
