#!/usr/bin/env python3
"""
Quick example: Running MoA ensemble in mock mode.

This demonstrates the core functionality without requiring AWS credentials.
"""

import asyncio
from moa import create_moa_from_recipe


async def main():
    print("=" * 60)
    print("MoA on Bedrock - Quick Example (Mock Mode)")
    print("=" * 60)

    # Example 1: Ultra-cheap ensemble
    print("\n[Example 1] Ultra-Cheap Ensemble")
    print("-" * 60)

    moa = create_moa_from_recipe("ultra-cheap", mock_mode=True)
    prompt = "What is the CAP theorem in distributed systems?"

    print(f"Prompt: {prompt}")
    print("\nRunning ensemble...\n")

    response = await moa.run(prompt)

    print("Final Response:")
    print(response.final_response)
    print("\n" + "-" * 60)
    print("Cost Summary:")
    print(f"  Total cost: ${response.cost_summary['total_cost']:.6f}")
    print(f"  Total invocations: {response.cost_summary['num_invocations']}")
    print("\nLatency Summary:")
    print(f"  Total duration: {response.latency_summary['total_duration_ms']:.2f}ms")
    print(f"  Number of layers: {response.latency_summary['num_layers']}")

    # Example 2: Code generation ensemble
    print("\n\n[Example 2] Code Generation Ensemble")
    print("-" * 60)

    moa = create_moa_from_recipe("code-generation", mock_mode=True)
    prompt = "Write a Python function to check if a string is a palindrome."

    print(f"Prompt: {prompt}")
    print("\nRunning ensemble...\n")

    response = await moa.run(prompt)

    print("Final Response:")
    print(response.final_response[:300] + "..." if len(response.final_response) > 300 else response.final_response)
    print("\n" + "-" * 60)
    print("Cost Summary:")
    print(f"  Total cost: ${response.cost_summary['total_cost']:.6f}")
    print(f"  Layer 0 (proposers): ${response.cost_summary['layer_costs']['layer_0']:.6f}")
    print(f"  Layer 1 (aggregator): ${response.cost_summary['layer_costs']['layer_1']:.6f}")
    print("\nLatency Summary:")
    print(f"  Total duration: {response.latency_summary['total_duration_ms']:.2f}ms")

    # Example 3: Compare recipes
    print("\n\n[Example 3] Recipe Comparison")
    print("-" * 60)

    recipes = ["ultra-cheap", "code-generation", "reasoning"]
    test_prompt = "Explain how a LRU cache works and how to implement it efficiently."

    print(f"Prompt: {test_prompt}")
    print("\nComparing recipes...\n")

    for recipe_name in recipes:
        moa = create_moa_from_recipe(recipe_name, mock_mode=True)
        response = await moa.run(test_prompt)

        print(f"{recipe_name:20s} | "
              f"Cost: ${response.cost_summary['total_cost']:.6f} | "
              f"Latency: {response.latency_summary['total_duration_ms']:.0f}ms | "
              f"Invocations: {response.cost_summary['num_invocations']}")

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("\nTo use with real Bedrock API:")
    print("  1. Configure AWS credentials (aws configure)")
    print("  2. Set mock_mode=False in create_moa_from_recipe()")
    print("  3. Run the script")
    print("\nFor more examples, see README.md")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
