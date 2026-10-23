"""Roster config loading and validation.

The roster is the single source of truth for which models the harness may
call. Only the 10 REQUIREMENTS.md models with global. profile ids are
allowed; any reference to retired model families is a hard error.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Substrings that must never appear in a roster config. April-era and
# superseded models (see REQUIREMENTS.md "Not in the panel").
BANNED_SUBSTRINGS = [
    "mantle",            # bedrock-mantle endpoints / mantle-prefixed ids
    "grok-4.3",
    "gpt-5.5",
    "claude-opus-4",     # April roster: Opus 4.6
    "claude-sonnet-4",   # April roster: Sonnet 4.6
    "claude-haiku-4",    # April roster: Haiku 4.5
    "nova-lite-v1",      # Nova 1 Lite (nova-2-lite-v1 does not contain this)
    "nova-micro",
    "nova-pro",
    "nova-premier",
    "mistral",
    "llama",
]

ALLOWED_PROFILE_IDS = {
    "global.anthropic.claude-fable-5-1",
    "global.anthropic.claude-opus-5-5",
    "global.anthropic.claude-sonnet-5-5",
    "global.anthropic.claude-haiku-5-5",
    "global.openai.gpt-6-astra",
    "global.openai.gpt-6.1-sol",
    "global.openai.gpt-6-luna",
    "global.xai.grok-4.7",
    "global.moonshotai.kimi-k3",
    "global.amazon.nova-2-lite-v1:0",
}

EFFORT_STYLES = {"claude", "openai_xai_kimi", "nova"}

# Full candidate ladder used by the probe.
ALL_LEVELS = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class RosterError(ValueError):
    """Raised when a roster config references banned or malformed models."""


def short_id(profile_id: str) -> str:
    """Display name for a profile id: strip the 'global.' prefix only.
    Model names contain dots (gpt-6.1-sol, grok-4.7, nova-2-lite-v1:0), so
    split('.')[-1] mangles them ('1-sol', '7')."""
    return profile_id.removeprefix("global.")


@dataclass
class ModelSpec:
    profile_id: str
    family: str
    tier: str
    effort_style: str
    candidate_levels: list
    default_level: str
    released: str = ""
    concurrency: int = 4


@dataclass
class Roster:
    region: str
    models: list
    default_max_tokens: int = 32000
    arms: dict = field(default_factory=dict)

    def by_id(self, profile_id: str) -> ModelSpec:
        for m in self.models:
            if m.profile_id == profile_id:
                return m
        raise KeyError(profile_id)

    @property
    def profile_ids(self):
        return [m.profile_id for m in self.models]


def validate_roster_dict(raw: dict) -> None:
    """Hard-fail on any banned model reference anywhere in the config."""
    import json

    blob = json.dumps(raw).lower()
    for banned in BANNED_SUBSTRINGS:
        if banned in blob:
            raise RosterError(
                f"roster config references banned model/endpoint {banned!r}; "
                "only the 10 REQUIREMENTS.md global. profiles are allowed"
            )
    for entry in raw.get("models", []):
        pid = entry.get("profile_id", "")
        if pid not in ALLOWED_PROFILE_IDS:
            raise RosterError(f"profile_id {pid!r} is not in the approved roster")
        if not pid.startswith("global."):
            raise RosterError(f"profile_id {pid!r} is not a global. inference profile")
        if entry.get("effort_style") not in EFFORT_STYLES:
            raise RosterError(f"{pid}: unknown effort_style {entry.get('effort_style')!r}")
        levels = entry.get("candidate_levels", [])
        bad = [l for l in levels if l not in ALL_LEVELS]
        if bad:
            raise RosterError(f"{pid}: unknown levels {bad}")
        if entry.get("default_level") not in levels:
            raise RosterError(f"{pid}: default_level not in candidate_levels")


def load_roster(path) -> Roster:
    raw = yaml.safe_load(Path(path).read_text())
    validate_roster_dict(raw)
    models = [
        ModelSpec(
            profile_id=e["profile_id"],
            family=e["family"],
            tier=e["tier"],
            effort_style=e["effort_style"],
            candidate_levels=list(e["candidate_levels"]),
            default_level=e["default_level"],
            released=e.get("released", ""),
            concurrency=int(e.get("concurrency", raw.get("default_concurrency", 4))),
        )
        for e in raw["models"]
    ]
    return Roster(
        region=raw.get("region", "us-east-1"),
        models=models,
        default_max_tokens=int(raw.get("default_max_tokens", 32000)),
        arms=raw.get("arms", {}),
    )
