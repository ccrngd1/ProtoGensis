# Self-Consistency Ensemble Guide

## What is Self-Consistency?

**Self-consistency** is an ensemble method where you run the SAME model multiple times with different random seeds (temperature > 0) and take the majority vote on answers.

**Key paper:** Wang et al. (2023) "Self-Consistency Improves Chain of Thought Reasoning in Language Models"

### How it Works

1. Run model 5 times on same prompt (temperature=0.7 for diversity)
2. Extract answer from each response
3. Take majority vote (most common answer)
4. Return majority answer as final result

**No judge model needed** - the model verifies itself through multiple samples.

## Why Self-Consistency is Better Than Haiku-Judge Ensemble

### Problem with Haiku-Judge (from REVIEW.md)

**Vote ensemble (vote.py):**
- Runs 6 different models (opus, sonnet, haiku × fast/thinking)
- Uses **Haiku as judge** to pick "best" answer
- **Architectural flaw:** Haiku scored 40% on GPQA but judged models scoring 70%
- Result: 0/40 wins on custom prompts, 0/4 wins on benchmarks

**Analogy:** Having an intern (Haiku) grade senior engineer (Opus/Sonnet) work

### Advantages of Self-Consistency

| Aspect | Haiku-Judge Ensemble | Self-Consistency |
|--------|---------------------|------------------|
| **Judge model** | Haiku (weakest) | No judge needed |
| **Bottleneck** | Haiku's 40% knowledge | Model's own 70% knowledge |
| **Method** | Semantic similarity | Majority vote |
| **Diversity** | Different models | Same model, different samples |
| **Cost** | 6 models + judge call | 1 model × N samples |
| **Literature** | Naive approach | Proven method (Wang et al. 2023) |

**Key insight:** A model can verify its own answers better than a weaker model can.

## Example

### Prompt: "What causes seasons on Earth?"

**Haiku-Judge Ensemble:**
1. Opus: "23.5° axial tilt causes seasons" ✓
2. Sonnet: "Axial tilt of Earth (23.5°)" ✓  
3. Haiku: "Distance from sun varies" ✗
4. **Haiku judge picks:** "Distance from sun" (because 3 models mention "sun") ✗

**Self-Consistency (Opus only):**
1. Run 1: "23.5° axial tilt causes seasons"
2. Run 2: "Earth's tilted axis (23.5 degrees)"
3. Run 3: "Axial tilt of 23.5° relative to orbit"
4. Run 4: "The tilt in Earth's rotational axis"
5. Run 5: "23.5 degree tilt of axis"
6. **Majority vote:** "Axial tilt / 23.5°" (5/5 agree) ✓

**Result:** Self-consistency gets it right because Opus knows the answer. Haiku-judge gets it wrong because Haiku doesn't understand enough to judge correctly.

## Usage

### Basic Self-Consistency

```bash
# Run sonnet-fast 5 times on each prompt, take majority vote
python3 aggregators/self_consistency.py \
  prompts/gpqa_test_10.json \
  --model sonnet-fast \
  --samples 5 \
  --live \
  --output results/self_consistency_results.json
```

### Evaluate Results

```bash
# Compare self-consistency to individual single-run performance
python3 benchmarks/evaluate_self_consistency.py \
  results/self_consistency_results.json \
  results/benchmarks/gpqa/ensemble_pilot_responses.json \
  prompts/gpqa_test_10.json
```

### Available Models

```bash
--model opus-fast          # Opus 4.6 (fast inference)
--model opus-thinking      # Opus 4.6 (extended thinking)
--model sonnet-fast        # Sonnet 4.6 (fast inference)
--model sonnet-thinking    # Sonnet 4.6 (extended thinking)
--model haiku-fast         # Haiku 4.5 (fast inference)
--model haiku-thinking     # Haiku 4.5 (extended thinking)
```

## Cost Analysis

### Example: 10 prompts, sonnet-fast, 5 samples

**Self-consistency:**
- Sonnet-fast: ~$0.015 per call
- 5 samples × 10 prompts = 50 calls
- Total: ~$0.75

**Individual (baseline):**
- Sonnet-fast: ~$0.015 per call
- 1 sample × 10 prompts = 10 calls
- Total: ~$0.15

**Cost multiplier:** 5x (expected, since we run 5 samples)

**Trade-off:** If self-consistency improves accuracy, is 5x cost worth it?
- If individual: 7/10 correct (70%)
- If self-consistency: 8/10 correct (80%)
- **Value:** Pay 5x more to get 1 additional correct answer

