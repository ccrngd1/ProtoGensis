#!/usr/bin/env python3
"""Run all demo attack scenarios."""

import subprocess
import sys
from pathlib import Path

demos = [
    'attack_shell_injection.py',
    'attack_path_traversal.py',
    'attack_pii_leak.py',
    'attack_secret_exfiltration.py',
]

def main():
    print("=" * 60)
    print("Running All AEGIS Demo Scenarios")
    print("=" * 60)

    demo_dir = Path(__file__).parent
    passed = 0
    failed = 0

    for demo in demos:
        demo_path = demo_dir / demo
        print(f"\n\nRunning: {demo}")
        print("-" * 60)

        try:
            result = subprocess.run(
                [sys.executable, str(demo_path)],
                cwd=demo_dir.parent,
                capture_output=False,
                check=True
            )
            passed += 1
        except subprocess.CalledProcessError:
            print(f"\n✗ {demo} FAILED")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
