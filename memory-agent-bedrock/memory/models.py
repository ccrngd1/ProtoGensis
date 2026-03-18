"""Pydantic models for Memory and Consolidation."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, List

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _new_id() -> str:
    return str(uuid.uuid4())


class Memory(BaseModel):
    model_config = ConfigDict()

    id: str = Field(default_factory=_new_id)
    summary: str
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consolidated: bool = False

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        return v.isoformat()


class Consolidation(BaseModel):
    model_config = ConfigDict()

    id: str = Field(default_factory=_new_id)
    memory_ids: List[str]
    connections: str
    insights: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        return v.isoformat()
