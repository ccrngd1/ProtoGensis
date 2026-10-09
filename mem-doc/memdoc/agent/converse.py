"""Bedrock Converse codec + live loop ([bedrock] extra; AC #13).

The codec (request/response <-> internal dicts) is pure and tested offline
against JSON fixtures (tests/fixtures/converse/). boto3 imports lazily, only
inside LiveRunner, so the core stays stdlib-only.

Live runs are optional, budget-capped, re-scorable offline:
- --max-usd is required; the runner sums per-call cost from usage fields and
  aborts cleanly (exit 5, partial log kept, marked ABORTED_BUDGET) before the
  next call would cross the cap.
- usage fields are copied verbatim into call events (source=bedrock_usage).
- retries on throttling use exponential backoff and are logged; a retried call's
  usage is recorded once per successful response; failed calls log zero usage.
"""

from dataclasses import dataclass, field

USAGE_FIELDS = ("inputTokens", "cacheReadInputTokens", "cacheWriteInputTokens",
                "outputTokens")


# ------------------------------------------------------------------- codec

def encode_request(system_prefix: str, messages: list, tools: list,
                   max_tokens: int = 1024) -> dict:
    """Build a Converse request with a cachePoint after the system prefix."""
    req = {
        "system": [{"text": system_prefix}, {"cachePoint": {"type": "default"}}],
        "messages": [{"role": m["role"], "content": [{"text": m["text"]}]}
                     for m in messages],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if tools:
        req["toolConfig"] = {"tools": [
            {"toolSpec": {"name": t.name, "description": t.description,
                          "inputSchema": {"json": {"type": "object", "properties": {
                              k: {"type": "string"} for k in t.input_schema}}}}}
            for t in tools]}
    return req


def decode_response(resp: dict) -> dict:
    """Extract text, tool uses, stop reason, and usage (verbatim)."""
    msg = resp.get("output", {}).get("message", {})
    text_parts, tool_uses = [], []
    for block in msg.get("content", []):
        if "text" in block:
            text_parts.append(block["text"])
        elif "toolUse" in block:
            tu = block["toolUse"]
            tool_uses.append({"toolUseId": tu.get("toolUseId", ""),
                              "name": tu.get("name", ""),
                              "input": tu.get("input", {})})
    usage = {k: int(resp.get("usage", {}).get(k, 0)) for k in USAGE_FIELDS}
    return {"text": "\n".join(text_parts), "tool_uses": tool_uses,
            "stop_reason": resp.get("stopReason", ""), "usage": usage}


def encode_tool_result(tool_use_id: str, content: str) -> dict:
    return {"role": "user",
            "content": [{"toolResult": {"toolUseId": tool_use_id,
                                        "content": [{"text": content}]}}]}


# ----------------------------------------------------------------- live loop

@dataclass
class BudgetTracker:
    max_usd: float
    spent: float = 0.0
    aborted: bool = False

    def would_exceed(self, next_call_estimate: float) -> bool:
        return self.spent + next_call_estimate > self.max_usd

    def charge(self, usd: float):
        self.spent += usd


class LiveRunner:
    """Minimal live loop: fresh context per session, usage copied verbatim.

    Never invoked by tests. Requires the [bedrock] extra and credentials."""

    def __init__(self, model_id: str, region: str, max_usd: float, log, prices,
                 max_retries: int = 5):
        import boto3  # lazy: [bedrock] extra, live modules only

        self._client = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
        self.budget = BudgetTracker(max_usd=max_usd)
        self.log = log
        self.prices = prices
        self.max_retries = max_retries
        self._avg_call_usd = 0.01   # refined from observed usage as calls land

    def converse(self, request: dict, meta: dict) -> dict | None:
        """One budget-gated call. Returns decoded response or None on abort."""
        import time as _time
        from ..cost import call_cost

        if self.budget.would_exceed(self._avg_call_usd):
            self.budget.aborted = True
            self.log.write({"event": "abort", "reason": "ABORTED_BUDGET",
                            "spent_usd": round(self.budget.spent, 4), **meta})
            return None
        delay = 1.0
        for attempt in range(self.max_retries):
            try:
                resp = self._client.converse(modelId=self.model_id, **request)
                break
            except Exception as e:  # throttling / transient
                name = type(e).__name__
                self.log.write({"event": "retry", "attempt": attempt, "error": name,
                                **meta})
                if attempt == self.max_retries - 1:
                    self.log.write({"event": "call", "source": "bedrock_usage",
                                    "failed": True,
                                    **{k: 0 for k in USAGE_FIELDS}, **meta})
                    return None
                _time.sleep(delay)
                delay *= 2
        decoded = decode_response(resp)
        usd = call_cost(decoded["usage"], self.prices)
        self.budget.charge(usd)
        self._avg_call_usd = max(self._avg_call_usd, usd)
        self.log.write({"event": "call", "source": "bedrock_usage",
                        **decoded["usage"], **meta})
        return decoded
