"""Roster guard: only the 10 approved global. profiles; banned models hard-fail."""

from pathlib import Path

import pytest

from ensemble_reboot.roster import (
    ALLOWED_PROFILE_IDS,
    RosterError,
    load_roster,
    validate_roster_dict,
)

ROOT = Path(__file__).resolve().parent.parent


def _entry(pid, **kw):
    return {
        "profile_id": pid, "family": "x", "tier": "frontier",
        "effort_style": "claude", "candidate_levels": ["low", "medium"],
        "default_level": "medium", **kw,
    }


def test_real_roster_loads_with_exactly_10_models():
    roster = load_roster(ROOT / "config" / "roster.yaml")
    assert len(roster.models) == 10
    assert set(roster.profile_ids) == ALLOWED_PROFILE_IDS


@pytest.mark.parametrize("banned_pid", [
    "mantle.anthropic.claude-opus-4-6",
    "global.xai.grok-4.3",
    "global.openai.gpt-5.5",
    "global.anthropic.claude-opus-4-6",
    "global.amazon.nova-lite-v1:0",
    "global.meta.llama-4-maverick",
])
def test_banned_models_hard_fail(banned_pid):
    with pytest.raises(RosterError):
        validate_roster_dict({"models": [_entry(banned_pid)]})


def test_banned_substring_anywhere_in_config_fails():
    # even outside the models list (e.g. a stray arms reference)
    raw = {
        "models": [_entry("global.anthropic.claude-fable-5-1")],
        "arms": {"a4a_aggregator": "mantle.anthropic.claude-opus-4-6"},
    }
    with pytest.raises(RosterError, match="mantle"):
        validate_roster_dict(raw)


def test_unlisted_model_rejected():
    with pytest.raises(RosterError, match="not in the approved roster"):
        validate_roster_dict({"models": [_entry("global.anthropic.claude-fable-4-9")]})


def test_non_global_profile_rejected():
    with pytest.raises(RosterError):
        validate_roster_dict({"models": [_entry("us.anthropic.claude-fable-5-1")]})


def test_default_level_must_be_candidate():
    e = _entry("global.anthropic.claude-fable-5-1", default_level="xhigh")
    with pytest.raises(RosterError, match="default_level"):
        validate_roster_dict({"models": [e]})


def test_unknown_level_rejected():
    e = _entry("global.anthropic.claude-fable-5-1",
               candidate_levels=["low", "turbo"], default_level="low")
    with pytest.raises(RosterError, match="turbo"):
        validate_roster_dict({"models": [e]})
