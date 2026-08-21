"""Shared fixtures. NO network calls anywhere in the suite: litellm.completion
is always mocked, and a guard fixture fails any test that would touch it
unmocked."""

from __future__ import annotations

import json

import pytest

from docprobe.judge import Judge, JudgeCache


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail fast if any test reaches litellm without an explicit mock."""
    import litellm

    def _boom(*args, **kwargs):
        raise AssertionError("Test attempted a real LLM/network call")

    monkeypatch.setattr(litellm, "completion", _boom)


@pytest.fixture
def tmp_cache(tmp_path):
    return JudgeCache(cache_dir=str(tmp_path / "cache"))


def make_llm_response(payload: dict):
    """Build a litellm-shaped response carrying a JSON payload."""
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


@pytest.fixture
def mock_judge(monkeypatch, tmp_cache):
    """A Judge whose litellm.completion returns a canned clean verdict."""
    import litellm

    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kw: make_llm_response({"grade": "B", "flags": []}),
    )
    return Judge(cache=tmp_cache)


GOOD_DOC = """\
# Agent instructions

## Build

- Run `make test` before every commit; it must exit 0.
- Never commit directly to main, because branch protection blocks it.

## Style

- Use 4-space indentation in Python files.
- Prefer pathlib over os.path in new code.
"""

VAGUE_DOC = """\
# Notes

This project has a long history and we value craftsmanship above all else.
The team meets often and we care deeply about quality and communication.

Please write clean code and follow best practices when possible.
"""


@pytest.fixture
def good_file(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text(GOOD_DOC, encoding="utf-8")
    return p


@pytest.fixture
def vague_file(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(VAGUE_DOC, encoding="utf-8")
    return p
