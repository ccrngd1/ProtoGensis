"""Data schemas for NeedleRoute."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any] = Field(default_factory=dict)


class IndexedTool(BaseModel):
    """Tool with embedding vector for semantic search."""
    name: str
    description: str
    embedding: List[float]
    server_name: str
    full_tool: MCPTool


class ToolStub(BaseModel):
    """Truncated tool for phase 1 (listTools) - minimal schema."""
    name: str
    description: str

    @classmethod
    def from_tool(cls, tool: MCPTool, max_desc_len: int = 200) -> "ToolStub":
        """Create stub from full tool."""
        desc = tool.description or ""
        if len(desc) > max_desc_len:
            desc = desc[:max_desc_len] + "..."
        return cls(name=tool.name, description=desc)


class GatingResult(BaseModel):
    """Result of ToolGate filtering."""
    tools: List[str]
    scores: Dict[str, float]
    boosted: List[str] = Field(default_factory=list)
    forced_include: List[str] = Field(default_factory=list)
    forced_exclude: List[str] = Field(default_factory=list)


class NeedleScore(BaseModel):
    """Needle model scoring result for a single tool."""
    tool_name: str
    score: float  # Cosine similarity score
    confidence: float  # Confidence metric (e.g., gap from runner-up)


class RoutingDecision(BaseModel):
    """Final routing decision from NeedleRouter."""
    selected_tool: str
    confidence: float
    needle_scores: List[NeedleScore]
    escalated: bool
    escalation_reason: Optional[str] = None
    destructive_hint: bool = False


class EscalationRequest(BaseModel):
    """Request for frontier model escalation."""
    query: str
    available_tools: List[MCPTool]
    reason: str  # Why we're escalating


class EscalationResponse(BaseModel):
    """Response from frontier model escalation."""
    selected_tool: str
    arguments: Dict[str, Any]
    reasoning: Optional[str] = None
    model_used: str
    tokens_used: int = 0
