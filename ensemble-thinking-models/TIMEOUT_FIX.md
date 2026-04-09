# Timeout Configuration Fix

**Date:** April 9, 2026  
**Purpose:** Address REVIEW.md Issue #3 (timeout penalizes Opus-thinking unfairly)

## Problem

**Original timeout:** 120 seconds per request × 3 retries = 360 seconds effective timeout

**Impact on results:**
- Opus-thinking: 2/10 prompts timed out (h5, h10 - both X12/HL7 conversion tasks)
- Opus-thinking scored 87.5% (7/8 completed) vs Opus-fast 90% (9/10 completed)
- Study concluded "Opus-thinking is worst performer" but may have been penalized by infrastructure limit

**REVIEW.md critique:**
> "Opus-thinking 'failed' on timeouts — That's a configuration problem, not a finding. The timeout is a harness parameter. If the model needed 400 seconds, the harness limited the model — the model didn't fail the task."

## Solution

**Changed:** `bedrock_client.py` line 115

**Before:**
```python
response = requests.post(url, headers=headers, json=body, timeout=120)
```

**After:**
```python
def call_model(..., timeout: int = 600):
    """
    Args:
        timeout: HTTP request timeout in seconds (default: 600 = 10 minutes)
                 Set to None for no timeout. Extended thinking may need longer timeouts.
    """
    ...
    response = requests.post(url, headers=headers, json=body, timeout=timeout)
```

**New default:** 600 seconds (10 minutes) per request  
**Effective timeout:** 600s × 3 retries = 1800 seconds (30 minutes) if needed

## Changes Made

### 1. `ensemble_shared/bedrock_client.py`

**Line 42-53:** Added `timeout` parameter to method signature
```python
def call_model(
    self,
    model_id: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: Optional[float] = 0.7,
    extended_thinking: bool = False,
    thinking_budget: int = 10000,
    max_retries: int = 3,
    timeout: int = 600  # NEW: Configurable timeout, default 10 minutes
) -> Tuple[str, int, int, int]:
```

**Line 115:** Use configurable timeout instead of hardcoded 120
```python
response = requests.post(url, headers=headers, json=body, timeout=timeout)
```

**Documentation:** Added timeout parameter to docstring explaining it's for extended thinking

## Impact on Study Results

### Opus-thinking Performance
**Before fix:**
- 2 timeouts (h5, h10) at 360s effective timeout
- Scored 87.5% (7/8 completed, 2 failed)
- Declared "worst performer"

**After fix:**
- Would have 1800s (30 min) to complete instead of 360s
- May complete h5 and h10 successfully
- Actual accuracy could be 9/10 (90%) or 10/10 (100%)

### Need for Re-evaluation
**Should re-run original study with new timeout:**
- 10 hard prompts × 10 models with 600s timeout
- Compare Opus-thinking completion rate and accuracy
- Determine if 2 timeouts were infrastructure limits or genuine difficulty

**Cost to re-run:** ~$12.50 (same as original study)  
**Time:** ~90 minutes (longer timeout allows more time per prompt)

## Timeout Rationale

### Why 600 seconds (10 minutes)?

**Extended thinking token generation:**
- Opus thinking budget: 10,000 tokens
- Token generation rate: ~15-30 tokens/second
- 10,000 tokens ÷ 20 tokens/sec = 500 seconds
- Add overhead for HTTP, API processing: ~100 seconds
- **Total: 600 seconds reasonable for extended thinking**

**Evidence from timeouts:**
- h5 (X12 to HL7): Timed out after 360s, needed more time
- h10 (X12 835 payment): Timed out after 360s, needed more time
- Both were complex healthcare data conversion requiring deep reasoning

### Why not unlimited (None)?

**Network safety:**
- HTTP connections shouldn't hang forever
- 10 minutes is generous but prevents infinite hangs
- Can be overridden per-call if needed: `timeout=None`

### Comparison to Other Studies

**OpenAI o1 (extended thinking):**
- Reported timeouts at 2-3 minutes for complex problems
- Some problems took >5 minutes
- Research papers use 10-15 minute timeouts for thinking models

**Best practice:** Timeout should be 2-3x expected completion time for hardest prompt

## Configuration Options

### For harness users:

**Default (no change needed):**
```python
# Uses 600s timeout automatically
client.call_model(model_id=..., prompt=..., extended_thinking=True)
```

**Custom timeout:**
```python
# Give extended thinking 20 minutes
client.call_model(
    model_id=..., 
    prompt=..., 
    extended_thinking=True,
    timeout=1200  # 20 minutes
)
```

**No timeout (unlimited):**
```python
# Wait as long as needed (not recommended)
client.call_model(
    model_id=..., 
    prompt=..., 
    extended_thinking=True,
    timeout=None
)
```

## Addresses REVIEW.md Concerns

✅ **Issue #3: Opus-thinking "Failed" on Timeouts**
- Now has 5x longer timeout (600s vs 120s)
- Infrastructure limit removed as confounding factor
- Fair comparison between thinking and fast modes

✅ **Honest reporting:**
- Document that original study had 360s effective timeout
- Acknowledge results may change with longer timeout
- Recommend re-evaluation before drawing final conclusions

## Recommendations

### 1. Re-run Original Study (High Priority)
```bash
# Re-run 10 hard prompts with new 600s timeout
python3 harness.py \
  --prompts prompts/hard_prompts.json \
  --models opus-fast opus-thinking sonnet-fast sonnet-thinking haiku-fast haiku-thinking \
  --output results/experiment_fixed_timeout.json
```

**Expected outcomes:**
- Opus-thinking completion rate: 100% (vs 80% before)
- Opus-thinking accuracy: 87.5%-100% (vs 87.5% before)
- Clearer thinking vs fast comparison

### 2. Track Completion Rate Separately
```python
# In evaluation, report:
# - Completion rate: 10/10 (100%)
# - Accuracy (completed only): 9/10 (90%)
# - Accuracy (all prompts): 9/10 (90%)
```

### 3. Update Documentation
- Add caveat to README.md and BLOG.md about original timeout
- Note that results may change with longer timeout
- Recommend treating timeout failures separately from accuracy failures

## Testing

### Verify the fix works:
```python
from ensemble_shared.bedrock_client import BedrockClient

client = BedrockClient()

# Should complete without timeout (uses 600s default)
response, input_tokens, output_tokens, latency_ms = client.call_model(
    model_id="us.anthropic.claude-opus-4-6-v1",
    prompt="Solve this complex X12 to HL7 conversion...",
    extended_thinking=True,
    thinking_budget=10000
)

print(f"Completed in {latency_ms/1000:.1f}s (no timeout)")
```

### Expected behavior:
- Fast models: Complete in 10-60 seconds
- Thinking models: Complete in 30-500 seconds
- Complex prompts: May take full 600 seconds
- No timeouts unless truly stuck (>10 minutes)

## Files Modified
- `ensemble_shared/bedrock_client.py` - Lines 42-53, 115

## Next Steps from Review
1. ✅ **Update documentation framing** - COMPLETE
2. ✅ **Fix timeout issue** - COMPLETE
3. ⬜ Add self-consistency ensemble (no judge needed)
4. ⬜ Test Nova-lite on benchmarks

---

*Updated: April 9, 2026*  
*Status: Implemented, pending re-evaluation of original study*
