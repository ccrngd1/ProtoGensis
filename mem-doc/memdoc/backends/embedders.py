"""Embedders.

HashingEmbedder (core, deterministic): 1024-dim signed feature hashing over
normalized tokens via sha256, L2-normalized. Offline rankings are arbitrary with
respect to semantics (R4): they exercise the code path, nothing more. Every
offline surface labels them "hashing embedder, not Titan".

TitanEmbedder ([bedrock] extra, lazy import): amazon.titan-embed-text-v2:0 with
dimensions=1024, normalize=true, as in the research spike.
"""

import hashlib
import math

from ..text import tokenize

DIM = 1024


_EMBED_MEMO: dict[str, dict[int, float]] = {}
_TOKEN_VEC_MEMO: dict[str, tuple[int, float]] = {}


class HashingEmbedder:
    """Deterministic sparse embedding: dict index -> weight, L2-normalized.

    Pure function of the text, so results are memoized process-wide (the demo
    embeds the same distractor lines thousands of times across cells)."""

    name = "hashing"
    dim = DIM
    is_live = False

    def embed(self, text: str) -> dict[int, float]:
        hit = _EMBED_MEMO.get(text)
        if hit is not None:
            return hit
        acc: dict[int, float] = {}
        for tok in tokenize(text):
            tv = _TOKEN_VEC_MEMO.get(tok)
            if tv is None:
                h = hashlib.sha256(tok.encode("utf-8")).digest()
                tv = (int.from_bytes(h[:4], "big") % DIM, 1.0 if h[4] & 1 else -1.0)
                _TOKEN_VEC_MEMO[tok] = tv
            idx, sign = tv
            acc[idx] = acc.get(idx, 0.0) + sign
        norm = math.sqrt(sum(v * v for v in acc.values()))
        vec = {} if norm == 0.0 else {i: v / norm for i, v in acc.items()}
        if len(_EMBED_MEMO) < 200_000:
            _EMBED_MEMO[text] = vec
        return vec


def cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(i, 0.0) for i, v in a.items())


def to_blob(vec: dict[int, float]) -> bytes:
    """Dense little-endian float32 BLOB for sqlite storage."""
    import struct
    dense = [0.0] * DIM
    for i, v in vec.items():
        dense[i] = v
    return struct.pack(f"<{DIM}f", *dense)


def from_blob(blob: bytes) -> dict[int, float]:
    import struct
    dense = struct.unpack(f"<{DIM}f", blob)
    return {i: v for i, v in enumerate(dense) if v != 0.0}


class TitanEmbedder:
    """Live Titan v2 embeddings ([bedrock] extra). Never used by tests/demos."""

    name = "titan-v2"
    dim = DIM
    is_live = True

    def __init__(self, region: str = "us-east-1"):
        import boto3  # lazy: live modules only
        import json

        self._json = json
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def embed(self, text: str) -> dict[int, float]:
        resp = self._client.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=self._json.dumps({"inputText": text, "dimensions": DIM, "normalize": True}),
        )
        dense = self._json.loads(resp["body"].read())["embedding"]
        return {i: v for i, v in enumerate(dense) if v != 0.0}