### Comparison to Haiku-Judge Ensemble

**Haiku-judge (GPQA, 20 prompts):**
- Cost: $6.54 (6 models + judge)
- Accuracy: 55% (11/20)
- Best individual: 70% (14/20)
- **Result:** 19.5x more expensive, WORSE accuracy

**Self-consistency (hypothetical):**
- Cost: ~$3.50 (sonnet × 5 samples)
- Accuracy: 75%? (15/20) - to be tested
- Best individual: 70% (14/20)
- **Potential result:** 10x more expensive, BETTER accuracy

**If self-consistency beats individual, it validates ensemble concept with better architecture.**

## Expected Results

### Hypothesis

Self-consistency should improve accuracy when:
1. Model is capable but inconsistent (sometimes right, sometimes wrong)
2. Temperature > 0 provides diverse reasoning paths
3. Correct answer appears in majority of samples

Self-consistency won't help when:
1. Model consistently gets it wrong (majority will still be wrong)
2. Problem is too hard for the model
3. Temperature = 0 (all samples identical)

### Test on GPQA

**Individual (sonnet-fast):** 14/20 = 70%  
**Self-consistency (sonnet-fast × 5):** Expected 72-78%

**Why:** On the 6 prompts sonnet-fast got wrong, if even 1-2 were "unlucky" samples, self-consistency should fix them. If all 6 were genuinely too hard, self-consistency won't help.

**Break-even:** Need to get 1 additional correct answer to justify 5x cost.

## Comparison to Other Ensemble Methods

| Method | Judge Needed | Models | Samples | Cost Mult. | Our Results |
|--------|-------------|--------|---------|------------|-------------|
| **Vote (Haiku judge)** | Yes (weak) | 6 different | 1 each | 19x | 0/4 wins |
| **Stitch (Haiku synth)** | Yes (weak) | 6 different | 1 each | 19x | 0/4 wins |
| **Self-consistency** | No | 1 same | 5 each | 5x | Testing now |
| **Best-of-N** | No | 1 same | N each | Nx | Not tested |
| **Weighted vote** | No | 6 different | 1 each | 19x | Not tested |
| **Strong verifier** | Yes (strong) | 6 different | 1 each | 25x | Not tested |

**Self-consistency is the most cost-effective ensemble method if it works.**

## Implementation Details

### Answer Extraction

The `_extract_answer_key()` method normalizes answers for voting:

1. **Numeric answers** (GSM8K): Extract last number
2. **Multiple choice** (MMLU, GPQA): Extract letter (A/B/C/D)
3. **Text answers**: Normalize and take first 50 chars

**Example:**
- "The answer is 3/8" → "0.375"
- "I choose B because..." → "B"
- "Axial tilt causes seasons" → "axial tilt causes seasons"

### Agreement Rate

**Agreement rate** = (count of majority answer) / (total samples)

**Interpretation:**
- 100% (5/5): Perfect agreement, high confidence
- 80% (4/5): Strong majority
- 60% (3/5): Weak majority, model uncertain
- <60%: No clear majority, flip a coin

**Use case:** Can use agreement rate as confidence score. If <60%, might want to defer to human or run more samples.

## Addresses REVIEW.md Concerns

✅ **Issue #4: Naive Ensemble Design**
- Self-consistency is a proven method from literature
- No weak judge bottleneck
- Tests if ensembles work with better architecture

✅ **Issue #8: No Variance Estimate**
- Multiple samples provide variance estimate
- Agreement rate shows model confidence
- Can identify high-uncertainty prompts

## Limitations

1. **Only helps with stochastic errors** - If model genuinely doesn't know, majority will be wrong
2. **Cost multiplier** - Nx more expensive than single run
3. **Requires temperature > 0** - Deterministic sampling (temp=0) produces identical samples
4. **Answer extraction** - May fail on complex answer formats
5. **No new information** - Just statistical aggregation, not synthesis

## Next Steps

1. ✅ **Implement self-consistency** - COMPLETE
2. ⏳ **Test on GPQA (10 prompts)** - RUNNING
3. ⬜ **Compare to individual baseline** - After test completes
4. ⬜ **Test on other benchmarks** - GSM8K, MMLU
5. ⬜ **Try with thinking mode** - opus-thinking × 5 samples

---

*Created: April 9, 2026*  
*Status: Implementation complete, testing in progress*
