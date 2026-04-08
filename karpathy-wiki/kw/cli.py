"""Command-line interface for karpathy-wiki."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from .config import Config, find_kb_root
from .db import Database
from .llm import BedrockLLM
from .ingestion import Ingester
from .compiler import Compiler
from .query import QueryEngine
from .health import HealthChecker
from .watcher import watch_and_compile

app = typer.Typer(
    name="kw",
    help="karpathy-wiki: LLM Knowledge Base CLI",
    add_completion=False,
)
console = Console()


def get_kb_context() -> tuple[Config, Database, BedrockLLM]:
    """Get knowledge base context (config, db, llm).

    Returns:
        Tuple of (Config, Database, BedrockLLM)

    Raises:
        typer.Exit: If not in a knowledge base directory
    """
    kb_root = find_kb_root()
    if not kb_root:
        console.print(
            "[red]Error:[/red] Not in a knowledge base directory. "
            "Run [cyan]kw init[/cyan] first."
        )
        raise typer.Exit(1)

    config = Config(kb_root)
    db = Database(config.db_path)
    llm = BedrockLLM(
        model=config.llm_model,
        region=config.llm_region,
        max_tokens=config.llm_max_tokens,
        temperature=config.llm_temperature,
    )

    return config, db, llm


@app.command()
def init(
    path: Optional[str] = typer.Argument(
        None, help="Path to initialize knowledge base (default: current directory)"
    )
):
    """Initialize a new knowledge base."""
    kb_root = Path(path) if path else Path.cwd()
    kb_root = kb_root.resolve()

    # Check if already initialized
    if (kb_root / "kb.db").exists():
        console.print(f"[yellow]Knowledge base already exists at {kb_root}[/yellow]")
        raise typer.Exit(1)

    # Create directory structure
    kb_root.mkdir(parents=True, exist_ok=True)

    config = Config(kb_root)
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    config.wiki_dir.mkdir(parents=True, exist_ok=True)

    # Save default config
    config.save()

    # Initialize database
    db = Database(config.db_path)
    db.init_schema()
    db.close()

    console.print(Panel.fit(
        f"[green]✓[/green] Knowledge base initialized at [cyan]{kb_root}[/cyan]\n\n"
        f"Directories created:\n"
        f"  • {config.raw_dir.name}/  - Raw source inbox\n"
        f"  • {config.wiki_dir.name}/ - Wiki articles\n"
        f"  • kb.db      - SQLite database\n"
        f"  • kb.toml    - Configuration\n\n"
        f"Next steps:\n"
        f"  1. [cyan]kw ingest <file|url>[/cyan] - Add content\n"
        f"  2. [cyan]kw compile[/cyan] - Compile into wiki\n"
        f"  3. [cyan]kw query \"question\"[/cyan] - Ask questions",
        title="Knowledge Base Ready"
    ))


@app.command()
def ingest(
    source: str = typer.Argument(..., help="File path or URL to ingest"),
):
    """Add a file or URL to the raw/ inbox."""
    config, db, _ = get_kb_context()
    ingester = Ingester(config.raw_dir)

    try:
        # Determine if it's a URL or file
        if source.startswith(("http://", "https://")):
            console.print(f"Fetching URL: [cyan]{source}[/cyan]")
            relative_path, source_type, original_url = ingester.ingest_url(source)
        else:
            console.print(f"Ingesting file: [cyan]{source}[/cyan]")
            relative_path, source_type, original_url = ingester.ingest_file(source)

        # Add to database
        source_id = db.add_source(
            path=relative_path,
            source_type=source_type,
            original_url=original_url,
            status="pending",
        )

        console.print(
            f"[green]✓[/green] Ingested as [cyan]{source_type}[/cyan] "
            f"(ID: {source_id})\n"
            f"Path: {relative_path}\n\n"
            f"Run [cyan]kw compile[/cyan] to process this source."
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def compile(
    all: bool = typer.Option(False, "--all", help="Compile all pending sources"),
    source_id: Optional[int] = typer.Option(
        None, "--id", help="Compile specific source by ID"
    ),
):
    """Compile raw sources into wiki articles."""
    config, db, llm = get_kb_context()
    compiler = Compiler(config, db, llm)

    try:
        if source_id:
            # Compile specific source
            console.print(f"Compiling source ID {source_id}...")
            with console.status("[cyan]Compiling...[/cyan]"):
                article_ids = compiler.compile_source(source_id)

            console.print(
                f"[green]✓[/green] Created {len(article_ids)} article(s)"
            )

        elif all:
            # Compile all pending
            pending = db.get_pending_sources()
            if not pending:
                console.print("[yellow]No pending sources to compile[/yellow]")
                return

            console.print(f"Compiling {len(pending)} pending source(s)...")

            with console.status("[cyan]Compiling...[/cyan]"):
                results = compiler.compile_all_pending()

            console.print(
                f"[green]✓[/green] Compilation complete\n"
                f"  Success: {results['success']}\n"
                f"  Failed: {results['failed']}\n"
                f"  Articles created: {results['articles_created']}"
            )

        else:
            # Compile oldest pending
            pending = db.get_pending_sources()
            if not pending:
                console.print("[yellow]No pending sources to compile[/yellow]")
                return

            source = pending[0]
            console.print(f"Compiling: [cyan]{source['path']}[/cyan]")

            with console.status("[cyan]Compiling...[/cyan]"):
                article_ids = compiler.compile_source(source["id"])

            console.print(
                f"[green]✓[/green] Created {len(article_ids)} article(s)\n"
                f"Remaining pending: {len(pending) - 1}"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to answer"),
    no_save: bool = typer.Option(
        False, "--no-save", help="Don't save answer as wiki article"
    ),
):
    """Ask a question and navigate the wiki for an answer."""
    config, db, llm = get_kb_context()
    engine = QueryEngine(config, db, llm)

    try:
        console.print(f"[cyan]Question:[/cyan] {question}\n")

        with console.status("[cyan]Searching wiki...[/cyan]"):
            response = engine.query(question, save_as_article=not no_save)

        console.print(Panel(Markdown(response), title="Answer", border_style="green"))

        if not no_save:
            console.print(
                "\n[dim]Answer saved as wiki article for future reference[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def health():
    """Run health check on the wiki."""
    config, db, llm = get_kb_context()
    checker = HealthChecker(config, db, llm)

    try:
        console.print("Running health check...\n")

        with console.status("[cyan]Analyzing wiki...[/cyan]"):
            results = checker.run_health_check()

        if results["issues_found"] == 0:
            console.print(
                Panel(
                    "[green]✓[/green] No issues found. Wiki is healthy!",
                    border_style="green",
                )
            )
        else:
            console.print(
                f"[yellow]Found {results['issues_found']} issue(s)[/yellow]\n"
            )

            # Show summary by severity
            by_severity = {"high": 0, "medium": 0, "low": 0}
            for issue in results["issues"]:
                severity = issue.get("severity", "low")
                if severity in by_severity:
                    by_severity[severity] += 1

            console.print("Summary:")
            if by_severity["high"]:
                console.print(f"  [red]High:[/red] {by_severity['high']}")
            if by_severity["medium"]:
                console.print(f"  [yellow]Medium:[/yellow] {by_severity['medium']}")
            if by_severity["low"]:
                console.print(f"  [dim]Low:[/dim] {by_severity['low']}")

            console.print(f"\nFull report: [cyan]{results['report_path']}[/cyan]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def watch():
    """Watch raw/ directory and auto-compile new files."""
    config, db, llm = get_kb_context()
    compiler = Compiler(config, db, llm)

    console.print(
        Panel(
            f"Watching [cyan]{config.raw_dir}[/cyan]\n\n"
            "Drop files into raw/ to auto-ingest and compile.\n"
            "Press Ctrl+C to stop.",
            title="File Watcher Active",
        )
    )

    try:
        watch_and_compile(config, db, compiler)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watcher stopped[/yellow]")


@app.command()
def status():
    """Show knowledge base statistics."""
    config, db, _ = get_kb_context()

    try:
        stats = db.get_stats()

        table = Table(title="Knowledge Base Status", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Articles", str(stats["articles"]))
        table.add_row("Total Sources", str(stats["sources_total"]))
        table.add_row("Pending Sources", str(stats["sources_pending"]))
        table.add_row("Total Words", f"{stats['total_words']:,}")
        table.add_row(
            "Last Compilation", stats["last_compile"] or "Never"
        )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def list(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of articles to show"),
):
    """List wiki articles."""
    config, db, _ = get_kb_context()

    try:
        articles = db.get_all_articles()

        if not articles:
            console.print("[yellow]No articles yet. Run [cyan]kw compile[/cyan] first.[/yellow]")
            return

        table = Table(title=f"Wiki Articles ({len(articles)} total)")
        table.add_column("Title", style="cyan")
        table.add_column("Tags", style="dim")
        table.add_column("Words", justify="right")
        table.add_column("Created", style="dim")

        for article in articles[:limit]:
            tags = article.get("tags", "") or ""
            words = str(article.get("word_count", 0))
            created = article["created_at"][:10] if article.get("created_at") else ""

            table.add_row(article["title"], tags, words, created)

        console.print(table)

        if len(articles) > limit:
            console.print(f"\n[dim]Showing {limit} of {len(articles)} articles[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
