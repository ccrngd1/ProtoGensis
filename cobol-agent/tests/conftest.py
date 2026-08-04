"""Shared fixtures.

Test policy (from the requirements): the suite makes NO real LLM API calls
(cobalt.provider.complete is monkeypatched) and needs NO JVM (parser input
comes from tests/fixtures/parser_output.json, a canned cobalt-parser-v0
document, or from the pure-Python fallback parser).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURE_JSON = TESTS_DIR / "fixtures" / "parser_output.json"
SAMPLES = PROJECT_ROOT / "assets" / "samples"
SAMPLE_CBL = SAMPLES / "claimcalc.cbl"
SAMPLE_COPY = SAMPLES / "copy"
GOLDEN = SAMPLES / "golden" / "expected_output.txt"


@pytest.fixture()
def fixture_doc() -> dict:
    """The canned parser JSON (cobalt-parser-v0) for claimcalc.cbl."""
    with FIXTURE_JSON.open() as f:
        doc = json.load(f)
    return copy.deepcopy(doc)


@pytest.fixture()
def mock_llm(monkeypatch):
    """Replace provider.complete with a recorder. No API calls possible.

    Returns a list of (system, user) call tuples; the canned reply embeds a
    MOCK marker so nothing downstream can mistake it for model output.
    """
    calls: list[tuple[str, str]] = []

    def fake_complete(system: str, user: str, max_tokens: int = 8000) -> str:
        calls.append((system, user))
        return "[MOCK LLM OUTPUT — no API call was made]"

    monkeypatch.setattr("cobalt.provider.complete", fake_complete)
    # Command modules import `provider` as a module, so patching the
    # function on the module covers them all.
    return calls


@pytest.fixture()
def use_fixture_parser(monkeypatch, fixture_doc):
    """Make every command parse from the canned JSON instead of any backend."""

    def fake_parse(source, copy_dirs=None, prefer="auto"):
        return copy.deepcopy(fixture_doc)

    for mod in ("cobalt.commands.explain", "cobalt.commands.translate",
                "cobalt.commands.testgen"):
        monkeypatch.setattr(f"{mod}.parse", fake_parse)
    monkeypatch.setattr("cobalt.parser.parse", fake_parse)
    return fake_parse
