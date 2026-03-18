"""Shared utility functions for agents."""
from __future__ import annotations

import json
import re


def parse_json(text: str) -> dict:
    """Extract first JSON object from LLM response.

    Strips markdown fences and extracts the first {...} JSON object.
    """
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Find first { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)
