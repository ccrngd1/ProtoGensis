"""
Pydantic models for xMemory hierarchy levels and retrieval results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Message(BaseModel):
    """A single conversation message (raw level)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    session_id: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    episode_id: Optional[int] = None  # FK to Episode, set after episode construction


class Episode(BaseModel):
    """A summary of a contiguous block of messages within a session."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    session_id: str
    summary: str
    message_ids: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("message_ids", mode="before")
    @classmethod
    def parse_message_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class SemanticNode(BaseModel):
    """A distilled, reusable fact extracted from one or more episodes."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    fact: str
    source_episode_ids: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_episode_ids", mode="before")
    @classmethod
    def parse_episode_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class Theme(BaseModel):
    """A cluster of related semantic nodes grouped by topic."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    label: str
    semantic_ids: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("semantic_ids", mode="before")
    @classmethod
    def parse_semantic_ids(cls, v: Any) -> List[int]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class RetrievalResult(BaseModel):
    """The assembled context returned from a top-down retrieval query."""

    query: str
    themes: List[Theme] = Field(default_factory=list)
    semantics: List[SemanticNode] = Field(default_factory=list)
    episodes: List[Episode] = Field(default_factory=list)
    messages: List[Message] = Field(default_factory=list)
    total_tokens: int = 0
    retrieval_level: str = "semantic"  # "theme" | "semantic" | "episode" | "message"

    def to_context_string(self) -> str:
        """Flatten the retrieval result into a single context string for LLM consumption."""
        parts: List[str] = []

        if self.themes:
            parts.append("## Relevant Themes")
            for t in self.themes:
                parts.append(f"- **{t.label}**")

        if self.semantics:
            parts.append("\n## Key Facts")
            for s in self.semantics:
                parts.append(f"- {s.fact}")

        if self.episodes:
            parts.append("\n## Episode Summaries")
            for e in self.episodes:
                parts.append(f"[Session {e.session_id}] {e.summary}")

        if self.messages:
            parts.append("\n## Raw Messages")
            for m in self.messages:
                parts.append(f"[{m.timestamp.isoformat()}] {m.content}")

        return "\n".join(parts)

    def token_estimate(self) -> int:
        """Rough token estimate: ~4 chars per token."""
        text = self.to_context_string()
        return len(text) // 4
