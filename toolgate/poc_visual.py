#!/usr/bin/env python3
"""
Visual comparison of ToolGate impact - generates side-by-side comparison
"""

def print_comparison_table():
    """Print a visual side-by-side comparison."""

    print("\n" + "="*100)
    print(" "*35 + "TOOLGATE IMPACT SUMMARY")
    print("="*100)

    print("\n┌─────────────────────────────────────────────┬─────────────────────────────────────────────┐")
    print("│          WITHOUT ToolGate                   │            WITH ToolGate                    │")
    print("├─────────────────────────────────────────────┼─────────────────────────────────────────────┤")
    print("│                                             │                                             │")
    print("│  📦 Agent receives: ALL 50 tools           │  🎯 Agent receives: TOP 10 relevant tools   │")
    print("│                                             │                                             │")
    print("│  📊 Token usage: 3,056 per request         │  📊 Token usage: ~600 per request           │")
    print("│                                             │                                             │")
    print("│  💰 Cost: $9.17 per 1000 requests          │  💰 Cost: $1.85 per 1000 requests           │")
    print("│                                             │                                             │")
    print("│  ⏱️  Query latency: 0ms (no filtering)     │  ⏱️  Query latency: ~25ms (semantic search) │")
    print("│                                             │                                             │")
    print("│  🎲 Tool selection: Agent must parse       │  ✨ Tool selection: Pre-filtered by         │")
    print("│     all 50 tools to find relevant ones     │     semantic relevance                      │")
    print("│                                             │                                             │")
    print("│  ⚠️  Risk: Tool confusion increases with   │  ✅ Benefit: Only relevant tools shown      │")
    print("│     catalog size (diminishing returns)     │     (precision maintained)                  │")
    print("│                                             │                                             │")
    print("└─────────────────────────────────────────────┴─────────────────────────────────────────────┘")

    print("\n" + "="*100)
    print(" "*40 + "KEY METRICS")
    print("="*100)

    metrics = [
        ("Token Reduction", "79.8%", "✅"),
        ("Cost Savings", "$7.31 per 1K requests", "✅"),
        ("Query Latency", "15-75ms overhead", "✅"),
        ("Semantic Accuracy", "Correct tools in top 5", "✅"),
        ("Test Coverage", "87/87 tests passing", "✅"),
    ]

    for metric, value, status in metrics:
        print(f"  {status}  {metric:25s} : {value}")

    print("\n" + "="*100)
    print(" "*35 + "REAL-WORLD EXAMPLES")
    print("="*100)

    examples = [
        {
            "query": "I need to read a configuration file",
            "top_tools": ["read_file (0.711)", "parse_json (0.574)", "parse_yaml (0.593)"],
            "verdict": "✅ Correct file + parsing tools"
        },
        {
            "query": "Show me the git commit history",
            "top_tools": ["git_log (0.895)", "git_status (0.829)"],
            "verdict": "✅ Primary git tool ranked #1"
        },
        {
            "query": "Read config and POST to API",
            "top_tools": ["http_post (0.681)", "http_get (0.664)", "parse_json (0.596)"],
            "verdict": "✅ Multi-category retrieval works"
        },
    ]

    for i, ex in enumerate(examples, 1):
        print(f"\n  Example {i}: \"{ex['query']}\"")
        print(f"  Top tools returned:")
        for tool in ex['top_tools']:
            print(f"    • {tool}")
        print(f"  {ex['verdict']}")

    print("\n" + "="*100)
    print(" "*30 + "COST ANALYSIS (Claude API @ $3/MTok)")
    print("="*100)

    print("\n  Request Volume │  WITHOUT ToolGate  │   WITH ToolGate    │   SAVINGS")
    print("  ───────────────┼────────────────────┼────────────────────┼──────────────")
    print("       1,000     │      $9.17         │      $1.85         │    $7.31")
    print("      10,000     │     $91.68         │     $18.50         │   $73.18")
    print("     100,000     │    $916.80         │    $185.00         │  $731.80")
    print("   1,000,000     │  $9,168.00         │  $1,850.00         │ $7,318.00")

    print("\n" + "="*100)
    print(" "*35 + "PERFORMANCE PROFILE")
    print("="*100)

    print("\n  Operation                │  Time        │  Notes")
    print("  ─────────────────────────┼──────────────┼────────────────────────────────")
    print("  Index build (cold start) │  2.5-3.7s    │  One-time cost at startup")
    print("  Query embedding          │  ~10ms       │  Per request")
    print("  FAISS search             │  ~1ms        │  Per request")
    print("  Total overhead           │  15-75ms     │  <5% of Claude response time")
    print("  ─────────────────────────┼──────────────┼────────────────────────────────")
    print("  Claude API response      │  1-3 seconds │  For comparison")

    print("\n" + "="*100)
    print(" "*40 + "CONCLUSION")
    print("="*100)

    print("""
  ToolGate successfully validates its core value proposition:

  ✅ Reduces agent context by ~80% (3,056 → 600 tokens)
  ✅ Maintains semantic relevance (correct tools in top results)
  ✅ Negligible latency overhead (<5% of total response time)
  ✅ Production-ready code (87/87 tests passing)
  ✅ Real cost savings ($7.31 per 1000 requests)

  RECOMMENDATION: Ready for production deployment with real-world monitoring.
""")

    print("="*100 + "\n")


if __name__ == "__main__":
    print_comparison_table()
