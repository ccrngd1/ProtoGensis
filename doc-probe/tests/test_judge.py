"""LLM judge tests — litellm fully mocked; never assert exact LLM grades."""

import json

import pytest

from docprobe.judge import DEFAULT_MODEL, Judge, JudgeCache, _worst_grade, load_rubric
from docprobe.parser import parse
from tests.conftest import make_llm_response

DOC = """\
# Rules

- Always use tabs for indentation.
- Indent with 4 spaces in all files.
- Write clean code and follow best practices.
"""


def test_model_pin_default():
    assert DEFAULT_MODEL == "bedrock/anthropic.claude-sonnet-4-5"
    assert Judge(cache=JudgeCache(cache_dir="/tmp/x")).model == DEFAULT_MODEL


def test_judge_sends_temperature_zero_and_pinned_model(monkeypatch, tmp_cache):
    import litellm

    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return make_llm_response({"grade": "A", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    judge = Judge(cache=tmp_cache)
    judge.score_specificity(parse("AGENTS.md", DOC))
    assert captured["temperature"] == 0
    assert captured["model"] == DEFAULT_MODEL


def test_rubric_text_is_the_prompt(monkeypatch, tmp_cache):
    """The judge's system prompt comes verbatim from rubric.md."""
    import litellm

    captured = {}

    def fake(**kwargs):
        captured["system"] = kwargs["messages"][0]["content"]
        return make_llm_response({"grade": "A", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    Judge(cache=tmp_cache).score_specificity(parse("AGENTS.md", DOC))
    rubric = load_rubric()
    # First line of the rubric's specificity judge block must appear verbatim.
    assert "auditing an AI-agent instruction file for specificity" in captured["system"]
    assert "auditing an AI-agent instruction file for specificity" in rubric


def test_specificity_returns_flags_with_lines(monkeypatch, tmp_cache):
    import litellm

    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kw: make_llm_response(
            {
                "grade": "D",
                "flags": [
                    {
                        "passage": "Write clean code and follow best practices.",
                        "rationale": "No checkable criterion",
                        "suggestion": "Name the linter and its config",
                    }
                ],
            }
        ),
    )
    d = Judge(cache=tmp_cache).score_specificity(parse("AGENTS.md", DOC))
    # Structural assertions only — never exact-grade equality from a live model,
    # and even for the mock we check shape, not semantics.
    assert d.method == "llm"
    assert d.evidence_tier == "opinionated"
    assert len(d.flags) == 1
    assert d.flags[0].line == 5  # passage located back to its source line


def test_contradiction_pairs_are_sent(monkeypatch, tmp_cache):
    import litellm

    captured = {}

    def fake(**kwargs):
        captured["user"] = kwargs["messages"][1]["content"]
        return make_llm_response({"grade": "C", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    d = Judge(cache=tmp_cache).score_contradiction(parse("AGENTS.md", DOC))
    payload = json.loads(captured["user"])
    assert "directives" in payload and "candidate_pairs" in payload
    assert [0, 1] in payload["candidate_pairs"]  # tabs vs 4-spaces pair
    assert d.evidence_tier == "grounded"
    assert d.weight == 1.5


def test_cache_hit_makes_zero_calls(monkeypatch, tmp_cache):
    import litellm

    calls = {"n": 0}

    def fake(**kwargs):
        calls["n"] += 1
        return make_llm_response({"grade": "B", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    doc = parse("AGENTS.md", DOC)
    j1 = Judge(cache=tmp_cache)
    j1.score_specificity(doc)
    first = calls["n"]
    assert first >= 1

    j2 = Judge(cache=tmp_cache)
    j2.score_specificity(doc)
    assert calls["n"] == first  # second scan fully served from cache
    assert j2.cache.hits >= 1


def test_cache_key_changes_with_content():
    k1 = JudgeCache.key("m", "p", "content-a")
    k2 = JudgeCache.key("m", "p", "content-b")
    assert k1 != k2


def test_prepass_uses_cheap_model_then_judge(monkeypatch, tmp_cache):
    import litellm

    models_called = []

    def fake(**kwargs):
        models_called.append(kwargs["model"])
        if "haiku" in kwargs["model"]:
            return make_llm_response({"suspicious": [0]})
        return make_llm_response({"grade": "B", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    judge = Judge(cache=tmp_cache, prepass=True)
    judge.score_specificity(parse("AGENTS.md", DOC))
    assert any("haiku" in m for m in models_called)
    assert any("sonnet-4-5" in m for m in models_called)
    # Haiku prepass must run before the pinned judge model.
    assert "haiku" in models_called[0]


def test_malformed_llm_reply_degrades_gracefully(monkeypatch, tmp_cache):
    import litellm

    monkeypatch.setattr(
        litellm,
        "completion",
        lambda **kw: {"choices": [{"message": {"content": "not json at all"}}]},
    )
    d = Judge(cache=tmp_cache).score_specificity(parse("AGENTS.md", DOC))
    assert d.grade in "ABCDF"  # falls back rather than crashing


def test_json_in_code_fence_is_parsed():
    text = '```json\n{"grade": "A", "flags": []}\n```'
    assert Judge._parse_json(text)["grade"] == "A"


def test_worst_grade():
    assert _worst_grade(["A", "C", "B"]) == "C"
    assert _worst_grade(["A", "F"]) == "F"
    assert _worst_grade([]) == "C"


def test_no_llm_never_imports_litellm(monkeypatch, tmp_path):
    """--no-llm path: scan completes even if litellm.completion would explode.

    conftest's autouse guard already replaces litellm.completion with a
    hard failure; a judge=None scan must not trip it.
    """
    from docprobe.scanner import run_scan

    p = tmp_path / "AGENTS.md"
    p.write_text("# T\n\n- Always run tests.\n", encoding="utf-8")
    result = run_scan([str(p)], judge=None)
    assert result.llm.enabled is False
    assert result.files[0].skipped_dimensions == ["specificity", "contradiction"]
