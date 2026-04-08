# Migration to Live Bedrock API Calls

## Summary

The codebase has been updated to **remove mock mode references** and clarify that all calls use **live Bedrock API** via bearer token authentication.

## What Changed

### 1. Authentication Method
- **Before:** Documentation referenced AWS IAM credentials (Access Key/Secret Key)
- **After:** Uses bearer token authentication via `AWS_BEARER_TOKEN_BEDROCK` environment variable

### 2. Mock Mode Removal
- **Before:** Documentation mentioned `mock_mode=True/False` parameter
- **After:** All references to mock mode removed - code always uses live API calls

### 3. Dependencies
- **Before:** `boto3` (AWS SDK)
- **After:** `requests` (HTTP client) - lighter weight, direct API access

## Setup Instructions

### 1. Set Bearer Token

```bash
export AWS_BEARER_TOKEN_BEDROCK=your_bearer_token_here
export AWS_DEFAULT_REGION=us-east-1
```

### 2. Install Dependencies

```bash
pip install requests
```

### 3. Test Authentication

```bash
python test_auth.py
```

Expected output:
```
============================================================
Bearer Token Authentication Test
============================================================

✓ Bearer token is set (length: XXX chars)
✓ BedrockClient initialized successfully
✓ Region: us-east-1
✓ Rate limit: 0.1s between calls

============================================================
✅ Authentication check PASSED
============================================================

Ready to run live Bedrock API calls!
```

### 4. Run Examples

```bash
# WARNING: This will incur AWS charges
python example.py
```

### 5. Run Benchmarks

```bash
# Test with 5 prompts first (cost: ~$0.05)
python benchmark/run.py --limit 5

# Full benchmark suite (cost: ~$0.50-$1.00)
python benchmark/run.py --output results/benchmark_results.json
```

## Cost Expectations

All calls now incur real AWS charges:

| Operation | Cost per call | Notes |
|-----------|---------------|-------|
| Single model (Nova Lite) | ~$0.00001 | Cheapest option |
| Ultra-cheap ensemble | ~$0.00005 | 3 cheap models + aggregator |
| Code-generation ensemble | ~$0.00074 | Mid-tier models |
| Reasoning ensemble | ~$0.00137 | 3-layer with refiners |
| Full benchmark (20 prompts) | ~$0.50-$1.00 | All configurations |

## Files Changed

### Updated Files
- `README.md` - Removed mock mode references, updated auth instructions
- `BLOG.md` - Added note about live API usage
- `example.py` - Removed `mock_mode` parameter from all calls
- `moa/models.py` - Updated pricing date to April 2026

### New Files
- `test_auth.py` - Script to verify bearer token authentication
- `MIGRATION.md` - This file

### Unchanged Files
- `moa/core.py` - Already used live API calls (no mock mode implemented)
- `moa/bedrock_client.py` - Already used bearer token authentication
- `benchmark/run.py` - Already used live API calls
- `moa/cost_tracker.py` - No changes needed
- `moa/latency_tracker.py` - No changes needed

## Key Points

1. **Mock mode never existed** in the actual implementation - it was only documented
2. The code **always used live Bedrock calls** via the shared `ensemble-shared/bedrock_client.py`
3. Bearer token authentication was **already implemented** - just not documented clearly
4. All cost and latency tracking reflects **real API usage**

## Rate Limiting

The shared Bedrock client enforces a minimum 0.1s delay between API calls (configurable). This allows ~10 QPS and prevents throttling during parallel ensemble execution.

To adjust:
```python
from moa import BedrockClient

# Custom rate limit
client = BedrockClient(region="us-east-1")
client.client.min_delay = 0.2  # 5 QPS
```

## Troubleshooting

### Error: "AWS_BEARER_TOKEN_BEDROCK environment variable not set"

```bash
export AWS_BEARER_TOKEN_BEDROCK=your_token
```

### Error: "API error 403: Forbidden"

- Check that your bearer token is valid and not expired
- Verify you have access to the models you're trying to use

### Error: "API error 429: Throttled"

- The client auto-retries with exponential backoff
- If persistent, increase the rate limit delay:
  ```python
  client.client.min_delay = 0.5  # Slower rate
  ```

### Error: Model access denied

1. Go to AWS Bedrock console
2. Navigate to "Model access"
3. Request access for the models you need
4. Wait for approval (usually instant)

## Next Steps

1. Run `python test_auth.py` to verify setup
2. Test with `python example.py` (will incur ~$0.002 in charges)
3. Run limited benchmark: `python benchmark/run.py --limit 5`
4. Review costs in AWS Cost Explorer before scaling up

## Questions?

See README.md FAQ section or open an issue.
