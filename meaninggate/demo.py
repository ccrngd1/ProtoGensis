#!/usr/bin/env python3
"""
P5: MeaningGate demo CLI.
Side-by-side ungoverned vs governed + verification report.
"""
import argparse
import json
import sys
import os

# Check for Bedrock creds
if not os.getenv("AWS_ACCESS_KEY_ID"):
    print("⚠️  WARNING: No AWS credentials found. Running in MOCK MODE (no live LLM).", file=sys.stderr)
    MOCK_MODE = True
else:
    MOCK_MODE = False


def run_demo(question: str, mock: bool = MOCK_MODE):
    """Run side-by-side demo: ungoverned vs governed."""
    print("=" * 80)
    print("MeaningGate Demo: Semantic Governance for Healthcare Denials")
    print("=" * 80)
    print(f"Question: {question}")
    print()

    if mock:
        print("🔸 MOCK MODE: Using cached responses (no live LLM)")
        print()
        return run_mock_demo(question)

    # Real LLM mode
    from agents.ungoverned import UngovernedAgent
    from agents.governed import GovernedAgent
    from eval.verify import verify_governed_answer

    print("--- Ungoverned Agent (raw SQL tool) ---")
    ungoverned = UngovernedAgent()
    try:
        ung_result = ungoverned.answer(question, timeout=120)
        if "error" in ung_result:
            print(f"❌ Error: {ung_result['error']}")
        else:
            print(f"Answer: {ung_result['answer'][:500]}...")
            print(f"Tool calls: {ung_result['tool_calls']}, Turns: {ung_result['turns']}")
    except Exception as e:
        print(f"❌ Exception: {e}")
        ung_result = {"error": str(e)}

    print()
    print("--- Governed Agent (semantic tools) ---")
    governed = GovernedAgent()
    try:
        gov_result = governed.answer(question, timeout=120)
        if "error" in gov_result:
            print(f"❌ Error: {gov_result['error']}")
        else:
            print(f"Answer: {gov_result['answer'][:500]}...")
            print(f"Tool calls: {gov_result['tool_calls']}, Turns: {gov_result['turns']}")
    except Exception as e:
        print(f"❌ Exception: {e}")
        gov_result = {"error": str(e)}

    print()
    print("--- Verification Report ---")
    if "error" not in gov_result:
        verification = verify_governed_answer(gov_result)
        print(f"Diff count: {verification['diff_count']}")
        print(f"Passed: {'✅' if verification['passed'] else '❌'}")
        if verification['diffs']:
            print("Diffs:")
            for diff in verification['diffs']:
                print(f"  - {diff}")
    else:
        print("⚠️  Cannot verify - governed agent failed")

    return {
        "ungoverned": ung_result,
        "governed": gov_result,
        "verification": verification if "error" not in gov_result else None
    }


def run_mock_demo(question: str):
    """Mock demo with cached responses."""
    # Mock ungoverned answer (realistic ambiguity)
    ung_answer = """Based on the data, I found that Ohio had 604 denied claim lines
in the last quarter with a denial rate of 12.9%. The main reason code is CARC-197
which accounts for about 61% of denials. The total allowed amount for these denials
is approximately $354,110.

The high rate appears to be related to authorization issues, but without more
context about your specific policies and authorization workflows, I can't determine
the exact root cause. You may want to check with your authorization team."""

    ung_result = {
        "answer": ung_answer,
        "tool_calls": 3,
        "turns": 2
    }

    # Mock governed answer (precise, traced)
    gov_answer = """The first-pass line denial rate in Ohio for outpatient imaging is 12.9%
(604 denied out of 4,678 eligible lines). CARC-197 accounts for 61.6% of these denials,
representing $354,110.56 in at-risk allowed dollars.

Root cause: UM-RAD-2026 policy (effective 2026-04-01) requires 120-day prior
authorization notice per MP-RAD-114 §4.2 and contract §7.3. Health System 14 (HS-14)
was omitted from notification cohort NC-2026-03, resulting in all HS-14 outpatient
imaging claims being denied with CARC-197.

Accountable party: Plan (ACME Commercial PPO - Ohio) - notification gap.

Remediation: Add HS-14 TINs to notification cohort and reprocess denied claims under appeal."""

    gov_result = {
        "answer": gov_answer,
        "tool_calls": 5,
        "turns": 3
    }

    print("--- Ungoverned Agent (raw SQL tool) ---")
    print(f"Answer: {ung_result['answer']}")
    print(f"Tool calls: {ung_result['tool_calls']}, Turns: {ung_result['turns']}")
    print()

    print("--- Governed Agent (semantic tools) ---")
    print(f"Answer: {gov_result['answer']}")
    print(f"Tool calls: {gov_result['tool_calls']}, Turns: {gov_result['turns']}")
    print()

    print("--- Verification Report ---")
    from eval.verify import verify_governed_answer
    verification = verify_governed_answer(gov_result)
    print(f"Diff count: {verification['diff_count']}")
    print(f"Passed: {'✅' if verification['passed'] else '❌'}")
    if verification['diffs']:
        print("Diffs:")
        for diff in verification['diffs']:
            print(f"  - {diff}")

    return {
        "ungoverned": ung_result,
        "governed": gov_result,
        "verification": verification
    }


def main():
    parser = argparse.ArgumentParser(description="MeaningGate demo")
    parser.add_argument("--question", type=str,
                       default="Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?",
                       help="Question to answer")
    parser.add_argument("--mock", action="store_true",
                       help="Force mock mode (no LLM)")

    args = parser.parse_args()

    result = run_demo(args.question, mock=args.mock or MOCK_MODE)

    # Save result
    with open("demo_result.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    print()
    print("=" * 80)
    print("Demo complete. Results saved to demo_result.json")


if __name__ == "__main__":
    main()
