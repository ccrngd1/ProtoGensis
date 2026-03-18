#!/usr/bin/env python3
"""
Demo script showing PseudoAct and ReAct in action.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pseudoact import run_pseudoact, run_react, get_default_tools


def print_separator(title=""):
    """Print a separator line."""
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)
    print()


def demo_calculator_task():
    """Demo: Simple calculation task."""
    query = "Calculate (15 + 7) * 3 and then take the square root of the result"

    print_separator("DEMO 1: Calculator Task")
    print(f"Query: {query}\n")

    # Run PseudoAct
    print("Running PseudoAct approach...")
    pseudoact_result = run_pseudoact(query)
    print(f"\nPseudoAct Result: {pseudoact_result['result']}")
    print(f"Token Usage: {pseudoact_result['usage']['total_input']} input, {pseudoact_result['usage']['total_output']} output")
    print(f"\nGenerated Plan:\n{pseudoact_result['plan']}")

    # Run ReAct
    print("\n" + "-" * 80)
    print("Running ReAct baseline...")
    react_result = run_react(query)
    print(f"\nReAct Result: {react_result['result']}")
    print(f"Token Usage: {react_result['usage']['input_tokens']} input, {react_result['usage']['output_tokens']} output")
    print(f"Iterations: {react_result['iterations']}")


def demo_search_task():
    """Demo: Search and fact-gathering task."""
    query = "Search for information about Python and AI, then combine the results"

    print_separator("DEMO 2: Search Task")
    print(f"Query: {query}\n")

    # Run PseudoAct
    print("Running PseudoAct approach...")
    pseudoact_result = run_pseudoact(query)
    print(f"\nPseudoAct Result: {pseudoact_result['result']}")
    print(f"Token Usage: {pseudoact_result['usage']['total_input']} input, {pseudoact_result['usage']['total_output']} output")

    # Run ReAct
    print("\n" + "-" * 80)
    print("Running ReAct baseline...")
    react_result = run_react(query)
    print(f"\nReAct Result: {react_result['result']}")
    print(f"Token Usage: {react_result['usage']['input_tokens']} input, {react_result['usage']['output_tokens']} output")
    print(f"Iterations: {react_result['iterations']}")


def demo_conditional_task():
    """Demo: Task with conditional logic."""
    query = "Calculate 5 + 3. If the result is greater than 5, search for 'AI', otherwise search for 'Python'"

    print_separator("DEMO 3: Conditional Task")
    print(f"Query: {query}\n")

    # Run PseudoAct
    print("Running PseudoAct approach...")
    try:
        pseudoact_result = run_pseudoact(query)
        print(f"\nPseudoAct Result: {pseudoact_result['result']}")
        print(f"Token Usage: {pseudoact_result['usage']['total_input']} input, {pseudoact_result['usage']['total_output']} output")
        print(f"\nGenerated Plan:\n{pseudoact_result['plan']}")
    except Exception as e:
        print(f"PseudoAct error: {e}")

    # Run ReAct
    print("\n" + "-" * 80)
    print("Running ReAct baseline...")
    try:
        react_result = run_react(query)
        print(f"\nReAct Result: {react_result['result']}")
        print(f"Token Usage: {react_result['usage']['input_tokens']} input, {react_result['usage']['output_tokens']} output")
        print(f"Iterations: {react_result['iterations']}")
    except Exception as e:
        print(f"ReAct error: {e}")


def main():
    """Run all demos."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("║                  PseudoAct Demo - Protogenesis W10                        ║")
    print("║              Pseudocode Planning for LLM Agents                           ║")
    print("╚═══════════════════════════════════════════════════════════════════════════╝")

    try:
        # Demo 1: Calculator
        demo_calculator_task()

        # Demo 2: Search
        demo_search_task()

        # Demo 3: Conditional
        demo_conditional_task()

        print_separator("Demo Complete")
        print("All demos completed successfully!")

    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
