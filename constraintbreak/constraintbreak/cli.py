"""CLI interface for ConstraintBreak."""

import typer
from typing import Optional
from rich.console import Console
import uuid

from .providers import OpenAIProvider, AnthropicProvider, BedrockProvider, MockProvider
from .constraints.engine import ConstraintEngine
from .tasks.loader import TaskLoader
from .engine import PairwiseEngine
from .recovery import RecoveryTester
from .storage import ResultStorage
from .report import ReportGenerator

app = typer.Typer(
    name="constraintbreak",
    help="Test whether output constraints silently degrade LLM quality.",
)
console = Console()


def get_provider(
    provider: str,
    model: str,
    api_key: Optional[str] = None,
):
    """Get provider instance.

    Args:
        provider: Provider name (openai/anthropic/bedrock/mock)
        model: Model name
        api_key: Optional API key

    Returns:
        Provider instance
    """
    provider = provider.lower()

    if provider == "openai":
        kwargs = {"api_key": api_key} if api_key else {}
        return OpenAIProvider(model_name=model, **kwargs)
    elif provider == "anthropic":
        kwargs = {"api_key": api_key} if api_key else {}
        return AnthropicProvider(model_name=model, **kwargs)
    elif provider == "bedrock":
        return BedrockProvider(model_name=model)
    elif provider == "mock":
        return MockProvider(model_name=model)
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)


