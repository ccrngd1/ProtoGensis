"""Surface-mapper snapshot tests (FR5, NFR4)."""

from __future__ import annotations

import pytest

from setup_trap.model import Provenance
from setup_trap.surface_mapper import get_inventory, list_runtimes

EXPECTED_RUNTIMES = ["claude_code", "copilot", "cursor", "openclaw"]

# Snapshot of entry counts per runtime — guards against accidental drops.
EXPECTED_ENTRY_COUNTS = {
    "claude_code": 7,
    "cursor": 5,
    "copilot": 4,
    "openclaw": 9,
}


def test_all_runtimes_registered():
    assert list_runtimes() == EXPECTED_RUNTIMES


@pytest.mark.parametrize("runtime", EXPECTED_RUNTIMES)
def test_inventory_entry_count_snapshot(runtime):
    inv = get_inventory(runtime)
    assert len(inv.entries) == EXPECTED_ENTRY_COUNTS[runtime]


@pytest.mark.parametrize("runtime", EXPECTED_RUNTIMES)
def test_every_entry_has_provenance_and_risk(runtime):
    inv = get_inventory(runtime)
    for e in inv.entries:
        assert isinstance(e.provenance, Provenance)
        assert e.risk and "->" in e.risk  # "write THIS -> do THAT"
        assert e.scope
        assert e.when_read


def test_copilot_is_mostly_inferred():
    # The brief flags Copilot as best-effort / inferred; ensure we don't over-claim.
    inv = get_inventory("copilot")
    inferred = [e for e in inv.entries if e.provenance is Provenance.INFERRED]
    assert inferred, "Copilot inventory should carry inferred entries (best-effort)"


def test_openclaw_has_sourced_bootstrap_entries():
    inv = get_inventory("openclaw")
    sourced = [e for e in inv.entries if e.provenance is Provenance.SOURCED]
    # AGENTS.md / SOUL.md / SKILL.md / hooks are documented behaviors.
    assert len(sourced) >= 4


def test_unknown_runtime_raises():
    with pytest.raises(KeyError):
        get_inventory("does-not-exist")


def test_inventory_json_roundtrip():
    inv = get_inventory("openclaw")
    d = inv.to_dict()
    assert d["runtime"] == "openclaw"
    assert len(d["entries"]) == EXPECTED_ENTRY_COUNTS["openclaw"]
    assert all("provenance" in e for e in d["entries"])
