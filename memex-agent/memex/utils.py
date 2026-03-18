"""
utils.py — Shared utilities for token counting and misc helpers.
"""

import re


def estimate_tokens(text: str) -> int:
    """
    Rough token count estimate: ~4 characters per token (GPT-style).
    Good enough for tracking compression ratios without a tokenizer dependency.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def slugify(text: str) -> str:
    """Convert free-form text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "entry"


def validate_index_key(key: str) -> str:
    """
    Validate and normalise an index key.
    Expected format: [namespace:topic-slug] (brackets are optional but canonical).
    Raises ValueError for invalid keys.
    """
    key = key.strip()
    if not key:
        raise ValueError("Index key must not be empty")
    # Normalise: wrap in brackets if not already present
    if not (key.startswith("[") and key.endswith("]")):
        # Try to add brackets if key looks like "ns:slug"
        if ":" in key:
            key = f"[{key}]"
        else:
            key = f"[memex:{slugify(key)}]"
    return key


def build_indexed_summary(key: str, summary: str, archived_at: str, tokens_saved: int) -> str:
    """
    Build the compact indexed summary block that replaces the full content
    in the agent's working context after compression.
    """
    return (
        f"{key}\n"
        f"Summary: {summary}\n"
        f"Archived: {archived_at} | Tokens saved: {tokens_saved:,}"
    )
