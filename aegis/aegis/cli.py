"""CLI interface for AEGIS firewall."""

import click
import json
import asyncio
from pathlib import Path
from .proxy import MCPProxy
from .decision import DecisionEngine
from .policy import PolicyEngine, get_builtin_policy_path
from .audit import AuditLogger


@click.group()
@click.version_option(version='0.1.0')
def main():
    """AEGIS - MCP Pre-Execution Firewall Proxy"""
    pass


@main.command()
@click.argument('server_command', nargs=-1, required=True)
@click.option('--policy', '-p', default='default', help='Policy profile (default, strict, permissive) or path to YAML file')
@click.option('--audit-file', '-a', type=click.Path(), help='Path to audit log file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def run(server_command, policy, audit_file, verbose):
    """
    Run MCP server through AEGIS firewall proxy.

    Example:
        aegis run -- python mcp_server.py
    """
    if not server_command:
        click.echo("Error: No server command provided", err=True)
        raise click.Abort()

    # Convert tuple to list
    server_command = list(server_command)

    audit_path = Path(audit_file) if audit_file else None

    # Create and run proxy
    proxy = MCPProxy(
        server_command=server_command,
        policy_profile=policy,
        audit_file=audit_path,
        verbose=verbose
    )

    try:
        asyncio.run(proxy.start())
    except KeyboardInterrupt:
        if verbose:
            click.echo("\n[AEGIS] Shutting down...", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@main.command()
@click.argument('tool_call_json')
@click.option('--policy', '-p', default='default', help='Policy profile (default, strict, permissive) or path to YAML file')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed scan results')
def check(tool_call_json, policy, verbose):
    """
    Dry-run check of a tool call (no server started).

    Example:
        aegis check '{"name": "execute_command", "arguments": {"command": "rm -rf /"}}'
    """
    try:
        tool_call = json.loads(tool_call_json)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON - {e}", err=True)
        raise click.Abort()

    # Initialize decision engine
    if Path(policy).exists():
        policy_path = Path(policy)
    else:
        policy_path = get_builtin_policy_path(policy)

    policy_engine = PolicyEngine(policy_path)
    decision_engine = DecisionEngine(policy_engine)

    # Run decision pipeline
    decision, scan_results = decision_engine.decide(tool_call)

    # Output results
    click.echo(f"\n{'='*60}")
    click.echo(f"Tool: {tool_call.get('name', 'unknown')}")
    click.echo(f"Decision: {decision.upper()}")
    click.echo(f"{'='*60}\n")

    if scan_results:
        click.echo(f"Threats Detected: {len(scan_results)}\n")
        for i, result in enumerate(scan_results, 1):
            click.echo(f"{i}. {result['type'].upper()} ({result['severity']})")
            click.echo(f"   {result['message']}")
            if verbose:
                click.echo(f"   Pattern: {result.get('pattern', 'N/A')}")
            click.echo()
    else:
        click.echo("No threats detected.\n")

    # Exit with appropriate code
    if decision == 'deny':
        raise click.Abort()


@main.command()
@click.argument('audit_file', type=click.Path(exists=True))
def verify(audit_file):
    """
    Verify the integrity of an audit log chain.

    Example:
        aegis verify ~/.aegis/audit.jsonl
    """
    audit_path = Path(audit_file)

    # Create temporary audit logger to verify
    audit_logger = AuditLogger(audit_path)

    click.echo(f"Verifying audit chain: {audit_path}")

    if audit_logger.verify_chain():
        click.echo("✓ Audit chain is valid")
    else:
        click.echo("✗ Audit chain verification FAILED", err=True)
        raise click.Abort()


if __name__ == '__main__':
    main()
