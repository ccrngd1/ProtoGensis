"""Bedrock Converse HTTP client with per-provider effort mapping.

The bearer token comes from AWS_BEARER_TOKEN_BEDROCK and is never logged,
printed, or stored in records. Request shapes match the verified smoke test
(results/smoke_2026-10-22.json).

Effort mapping (additionalModelRequestFields):
  claude           -> {"output_config": {"effort": L}}
  openai_xai_kimi  -> {"reasoning_config": L}        (string; grok has no max)
  nova             -> {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": L}}
                      and at L == "high" inferenceConfig.maxTokens must be OMITTED
                      (Bedrock returns 400 otherwise).

temperature is NOT sent to reasoning models; seeds are independent samples
identified by a seed index recorded alongside each record.
"""

import os
import random
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from .roster import ModelSpec

TOKEN_ENV = "AWS_BEARER_TOKEN_BEDROCK"

# xhigh/max reasoning can take minutes.
DEFAULT_TIMEOUT_S = 1800
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 6


class BedrockError(Exception):
    """Non-retryable Bedrock API error (e.g. 400)."""

    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        super().__init__(f"HTTP {status_code}: {text[:300]}")


class BedrockRetriesExhausted(Exception):
    pass


def build_effort_fields(effort_style: str, level: str) -> dict:
    if effort_style == "claude":
        return {"output_config": {"effort": level}}
    if effort_style == "openai_xai_kimi":
        return {"reasoning_config": level}
    if effort_style == "nova":
        return {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": level}}
    raise ValueError(f"unknown effort_style {effort_style!r}")


def build_request_body(
    spec: ModelSpec,
    prompt: str,
    level: str,
    max_tokens: int,
    system_prompt: str | None = None,
) -> dict:
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "additionalModelRequestFields": build_effort_fields(spec.effort_style, level),
    }
    # Nova 2 at high: omit maxTokens entirely (400 otherwise).
    if not (spec.effort_style == "nova" and level == "high"):
        body["inferenceConfig"] = {"maxTokens": max_tokens}
    if system_prompt:
        body["system"] = [{"text": system_prompt}]
    return body


@dataclass
class ConverseResult:
    status_code: int
    text: str                 # concatenated text blocks (reasoningContent skipped)
    stop_reason: str | None
    usage: dict
    latency_s: float
    error_text: str | None = None
    request_params: dict = field(default_factory=dict)  # body sans token

    @property
    def truncated(self) -> bool:
        return self.stop_reason == "max_tokens"

    @property
    def input_tokens(self) -> int:
        return int(self.usage.get("inputTokens", 0))

    @property
    def output_tokens(self) -> int:
        return int(self.usage.get("outputTokens", 0))

    @property
    def cache_read_tokens(self) -> int:
        return int(self.usage.get("cacheReadInputTokens", 0))


class BedrockClient:
    """Thread-safe Converse client with retries and per-model concurrency limits."""

    def __init__(
        self,
        region: str = "us-east-1",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        per_model_concurrency: int = 4,
        session: requests.Session | None = None,
        sleep=time.sleep,
    ):
        token = os.environ.get(TOKEN_ENV)
        if not token:
            raise ValueError(f"{TOKEN_ENV} is not set")
        self._token = token
        self.region = region
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.per_model_concurrency = per_model_concurrency
        self._session = session or requests.Session()
        self._sleep = sleep
        self._sems: dict[str, threading.Semaphore] = {}
        self._sems_lock = threading.Lock()

    def _sem(self, profile_id: str, limit: int) -> threading.Semaphore:
        with self._sems_lock:
            if profile_id not in self._sems:
                self._sems[profile_id] = threading.Semaphore(limit)
            return self._sems[profile_id]

    def converse(
        self,
        spec: ModelSpec,
        prompt: str,
        level: str,
        max_tokens: int = 32000,
        system_prompt: str | None = None,
    ) -> ConverseResult:
        """One Converse call with retries on 429/5xx/timeouts.

        Raises BedrockError on non-retryable HTTP errors (e.g. 400) and
        BedrockRetriesExhausted when retries run out.
        """
        body = build_request_body(spec, prompt, level, max_tokens, system_prompt)
        url = (
            f"https://bedrock-runtime.{self.region}.amazonaws.com"
            f"/model/{quote(spec.profile_id, safe='')}/converse"
        )
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        limit = getattr(spec, "concurrency", None) or self.per_model_concurrency
        sem = self._sem(spec.profile_id, limit)
        last_err = None
        with sem:
            for attempt in range(self.max_retries):
                if attempt:
                    # Exponential backoff with jitter: 1-2s, 2-4s, 4-8s, ...
                    backoff = (2 ** (attempt - 1)) * (1.0 + random.random())
                    self._sleep(backoff)
                t0 = time.time()
                try:
                    resp = self._session.post(
                        url, json=body, headers=headers, timeout=self.timeout_s
                    )
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    last_err = f"{type(e).__name__}: {e}"
                    continue
                latency = time.time() - t0
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("output", {}).get("message", {}).get("content", [])
                    text = "\n".join(c["text"] for c in content if "text" in c)
                    return ConverseResult(
                        status_code=200,
                        text=text,
                        stop_reason=data.get("stopReason"),
                        usage=data.get("usage", {}),
                        latency_s=latency,
                        request_params=body,
                    )
                if resp.status_code in RETRYABLE_STATUS:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    continue
                raise BedrockError(resp.status_code, resp.text)
        raise BedrockRetriesExhausted(
            f"{spec.profile_id} level={level}: retries exhausted; last error: {last_err}"
        )

    def probe(self, spec: ModelSpec, level: str, max_tokens: int = 16000) -> ConverseResult:
        """Tiny call used by scripts/probe_levels.py. Returns a ConverseResult
        with status 400 info instead of raising, so the probe can record it."""
        try:
            return self.converse(
                spec, "What is 17 * 23? Reply with only the number.", level, max_tokens
            )
        except BedrockError as e:
            return ConverseResult(
                status_code=e.status_code,
                text="",
                stop_reason=None,
                usage={},
                latency_s=0.0,
                error_text=e.text[:500],
            )
