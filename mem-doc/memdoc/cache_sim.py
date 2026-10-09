"""CacheSimulator: deterministic model of Bedrock prefix caching (AC #5, R3).

A request is an ordered list of blocks. Each block is either content or a cache
point:

    {"text": "..."}                      content; tokens via the tokenizer
    {"tokens": 123, "key": "stable-id"}  content with precounted tokens
    {"cachePoint": True}                 cache checkpoint

Cache entries live at cache-point boundaries, keyed by the sha256 of the content
prefix up to that boundary. At each cache point the simulator finds the longest
previously written prefix (within TTL, injectable clock) among the current
request's block boundaries: tokens up to that match count as cacheRead, the
remainder up to the cache point counts as cacheWrite (if the full prefix is at
least ``min_cache_tokens``, else uncached). Tokens after the last honored cache
point are uncached input. This mirrors Converse-style caching, where moving the
cachePoint past newly appended history still hits the prefix written last call.

Consequence (AC #5b): content appended at the *tail* reads all history from
cache and writes only the new segment, while content changed at the *head*
changes every prefix hash behind it, so all history is re-written each call.

``min_cache_tokens`` / ``max_cache_points`` / ``ttl_seconds`` default from
config/pricing.toml and are flagged "verify per model" (R3): Bedrock's real
per-model minimum cacheable prefix and cachePoint limit are not verified for
every model. On the first live dry run the simulator is compared call-by-call
against returned usage fields; usage fields win (docs/CACHE_VALIDATION.md).
"""

import hashlib
from dataclasses import dataclass, field

from .tokens import ApproxTokenizer


@dataclass
class SimUsage:
    inputTokens: int = 0              # uncached input tokens
    cacheReadInputTokens: int = 0
    cacheWriteInputTokens: int = 0
    outputTokens: int = 0

    def as_dict(self):
        return {
            "inputTokens": self.inputTokens,
            "cacheReadInputTokens": self.cacheReadInputTokens,
            "cacheWriteInputTokens": self.cacheWriteInputTokens,
            "outputTokens": self.outputTokens,
        }


@dataclass
class _Entry:
    written_at: float


class CacheSimulator:
    """Deterministic prefix cache with an injectable clock.

    The clock is a plain float timestamp passed to ``simulate_call``; the
    simulator never reads wall-clock time.
    """

    def __init__(self, ttl_seconds: float = 300.0, min_cache_tokens: int = 1024,
                 max_cache_points: int = 4, tokenizer=None):
        self.ttl_seconds = ttl_seconds
        self.min_cache_tokens = min_cache_tokens
        self.max_cache_points = max_cache_points
        self._tok = tokenizer or ApproxTokenizer()
        self._cache: dict[int, _Entry] = {}
        # Prefix identity is interned trie-style: (parent_prefix_id, block_key)
        # -> prefix_id. Equal block sequences always get the same id, so this is
        # exactly equivalent to hashing the whole prefix, at O(1) per block.
        self._intern: dict[tuple[int, str], int] = {}
        self._next_id = 1

    def _prefix_id(self, parent: int, key: str) -> int:
        node = (parent, key)
        pid = self._intern.get(node)
        if pid is None:
            pid = self._next_id
            self._next_id += 1
            self._intern[node] = pid
        return pid

    def _block_tokens_and_key(self, block) -> tuple[int, str]:
        if "text" in block:
            text = block["text"]
            return self._tok.count(text), hashlib.sha256(text.encode("utf-8")).hexdigest()
        tokens = int(block["tokens"])
        key = str(block.get("key", ""))
        return tokens, f"{key}:{tokens}"

    def simulate_call(self, blocks, now: float, output_tokens: int = 0) -> SimUsage:
        """Simulate one model call at time ``now``; returns the usage split."""
        usage = SimUsage(outputTokens=output_tokens)
        # Walk the blocks once, recording (prefix_id, prefix_tokens) at every
        # block boundary so cache points can match any earlier boundary.
        boundaries = [(0, 0)]
        cache_point_positions = []
        for block in blocks:
            if block.get("cachePoint"):
                cache_point_positions.append(len(boundaries) - 1)
            else:
                tokens, key = self._block_tokens_and_key(block)
                pid = self._prefix_id(boundaries[-1][0], key)
                boundaries.append((pid, boundaries[-1][1] + tokens))

        covered = 0                 # tokens already accounted for (read/write/uncached)
        cache_points_used = 0
        for pos in cache_point_positions:
            if cache_points_used >= self.max_cache_points:
                break
            cache_points_used += 1
            cp_hash, cp_tokens = boundaries[pos]
            if cp_tokens <= covered:
                continue
            # longest previously cached prefix at or before this cache point
            hit_tokens, hit_hash = covered, None
            for h, t in boundaries[:pos + 1]:
                if t <= covered or t > cp_tokens:
                    continue
                entry = self._cache.get(h)
                if entry is not None and (now - entry.written_at) <= self.ttl_seconds:
                    if t > hit_tokens:
                        hit_tokens, hit_hash = t, h
            if hit_hash is not None:
                usage.cacheReadInputTokens += hit_tokens - covered
                self._cache[hit_hash].written_at = now  # TTL refresh on use
                covered = hit_tokens
            remainder = cp_tokens - covered
            if remainder > 0:
                if cp_tokens >= self.min_cache_tokens:
                    usage.cacheWriteInputTokens += remainder
                    self._cache[cp_hash] = _Entry(written_at=now)
                else:
                    usage.inputTokens += remainder
                covered = cp_tokens
        total = boundaries[-1][1]
        usage.inputTokens += total - covered
        return usage
