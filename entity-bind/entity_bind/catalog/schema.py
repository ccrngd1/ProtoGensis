"""
Entity Catalog Schema

Pydantic models for entities, tool specifications, and preconditions.
Based on the paper's formalism and extended with structured signals
for disambiguation (owner, timestamp, email, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Entity Schema
# ============================================================================


class EntityType(str, Enum):
    """Common entity types across agent domains."""

    PERSON = "person"
    DOCUMENT = "document"
    CALENDAR_EVENT = "calendar_event"
    EMAIL_THREAD = "email_thread"
    CUSTOMER_ACCOUNT = "customer_account"
    TICKET = "ticket"
    CHANNEL = "channel"
    PROJECT = "project"
    FILE = "file"
    RECORD = "record"
    OTHER = "other"


class Entity(BaseModel):
    """
    Entity catalog entry.

    Core fields (required):
    - id: canonical identifier used for binding and scoring
    - type: entity type (person, document, calendar_event, etc.)
    - name/title: primary display name

    Structured signals (optional, aid disambiguation):
    - aliases: alternate names/titles
    - email: for person entities
    - owner: creator/owner of documents/records
    - timestamp/updated_at: for temporal disambiguation
    - time: for calendar events
    - status: active/closed/archived
    - parent/subsidiary: organizational hierarchy
    - system_of_origin: cross-system disambiguation
    - account_id: for customer/account entities
    - metadata: free-text context for semantic matching
    """

    id: str = Field(
        ...,
        description="Canonical entity identifier (immutable, used for binding)"
    )
    type: Union[EntityType, str] = Field(
        ...,
        description="Entity type (person, document, calendar_event, etc.)"
    )

    # Primary name/title (one of these is required)
    name: Optional[str] = Field(
        None,
        description="Primary name (for person, channel, account)"
    )
    title: Optional[str] = Field(
        None,
        description="Primary title (for document, event, ticket)"
    )

    # Aliases for fuzzy matching
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternate names/titles for candidate retrieval"
    )

    # Structured signals for disambiguation
    email: Optional[str] = Field(
        None,
        description="Email address (person entities)"
    )
    owner: Optional[str] = Field(
        None,
        description="Owner/creator (documents, records)"
    )
    timestamp: Optional[Union[datetime, str]] = Field(
        None,
        description="Creation/update timestamp (temporal disambiguation)"
    )
    updated_at: Optional[Union[datetime, str]] = Field(
        None,
        description="Last update timestamp (temporal disambiguation)"
    )
    time: Optional[str] = Field(
        None,
        description="Event time/date (calendar events)"
    )
    status: Optional[str] = Field(
        None,
        description="Status (active, closed, archived, etc.)"
    )
    parent: Optional[str] = Field(
        None,
        description="Parent entity ID (organizational hierarchy)"
    )
    subsidiary: Optional[str] = Field(
        None,
        description="Subsidiary/child entity ID"
    )
    system_of_origin: Optional[str] = Field(
        None,
        description="Source system (email, calendar, docs, tickets)"
    )
    account_id: Optional[str] = Field(
        None,
        description="Account/customer ID"
    )

    # Free-text metadata for semantic matching
    metadata: Optional[str] = Field(
        None,
        description="Free-text context for semantic matching"
    )

    # Extension point for domain-specific fields
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Domain-specific extension fields"
    )

    @field_validator('type', mode='before')
    @classmethod
    def normalize_type(cls, v):
        """Normalize type to lowercase."""
        if isinstance(v, str):
            return v.lower()
        return v

    @property
    def display_name(self) -> str:
        """Primary display name (name or title)."""
        return self.name or self.title or self.id

    @property
    def all_names(self) -> List[str]:
        """All names/titles for matching (primary + aliases)."""
        names = []
        if self.name:
            names.append(self.name)
        if self.title:
            names.append(self.title)
        names.extend(self.aliases)
        return names

    def matches_type(self, entity_type: str) -> bool:
        """Check if entity matches a given type."""
        return self.type == entity_type.lower()

    model_config = {
        "extra": "allow",  # Allow additional fields not in schema
        "str_strip_whitespace": True
    }


# ============================================================================
# Precondition Schema
# ============================================================================


class Precondition(BaseModel):
    """
    Entity precondition for a tool argument slot.

    Specifies which entity type must be resolved for a tool argument.
    Example: send_email requires {recipient:person:required}
    """

    slot: str = Field(
        ...,
        description="Argument slot name (e.g., 'recipient', 'document', 'event')"
    )
    entity_type: str = Field(
        ...,
        description="Required entity type (person, document, calendar_event, etc.)"
    )
    required: bool = Field(
        True,
        description="Whether this slot must be resolved to execute the tool"
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description of this precondition"
    )

    @classmethod
    def from_string(cls, spec: str) -> "Precondition":
        """
        Parse precondition from 'slot:type' or 'slot:type:required' format.

        Examples:
            'recipient:person' -> Precondition(slot='recipient', entity_type='person', required=True)
            'attachment:document:optional' -> Precondition(slot='attachment', entity_type='document', required=False)
        """
        parts = spec.split(':')
        if len(parts) == 2:
            slot, entity_type = parts
            required = True
        elif len(parts) == 3:
            slot, entity_type, req_str = parts
            required = req_str.lower() != 'optional'
        else:
            raise ValueError(f"Invalid precondition format: {spec}")

        return cls(
            slot=slot,
            entity_type=entity_type,
            required=required
        )

    def to_string(self) -> str:
        """Convert to 'slot:type:required/optional' format."""
        req_str = "required" if self.required else "optional"
        return f"{self.slot}:{self.entity_type}:{req_str}"


# ============================================================================
# Tool Specification Schema
# ============================================================================


class RiskLevel(str, Enum):
    """Risk level for tool actions (determines tau/delta thresholds)."""

    LOW = "low"          # Read/retrieve operations
    MEDIUM = "medium"    # Draft/prepare operations
    HIGH = "high"        # Send/share/update operations
    CRITICAL = "critical"  # Delete/cancel/close operations


class ToolSpec(BaseModel):
    """
    Tool specification with entity preconditions.

    Defines which entity types must be resolved for each tool argument,
    and the risk level (determines confidence/margin thresholds).
    """

    name: str = Field(
        ...,
        description="Tool name (must match the tool_calls[].function.name)"
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable tool description"
    )
    preconditions: List[Precondition] = Field(
        default_factory=list,
        description="Entity preconditions (P_E(t) in the paper)"
    )
    risk: RiskLevel = Field(
        RiskLevel.MEDIUM,
        description="Risk level (determines tau/delta thresholds)"
    )

    # Additional tool metadata
    returns: Optional[str] = Field(
        None,
        description="Return value description"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Non-entity parameters (for completeness)"
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolSpec":
        """
        Create ToolSpec from reference data format.

        Reference format:
        {
            "name": "send_email",
            "description": "Send an email...",
            "requires": ["recipient:person", "thread:email_thread:optional"]
        }
        """
        preconditions = []
        if 'requires' in data:
            for req in data['requires']:
                preconditions.append(Precondition.from_string(req))

        return cls(
            name=data['name'],
            description=data.get('description'),
            preconditions=preconditions,
            risk=data.get('risk', RiskLevel.MEDIUM)
        )

    @property
    def required_preconditions(self) -> List[Precondition]:
        """Get only required preconditions."""
        return [p for p in self.preconditions if p.required]

    @property
    def optional_preconditions(self) -> List[Precondition]:
        """Get only optional preconditions."""
        return [p for p in self.preconditions if not p.required]

    def get_precondition(self, slot: str) -> Optional[Precondition]:
        """Get precondition for a specific slot."""
        for p in self.preconditions:
            if p.slot == slot:
                return p
        return None


# ============================================================================
# Threshold Configuration
# ============================================================================


class ThresholdConfig(BaseModel):
    """
    Confidence (tau) and margin (delta) thresholds per risk level.

    tau: absolute confidence threshold s(ê) >= tau
    delta: margin threshold s(ê) - s(e2) >= delta

    Higher risk → higher thresholds → more likely to clarify.
    """

    tau: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Absolute confidence threshold (0-1)"
    )
    delta: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Top1-top2 margin threshold (0-1)"
    )

    @classmethod
    def defaults(cls) -> Dict[RiskLevel, "ThresholdConfig"]:
        """
        Default threshold configurations per risk level.

        Tuned to hit ~0% wrong-entity on the benchmark without
        excessive over-clarification. These can be adjusted based
        on deployment requirements.
        """
        return {
            RiskLevel.LOW: cls(tau=0.60, delta=0.15),
            RiskLevel.MEDIUM: cls(tau=0.75, delta=0.25),
            RiskLevel.HIGH: cls(tau=0.85, delta=0.35),
            RiskLevel.CRITICAL: cls(tau=0.95, delta=0.50),
        }
