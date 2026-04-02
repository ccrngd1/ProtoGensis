#!/usr/bin/env python3
"""
Demo: PII Leakage Detection

This demonstrates AEGIS detecting PII in tool arguments.
"""

import sys
sys.path.insert(0, '/tmp/aegis-firewall-build')

from aegis.engine import DecisionEngine


def main():
    print("=" * 60)
    print("DEMO: PII Leakage Detection")
    print("=" * 60)

    engine = DecisionEngine('policies/standard.yaml')

    # Tool call containing PII
    tool_name = "send_message"
    arguments = {
        "to": "support@example.com",
        "subject": "User Data",
        "body": "Customer John Doe, SSN: 123-45-6789, Credit Card: 4532-1234-5678-9010, Email: john.doe@example.com"
    }

    print(f"\nAttempting tool call: {tool_name}")
    print(f"Arguments: (contains PII)")

    decision = engine.evaluate(tool_name, arguments)

    print(f"\n>>> DECISION: {decision['action'].upper()}")
    print(f">>> REASON: {decision['reason']}")
    print(f">>> Max Severity: {decision['policy_decision']['max_severity']}")

    # Show scanner results
    print("\nScanner Results:")
    for result in decision['scanner_results']:
        if result['detected']:
            print(f"  - {result['scanner']}: {result['severity']} severity")
            print(f"    Findings: {len(result['findings'])} PII items detected")

    # Expected: ESCALATE due to PII
    assert decision['action'] in ['escalate', 'deny'], "Expected ESCALATE or DENY"
    print(f"\n✓ PII detected! Action: {decision['action'].upper()}")


if __name__ == '__main__':
    main()
