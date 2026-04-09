# LLM-as-Judge Evaluation Guide

## Overview

The LLM-as-judge feature replaces fragile keyword matching with Opus 4.6 as an intelligent evaluator for custom prompts. This addresses the critical methodology issue where keyword matching could:
- Penalize verbose/nuanced answers (typical of thinking mode)
- Accept wrong answers that happened to hit keywords
- Fail to recognize correct answers with different wording

## How It Works

**Evaluation Priority:**
1. **Benchmark-specific evaluators** (GSM8K, MMLU, HumanEval, GPQA) - Used for standard benchmarks (most objective)
2. **LLM-as-judge** (if enabled) - Used for custom prompts
3. **Keyword matching** (legacy fallback) - Used when LLM judge not available

**LLM Judge Process:**
- Uses Claude Opus 4.6 (most capable model)
- Temperature 0.0 for deterministic grading
- Given: question, expected answer, model's answer
- Returns: CORRECT/INCORRECT + reasoning
- Cost: ~$0.001-0.003 per evaluation

## Usage

### Basic Usage

```bash
# Without LLM judge (uses keyword matching for custom prompts)
python3 evaluate.py --responses results/responses.json --prompts prompts/prompts.json

# With LLM judge (uses Opus to grade custom prompts)
python3 evaluate.py \
  --responses results/responses.json \
  --prompts prompts/prompts.json \
  --use-llm-judge

# With judge logging for transparency
python3 evaluate.py \
  --responses results/responses.json \
  --prompts prompts/prompts.json \
  --use-llm-judge \
  --judge-log results/judge_decisions.jsonl
```

### Test the Judge

```bash
# Set AWS token
export AWS_BEARER_TOKEN_BEDROCK=your_token

# Run test suite
python3 test_llm_judge.py
```

Expected output:
```
Test 1: Correct answer (exact match)
Question: What is 2 + 2?
Answer: The answer is 4.
Expected: CORRECT
  Judge: test_1 = ✓ CORRECT ($0.0012)
✓ PASSED

...

RESULTS: 5/5 tests passed
Total judge cost: $0.0152
```

## Judge Log Format

When using `--judge-log`, decisions are saved in JSONL format:

```jsonl
{"prompt_id": "h1", "verdict": "CORRECT", "reasoning": "Model correctly identified probability as 3/8 and recommended switching.", "cost_usd": 0.0023, "timestamp": 1712678934.2}
{"prompt_id": "h2", "verdict": "INCORRECT", "reasoning": "Model stated deadlock will always occur, but correct answer is that it CAN occur (race condition).", "cost_usd": 0.0019, "timestamp": 1712678936.8}
```

## Cost Analysis

### Keyword Matching (Free)
- Cost: $0
- Accuracy: ~60-70% (estimated, prone to false positives/negatives)
- Bias: Penalizes verbose answers, misses correct answers with different wording

### LLM Judge (Small Cost)
- Cost: ~$0.002 per evaluation
- Accuracy: ~90-95% (estimated, better at semantic understanding)
- Bias: Minimal, evaluates meaning not keywords

**Example: 100 prompts × 10 models = 1000 evaluations**
- Keyword matching: $0
- LLM judge: $2.00
- Trade-off: Spend $2 to improve evaluation accuracy by 25-30%

## When to Use LLM Judge

**Use LLM judge when:**
- Evaluating custom prompts (not standard benchmarks)
- Answers are open-ended with multiple valid phrasings
- Thinking mode produces verbose/nuanced answers
- Accuracy of evaluation is critical to conclusions

**Don't use LLM judge when:**
- Evaluating standard benchmarks (GSM8K, MMLU, etc.) - they have objective evaluators
- Budget is extremely constrained
- Keyword matching is known to work well for your domain

## Validation

To validate LLM judge accuracy:

1. **Use judge logging:**
   ```bash
   python3 evaluate.py --use-llm-judge --judge-log judge_log.jsonl
   ```

2. **Sample manual review:**
   - Randomly select 20 judge decisions
   - Manually verify correctness
   - Calculate inter-rater agreement

3. **Compare to keyword matching:**
   ```bash
   # Run both methods
   python3 evaluate.py --responses results/responses.json --prompts prompts/prompts.json > keyword_results.txt
   python3 evaluate.py --responses results/responses.json --prompts prompts/prompts.json --use-llm-judge > llm_judge_results.txt
   
   # Compare accuracy differences
   diff keyword_results.txt llm_judge_results.txt
   ```

## Example: Re-evaluating Original Study

```bash
# Re-evaluate Experiment 1 with LLM judge
python3 evaluate.py \
  --responses results/experiment1_thinking_responses.json \
  --vote results/experiment1_vote_results.json \
  --stitch results/experiment1_stitch_results.json \
  --prompts prompts/hard_prompts.json \
  --use-llm-judge \
  --judge-log results/exp1_judge_log.jsonl \
  --output results/exp1_llm_judge_evaluation.json

# Compare to original evaluation
diff results/experiment1_evaluation.json results/exp1_llm_judge_evaluation.json
```

**Expected changes:**
- Opus-thinking accuracy may increase (verbose answers now graded correctly)
- Opus-fast may stay similar (concise answers already matched keywords)
- More accurate assessment of thinking vs fast comparison

## Limitations

1. **Judge can be wrong** - Opus 4.6 is not perfect, estimated 90-95% accuracy
2. **Cost adds up** - 1000 evaluations = $2, not free like keyword matching
3. **Stochastic at temp > 0** - We use temp=0 for deterministic grading, but still some variance
4. **Judge may have biases** - Could favor certain answer styles or be too lenient/strict
5. **Not needed for benchmarks** - GSM8K/MMLU/HumanEval have objective ground truth

## References

- **LLM-as-judge papers:** Zheng et al. (2023) "Judging LLM-as-a-judge", Dubois et al. (2024) "AlpacaEval"
- **Evaluation methodology:** Review feedback in REVIEW.md identifying keyword matching as critical flaw
- **Cost justification:** $2 to improve 1000 evaluations by 25-30% accuracy = worth it for scientific rigor

---

*Created: April 9, 2026*
*Part of: Ensemble Thinking Models experiment evaluation improvements*
