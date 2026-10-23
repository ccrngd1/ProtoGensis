"""Silent retries are no longer silent, and ambiguous attempts are charged.

Timeouts / connection errors AFTER the request was sent may still be billed
by Bedrock even though no response arrived. The client now records every
failed attempt (kind + reason + ambiguous flag) on both the successful result
and on BedrockRetriesExhausted, logs each retry, and PilotRunner settles a
conservative worst-case charge per ambiguous attempt, surfaced in
guard.status() as ambiguous_attempts / ambiguous_charge_usd.
"""

import pytest
import requests

from ensemble_reboot.budget import BudgetGuard
from ensemble_reboot.client import (
    BedrockClient,
    BedrockRetriesExhausted,
    ConverseResult,
)
from ensemble_reboot.pilot import PilotRunner, PlannedCall
from ensemble_reboot.pricing import Price, PricingTable
from ensemble_reboot.records import RecordStore
from ensemble_reboot.roster import ModelSpec, Roster
from tests.test_client_effort import FakeResponse, FakeSession, _ok_body, spec


def make_client(responses, monkeypatch, retries=4, log=None):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token")
    return BedrockClient(session=FakeSession(responses), max_retries=retries,
                         sleep=lambda s: None, log=log or (lambda *a: None))


# ------------------------------------------------------- client attempt history

def test_attempts_recorded_on_success(monkeypatch):
    client = make_client(
        [requests.exceptions.ReadTimeout("read timed out"),
         FakeResponse(429, text="slow down"),
         FakeResponse(200, _ok_body())],
        monkeypatch,
    )
    res = client.converse(spec("claude"), "q", "low")
    assert res.status_code == 200
    assert len(res.attempts) == 2
    assert res.attempts[0]["ambiguous"] is True          # sent, no response
    assert "ReadTimeout" in res.attempts[0]["reason"]
    assert res.attempts[1]["ambiguous"] is False         # 429 => not billed
    assert res.attempts[1]["kind"] == "http-429"


def test_attempts_on_retries_exhausted(monkeypatch):
    client = make_client(
        [requests.exceptions.ConnectionError("reset"),
         FakeResponse(503, text="x")],
        monkeypatch, retries=2,
    )
    with pytest.raises(BedrockRetriesExhausted) as e:
        client.converse(spec("claude"), "q", "low")
    assert len(e.value.attempts) == 2
    assert e.value.attempts[0]["ambiguous"] is True
    assert e.value.attempts[1]["ambiguous"] is False


def test_connect_timeout_is_unambiguous(monkeypatch):
    """A connect timeout means the request never reached the server: not
    billable, so not an ambiguous attempt."""
    client = make_client(
        [requests.exceptions.ConnectTimeout("no route"),
         FakeResponse(200, _ok_body())],
        monkeypatch,
    )
    res = client.converse(spec("claude"), "q", "low")
    assert len(res.attempts) == 1
    assert res.attempts[0]["ambiguous"] is False
    assert res.attempts[0]["kind"] == "connect-timeout"


def test_retries_are_logged(monkeypatch):
    logged = []
    client = make_client(
        [requests.exceptions.ReadTimeout("t"),
         FakeResponse(429, text="x"),
         FakeResponse(200, _ok_body())],
        monkeypatch, log=logged.append,
    )
    client.converse(spec("claude"), "q", "low")
    assert len(logged) == 2
    assert "AMBIGUOUS" in logged[0]
    assert "not billed" in logged[1]


# ------------------------------------------- runner settlement of ambiguous cost

class FakeItem:
    item_id = "q1"
    item_sha256 = "x"
    prompt = "pick a letter"
    correct_letter = "A"


class RetryingClient:
    """One ambiguous timeout, one unambiguous 429, then success."""

    def __init__(self, fail_terminally=False):
        self.fail_terminally = fail_terminally

    def converse(self, spec, prompt, level, max_tokens=1000, system_prompt=None):
        attempts = [
            {"attempt": 0, "kind": "ReadTimeout", "reason": "t", "ambiguous": True},
            {"attempt": 1, "kind": "http-429", "reason": "x", "ambiguous": False},
        ]
        if self.fail_terminally:
            raise BedrockRetriesExhausted("gone", attempts=attempts)
        return ConverseResult(
            status_code=200, text="Answer: A", stop_reason="end_turn",
            usage={"inputTokens": 10, "outputTokens": 20},
            latency_s=0.1, request_params={"inferenceConfig": {}},
            attempts=attempts,
        )


def make_runner(tmp_path, client):
    mspec = ModelSpec(profile_id="m1", family="fam", tier="frontier",
                      effort_style="claude", candidate_levels=["high"],
                      default_level="high")
    roster = Roster(region="us-east-1", models=[mspec],
                    default_max_tokens=1000, arms={})
    pricing = PricingTable({"m1": Price(input=10.0, output=50.0,
                                        cache_read=None, status="OK")})
    store = RecordStore(tmp_path, "run1")
    guard = BudgetGuard(cap_usd=100.0)
    runner = PilotRunner(roster, pricing, store, guard, client,
                         {"gpqa": [FakeItem()]}, max_workers=1)
    return runner, guard, store


def worst_case_usd():
    # est input: len("pick a letter")//2 = 6 tokens; output 1000 max_tokens
    return (6 * 10.0 + 1000 * 50.0) / 1e6


def test_ambiguous_attempt_charged_on_success(tmp_path):
    runner, guard, store = make_runner(tmp_path, RetryingClient())
    call = PlannedCall("stage0", "a1", "gpqa", "q1", "m1", "high", 0)
    rec = runner.execute_call(call, FakeItem.prompt, None)
    s = guard.status()
    # exactly ONE ambiguous attempt charged (the 429 is logged only)
    assert s["ambiguous_attempts"] == 1
    assert s["ambiguous_charge_usd"] == pytest.approx(worst_case_usd(), abs=1e-4)
    # the real call cost is settled on top of the ambiguous charge
    real = (10 * 10.0 + 20 * 50.0) / 1e6
    assert s["spent_conservative_usd"] == pytest.approx(
        worst_case_usd() + real, abs=1e-4)
    # retry history lands in the record
    assert rec["request_params"]["retry_attempts"][0]["kind"] == "ReadTimeout"
    assert len(rec["request_params"]["retry_attempts"]) == 2


def test_ambiguous_attempt_charged_on_exhausted(tmp_path):
    runner, guard, _ = make_runner(tmp_path, RetryingClient(fail_terminally=True))
    call = PlannedCall("stage0", "a1", "gpqa", "q1", "m1", "high", 0)
    with pytest.raises(BedrockRetriesExhausted):
        runner.execute_call(call, FakeItem.prompt, None)
    s = guard.status()
    assert s["ambiguous_attempts"] == 1
    assert s["ambiguous_charge_usd"] == pytest.approx(worst_case_usd(), abs=1e-4)


def test_guard_status_has_ambiguous_fields():
    g = BudgetGuard(cap_usd=10.0)
    s = g.status()
    assert s["ambiguous_attempts"] == 0
    assert s["ambiguous_charge_usd"] == 0.0
    g.settle_ambiguous(1.25)
    s = g.status()
    assert s["ambiguous_attempts"] == 1
    assert s["ambiguous_charge_usd"] == 1.25
    # it counts toward the cap
    assert s["spent_conservative_usd"] == 1.25
