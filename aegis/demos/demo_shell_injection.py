#!/usr/bin/env python3
"""
Demo: Shell Injection Attack

Shows how AEGIS blocks a tool call containing shell injection.
"""

import json
import subprocess
import sys


def demo_shell_injection():
    """Demonstrate shell injection blocking."""
    print("\n" + "="*60)
    print("DEMO: Shell Injection Attack")
    print("="*60 + "\n")

    # Malicious tool call with shell injection
    malicious_call = {
        "name": "execute_command",
        "arguments": {
            "command": "ls -la; rm -rf /tmp/*; echo 'pwned'"
        }
    }

    print("Testing malicious tool call:")
    print(json.dumps(malicious_call, indent=2))
    print()

    # Run through AEGIS check
    result = subprocess.run(
        ['aegis', 'check', json.dumps(malicious_call)],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print("✓ Attack BLOCKED by AEGIS")
        print(f"  Exit code: {result.returncode}")
    else:
        print("✗ Attack was NOT blocked (unexpected!)")

    print("\n" + "-"*60 + "\n")

    # Clean tool call for comparison
    clean_call = {
        "name": "execute_command",
        "arguments": {
            "command": "ls -la /tmp"
        }
    }

    print("Testing clean tool call:")
    print(json.dumps(clean_call, indent=2))
    print()

    result = subprocess.run(
        ['aegis', 'check', json.dumps(clean_call)],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode == 0:
        print("✓ Clean call ALLOWED by AEGIS")
    else:
        print("✗ Clean call was blocked (unexpected!)")


if __name__ == '__main__':
    demo_shell_injection()
