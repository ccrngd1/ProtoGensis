#!/usr/bin/env python3
"""AlignBias live demo.

Runs a small inverted-pair audit (Track A calibration subset + a few Track B
pairs) against Anthropic and OpenAI models with REAL API calls, then prints
Skew cards side by side.

Requires ANTHROPIC_API_KEY and/or OPENAI_API_KEY. If neither is set, prints
setup instructions and exits cleanly (no traceback).
"""

from __future__ import annotations

import asyncio
import os
import sys

ANTHROPIC_MODEL = os.environ.get("ALIGNBIAS_DEMO_ANTHROPIC_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.environ.get("ALIGNBIAS_DEMO_OPENAI_MODEL", "gpt-5.6")
DEMO_TRACK_B_PAIRS = 6  # one per domain — keeps the demo fast and cheap
DEMO_RUNS = 1


def _print_no_keys_help() -> None:
    print(
        "\n"
        "No API keys found - the demo makes real API calls and needs at\n"
        "least one of:\n"
        "\n"
        "  export ANTHROPIC_API_KEY=sk-ant-...   (console.anthropic.com)\n"
        "  export OPENAI_API_KEY=sk-...          (platform.openai.com)\n"
        "\n"
        "Then re-run:  alignbias demo    (or: python demo/run_demo.py)\n"
        "\n"
        "No keys handy? You can still explore offline:\n"
        "  alignbias list-scenarios --track B    # browse the 60 Track-B pairs\n"
        "  pytest                                # mock-provider test suite\n"
    )


async def _demo() -> int:
    from alignbias.prober import Prober
    from alignbias.providers.base import ProviderError
    from alignbias.report import comparison_matrix, fmt_pp, skew_card
    from alignbias.scenarios.loader import load_scenarios, track_a_path, track_b_path
    from alignbias.skew import summarize

    providers = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        from alignbias.providers.anthropic import AnthropicProvider

        try:
            providers.append(AnthropicProvider(ANTHROPIC_MODEL))
        except ProviderError as exc:
            print(f"skipping Anthropic: {exc}")
    else:
        print("ANTHROPIC_API_KEY not set - skipping Anthropic.")

    if os.environ.get("OPENAI_API_KEY"):
        from alignbias.providers.openai import OpenAIProvider

        try:
            providers.append(OpenAIProvider(OPENAI_MODEL))
        except ProviderError as exc:
            print(f"skipping OpenAI: {exc}")
    else:
        print("OPENAI_API_KEY not set - skipping OpenAI.")

    if not providers:
        _print_no_keys_help()
        return 0

    # Small sample: 3 Track A calibration items (harness sanity) + one Track B
    # pair per domain (the actual bias probe).
    track_a = load_scenarios(track_a_path())[:3]
    track_b_all = load_scenarios(track_b_path())
    seen_domains, track_b = set(), []
    for s in track_b_all:
        if s.domain not in seen_domains:
            seen_domains.add(s.domain)
            track_b.append(s)
        if len(track_b) >= DEMO_TRACK_B_PAIRS:
            break

    print(
        f"\nDemo audit: {len(track_a)} Track-A calibration items + "
        f"{len(track_b)} Track-B pairs, {DEMO_RUNS} run(s) each, "
        f"{len(providers)} model(s). This makes "
        f"{2 * DEMO_RUNS * (len(track_a) + len(track_b)) * len(providers)} "
        "API calls.\n"
    )

    reports = []
    for provider in providers:
        print(f"--- {provider.label} ---")
        prober = Prober(provider, concurrency=4)
        try:
            control_probe = await prober.probe(track_a, runs=DEMO_RUNS)
            audit_probe = await prober.probe(track_b, runs=DEMO_RUNS)
        except Exception as exc:  # keep the demo resilient to API hiccups
            print(f"  audit failed: {exc}")
            continue

        control = summarize(provider.label, control_probe.results)
        print(
            f"  Track A control Skew: {fmt_pp(control.skew_mean)} "
            "(should be near 0 - validates the harness, not the model)"
        )
        report = summarize(provider.label, audit_probe.results)
        reports.append(report)
        print(skew_card(report))
        print()

    if len(reports) > 1:
        print(comparison_matrix(reports))
        print()
    if reports:
        print(
            "Interpretation: Skew > 0 = optimistic tilt, < 0 = pessimistic, in\n"
            "probability points (pp). Skew measures internal coherence between\n"
            "inverted framings, not deviation from truth. This tiny sample is a\n"
            "demo - use `alignbias audit` with the full 60-pair set and\n"
            "--runs 5 for a real measurement."
        )
    return 0


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        _print_no_keys_help()
        return 0
    try:
        return asyncio.run(_demo())
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
