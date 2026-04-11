#!/usr/bin/env python3
"""
Fix GSM8K-20 pilot answer extraction.

The pilot_responses.json has full text answers that need numeric extraction.
This is different from the self-consistency files - here we extract from
the 'answer' field within each model's response.
"""

import json
import re
from pathlib import Path

def extract_numeric_answer(text):
    """
    Extract numeric answer from text.
    Prioritizes final answer patterns over intermediate calculations.
    """
    if not text:
        return None

    text = str(text).strip()

    # PRIORITY 1: Final answer indicators (look in last 200 chars first)
    last_part = text[-200:]
    final_patterns = [
        r'(?:answer|profit|total|result|makes|made|gets|got|has|sells for|is)\s+(?:of\s+|is\s+)?\$?([\d,]+\.?\d*)',
        r'(?:Answer|Profit|Total|Result):\s*\$?([\d,]+\.?\d*)',
        r'^\s*\$?([\d,]+\.?\d*)\s*\.?\s*$',  # Just a number on its own line at end
    ]

    for pattern in final_patterns:
        matches = re.findall(pattern, last_part, re.IGNORECASE)
        if matches:
            # Take the LAST match (most likely the final answer)
            last_match = matches[-1]
            cleaned = str(last_match).replace('$', '').replace(',', '').strip()
            try:
                num = float(cleaned) if '.' in cleaned else int(cleaned)
                return str(int(num)) if isinstance(num, float) and num == int(num) else str(num)
            except (ValueError, TypeError):
                continue

    # PRIORITY 2: Common calculation patterns (throughout text)
    calc_patterns = [
        r'=\s*\$?([\d,]+\.?\d*)\s*(?:per day|every day|dollars|at|$)',  # "= $18 per day"
        r'×\s*\$?\d+[\d,]*\s*=\s*\$?([\d,]+\.?\d*)',  # "9 × $2 = $18" (take result)
    ]

    for pattern in calc_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Take LAST match (most likely final calculation)
            last_match = matches[-1]
            cleaned = str(last_match).replace('$', '').replace(',', '').strip()
            try:
                num = float(cleaned) if '.' in cleaned else int(cleaned)
                return str(int(num)) if isinstance(num, float) and num == int(num) else str(num)
            except (ValueError, TypeError):
                continue

    # PRIORITY 3: Last number with currency symbol
    currency_numbers = re.findall(r'\$([\d,]+\.?\d*)', text)
    if currency_numbers:
        # Take last currency number
        cleaned = currency_numbers[-1].replace(',', '').strip()
        try:
            num = float(cleaned) if '.' in cleaned else int(cleaned)
            return str(int(num)) if isinstance(num, float) and num == int(num) else str(num)
        except (ValueError, TypeError):
            pass

    # PRIORITY 4: Last number in text (fallback)
    all_numbers = re.findall(r'\b([\d,]+\.?\d*)\b', text)
    if all_numbers:
        # Take last number
        cleaned = all_numbers[-1].replace(',', '').strip()
        try:
            num = float(cleaned) if '.' in cleaned else int(cleaned)
            return str(int(num)) if isinstance(num, float) and num == int(num) else str(num)
        except (ValueError, TypeError):
            pass

    return None

def fix_pilot_file(input_path, output_path):
    """
    Fix the pilot_responses.json file by extracting numeric answers.
    """
    print(f"\nProcessing: {input_path}")
    print("-" * 80)

    with open(input_path) as f:
        data = json.load(f)

    total_prompts = len(data)
    fixed_counts = {}
    failed_counts = {}

    for i, item in enumerate(data):
        prompt_id = item['prompt']['id']
        ground_truth = item['prompt'].get('ground_truth', '')
        responses = item.get('responses', {})

        # Extract for each model
        for model_key, response_data in responses.items():
            if model_key not in fixed_counts:
                fixed_counts[model_key] = 0
                failed_counts[model_key] = 0

            old_answer = response_data.get('answer', '')
            numeric_answer = extract_numeric_answer(old_answer)

            if numeric_answer:
                response_data['extracted_answer'] = numeric_answer
                response_data['original_answer'] = old_answer
                fixed_counts[model_key] += 1

                # Show first 3 for each model
                if i < 3:
                    old_preview = old_answer[:60] + "..." if len(old_answer) > 60 else old_answer
                    is_correct = numeric_answer == ground_truth
                    status = "✓" if is_correct else "✗"
                    print(f"  [{prompt_id}] {model_key}: {old_preview}")
                    print(f"    → Extracted: {numeric_answer} (ground_truth: {ground_truth}) {status}")
            else:
                failed_counts[model_key] += 1
                print(f"  ⚠️  [{prompt_id}] {model_key}: Could not extract numeric answer")

    # Write fixed data
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n  Total prompts: {total_prompts}")
    for model_key in fixed_counts:
        fixed = fixed_counts[model_key]
        failed = failed_counts[model_key]
        print(f"  {model_key}:")
        print(f"    Fixed: {fixed} ({fixed/total_prompts*100:.1f}%)")
        print(f"    Failed: {failed}")

    print(f"  Output: {output_path}")

    return sum(fixed_counts.values()), sum(failed_counts.values())

def main():
    print("=" * 80)
    print("GSM8K-20 PILOT ANSWER EXTRACTION FIX")
    print("=" * 80)

    pilot_file = 'results/benchmarks/gsm8k/pilot_responses.json'
    input_path = Path(pilot_file)

    if not input_path.exists():
        print(f"\n⚠️  File not found: {pilot_file}")
        return

    output_path = input_path.parent / f"{input_path.stem}_fixed.json"

    fixed, failed = fix_pilot_file(input_path, output_path)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal extractions attempted: {fixed + failed}")
    print(f"Total fixed: {fixed}")
    print(f"Total failed: {failed}")

    if failed == 0:
        print("\n✅ All answers successfully extracted!")
    else:
        print(f"\n⚠️  {failed} answers could not be extracted")

    print("\nFixed file created: pilot_responses_fixed.json")
    print("Review the fixed file, then rename to replace original if correct")
    print("=" * 80)

if __name__ == '__main__':
    main()