@app.command()
def scan(
    provider: str = typer.Option("mock", "--provider", "-p", help="LLM provider"),
    model: str = typer.Option("mock-model", "--model", "-m", help="Model name"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key"),
    constraints_file: Optional[str] = typer.Option(None, "--constraints", help="Custom constraints YAML"),
    tasks_file: Optional[str] = typer.Option(None, "--tasks", help="Custom tasks YAML"),
    constraint_name: Optional[str] = typer.Option(None, "--constraint", help="Test single constraint"),
    task_category: Optional[str] = typer.Option(None, "--category", help="Filter tasks by category"),
    use_logit_bias: bool = typer.Option(False, "--logit-bias", help="Use token-level constraints"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output report file (.md or .json)"),
    db: str = typer.Option("constraintbreak.db", "--db", help="Database file"),
):
    """Run constraint fragility scan against a model."""
    console.print("[bold]ConstraintBreak: Constraint Fragility Scanner[/bold]\n")

    # Initialize components
    provider_instance = get_provider(provider, model, api_key)
    constraint_engine = ConstraintEngine(constraints_file)
    task_loader = TaskLoader(tasks_file)
    pairwise_engine = PairwiseEngine(provider_instance)
    storage = ResultStorage(db)
    report_gen = ReportGenerator()

    # Get constraints
    if constraint_name:
        constraint = constraint_engine.get_constraint(constraint_name)
        if not constraint:
            console.print(f"[red]Constraint not found: {constraint_name}[/red]")
            raise typer.Exit(1)
        constraints = [constraint]
    else:
        constraints = constraint_engine.list_constraints()

    # Get tasks
    tasks = task_loader.get_tasks(task_category)

    console.print(f"Provider: {provider} / {model}")
    console.print(f"Constraints: {len(constraints)}")
    console.print(f"Tasks: {len(tasks)}")
    console.print(f"Total comparisons: {len(constraints) * len(tasks)}\n")

    # Run scan
    results = pairwise_engine.scan_full_matrix(
        tasks=tasks,
        constraints=constraints,
        use_logit_bias=use_logit_bias,
        progress=True,
    )

    # Save to database
    run_id = str(uuid.uuid4())
    storage.save_run_metadata(
        run_id=run_id,
        provider=provider,
        model_name=model,
        test_type="scan",
        config={"use_logit_bias": use_logit_bias},
    )
    storage.save_comparison_results(results, run_id, provider, model)

    # Generate reports
    console.print("\n")
    report_gen.print_summary(results)
    console.print("\n")
    report_gen.generate_comparison_heatmap(results, show=True)

    # Save output file
    if output:
        if output.endswith(".json"):
            report_gen.generate_json_report(results, provider, model, output)
            console.print(f"\n[green]JSON report saved to {output}[/green]")
        else:
            report_gen.generate_markdown_report(results, provider, model, output)
            console.print(f"\n[green]Markdown report saved to {output}[/green]")

    console.print(f"\n[green]Results saved to database: {db}[/green]")
    console.print(f"[dim]Run ID: {run_id}[/dim]")


@app.command()
def recover(
    constraint: str = typer.Argument(..., help="Constraint name to test"),
    provider: str = typer.Option("mock", "--provider", "-p", help="LLM provider"),
    model: str = typer.Option("mock-model", "--model", "-m", help="Model name"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key"),
    tasks_file: Optional[str] = typer.Option(None, "--tasks", help="Custom tasks YAML"),
    task_category: Optional[str] = typer.Option(None, "--category", help="Filter tasks by category"),
    use_logit_bias: bool = typer.Option(False, "--logit-bias", help="Use token-level constraints"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output report file"),
    db: str = typer.Option("constraintbreak.db", "--db", help="Database file"),
):
    """Test two-pass recovery for a specific constraint."""
    console.print("[bold]ConstraintBreak: Two-Pass Recovery Tester[/bold]\n")

    # Initialize components
    provider_instance = get_provider(provider, model, api_key)
    constraint_engine = ConstraintEngine()
    task_loader = TaskLoader(tasks_file)
    recovery_tester = RecoveryTester(provider_instance)
    storage = ResultStorage(db)
    report_gen = ReportGenerator()

    # Get constraint
    constraint_obj = constraint_engine.get_constraint(constraint)
    if not constraint_obj:
        console.print(f"[red]Constraint not found: {constraint}[/red]")
        raise typer.Exit(1)

    # Get tasks
    tasks = task_loader.get_tasks(task_category)

    console.print(f"Provider: {provider} / {model}")
    console.print(f"Constraint: {constraint}")
    console.print(f"Tasks: {len(tasks)}\n")

    # Run recovery tests
    results = recovery_tester.test_multiple(
        tasks=tasks,
        constraint=constraint_obj,
        use_logit_bias=use_logit_bias,
        progress=True,
    )

    # Calculate recovery rate
    recovery_rate = recovery_tester.calculate_recovery_rate(results)

    # Save to database
    run_id = str(uuid.uuid4())
    storage.save_run_metadata(
        run_id=run_id,
        provider=provider,
        model_name=model,
        test_type="recover",
        config={"constraint": constraint, "use_logit_bias": use_logit_bias},
    )
    storage.save_recovery_results(results, run_id, provider, model)

    # Generate report
    console.print("\n")
    console.print(f"[bold]Overall Recovery Rate: {recovery_rate * 100:.1f}%[/bold]\n")

    report_text = report_gen.generate_recovery_report(
        results, provider, model, constraint
    )

    if output:
        with open(output, "w") as f:
            f.write(report_text)
        console.print(f"[green]Report saved to {output}[/green]")
    else:
        console.print(report_text)

    console.print(f"\n[green]Results saved to database: {db}[/green]")
    console.print(f"[dim]Run ID: {run_id}[/dim]")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to generate report for"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (.md or .json)"),
    db: str = typer.Option("constraintbreak.db", "--db", help="Database file"),
):
    """Generate report from previous scan results."""
    console.print("[bold]ConstraintBreak: Report Generator[/bold]\n")

    storage = ResultStorage(db)
    report_gen = ReportGenerator()

    # Get results
    results_data = storage.get_comparison_results(run_id)

    if not results_data:
        console.print(f"[red]No results found for run ID: {run_id}[/red]")
        raise typer.Exit(1)

    # Convert to ComparisonResult objects
    from .engine import ComparisonResult

    results = []
    for r in results_data:
        result = ComparisonResult(
            task_name=r["task_name"],
            constraint_name=r["constraint_name"],
            unconstrained_response=r["unconstrained_response"] or "",
            constrained_response=r["constrained_response"] or "",
            winner_ab=r["winner_ab"],
            winner_ba=r["winner_ba"],
            degradation_detected=bool(r["degradation_detected"]),
            win_rate=r["win_rate"],
        )
        results.append(result)

    provider = results_data[0]["provider"]
    model = results_data[0]["model_name"]

    # Generate report
    report_gen.print_summary(results)
    console.print("\n")
    report_gen.generate_comparison_heatmap(results, show=True)

    if output:
        if output.endswith(".json"):
            report_gen.generate_json_report(results, provider, model, output)
            console.print(f"\n[green]JSON report saved to {output}[/green]")
        else:
            report_gen.generate_markdown_report(results, provider, model, output)
            console.print(f"\n[green]Markdown report saved to {output}[/green]")


@app.command("constraints")
def list_constraints(
    constraints_file: Optional[str] = typer.Option(None, "--constraints", help="Custom constraints YAML"),
):
    """List available constraints."""
    console.print("[bold]Available Constraints[/bold]\n")

    constraint_engine = ConstraintEngine(constraints_file)
    constraints = constraint_engine.list_constraints()

    for constraint in constraints:
        console.print(f"[bold cyan]{constraint.name}[/bold cyan]")
        console.print(f"  Category: {constraint.category}")
        console.print(f"  Description: {constraint.description}")
        console.print(f"  Instruction: {constraint.instruction}")
        if constraint.tokens:
            console.print(f"  Tokens: {', '.join(constraint.tokens)}")
        console.print("")

    console.print(f"[green]Total: {len(constraints)} constraints[/green]")


if __name__ == "__main__":
    app()
