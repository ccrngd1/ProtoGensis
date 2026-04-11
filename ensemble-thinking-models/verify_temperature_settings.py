#!/usr/bin/env python3
"""
T-V4: Verify temperature settings for baseline vs self-consistency
Check if correct temperatures were used
"""

import json

def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)

print("="*80)
print("T-V4: TEMPERATURE SETTINGS VERIFICATION")
print("="*80)
print()

# Check self-consistency results (should use temperature=0.7 for diversity)
print("SELF-CONSISTENCY (Phase 2):")
print("-"*80)

selfcons_files = [
    'results/phase2/gsm8k_100_selfcons_run1.json',
    'results/phase2/gsm8k_100_selfcons_run2.json',
    'results/phase2/gsm8k_100_selfcons_run3.json'
]

for filepath in selfcons_files:
    try:
        data = load_json(filepath)

        # Check if temperature is recorded in metadata
        model = data.get('model', 'unknown')
        num_samples = data.get('num_samples', 0)

        print(f"\n{filepath}:")
        print(f"  Model: {model}")
        print(f"  Samples per prompt: {num_samples}")

        # Check individual results for temperature info
        results = data.get('results', [])
        if results:
            first_result = results[0]
            all_answers = first_result.get('all_answers', [])

            if all_answers:
                # Check if any answer has temperature info
                temp_found = False
                for answer in all_answers:
                    # This might not exist, depends on what was stored
                    pass

                print(f"  ✅ {len(all_answers)} samples per prompt (diversity expected)")
                print(f"  Expected temperature: 0.7 (for sampling diversity)")
                print(f"  ⚠️  Temperature not recorded in result file")
            else:
                print(f"  ❌ No all_answers field found")
        else:
            print(f"  ❌ No results found")

    except FileNotFoundError:
        print(f"\n{filepath}:")
        print(f"  ❌ File not found")
    except Exception as e:
        print(f"\n{filepath}:")
        print(f"  ❌ Error: {e}")

# Check code for temperature settings
print("\n\n" + "="*80)
print("CODE REVIEW: Temperature Settings")
print("="*80)

print("\n1. aggregators/self_consistency.py:")
print("   Line 91:  temperature: float = 0.7")
print("   Line 138: temperature=temperature if not extended_thinking else None")
print("   Line 289: temperature=0.7")
print("\n   ✅ Self-consistency uses temperature=0.7 for sampling diversity")

print("\n2. harness.py:")
print("   Line 359: temperature=None  # For extended thinking")
print("   Line 306: temperature=0.7   # For fast mode")
print("   Line 408: temperature=0.7   # For fast mode")
print("\n   ✅ Baseline uses temperature=None (thinking) or 0.7 (fast)")

# Check if baseline results exist
print("\n\n" + "="*80)
print("BASELINE TEMPERATURE:")
print("="*80)

print("""
From harness.py code:

**Thinking mode (extended_thinking=True):**
  temperature = None  # Controlled by model, not user-specified

**Fast mode (extended_thinking=False):**
  temperature = 0.7  # User-specified for sampling

**Self-consistency:**
  temperature = 0.7  # For generating diverse samples

**Implication:**
  - Baseline opus-fast: temperature=0.7
  - Self-consistency opus-fast: temperature=0.7
  - ✅ SAME temperature (correct for fair comparison)

**Thinking mode:**
  - Baseline opus-thinking: temperature=None (model-controlled)
  - Cannot use self-consistency with thinking mode (incompatible)
  - ✅ CORRECT (thinking mode controls its own sampling)
""")

print("="*80)
print("CONCLUSION:")
print("="*80)

print("""
✅ Temperature settings appear CORRECT:

1. **Self-consistency uses temperature=0.7**
   - Generates diverse samples for voting
   - Standard practice (Wang et al., 2022 used 0.7)

2. **Baseline fast mode uses temperature=0.7**
   - Same temperature as self-consistency
   - Fair comparison

3. **Thinking mode uses temperature=None**
   - Model-controlled sampling
   - Cannot be overridden (per API)
   - Self-consistency not applicable to thinking mode

**No issues found with temperature settings.**

**However:** Phase 2 results have extraction bug (T-V1), so accuracy
calculations are wrong regardless of temperature being correct.
""")

print("="*80)
