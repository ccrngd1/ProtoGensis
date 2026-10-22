"""Effort-field mapping per provider, request body shapes, retries."""

import pytest

from ensemble_reboot.client import (
    BedrockClient,
    BedrockError,
    BedrockRetriesExhausted,
    build_effort_fields,
    build_request_body,
)
from ensemble_reboot.roster import ModelSpec


def spec(style, pid="global.test.model", levels=None, default="medium"):
    return ModelSpec(
        profile_id=pid, family="test", tier="frontier", effort_style=style,
        candidate_levels=levels or ["low", "medium", "high"], default_level=default,
    )


def test_claude_effort_field():
    assert build_effort_fields("claude", "xhigh") == {
        "output_config": {"effort": "xhigh"}
    }


def test_openai_xai_kimi_effort_is_string():
    assert build_effort_fields("openai_xai_kimi", "max") == {"reasoning_config": "max"}
    assert build_effort_fields("openai_xai_kimi", "none") == {"reasoning_config": "none"}


def test_nova_effort_field():
    assert build_effort_fields("nova", "medium") == {
        "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "medium"}
    }


def test_unknown_style_raises():
    with pytest.raises(ValueError):
        build_effort_fields("mystery", "low")


def test_nova_high_omits_max_tokens():
    body = build_request_body(spec("nova"), "hi", "high", max_tokens=32000)
    assert "inferenceConfig" not in body
    assert body["additionalModelRequestFields"]["reasoningConfig"]["maxReasoningEffort"] == "high"


def test_nova_low_keeps_max_tokens():
    body = build_request_body(spec("nova"), "hi", "low", max_tokens=32000)
    assert body["inferenceConfig"] == {"maxTokens": 32000}


def test_claude_body_keeps_max_tokens_at_max_effort():
    body = build_request_body(spec("claude"), "hi", "max", max_tokens=16000)
    assert body["inferenceConfig"] == {"maxTokens": 16000}


def test_no_temperature_sent():
    for style in ("claude", "openai_xai_kimi", "nova"):
        body = build_request_body(spec(style), "hi", "low", 1000)
        assert "temperature" not in body.get("inferenceConfig", {})


def test_grok_candidate_levels_exclude_max():
    """Roster-level invariant: grok has no max level (per smoke + REQUIREMENTS)."""
    from pathlib import Path

    from ensemble_reboot.roster import load_roster

    roster = load_roster(Path(__file__).parent.parent / "config" / "roster.yaml")
    grok = roster.by_id("global.xai.grok-4.7")
    assert "max" not in grok.candidate_levels


def test_system_prompt_included():
    body = build_request_body(spec("claude"), "hi", "low", 1000, system_prompt="be brief")
    assert body["system"] == [{"text": "be brief"}]


class FakeSession:
    """Scripted responses for retry testing."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class FakeResponse:
    def __init__(self, status_code, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


def _ok_body(text="391"):
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 5},
    }


def make_client(responses, monkeypatch, retries=4):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    return BedrockClient(
        session=FakeSession(responses), max_retries=retries, sleep=lambda s: None
    )


def test_retry_on_429_then_success(monkeypatch):
    client = make_client(
        [FakeResponse(429, text="slow down"), FakeResponse(200, _ok_body())], monkeypatch
    )
    res = client.converse(spec("claude"), "q", "low")
    assert res.status_code == 200
    assert res.text == "391"
    assert res.stop_reason == "end_turn"


def test_400_is_not_retried(monkeypatch):
    client = make_client([FakeResponse(400, text="bad field")], monkeypatch)
    with pytest.raises(BedrockError) as e:
        client.converse(spec("nova"), "q", "high")
    assert e.value.status_code == 400
    assert client._session.calls == 1


def test_retries_exhausted(monkeypatch):
    client = make_client([FakeResponse(503, text="x")] * 3, monkeypatch, retries=3)
    with pytest.raises(BedrockRetriesExhausted):
        client.converse(spec("claude"), "q", "low")


def test_truncation_detected(monkeypatch):
    body = _ok_body()
    body["stopReason"] = "max_tokens"
    client = make_client([FakeResponse(200, body)], monkeypatch)
    res = client.converse(spec("claude"), "q", "low")
    assert res.truncated


def test_token_never_in_request_params(monkeypatch):
    client = make_client([FakeResponse(200, _ok_body())], monkeypatch)
    res = client.converse(spec("claude"), "q", "low")
    import json as _json

    assert "test-token" not in _json.dumps(res.request_params)
