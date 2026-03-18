"""
compress.py — Compression engine: calls Haiku 4.5 via boto3 Bedrock to
produce a compact summary of verbose agent content, then archives the
full content in the SQLite store and updates the JSON manifest.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import boto3
import botocore

from .store import ExperienceStore
from .manifest import IndexManifest
from .utils import estimate_tokens, build_indexed_summary

logger = logging.getLogger(__name__)

# The actual Bedrock model ID (without the routing prefix)
_BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Cached boto3 client for AWS Bedrock
_AWS_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
_BEDROCK_CLIENT = None


def _get_bedrock_client():
    """Get or create cached boto3 Bedrock client."""
    global _BEDROCK_CLIENT
    if _BEDROCK_CLIENT is None:
        _BEDROCK_CLIENT = boto3.client("bedrock-runtime", region_name=_AWS_REGION)
    return _BEDROCK_CLIENT

_COMPRESSION_SYSTEM_PROMPT = """You are a compression engine for an AI agent's memory system.

Your job is to produce a compact, information-dense summary of the provided content.
The summary will serve as an indexed placeholder in the agent's working context.

Rules:
1. Preserve all key facts, decisions, and actionable findings
2. Drop verbatim quotes, redundant explanations, and filler text
3. Use terse, information-dense language (like a developer's notes)
4. Target 100-200 tokens (roughly 400-800 characters)
5. Start with the most important finding or outcome
6. Never include meta-commentary like "This document discusses..." — just the facts

Output ONLY the summary text. No preamble, no explanation."""


def _call_bedrock_haiku(content: str, context: Optional[str] = None) -> str:
    """
    Call Claude Haiku 4.5 via AWS Bedrock to compress content.
    Returns the summary string.
    """
    client = _get_bedrock_client()

    user_message = content
    if context:
        user_message = f"Context: {context}\n\n---\n\nContent to compress:\n{content}"

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "system": _COMPRESSION_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }

    try:
        response = client.invoke_model(
            modelId=_BEDROCK_MODEL_ID,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"].strip()
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as e:
        logger.error("Bedrock call failed: %s", e)
        raise


class CompressionEngine:
    """
    Orchestrates the full compress_experience operation:
    1. Call Haiku to produce a summary
    2. Archive full content in SQLite
    3. Update the JSON manifest
    4. Return the compact indexed summary block
    """

    def __init__(
        self,
        store: ExperienceStore,
        manifest: IndexManifest,
        bedrock_caller=None,
    ):
        self.store = store
        self.manifest = manifest
        # Allow injection of a custom caller (useful for testing)
        self._call_llm = bedrock_caller or _call_bedrock_haiku

    def compress(
        self,
        content: str,
        index_key: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Compress the given content, archive it, and return a compact indexed
        summary block ready to replace the original content in working context.

        Args:
            content:    The full verbose content to compress.
            index_key:  The index key (e.g. "[research:oauth-libs]").
            context:    Optional hint about what this content is about.

        Returns:
            Compact indexed summary string (~100-200 tokens).
        """
        logger.info("Compressing experience: %s", index_key)

        # 1. Generate summary via Haiku
        summary = self._call_llm(content, context)
        archived_at = datetime.now(timezone.utc).isoformat()

        # 2. Count tokens
        tokens_original = estimate_tokens(content)
        tokens_summary = estimate_tokens(summary)
        tokens_saved = max(0, tokens_original - tokens_summary)

        # 3. Archive to SQLite
        self.store.archive(
            key=index_key,
            full_content=content,
            summary=summary,
            token_count_original=tokens_original,
            token_count_summary=tokens_summary,
            metadata={"context": context} if context else {},
        )

        # 4. Update manifest
        self.manifest.add_entry(
            key=index_key,
            summary=summary,
            tokens_saved=tokens_saved,
            archived_at=archived_at,
        )

        # 5. Build and return the compact indexed block
        return build_indexed_summary(index_key, summary, archived_at, tokens_saved)
