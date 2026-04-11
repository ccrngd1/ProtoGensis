#!/usr/bin/env python3
"""
T-V3: Compare GSM8K-20 vs GSM8K-100 prompt IDs and thinking mode accuracy
Explain thinking mode discrepancy: 100% on GSM8K-20, but 89.7% on GSM8K-100
"""

import json

def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)

print("="*80)
print("T-V3: THINKING MODE DISCREPANCY VERIFICATION")
print("="*80)
print()

# Load GSM8K-20 pilot prompts
gsm8k_20_prompts = load_json('prompts/gsm8k_pilot_20.json')
gsm8k_20_ids = [p['id'] for p in gsm8k_20_prompts['prompts']]

print("GSM8K-20 Pilot Prompts:")
print(f"  Total: {len(gsm8k_20_ids)}")
print(f"  IDs: {gsm8k_20_ids[:5]} ... {gsm8k_20_ids[-2:]}")
print()

# Load GSM8K-100 Phase 2 results
gsm8k_100_run1 = load_json('results/phase2/gsm8k_100_selfcons_run1.json')
gsm8k_100_ids = [r['prompt_id'] for r in gsm8k_100_run1['results']]

print("GSM8K-100 Phase 2 Prompts:")
print(f"  Total: {len(gsm8k_100_ids)}")
print(f"  IDs: {gsm8k_100_ids[:5]} ... {gsm8k_100_ids[-2:]}")
print()

# Check if GSM8K-20 is subset of GSM8K-100
gsm8k_20_set = set(gsm8k_20_ids)
gsm8k_100_set = set(gsm8k_100_ids)

is_subset = gsm8k_20_set.issubset(gsm8k_100_set)
print("Prompt ID Comparison:")
print(f"  GSM8K-20 is subset of GSM8K-100: {is_subset}")

if is_subset:
    print(f"  ✅ All 20 pilot prompts are included in 100-prompt set")

    # Check if they're the FIRST 20
    first_20 = gsm8k_100_ids[:20]
    if gsm8k_20_ids == first_20:
        print(f"  ✅ GSM8K-20 is EXACTLY the first 20 prompts of GSM8K-100")
    else:
        print(f"  ⚠️  GSM8K-20 is subset but NOT the first 20 sequentially")
        missing = set(first_20) - gsm8k_20_set
        if missing:
            print(f"      Missing from first 20: {missing}")
else:
    print(f"  ❌ GSM8K-20 is NOT a subset (different prompt sets)")
    missing = gsm8k_20_set - gsm8k_100_set
    print(f"      Prompts in 20 but not in 100: {missing}")

print()
print("="*80)

# Load GSM8K-20 pilot responses (has both opus-fast and opus-thinking)
print("GSM8K-20 Pilot Results:")
print("-"*80)

pilot_responses = load_json('results/benchmarks/gsm8k/pilot_responses.json')

# Load ground truth from prompts
ground_truth = {p['id']: p['ground_truth'] for p in gsm8k_20_prompts['prompts']}

# Calculate accuracy for each model
for model_key in ['opus-fast', 'opus-thinking']:
    correct = 0
    total = 0
    errors = 0

    for prompt_response in pilot_responses:
        prompt_id = prompt_response['prompt']['id']
        response = prompt_response['responses'][model_key]

        if 'error' in response and response['error']:
            errors += 1
            continue

        total += 1
        answer = response.get('answer', '')
        truth = ground_truth.get(prompt_id, '')

        # Simple string comparison (may need normalization)
        if str(answer).strip() == str(truth).strip():
            correct += 1

    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"\n{model_key}:")
    print(f"  Correct: {correct}/{total}")
    print(f"  Accuracy: {accuracy:.1f}%")
    print(f"  Errors: {errors}")

print()
print("="*80)
print("GSM8K-100 Phase 2 Results (opus-fast baseline):")
print("-"*80)

# This would require comparing with ground truth which we don't have in phase2 results
# But we can get the reported accuracy from BLOG.md: 89.7%
print("\nReported in BLOG.md:")
print("  opus-fast on GSM8K-100: 89.7%")

print()
print("="*80)
print("ANALYSIS: Why Different Accuracies?")
print("="*80)

print("""
If GSM8K-20 is the first 20 prompts of GSM8K-100, then:

Scenario 1: First 20 prompts are HARDER than average
  - opus-fast: 85% on first 20 → 89.7% on all 100
  - Suggests difficulty decreases or easier prompts in 21-100

Scenario 2: Different test conditions
  - Pilot (GSM8K-20): Earlier test run, different conditions?
  - Phase 2 (GSM8K-100): Later test run, refined?

Scenario 3: Sample variance
  - 20 prompts: Small sample, more variance (85% ± higher margin)
  - 100 prompts: Larger sample, less variance (89.7% ± lower margin)
  - 4.7 point difference could be statistical noise

Scenario 4: Thinking mode scores need verification
  - BLOG claims opus-thinking: 100% on GSM8K-20
  - But if extraction bug exists, accuracy calculation may be wrong
  - Need to verify 100% claim is accurate
""")

print("="*80)
print("RECOMMENDATIONS:")
print("="*80)

print("""
1. Verify thinking mode 100% accuracy on GSM8K-20
   - Check if pilot_responses.json has correct answers
   - Compare extracted answers with ground truth
   - Confirm 100% claim

2. If 100% is wrong:
   - Recalculate actual accuracy
   - Update BLOG.md
   - Remove or revise "thinking beats fast on math" claim

3. If 100% is correct:
   - Document why thinking dropped (100% → 89.7%?)
   - OR explain why fast improved (85% → 89.7%)
   - Analyze first 20 vs full 100 difficulty

4. Consider re-running thinking mode on GSM8K-100
   - Direct comparison with same prompts
   - Eliminates prompt selection bias
   - ~$20-30 for 100 prompts with thinking mode
""")

print("="*80)
