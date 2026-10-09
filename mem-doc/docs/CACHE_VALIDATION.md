# Cache simulator validation (R3)

**State: pending first live dry run.**

`CacheSimulator` models Bedrock prefix caching deterministically. Two of its
parameters are **not verified per model** (R3): the minimum cacheable prefix
size and the cachePoint count limit. They are parameters in
`config/pricing.toml` (`min_cache_tokens`, `max_cache_points`, `ttl_seconds`),
flagged "verify per model".

## Procedure (run on the first live dry run)

1. Run `memdoc run --live bedrock --model-id <id> --max-usd <N> --dry-run 20`.
2. For every call in the dry-run log, the runner records both the simulator's
   predicted usage split and the returned Bedrock usage fields
   (`inputTokens`, `cacheReadInputTokens`, `cacheWriteInputTokens`,
   `outputTokens`).
3. Compare call by call. Record here, per model ID:
   - total predicted vs observed cacheRead / cacheWrite / uncached;
   - every call where the split classifications disagree, with the block layout
     that produced it;
   - the inferred per-model `min_cache_tokens` and cachePoint limit.
4. **If they disagree, the usage fields win.** Correct the simulator, re-run its
   tests, and update `config/pricing.toml` with the verified per-model values.

## Results

_None yet. No live run has been made._
