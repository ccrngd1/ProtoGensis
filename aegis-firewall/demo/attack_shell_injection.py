#!/usr/bin/env python3
"""
Demo: Shell Injection Attack (BLOCKED)

This demonstrates AEGIS blocking a shell injection attempt.
"""

import sys
sys.path.insert(0, '/tmp/aegis-firewall-build')

from aegis.engine import DecisionEngine


def main():
    print("=" * 60)
    print("DEMO: Shell Injection Attack")
    print("=" * 60)

    engine = DecisionEngine('policies/standard.yaml')

    # Malicious tool call with shell injection
    tool_name = "exec"
    arguments = {
        "command": "ls -la; rm -rf /important/data",
        "user": "attacker"
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
            print(f"    Findings: {len(result['findings'])}")

    # Expected: DENY due to shell injection
    assert decision['action'] == 'deny', "Expected DENY"
    print("\n✓ Attack successfully BLOCKED!")


if __name__ == '__main__':
    main()
