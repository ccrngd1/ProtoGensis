"""AlignBias CLI (click)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from . import __version__
from .prober import Prober
from .providers.base import ProviderError, resolve_provider
from .report import (
    comparison_matrix,
    fmt_pp,
    plot_domain_heatmap,
    plot_skew_histogram,
    skew_card,
    write_json,
)
from .scenarios.loader import load_scenarios, track_a_path, track_b_path
from .skew import summarize


@click.group()
@click.version_option(__version__, prog_name="alignbias")
def main():
    """Audit LLM stacks for directional probability bias (OptimismBench method).

    Skew is reported in probability points (pp) on the 0-100 scale:
    Skew = s+ - (100 - s-); >0 optimistic, <0 pessimistic.
    """


def _run_audit(models, scenarios_path, runs, temperature, concurrency):
    scenarios = load_scenarios(scenarios_path)
    click.echo(
        f"Loaded {len(scenarios)} scenarios from {scenarios_path}; "
        f"probing {runs} run(s) x 2 frames per scenario."
    )
    reports, results_by_model = [], {}
    for spec in models:
        try:
            provider = resolve_provider(spec, temperature=temperature)
        except (ProviderError, ValueError) as exc:
            click.echo(f"skipping {spec}: {exc}", err=True)
            continue
        click.echo(f"Auditing {provider.label} ...")
        prober = Prober(provider, concurrency=concurrency)
        probe = asyncio.run(prober.probe(scenarios, runs=runs))
        report = summarize(provider.label, probe.results)
        reports.append(report)
        results_by_model[provider.label] = probe.results
    return reports, results_by_model


@main.command()
@click.option("--models", required=True, help="Comma-separated model specs, e.g. "
              "'anthropic:claude-opus-4-8,openai:gpt-5.6'")
@click.option("--scenarios", "scenarios_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="Scenario JSONL (default: bundled Track B 60).")
@click.option("--runs", default=5, show_default=True, help="Repeats per scenario.")
@click.option("--temperature", default=0.7, show_default=True, type=float)
@click.option("--concurrency", default=8, show_default=True)
@click.option("--out", "out_dir", type=click.Path(file_okay=False), default="./out",
              show_default=True, help="Output directory for skew.json and charts.")
@click.option("--no-charts", is_flag=True, help="Skip matplotlib chart generation.")
def audit(models, scenarios_path, runs, temperature, concurrency, out_dir, no_charts):
    """Run the inverted-pair bias audit against one or more live models."""
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    scenarios_path = Path(scenarios_path) if scenarios_path else track_b_path()
    reports, results_by_model = _run_audit(
        model_list, scenarios_path, runs, temperature, concurrency
    )
    if not reports:
        raise click.ClickException("no models could be audited")

    click.echo()
    for report in reports:
        click.echo(skew_card(report))
        click.echo()
    if len(reports) > 1:
        click.echo(comparison_matrix(reports))
        click.echo()

    out = Path(out_dir)
    json_path = write_json(reports, out / "skew.json", results_by_model)
    click.echo(f"wrote {json_path}")
    if not no_charts:
        try:
            hist = plot_skew_histogram(results_by_model, out / "skew_histogram.png")
            click.echo(f"wrote {hist}")
            heat = plot_domain_heatmap(reports, out / "skew_domain_heatmap.png")
            click.echo(f"wrote {heat}")
        except ValueError as exc:
            click.echo(f"chart skipped: {exc}", err=True)


@main.command()
@click.option("--models", required=True, help="Comma-separated model specs.")
@click.option("--scenarios", "scenarios_path", type=click.Path(exists=True, dir_okay=False),
              default=None,
              help="Track A calibration JSONL (default: bundled 15-item set).")
@click.option("--runs", default=3, show_default=True)
@click.option("--temperature", default=0.7, show_default=True, type=float)
@click.option("--concurrency", default=8, show_default=True)
@click.option("--tolerance", default=5.0, show_default=True,
              help="Max |Skew| in pp for the control to pass.")
def control(models, scenarios_path, runs, temperature, concurrency, tolerance):
    """Track A calibration control: stated-base-rate items should give Skew ~ 0.

    This validates the tool itself (prompting + parsing + math), not the
    model's worldview. A large Skew here means the harness, not the model's
    optimism, is broken.
    """
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    scenarios_path = Path(scenarios_path) if scenarios_path else track_a_path()
    reports, _ = _run_audit(model_list, scenarios_path, runs, temperature, concurrency)
    if not reports:
        raise click.ClickException("no models could be audited")

    failed = False
    for report in reports:
        status = "n/a"
        if report.skew_mean is not None:
            ok = abs(report.skew_mean) <= tolerance
            status = "PASS" if ok else "FAIL"
            failed |= not ok
        click.echo(
            f"{report.model}: control Skew {fmt_pp(report.skew_mean)} "
            f"(tolerance ±{tolerance:.1f} pp) — {status}"
        )
    if failed:
        raise click.ClickException(
            "control Skew outside tolerance — inspect prompting/parsing before "
            "trusting Track B results"
        )


@main.command("routing-advisor")
@click.option("--config", "config_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="routing.yaml with task -> expected tilt policies.")
@click.option("--report", "report_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="skew.json produced by `alignbias audit`.")
def routing_advisor(config_path, report_path):
    """Rank audited models per task type given a routing policy."""
    from .routing import (
        advise,
        format_recommendations,
        load_routing_config,
        load_skew_report,
    )

    policies = load_routing_config(config_path)
    summaries = load_skew_report(report_path)
    recommendations = advise(policies, summaries)
    click.echo(format_recommendations(recommendations))


@main.command()
@click.option("--report", "report_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="skew.json produced by `alignbias audit`.")
@click.option("--out", "out_path", default="./out/offsets.json", show_default=True,
              type=click.Path(dir_okay=False))
def calibrate(report_path, out_path):
    """Derive additive correction offsets (separate success/failure sides)."""
    from .calibrate import derive_offsets, write_offsets
    from .routing import load_skew_report

    summaries = load_skew_report(report_path)
    offsets = derive_offsets(summaries)
    path = write_offsets(offsets, out_path)
    for model, entry in offsets.items():
        if entry.get("offset_success_pp") is None:
            click.echo(f"{model}: insufficient data")
            continue
        click.echo(
            f"{model}: offset_success {entry['offset_success_pp']:+.2f} pp, "
            f"offset_failure {entry['offset_failure_pp']:+.2f} pp"
        )
    click.echo(f"wrote {path}")
    click.echo("note: offsets are a starting correction measured on the audit "
               "distribution, not a universal fix")


@main.command()
def demo():
    """Run the live demo (real API calls; degrades gracefully without keys)."""
    demo_script = Path(__file__).resolve().parent.parent / "demo" / "run_demo.py"
    if not demo_script.exists():
        raise click.ClickException(
            f"demo script not found at {demo_script} — run from a source "
            "checkout (git clone + pip install -e .)"
        )
    import runpy

    sys.argv = [str(demo_script)]
    runpy.run_path(str(demo_script), run_name="__main__")


@main.command("list-scenarios")
@click.option("--track", type=click.Choice(["A", "B"]), default="B", show_default=True)
def list_scenarios(track):
    """Print the bundled scenario set (no API keys needed)."""
    path = track_a_path() if track == "A" else track_b_path()
    for s in load_scenarios(path):
        base = f"[{s.id}] ({s.domain}) {s.scenario[:80]}"
        if s.p_true_positive is not None:
            base += f"  [stated P+ = {s.p_true_positive}]"
        click.echo(base)


if __name__ == "__main__":
    main()
