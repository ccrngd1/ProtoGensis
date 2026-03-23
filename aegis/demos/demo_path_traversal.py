#!/usr/bin/env python3
"""
Demo: Path Traversal Attack

Shows how AEGIS blocks tool calls attempting path traversal.
"""

import json
import subprocess
import sys


def demo_path_traversal():
    """Demonstrate path traversal blocking."""
    print("\n" + "="*60)
    print("DEMO: Path Traversal Attack")
    print("="*60 + "\n")

    # Malicious tool call with path traversal
    malicious_calls = [
        {
            "name": "read_file",
            "arguments": {
                "path": "../../etc/passwd"
            }
        },
        {
            "name": "read_file",
            "arguments": {
                "path": "/var/www/uploads/../../../etc/shadow"
            }
        },
        {
            "name": "download_file",
            "arguments": {
                "url": "http://example.com/file",
                "output": "..\\..\\Windows\\System32\\malware.exe"
            }
        }
    ]

    for i, malicious_call in enumerate(malicious_calls, 1):
        print(f"Attack {i}: Testing path traversal:")
        print(json.dumps(malicious_call, indent=2))
        print()

        result = subprocess.run(
            ['aegis', 'check', json.dumps(malicious_call)],
            capture_output=True,
            text=True
        )

        print(result.stdout)

        if result.returncode != 0:
            print(f"✓ Attack {i} BLOCKED by AEGIS")
        else:
            print(f"✗ Attack {i} was NOT blocked (unexpected!)")

        print("\n" + "-"*60 + "\n")

    # Clean tool call
    clean_call = {
        "name": "read_file",
        "arguments": {
            "path": "/home/user/documents/report.txt"
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
    demo_path_traversal()
