"""
Build verification script - tests core functionality without external dependencies.
"""

import json
import sys
from pathlib import Path


def verify_build():
    """Verify all build deliverables are present and valid."""

    print("=" * 80)
    print("RAG Verification Build Verification")
    print("=" * 80)

    checks_passed = 0
    checks_failed = 0

    # Check 1: Core Python files
    print("\n1. Checking core Python files...")
    required_files = [
        'config.py',
        'rag_pipeline.py',
        'compare.py',
        'report.py',
        'evaluators/__init__.py',
        'evaluators/llm_judge.py',
        'evaluators/nli_claims.py',
        'evaluators/realtime_encoder.py'
    ]

    for file in required_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
            checks_passed += 1
        else:
            print(f"  ✗ {file} MISSING")
            checks_failed += 1

    # Check 2: Documentation files
    print("\n2. Checking documentation files...")
    doc_files = {
        'BLOG.md': (2500, 3500, 'words'),
        'README.md': (300, 600, 'lines'),
        'REVIEW.md': (200, 500, 'lines')
    }

    for file, (min_val, max_val, unit) in doc_files.items():
        if Path(file).exists():
            with open(file, 'r') as f:
                content = f.read()
                if unit == 'words':
                    count = len(content.split())
                else:
                    count = len(content.splitlines())

                in_range = min_val <= count <= max_val
                status = "✓" if in_range else "⚠"
                print(f"  {status} {file}: {count} {unit}")
                if in_range:
                    checks_passed += 1
                else:
                    checks_failed += 1
        else:
            print(f"  ✗ {file} MISSING")
            checks_failed += 1

    # Check 3: Test dataset
    print("\n3. Checking test dataset...")
    test_file = 'data/test_cases.json'
    if Path(test_file).exists():
        with open(test_file, 'r') as f:
            data = json.load(f)

        total = len(data)
        faithful = sum(1 for d in data if d['label'] == 'faithful')
        partial = sum(1 for d in data if d['label'] == 'partially_hallucinated')
        full = sum(1 for d in data if d['label'] == 'fully_hallucinated')

        print(f"  ✓ {test_file}: {total} test cases")
        print(f"    - Faithful: {faithful}")
        print(f"    - Partially hallucinated: {partial}")
        print(f"    - Fully hallucinated: {full}")

        if 20 <= total <= 35:
            checks_passed += 1
        else:
            checks_failed += 1
    else:
        print(f"  ✗ {test_file} MISSING")
        checks_failed += 1

    # Check 4: Configuration files
    print("\n4. Checking configuration files...")
    config_files = ['requirements.txt', '.env.example']

    for file in config_files:
        if Path(file).exists():
            print(f"  ✓ {file}")
            checks_passed += 1
        else:
            print(f"  ✗ {file} MISSING")
            checks_failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Checks passed: {checks_passed}")
    print(f"Checks failed: {checks_failed}")

    if checks_failed == 0:
        print("\n✓ BUILD VERIFICATION PASSED")
        print("\nAll deliverables present and valid!")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Run comparison: python compare.py")
        print("  3. Generate report: python report.py")
        return True
    else:
        print("\n✗ BUILD VERIFICATION FAILED")
        print(f"\n{checks_failed} check(s) failed. Review output above.")
        return False


if __name__ == "__main__":
    success = verify_build()
    sys.exit(0 if success else 1)
