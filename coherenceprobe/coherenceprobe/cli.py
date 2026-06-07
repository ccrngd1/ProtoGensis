"""Command-line interface for CoherenceProbe."""

import sys
from pathlib import Path
import click

from .models import CoherenceConfig
from .capture import load_outputs_from_jsonl, load_outputs_from_directory
from .extraction import extract_claims
from .detection import detect_contradictions
from .scoring import compute_coherence_score
from .reporting import format_report, save_report


@click.group()
@click.version_option(version="0.1.0")
def main():
    """CoherenceProbe - Detect contradictions in multi-agent AI pipelines."""
    pass


@main.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['json', 'text', 'html']), default='text',
              help='Output format')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path (default: stdout)')
@click.option('--model', '-m', default='openai/gpt-4o-mini',
              help='LiteLLM model for claim extraction')
@click.option('--threshold', '-t', type=float, default=0.7,
              help='NLI confidence threshold for contradictions (0.0-1.0)')
@click.option('--local', is_flag=True,
              help='Use fully local mode (spaCy extraction, no API calls)')
@click.option('--nli-model', default='cross-encoder/nli-deberta-v3-large',
              help='HuggingFace NLI model')
@click.option('--embedding-model', default='all-MiniLM-L6-v2',
              help='Sentence-transformers embedding model')
@click.option('--adjudicate', is_flag=True,
              help='Use LLM to explain ambiguous contradictions')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose output')
def check(input_path, format, output, model, threshold, local, nli_model,
         embedding_model, adjudicate, verbose):
    """Check coherence of agent outputs.

    INPUT_PATH can be:
    - A JSONL file with agent outputs (one JSON object per line)
    - A directory where each file is one agent's output (filename = agent name)
    """
    try:
        # Load outputs
        input_path = Path(input_path)
        if input_path.is_file():
            if verbose:
                click.echo(f"Loading outputs from JSONL: {input_path}")
            outputs = load_outputs_from_jsonl(input_path)
        elif input_path.is_dir():
            if verbose:
                click.echo(f"Loading outputs from directory: {input_path}")
            outputs = load_outputs_from_directory(input_path)
        else:
            click.echo(f"Error: {input_path} is neither a file nor a directory", err=True)
            sys.exit(1)

        if not outputs:
            click.echo("Error: No agent outputs found", err=True)
            sys.exit(1)

        if verbose:
            click.echo(f"Loaded {len(outputs)} agent outputs")

        # Configure
        config = CoherenceConfig(
            model=model,
            threshold=threshold,
            local=local,
            nli_model=nli_model,
            embedding_model=embedding_model,
            adjudicate_ambiguous=adjudicate,
            verbose=verbose
        )

        # Extract claims
        if verbose:
            click.echo("\nExtracting claims...")
        claims = extract_claims(outputs, config)

        if not claims:
            click.echo("Warning: No claims extracted", err=True)

        # Detect contradictions
        if verbose:
            click.echo("\nDetecting contradictions...")
        contradictions = detect_contradictions(claims, config)

        # Compute coherence score
        if verbose:
            click.echo("\nComputing coherence score...")
        report = compute_coherence_score(claims, contradictions, config)

        # Output report
        formatted_report = format_report(report, format)

        if output:
            save_report(report, output, format)
            click.echo(f"\nReport saved to: {output}")
        else:
            click.echo("\n" + formatted_report)

        # Exit with appropriate code
        if report.score < 0.5:
            sys.exit(1)  # Severe incoherence
        elif report.score < 0.8:
            sys.exit(0)  # Some issues but not critical

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument('output_path', type=click.Path())
def init(output_path):
    """Initialize a new capture file for collecting agent outputs.

    Creates an empty JSONL file ready for capturing agent outputs.
    """
    output_path = Path(output_path)

    if output_path.exists():
        if not click.confirm(f"{output_path} already exists. Overwrite?"):
            return

    # Create empty file
    output_path.write_text("")
    click.echo(f"Created capture file: {output_path}")
    click.echo("\nExample Python usage:")
    click.echo("  from coherenceprobe import FileCapture")
    click.echo(f'  capture = FileCapture("{output_path}")')
    click.echo('  capture.capture("agent1", "input", "output")')


@main.command()
def info():
    """Display information about CoherenceProbe configuration."""
    click.echo("CoherenceProbe v0.1.0")
    click.echo("\nDefault Configuration:")
    config = CoherenceConfig()
    click.echo(f"  LLM Model: {config.model}")
    click.echo(f"  NLI Model: {config.nli_model}")
    click.echo(f"  Embedding Model: {config.embedding_model}")
    click.echo(f"  Threshold: {config.threshold}")
    click.echo(f"  Local Mode: {config.local}")
    click.echo("\nTo use local mode (no API calls):")
    click.echo("  coherenceprobe check --local <input>")
    click.echo("\nFor help:")
    click.echo("  coherenceprobe check --help")


@main.command()
@click.argument('input_path', type=click.Path(exists=True))
def stats(input_path):
    """Show statistics about agent outputs without running full analysis."""
    try:
        # Load outputs
        input_path = Path(input_path)
        if input_path.is_file():
            outputs = load_outputs_from_jsonl(input_path)
        elif input_path.is_dir():
            outputs = load_outputs_from_directory(input_path)
        else:
            click.echo(f"Error: {input_path} is neither a file nor a directory", err=True)
            sys.exit(1)

        if not outputs:
            click.echo("No agent outputs found")
            return

        # Compute statistics
        agents = list(set(o.agent for o in outputs))
        agents.sort()

        click.echo(f"Total outputs: {len(outputs)}")
        click.echo(f"Total agents: {len(agents)}")
        click.echo(f"\nAgents: {', '.join(agents)}")

        click.echo("\nOutputs per agent:")
        from collections import Counter
        agent_counts = Counter(o.agent for o in outputs)
        for agent, count in sorted(agent_counts.items()):
            click.echo(f"  {agent}: {count}")

        # Average output length
        avg_length = sum(len(o.output) for o in outputs) / len(outputs)
        click.echo(f"\nAverage output length: {avg_length:.0f} characters")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
