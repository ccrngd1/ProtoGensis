# Parallelization Opportunities

## Current Performance Bottlenecks

### 1. **Harness: Sequential Model Calls (BIGGEST BOTTLENECK)**
**File:** `harness.py:455-478` (run_prompt method)

**Current Code:**
```python
def run_prompt(self, prompt_id: str, prompt_text: str) -> Dict[str, ModelResponse]:
    responses = {}
    for model_key in self.active_models.keys():
        response = self._call_model_generic(model_key, prompt_text, prompt_id)
        responses[model_key] = response  # Sequential!
    return responses
```

**Problem:**
- 13 models called sequentially
- Each call takes 1-15 seconds (depending on model)
- Total time per prompt: ~60-120 seconds
- **For 10 prompts: 10-20 minutes total**

**Solution Available:**
BedrockClient already has `call_batch()` method with ThreadPoolExecutor!

**Speedup Potential:**
- Current: 13 models × 5 seconds avg = **65 seconds per prompt**
- Parallel: max(all model latencies) = **15 seconds per prompt** (limited by slowest model)
- **Speedup: 4-5x faster** ⚡

**Implementation:**
Use `self.client.call_batch()` with all model calls in parallel:
```python
def run_prompt_parallel(self, prompt_id: str, prompt_text: str):
    # Build batch of calls
    calls = []
    for model_key in self.active_models.keys():
        model_config = self.active_models[model_key]
        json_prompt = self._build_json_prompt(prompt_text)
        
        calls.append({
            'model_id': model_config.model_id,
            'prompt': json_prompt,
            'max_tokens': 16000 if model_config.supports_thinking else 2048,
            'temperature': None if model_config.supports_thinking else 0.7,
            'extended_thinking': model_config.supports_thinking,
            'thinking_budget': 10000
        })
    
    # Execute all in parallel
    results = self.client.call_batch(calls, max_workers=13)
    
    # Parse results back to ModelResponse objects
    responses = {}
    for idx, model_key in enumerate(self.active_models.keys()):
        response_text, input_tokens, output_tokens, latency_ms = results[idx]
        answer, confidence = self._parse_json_response(response_text)
        # ... build ModelResponse object
    
    return responses
```

---

### 2. **Vote Aggregator: Sequential Prompt Processing**
**File:** `aggregators/vote.py:512-517` (main function)

**Current Code:**
```python
for item in data:
    prompt = item['prompt']
    responses = item['responses']
    vote_result = aggregator.aggregate(responses, prompt)  # Sequential!
    results.append(asdict(vote_result))
```

**Problem:**
- Each `aggregate()` call makes a Haiku API call (~3-5 seconds)
- 10 prompts × 4 seconds = **40 seconds**
- All prompts are independent (no dependencies)

**Speedup Potential:**
- Current: 10 prompts × 4 seconds = **40 seconds**
- Parallel: max(all Haiku calls) = **5 seconds** (all run at once)
- **Speedup: 8x faster** ⚡

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_all_prompts_parallel(data, aggregator):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        
        for item in data:
            future = executor.submit(aggregator.aggregate, item['responses'], item['prompt'])
            futures[future] = item['prompt']['id']
        
        results = []
        for future in as_completed(futures):
            vote_result = future.result()
            results.append(asdict(vote_result))
            print(f"✓ Completed: {futures[future]}")
        
        return results
```

---

### 3. **Stitch Synthesizer: Sequential Prompt Processing**
**File:** `aggregators/stitch.py:330-335` (main function)

**Current Code:**
```python
for item in data:
    prompt = item['prompt']
    responses = item['responses']
    stitch_result = synthesizer.synthesize(responses, prompt)  # Sequential!
    results.append(asdict(stitch_result))
