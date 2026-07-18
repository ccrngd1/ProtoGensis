"""Optional LLM behavioral simulation (FR6).

`--simulate` asks a model: "describe exactly what an agent would do at startup
reading this file, and rate each behavior BENIGN / SUSPICIOUS / MALICIOUS
against a clean-config baseline." The result is ADVISORY and clearly labeled
non-deterministic; it augments, never overrides, static findings (FR6.3).

Design constraints honored here:
  * No API key / no boto3 -> simulation cleanly disabled; static scan still runs
    (FR6.2). Nothing in the baseline scan path imports boto3.
  * Cost guard: callers only simulate files that already have findings unless
    --simulate-all is passed (enforced in cli.py) (FR6.4).
  * Model + region configurable via env / constructor.

IMPORTANT (benchmark honesty): this module ships the simulation *capability*.
Its accuracy against real LLMs has NOT been benchmarked. Do not infer detection
rates from it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# The research §8.4 prompt, inlined (no external baseline file needed for MVP).
SIMULATION_PROMPT = """\
You are a security analyst simulating an AI coding agent's startup.

Below is the FULL contents of a setup/config file that an AI coding agent reads
at initialization time (before any user task). A CLEAN config file only provides
neutral project context (build commands, code style, directory layout) and never
changes the agent's identity, exfiltrates data, rebinds tools to custom sources,
writes to durable memory unprompted, or installs conditional/hidden behavior.

Describe EXACTLY what an agent would do at startup as a direct result of reading
this file. For each distinct behavior, output one JSON object with fields:
  - "behavior": short description of the action the agent would take
  - "rating": one of BENIGN, SUSPICIOUS, MALICIOUS (vs. the clean baseline above)
  - "reason": why it diverges (or not) from a clean config

Return ONLY a JSON array of these objects. Be concrete; quote the triggering text.

FILE: {filename}
---
{content}
---
"""

_VALID_RATINGS = {"BENIGN", "SUSPICIOUS", "MALICIOUS"}


@dataclass
class Behavior:
    behavior: str
    rating: str
    reason: str


@dataclass
class SimulationResult:
    file: str
    available: bool
    behaviors: list = field(default_factory=list)  # list[Behavior]
    error: str | None = None
    model: str | None = None

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "available": self.available,
            "model": self.model,
            "error": self.error,
            "advisory": True,
            "non_deterministic": True,
            "behaviors": [
                {"behavior": b.behavior, "rating": b.rating, "reason": b.reason}
                for b in self.behaviors
            ],
        }

    @property
    def worst_rating(self) -> str | None:
        order = {"BENIGN": 0, "SUSPICIOUS": 1, "MALICIOUS": 2}
        rated = [b.rating for b in self.behaviors if b.rating in order]
        if not rated:
            return None
        return max(rated, key=lambda r: order[r])


def is_available() -> bool:
    """True only if boto3 is importable (creds are checked at call time)."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


class Simulator:
    """Thin Bedrock client wrapper. Degrades gracefully with no creds/lib."""

    def __init__(
        self,
        *,
        model: str | None = None,
        region: str | None = None,
    ):
        # Default to a current Claude model on Bedrock; overridable via env.
        self.model = (
            model
            or os.environ.get("SETUP_TRAP_SIM_MODEL")
            or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        self.region = (
            region or os.environ.get("AWS_REGION") or "us-east-1"
        )
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        import boto3  # imported lazily — never on the baseline scan path

        self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def simulate_text(self, filename: str, content: str) -> SimulationResult:
        if not is_available():
            return SimulationResult(
                file=filename,
                available=False,
                error="boto3 not installed; run `pip install -e '.[simulate]'` "
                "and configure AWS credentials to enable --simulate.",
            )
        prompt = SIMULATION_PROMPT.format(
            filename=filename, content=content[:20000]
        )
        try:
            client = self._get_client()
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1500,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            resp = client.invoke_model(modelId=self.model, body=body)
            payload = json.loads(resp["body"].read())
            text = "".join(
                blk.get("text", "")
                for blk in payload.get("content", [])
                if blk.get("type") == "text"
            )
            behaviors = _parse_behaviors(text)
            return SimulationResult(
                file=filename,
                available=True,
                behaviors=behaviors,
                model=self.model,
            )
        except Exception as exc:  # noqa: BLE001 — advisory layer, never fatal
            return SimulationResult(
                file=filename,
                available=False,
                error=f"simulation failed ({type(exc).__name__}): {exc}",
                model=self.model,
            )

    def simulate_file(self, path) -> SimulationResult:
        from pathlib import Path

        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return SimulationResult(
                file=str(p), available=False, error=f"could not read file: {exc}"
            )
        return self.simulate_text(p.name, content)


def _parse_behaviors(text: str) -> list:
    """Extract the JSON array of behaviors from the model output, tolerantly."""
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        rating = str(item.get("rating", "")).upper()
        if rating not in _VALID_RATINGS:
            rating = "SUSPICIOUS"
        out.append(
            Behavior(
                behavior=str(item.get("behavior", "")),
                rating=rating,
                reason=str(item.get("reason", "")),
            )
        )
    return out
