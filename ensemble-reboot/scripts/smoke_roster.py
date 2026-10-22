#!/usr/bin/env python3
"""Smoke-test the ensemble-reboot roster on Bedrock Converse.

For each model, sends one tiny prompt at the lowest and highest supported
reasoning/effort level and records: HTTP status, answer, token usage, latency.
Uses AWS_BEARER_TOKEN_BEDROCK (Bedrock API key). Cheap: ~2 calls per model.
"""
import json
import os
import sys
import time

import requests

REGION = "us-east-1"
TOKEN = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
PROMPT = "What is 17 * 23? Reply with only the number."
EXPECTED = "391"

# (profile id, effort-field style, levels to test)
#   effort  -> {"output_config": {"effort": L}}      (Claude 5.5 family, Fable 5.1)
#   reason  -> {"reasoning_config": L}               (OpenAI GPT-6.x, xAI, Kimi)
#   nova    -> {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": L}}
ROSTER = [
    ("global.anthropic.claude-fable-5-1", "effort", ["low", "max"]),
    ("global.anthropic.claude-opus-5-5", "effort", ["low", "max"]),
    ("global.anthropic.claude-sonnet-5-5", "effort", ["low", "max"]),
    ("global.anthropic.claude-haiku-5-5", "effort", ["low", "max"]),
    ("global.openai.gpt-6-astra", "reason", ["low", "max"]),
    ("global.openai.gpt-6.1-sol", "reason", ["low", "max"]),
    ("global.openai.gpt-6-luna", "reason", ["none", "max"]),
    ("global.xai.grok-4.7", "reason", ["low", "xhigh"]),
    ("global.moonshotai.kimi-k3", "reason", ["none", "max"]),
    ("global.amazon.nova-2-lite-v1:0", "nova", ["low", "high"]),
]


def extra_fields(style, level):
    if style == "effort":
        return {"output_config": {"effort": level}}
    if style == "reason":
        return {"reasoning_config": level}
    if style == "nova":
        return {"reasoningConfig": {"type": "enabled", "maxReasoningEffort": level}}
    return {}


def call(model, style, level):
    url = f"https://bedrock-runtime.{REGION}.amazonaws.com/model/{requests.utils.quote(model, safe='')}/converse"
    body = {
        "messages": [{"role": "user", "content": [{"text": PROMPT}]}],
        "inferenceConfig": {"maxTokens": 16000},
        "additionalModelRequestFields": extra_fields(style, level),
    }
    t0 = time.time()
    r = requests.post(url, json=body, timeout=300,
                      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    dt = time.time() - t0
    out = {"model": model, "level": level, "status": r.status_code, "latency_s": round(dt, 1)}
    if r.status_code != 200:
        out["error"] = r.text[:300]
        return out
    j = r.json()
    text = " ".join(c.get("text", "") for c in j["output"]["message"]["content"] if "text" in c).strip()
    out["answer"] = text[:40]
    out["correct"] = EXPECTED in text
    out["usage"] = j.get("usage", {})
    return out


def main():
    results = []
    for model, style, levels in ROSTER:
        for level in levels:
            try:
                res = call(model, style, level)
            except Exception as e:  # network etc.
                res = {"model": model, "level": level, "status": "EXC", "error": str(e)[:200]}
            results.append(res)
            print(json.dumps(res), flush=True)
    path = sys.argv[1] if len(sys.argv) > 1 else "smoke_results.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