```

**Problem:**
- Each `synthesize()` call makes a Sonnet API call (~5-8 seconds)
- 10 prompts × 6 seconds = **60 seconds**
- All prompts are independent

**Speedup Potential:**
- Current: 10 prompts × 6 seconds = **60 seconds**
- Parallel: max(all Sonnet calls) = **8 seconds**
- **Speedup: 7-8x faster** ⚡

**Implementation:** Same pattern as vote.py above

---

### 4. **Harness: Sequential Prompt Processing**
**File:** `harness.py:480-501` (run_all_prompts method)

**Current Code:**
```python
for prompt_data in data['prompts']:
    responses = self.run_prompt(prompt_id, prompt_text)
    all_results.append(result)
```

**Problem:**
- Processes 10 prompts sequentially
- Even after parallelizing model calls within each prompt, prompts still sequential

**Should NOT parallelize this one because:**
- Rate limiting: AWS Bedrock has per-region limits
- Cost visibility: Sequential shows progress
- Memory: 13 models × 10 prompts × ~16K tokens = high memory if all parallel

**Keep sequential:** Process prompts one at a time, but parallelize model calls within each prompt

---

## Summary: Parallelization Strategy

### Phase 1: Parallelize Model Calls (HIGHEST PRIORITY) ⭐⭐⭐
**Where:** `harness.py` - run_prompt method
**Impact:** 4-5x speedup (65s → 15s per prompt)
**Cost:** No additional API cost
**Implementation:** Use existing `call_batch()` method

### Phase 2: Parallelize Vote Aggregation ⭐⭐
**Where:** `aggregators/vote.py` - main function
**Impact:** 8x speedup (40s → 5s total)
**Cost:** No additional API cost
**Implementation:** ThreadPoolExecutor on aggregate calls

### Phase 3: Parallelize Stitch Synthesis ⭐⭐
**Where:** `aggregators/stitch.py` - main function
**Impact:** 7-8x speedup (60s → 8s total)
**Cost:** No additional API cost
**Implementation:** ThreadPoolExecutor on synthesize calls

### Phase 4: Do NOT Parallelize Prompts ⭐
**Where:** `harness.py` - run_all_prompts method
**Reason:** Rate limiting, cost visibility, memory concerns
**Keep:** Sequential prompt processing

---

## Expected Performance Improvement

**Current Full Experiment:**
- Harness: 13 models × 10 prompts × 5s = **650 seconds** (11 minutes)
- Vote: 10 prompts × 4s = **40 seconds**
- Stitch: 10 prompts × 6s = **60 seconds**
- **Total: ~13 minutes per experiment**
- **WITH + WITHOUT Opus: ~26 minutes total**

**After Parallelization:**
- Harness: 10 prompts × 15s = **150 seconds** (2.5 minutes)
- Vote: max(10 parallel) = **5 seconds**
- Stitch: max(10 parallel) = **8 seconds**
- **Total: ~3 minutes per experiment**
- **WITH + WITHOUT Opus: ~6 minutes total**

**Net speedup: 26 minutes → 6 minutes = 4.3x faster** 🚀

---

## Implementation Priority

1. **Start with harness.py model parallelization** - biggest impact
2. Then add vote.py parallelization
3. Then add stitch.py parallelization
4. Skip prompt-level parallelization

## Rate Limiting Concerns

**Current rate limiting:**
```python
# bedrock_client.py line 32-40
def _rate_limit(self):
    global _last_call_time
    with _rate_limit_lock:
        now = time.time()
        time_since_last = now - _last_call_time
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        _last_call_time = time.time()
```

**Issue:** Global rate limiter with 0.5s delay works for sequential calls, but with parallel calls:
- 13 models in parallel = first call goes immediately, next 12 are delayed by 0.5s increments
- This defeats the purpose of parallelization!

**Fix:** Remove or reduce `min_delay` when using parallel calls, OR change to per-model rate limiting instead of global.

**Recommendation:**
- Set `min_delay=0.1` (100ms between calls)
- AWS Bedrock can handle ~100 TPS per region
- 13 parallel calls every 10 seconds = 1.3 QPS (well within limits)
