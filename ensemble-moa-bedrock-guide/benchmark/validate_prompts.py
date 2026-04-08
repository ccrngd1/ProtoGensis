#!/usr/bin/env python3
"""Validate prompt set completeness and quality."""

import json
from collections import Counter
from pathlib import Path


def validate_prompts(prompts_file="benchmark/prompts.json"):
    """Validate prompt set."""

    with open(prompts_file) as f:
        data = json.load(f)

    prompts = data['prompts']

    print("="*60)
    print("PROMPT SET VALIDATION")
    print("="*60)

    # Count by category
    categories = Counter(p['category'] for p in prompts)
    print("\nPrompts by Category:")
    for category, count in sorted(categories.items()):
        print(f"  {category:15s} {count:3d} prompts")

    print(f"\nTotal: {len(prompts)} prompts")

    # Count by difficulty
    difficulties = Counter(p['difficulty'] for p in prompts)
    print("\nPrompts by Difficulty:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff:10s} {count:3d} prompts")

    # Check for missing expected_answer
    missing_answers = [p['id'] for p in prompts if 'expected_answer' not in p]
    if missing_answers:
        print(f"\n⚠️  Warning: {len(missing_answers)} prompts missing expected_answer:")
        for pid in missing_answers:
            print(f"    - {pid}")
    else:
        print("\n✅ All prompts have expected answers")

    # Check for duplicate IDs
    ids = [p['id'] for p in prompts]
    duplicates = [pid for pid in ids if ids.count(pid) > 1]
    if duplicates:
        print(f"\n❌ Error: Duplicate IDs found: {set(duplicates)}")
        return False
    else:
        print("✅ All prompt IDs are unique")

    # Category balance check
    target = 50
    min_per_category = 4
    balanced = all(count >= min_per_category for count in categories.values())
    if balanced:
        print(f"✅ Categories are reasonably balanced (all ≥{min_per_category} prompts)")
    else:
        print(f"⚠️  Warning: Some categories have <{min_per_category} prompts")
        for category, count in categories.items():
            if count < min_per_category:
                print(f"    - {category}: {count} prompts (need {min_per_category - count} more)")

    # Check target count
    if len(prompts) >= target:
        print(f"✅ Reached target of {target} prompts ({len(prompts)} total)")
    else:
        print(f"⚠️  Warning: Only {len(prompts)}/{target} prompts (need {target - len(prompts)} more)")

    # Check for required fields
    required_fields = ['id', 'category', 'difficulty', 'prompt', 'expected_answer']
    incomplete = []
    for p in prompts:
        missing = [field for field in required_fields if field not in p]
        if missing:
            incomplete.append((p.get('id', 'UNKNOWN'), missing))

    if incomplete:
        print(f"\n❌ Error: {len(incomplete)} prompts have missing fields:")
        for pid, missing_fields in incomplete:
            print(f"    - {pid}: missing {missing_fields}")
        return False
    else:
        print("✅ All prompts have required fields")

    print("\n" + "="*60)

    # Success criteria
    success = (
        len(prompts) >= target and
        not duplicates and
        not missing_answers and
        not incomplete and
        balanced
    )

    if success:
        print("✅ VALIDATION PASSED - Prompt set is ready!")
    else:
        print("⚠️  VALIDATION WARNINGS - Review issues above")

    print("="*60)

    return success


if __name__ == "__main__":
    import sys
    is_valid = validate_prompts()
    sys.exit(0 if is_valid else 1)
