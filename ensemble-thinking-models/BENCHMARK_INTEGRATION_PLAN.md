# Benchmark Integration Plan

## Current Code Analysis

### What Works Already ✅
- `harness.py` - Runs models, extracts answers, calculates costs
- `aggregators/vote.py` - Majority voting and semantic judging
- `aggregators/stitch.py` - Synthesis aggregation
- `evaluate.py` - Compares accuracy with ground truth

### What Needs Changes

## 1. Benchmark Data Loaders (NEW FILES)

### `benchmarks/gsm8k_loader.py`
```python
"""
Downloads and converts GSM8K to our format
"""
def download_gsm8k():
    # Download from HuggingFace or GitHub
    pass

def convert_to_prompts(count=100):
    # Convert GSM8K format to our prompt format
    return {
        "prompts": [
            {
                "id": "gsm8k_001",
                "category": "math",
                "difficulty": "grade_school",
                "text": "Natalia sold clips to 48 of her friends...",
                "ground_truth": "72",
                "evaluation_criteria": "numeric_match",
                "benchmark": "gsm8k"
            },
            # ... 99 more
        ]
    }
```

### `benchmarks/mmlu_loader.py`
```python
"""
Downloads and converts MMLU to our format
"""
def download_mmlu():
    # Download MMLU dataset
    pass

def convert_to_prompts(subjects=["math", "physics"], count=200):
    return {
        "prompts": [
            {
                "id": "mmlu_math_001",
                "category": "multiple_choice",
                "difficulty": "undergraduate",
                "text": "Question: What is 2+2?\nA) 3\nB) 4\nC) 5\nD) 6",
                "ground_truth": "B",
                "evaluation_criteria": "multiple_choice",
                "benchmark": "mmlu",
                "choices": ["A", "B", "C", "D"]
            },
            # ... 199 more
        ]
    }
```

### `benchmarks/humaneval_loader.py`
```python
"""
Downloads and converts HumanEval to our format
"""
def download_humaneval():
    # Download HumanEval dataset
    pass

def convert_to_prompts(count=164):
    return {
        "prompts": [
            {
                "id": "humaneval_001",
                "category": "code",
                "difficulty": "medium",
                "text": "Complete this Python function:\n\ndef largest_prime_factor(n):\n    \"\"\"Return largest prime factor of n\"\"\"",
                "ground_truth": {
                    "canonical_solution": "...",
                    "test_cases": ["assert largest_prime_factor(13195) == 29"]
                },
                "evaluation_criteria": "code_execution",
                "benchmark": "humaneval"
            },
            # ... 163 more
        ]
    }
```

## 2. Benchmark-Specific Evaluators (NEW FILES)

### `benchmarks/evaluators.py`
```python
"""
Benchmark-specific evaluation logic
"""

def evaluate_gsm8k(model_answer, ground_truth):
    """
    Extract final number from model answer
    Compare to ground truth number
    """
    # GSM8K answers are like "#### 72"
    # Models might answer "The answer is 72" or "72 clips"
    # Need to extract the number
    import re
    numbers = re.findall(r'\d+', model_answer)
    if numbers:
        return int(numbers[-1]) == int(ground_truth)
    return False

def evaluate_mmlu(model_answer, ground_truth, choices):
    """
    Extract A/B/C/D from model answer
    Compare to ground truth letter
    """
    # Models might say "The answer is B" or just "B"
    import re
    letter_match = re.search(r'\b([A-D])\b', model_answer.upper())
    if letter_match:
        return letter_match.group(1) == ground_truth
    return False

def evaluate_humaneval(model_answer, ground_truth):
    """
    Execute code and run test cases
    """
    # This is complex - need to:
    # 1. Extract code from model answer
    # 2. Execute in sandbox
    # 3. Run test cases
    # 4. Return pass/fail
    pass

def evaluate_benchmark(prompt, model_answer):
    """
    Route to appropriate evaluator based on benchmark type
    """
    benchmark = prompt.get('benchmark', 'unknown')
    ground_truth = prompt.get('ground_truth')
    
    if benchmark == 'gsm8k':
        return evaluate_gsm8k(model_answer, ground_truth)
    elif benchmark == 'mmlu':
        return evaluate_mmlu(model_answer, ground_truth, prompt.get('choices'))
    elif benchmark == 'humaneval':
        return evaluate_humaneval(model_answer, ground_truth)
    else:
        # Fall back to string matching for custom prompts
        return model_answer.lower().strip() in ground_truth.lower()
```

## 3. Update evaluate.py (MODIFY EXISTING)

```python
# Add at top:
from benchmarks.evaluators import evaluate_benchmark

# Modify accuracy evaluation section:
def evaluate_accuracy(prompt, response):
    """Evaluate if response is correct"""
    
    # Check if this is a benchmark prompt
    if 'benchmark' in prompt:
        return evaluate_benchmark(prompt, response['answer'])
    
    # Otherwise use existing ground_truth evaluation
    # ... existing code ...
```

## 4. Benchmark Runner Scripts (NEW FILES)

