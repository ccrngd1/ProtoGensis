#!/usr/bin/env python3
"""
Fix GSM8K answer extraction bug.

The self-consistency results store full text in selected_answer field,
but vote_counts already has the correctly extracted numeric answers.
This script extracts the winning answer from vote_counts and updates
selected_answer to contain only the numeric value.
"""

import json
import re
from pathlib import Path

def extract_numeric_answer(text):
    """
    Extract numeric answer from text.
    Handles formats like: "18", "$18", "18.5", "18,000", etc.
    """
    if not text:
        return None

    text = str(text).strip()

    # Remove common prefixes/suffixes
    text = text.replace('$', '').replace(',', '').strip()

    # Try to convert to number and back to clean string
    try:
        # Handle decimals
        if '.' in text:
            num = float(text)
            # Keep decimals only if non-zero
            if num == int(num):
                return str(int(num))
            return str(num)
        else:
            return str(int(text))
    except (ValueError, TypeError):
        return None

def get_winning_answer(vote_counts):
    """
    Get the answer with the most votes from vote_counts dict.
    Returns the numeric answer string.
    """
    if not vote_counts:
        return None

    # Find answer with max votes
    max_votes = max(vote_counts.values())
    winning_answers = [ans for ans, votes in vote_counts.items() if votes == max_votes]

    # If tie, return first one (alphabetically sorted for consistency)
    winning_answer = sorted(winning_answers)[0]

    # Clean and return
    return extract_numeric_answer(winning_answer)

def extract_from_markdown(text):
    """
    Fallback: Extract number from markdown like "**$18**" or "Total: **3 bolts**"
    """
    if not text:
        return None

    # Look for patterns like **$18** or **18** or **3 bolts**
    markdown_patterns = [
        r'\*\*\$?([\d,]+\.?\d*)\*\*',  # **$18** or **18**
        r'\$?([\d,]+\.?\d*)\s*\*\*',   # 18** or $18**
        r':\s*\$?([\d,]+\.?\d*)\s*$',  # ending with ": 18" or ": $18"
    ]

    for pattern in markdown_patterns:
        matches = re.findall(pattern, text)
        if matches:
            # Take the last match (usually the final answer)
            return extract_numeric_answer(matches[-1])

    # Last resort: find any number in the text
    numbers = re.findall(r'\$?([\d,]+\.?\d*)', text)
    if numbers:
        return extract_numeric_answer(numbers[-1])

    return None

def fix_result_file(input_path, output_path):
    """
    Fix a single result file by extracting numeric answers.
    """
    print(f"\nProcessing: {input_path}")
    print("-" * 80)

    with open(input_path) as f:
        data = json.load(f)

    results = data.get('results', [])
    fixed_count = 0
    failed_count = 0

    for i, result in enumerate(results):
        old_answer = result.get('selected_answer', '')
        vote_counts = result.get('vote_counts', {})

        # Try to extract from vote_counts first (most reliable)
        numeric_answer = get_winning_answer(vote_counts)

        # Fallback to markdown extraction
        if not numeric_answer:
            numeric_answer = extract_from_markdown(old_answer)

        if numeric_answer:
            result['selected_answer'] = numeric_answer
            result['original_answer'] = old_answer  # Keep original for reference
            fixed_count += 1

            # Show first 5 fixes
            if i < 5:
                old_preview = old_answer[:80] + "..." if len(old_answer) > 80 else old_answer
                print(f"  [{result['prompt_id']}] {old_preview}")
                print(f"  → Fixed to: {numeric_answer}")
        else:
            failed_count += 1
            print(f"  ⚠️  [{result['prompt_id']}] Could not extract numeric answer")

    # Write fixed data
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n  Total results: {len(results)}")
    print(f"  Fixed: {fixed_count} ({fixed_count/len(results)*100:.1f}%)")
    print(f"  Failed: {failed_count}")
    print(f"  Output: {output_path}")

    return fixed_count, failed_count

def main():
    print("=" * 80)
    print("GSM8K ANSWER EXTRACTION FIX")
    print("=" * 80)

    # Phase 2 self-consistency files
    phase2_files = [
        'results/phase2/gsm8k_100_selfcons_run1.json',
        'results/phase2/gsm8k_100_selfcons_run2.json',
        'results/phase2/gsm8k_100_selfcons_run3.json',
    ]

    total_fixed = 0
    total_failed = 0

    for filepath in phase2_files:
        input_path = Path(filepath)
        if not input_path.exists():
            print(f"\n⚠️  File not found: {filepath}")
            continue

        # Create fixed version
        output_path = input_path.parent / f"{input_path.stem}_fixed.json"

        fixed, failed = fix_result_file(input_path, output_path)
        total_fixed += fixed
        total_failed += failed

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal fixed: {total_fixed}")
    print(f"Total failed: {total_failed}")

    if total_failed == 0:
        print("\n✅ All answers successfully extracted!")
    else:
        print(f"\n⚠️  {total_failed} answers could not be extracted")

    print("\nFixed files created with '_fixed.json' suffix")
    print("Review the fixed files, then rename them to replace originals if correct")
    print("=" * 80)

if __name__ == '__main__':
    main()
