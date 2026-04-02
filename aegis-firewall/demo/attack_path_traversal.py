#!/usr/bin/env python3
"""
Demo: Path Traversal Attack (BLOCKED)

This demonstrates AEGIS blocking a path traversal attempt.
"""

import sys
sys.path.insert(0, '/tmp/aegis-firewall-build')

from aegis.engine import DecisionEngine


def main():
    print("=" * 60)
    print("DEMO: Path Traversal Attack")
    print("=" * 60)

    engine = DecisionEngine('policies/standard.yaml')

    # Malicious tool call with path traversal
    tool_name = "read_file"
    arguments = {
        "path": "../../../../etc/passwd",
        "encoding": "utf-8"
    }

    print(f"\nAttempting tool call: {tool_name}")
    print(f"Arguments: {arguments}")

    decision = engine.evaluate(tool_name, arguments)

    print(f"\n>>> DECISION: {decision['action'].upper()}")
    print(f">>> REASON: {decision['reason']}")
    print(f">>> Max Severity: {decision['policy_decision']['max_severity']}")

    # Show scanner results
    print("\nScanner Results:")
    for result in decision['scanner_results']:
        if result['detected']:
            print(f"  - {result['scanner']}: {result['severity']} severity")
            if result['findings']:
                for finding in result['findings'][:3]:  # Show first 3
                    print(f"    • {finding['type']}: {finding.get('pattern', 'N/A')}")

    # Expected: DENY due to path traversal
    assert decision['action'] == 'deny', "Expected DENY"
    print("\n✓ Attack successfully BLOCKED!")


if __name__ == '__main__':
    main()