### `scripts/run_gsm8k_study.sh`
```bash
#!/bin/bash
# Run GSM8K benchmark comparison

echo "Preparing GSM8K benchmark (100 problems)..."
python3 benchmarks/gsm8k_loader.py --count 100 --output prompts/gsm8k_100.json

echo "Running Experiment 1: Thinking vs Fast on GSM8K..."
python3 harness.py \
  --models opus-thinking opus-fast sonnet-thinking sonnet-fast haiku-thinking haiku-fast \
  --prompts prompts/gsm8k_100.json \
  --output results/benchmarks/gsm8k/responses.json

echo "Running vote aggregation..."
python3 aggregators/vote.py results/benchmarks/gsm8k/responses.json --live

echo "Evaluating accuracy..."
python3 evaluate.py \
  --responses results/benchmarks/gsm8k/responses.json \
  --vote results/benchmarks/gsm8k/vote_results.json \
  --prompts prompts/gsm8k_100.json \
  --output results/benchmarks/gsm8k/evaluation.json

echo "Comparing to published benchmarks..."
python3 benchmarks/compare_to_published.py results/benchmarks/gsm8k/evaluation.json
```

### Similar scripts for MMLU and HumanEval

## 5. Published Results Comparison (NEW FILE)

### `benchmarks/compare_to_published.py`
```python
"""
Compare our results to published benchmark numbers
"""

PUBLISHED_RESULTS = {
    "gsm8k": {
        "opus_standard": 85,
        "opus_thinking": 95,
        "sonnet_standard": 80,
        "sonnet_thinking": 90,
        "haiku_standard": 75,
        "haiku_thinking": 85
    },
    "mmlu": {
        "opus_standard": 86,
        "opus_thinking": 88,
        "sonnet_standard": 79,
        "sonnet_thinking": 81,
        "haiku_standard": 75,
        "haiku_thinking": 77
    },
    "humaneval": {
        "opus_standard": 84,
        "opus_thinking": 92,
        "sonnet_standard": 73,
        "sonnet_thinking": 79
    }
}

def compare_results(our_results, benchmark):
    """
    Load our results, compare to published
    Flag if we're way off
    """
    print(f"\n{'='*60}")
    print(f"COMPARISON: Our Results vs Published ({benchmark})")
    print(f"{'='*60}")
    
    for model in our_results:
        our_accuracy = our_results[model]['accuracy']
        published = PUBLISHED_RESULTS[benchmark].get(model, None)
        
        if published:
            diff = our_accuracy - published
            status = "✅" if abs(diff) < 5 else "⚠️" if abs(diff) < 10 else "❌"
            print(f"{status} {model:20} Our: {our_accuracy:5.1f}%  Published: {published:5.1f}%  Diff: {diff:+5.1f}%")
        else:
            print(f"   {model:20} Our: {our_accuracy:5.1f}%  Published: N/A")
    
    print()
```

## Implementation Order

### Phase 1: GSM8K (Validate Methodology)
1. Create `benchmarks/gsm8k_loader.py`
2. Download 100 GSM8K problems
3. Convert to our format
4. Run thinking vs fast comparison
5. Compare to published results
6. **If we match published:** ✅ Methodology validated
7. **If we don't match:** ❌ Fix our setup first

### Phase 2: MMLU (Validate on Diverse Topics)
1. Create `benchmarks/mmlu_loader.py`
2. Sample 200 questions across subjects
3. Run comparison
4. Validate against published results

### Phase 3: HumanEval (Validate on Code)
1. Create `benchmarks/humaneval_loader.py`
2. Set up code execution sandbox
3. Run all 164 problems
4. Validate against published results

## File Structure After Changes

```
ensemble-thinking-models/
├── benchmarks/                    # NEW
│   ├── __init__.py
│   ├── gsm8k_loader.py           # NEW
│   ├── mmlu_loader.py            # NEW
│   ├── humaneval_loader.py       # NEW
│   ├── evaluators.py             # NEW
│   └── compare_to_published.py   # NEW
├── prompts/
│   ├── hard_prompts.json         # Existing
│   ├── gsm8k_100.json            # NEW (generated)
│   ├── mmlu_200.json             # NEW (generated)
│   └── humaneval_164.json        # NEW (generated)
├── results/
│   └── benchmarks/               # NEW
│       ├── gsm8k/
│       ├── mmlu/
│       └── humaneval/
├── scripts/
│   ├── run_gsm8k_study.sh        # NEW
│   ├── run_mmlu_study.sh         # NEW
│   └── run_humaneval_study.sh    # NEW
├── harness.py                     # NO CHANGES NEEDED ✅
├── evaluate.py                    # MINOR CHANGES (add benchmark evaluator)
├── aggregators/                   # NO CHANGES NEEDED ✅
└── ...
```

## Minimal Changes to Existing Code

### harness.py
**Changes needed:** NONE ✅  
Already works with any prompt format with `id` and `text`

### evaluate.py
**Changes needed:** Add benchmark-specific evaluation  
```python
# Add one function call
from benchmarks.evaluators import evaluate_benchmark
```

### aggregators/vote.py, stitch.py
**Changes needed:** NONE ✅  
Already work with any prompt format

## Summary

**New files:** 8
- 3 loaders (GSM8K, MMLU, HumanEval)
- 1 evaluator
- 1 comparison tool
- 3 runner scripts

**Modified files:** 1
- evaluate.py (add benchmark evaluation routing)

**Unchanged files:** 3
- harness.py ✅
- aggregators/vote.py ✅
- aggregators/stitch.py ✅

**Total effort:** ~4-6 hours of development
**Total cost to run:** ~$25-40 for all 3 benchmarks
**Total runtime:** ~2-3 hours

## Next Steps

Would you like me to:
1. Start with GSM8K loader (download + convert 100 problems)?
2. Show you the code structure for all 3 loaders first?
3. Create a minimal pilot (20 GSM8K problems) to test the approach?
