#!/usr/bin/env python3
"""
T-V1: Verify self-consistency answer extraction for GSM8K
Check if selected_answer fields contain numbers or full text (bug)
"""

import json
import re

def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)

def is_numeric_answer(answer):
    """Check if answer is just a number (correct) or full text (bug)."""
    if not answer:
        return False, "empty"

    # Strip whitespace
    answer_clean = str(answer).strip()

    # Check if it's a simple number (with optional commas, decimals, dollar signs)
    # Examples: "18", "18.0", "$18", "18,000", "-5.5"
    numeric_pattern = r'^\$?-?[\d,]+\.?\d*$'

    if re.match(numeric_pattern, answer_clean):
        return True, "numeric"

    # Check if it contains explanation text (sentences, markdown, etc.)
    if len(answer_clean) > 20:  # Numeric answers are typically short
        return False, "full_text"

    if any(word in answer_clean.lower() for word in ['step', 'work', 'find', 'total', 'calculate', '**']):
        return False, "full_text"

    # Ambiguous (short but not clearly numeric)
    return False, "ambiguous"

print("="*80)
print("T-V1: SELF-CONSISTENCY ANSWER EXTRACTION VERIFICATION")
print("="*80)
print()

files = [
    'results/phase2/gsm8k_100_selfcons_run1.json',
    'results/phase2/gsm8k_100_selfcons_run2.json',
    'results/phase2/gsm8k_100_selfcons_run3.json'
]

total_prompts = 0
numeric_answers = 0
full_text_answers = 0
ambiguous_answers = 0
empty_answers = 0

for filepath in files:
    print(f"\nChecking: {filepath}")
    print("-"*80)

    try:
        data = load_json(filepath)
        results = data.get('results', [])

        file_numeric = 0
        file_full_text = 0
        file_ambiguous = 0
        file_empty = 0

        for i, result in enumerate(results):
            selected = result.get('selected_answer', '')
            is_numeric, answer_type = is_numeric_answer(selected)

            if answer_type == "numeric":
                file_numeric += 1
            elif answer_type == "full_text":
                file_full_text += 1
            elif answer_type == "ambiguous":
                file_ambiguous += 1
            elif answer_type == "empty":
                file_empty += 1

            # Show first 3 examples
            if i < 3:
                preview = str(selected)[:100] + "..." if len(str(selected)) > 100 else str(selected)
                print(f"  Prompt {i}: {answer_type:12s} | {preview}")

        print(f"\n  Total prompts: {len(results)}")
        print(f"  Numeric answers:    {file_numeric} ({file_numeric/len(results)*100:.1f}%)")
        print(f"  Full-text answers:  {file_full_text} ({file_full_text/len(results)*100:.1f}%)")
        print(f"  Ambiguous:          {file_ambiguous}")
        print(f"  Empty:              {file_empty}")

        total_prompts += len(results)
        numeric_answers += file_numeric
        full_text_answers += file_full_text
        ambiguous_answers += file_ambiguous
        empty_answers += file_empty

    except FileNotFoundError:
        print(f"  ❌ File not found")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "="*80)
print("OVERALL SUMMARY")
print("="*80)

print(f"\nTotal prompts across all files: {total_prompts}")
print(f"  Numeric answers:    {numeric_answers} ({numeric_answers/total_prompts*100:.1f}%)")
print(f"  Full-text answers:  {full_text_answers} ({full_text_answers/total_prompts*100:.1f}%)")
print(f"  Ambiguous:          {ambiguous_answers}")
print(f"  Empty:              {empty_answers}")

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)

if full_text_answers > total_prompts * 0.5:
    print("\n🔴 EXTRACTION BUG CONFIRMED")
    print(f"   {full_text_answers/total_prompts*100:.1f}% of selected_answer fields contain full text, not extracted numbers")
    print("   For GSM8K (math word problems), answers should be numeric values only")
    print("\n   This is a CRITICAL BUG that invalidates Phase 2 self-consistency results")
    print("\n   ACTION REQUIRED:")
    print("   1. Fix extraction logic to extract final numeric answer")
    print("   2. Re-run self-consistency experiment (3 runs × 100 prompts × 5 samples = 1500 API calls)")
    print("   3. Update BLOG.md with corrected results")
elif numeric_answers > total_prompts * 0.5:
    print("\n✅ EXTRACTION WORKING CORRECTLY")
    print(f"   {numeric_answers/total_prompts*100:.1f}% of selected_answer fields contain numeric answers")
    print("   Self-consistency extraction is working as expected for GSM8K")
else:
    print("\n⚠️  MIXED RESULTS")
    print("   Some answers are numeric, some are full text")
    print("   Extraction may be inconsistent or context-dependent")

print("\n" + "="*80)

# Check sample counts
print("\nSAMPLE COUNT VERIFICATION:")
print("-"*80)

for filepath in files:
    try:
        data = load_json(filepath)
        num_samples = data.get('num_samples', 0)
        total_prompts_file = data.get('total_prompts', 0)
        results = data.get('results', [])

        expected_api_calls = total_prompts_file * num_samples
        actual_results = len(results)

        print(f"\n{filepath}:")
        print(f"  Samples per prompt: {num_samples}")
        print(f"  Total prompts: {total_prompts_file}")
        print(f"  Expected API calls: {expected_api_calls}")
        print(f"  Actual results: {actual_results}")

        if actual_results == total_prompts_file:
            print(f"  ✅ Result count matches prompt count (aggregated)")
        elif actual_results == expected_api_calls:
            print(f"  ✅ Result count matches expected API calls")
        else:
            print(f"  ⚠️  Mismatch: expected {expected_api_calls}, got {actual_results}")

    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*80)
