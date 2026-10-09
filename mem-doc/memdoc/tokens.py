"""Token counting.

Offline: ApproxTokenizer, a deterministic estimate (ceil(utf8_bytes / 4)). Every
surface that prints its numbers labels them as an estimate.

Live: CountTokensClient wraps the Bedrock CountTokens API ([bedrock] extra; lazy
import, never used by tests or demos).
"""

import math

APPROX_LABEL = "estimate (ApproxTokenizer: ceil(utf8_bytes/4))"


class ApproxTokenizer:
    """Deterministic token estimate: ceil(utf8 byte length / 4)."""

    label = APPROX_LABEL

    def count(self, text: str) -> int:
        if not text:
            return 0
        return math.ceil(len(text.encode("utf-8")) / 4)


def approx_tokens(text: str) -> int:
    return ApproxTokenizer().count(text)


class CountTokensClient:
    """Bedrock CountTokens wrapper. Requires the [bedrock] extra; live only."""

    def __init__(self, region: str, model_id: str):
        import boto3  # lazy: live modules only

        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id

    def count(self, text: str) -> int:
        resp = self._client.count_tokens(
            modelId=self._model_id,
            input={"converse": {"system": [{"text": text}],
                                "messages": [{"role": "user", "content": [{"text": "hi"}]}]}},
        )
        return int(resp["inputTokens"])
