"""CLI entry point for AEGIS firewall."""

import argparse
import sys
import yaml
import asyncio
import uvicorn
from pathlib import Path
from typing import Dict, Any, Optional

from .engine import DecisionEngine
from .audit import AuditLogger
from .rate_limit import RateLimiter
from .hitl import HITLServer
from .proxy import MCPProxy


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dict
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='AEGIS - Security firewall for AI agent tool execution'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run AEGIS proxy')
    run_parser.add_argument('config', help='Path to configuration YAML file')
    run_parser.add_argument(
        '--hitl-port',
        type=int,
        default=8000,
        help='Port for HITL web interface'
    )

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify audit log')
    verify_parser.add_argument('log_path', help='Path to audit log file')
    verify_parser.add_argument(
        '--verify-key',
        help='Optional verification key (hex-encoded)'
    )

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show audit log statistics')
    stats_parser.add_argument('log_path', help='Path to audit log file')

    args = parser.parse_args()

    if args.command == 'run':
        run_proxy(args.config, args.hitl_port)
    elif args.command == 'verify':
        verify_audit_log(args.log_path, args.verify_key)
    elif args.command == 'stats':
        show_stats(args.log_path)
    else:
        parser.print_help()
        sys.exit(1)


def run_proxy(config_path: str, hitl_port: int):
    """
    Run the AEGIS proxy.

    Args:
        config_path: Path to configuration file
        hitl_port: Port for HITL interface
    """
    config = load_config(config_path)

    # Initialize components
    policy_path = config.get('policy_file', 'policies/standard.yaml')
    audit_path = config.get('audit_log', 'audit.jsonl')
    server_command = config.get('mcp_server_command', [])

    if not server_command:
        print("Error: mcp_server_command not specified in config", file=sys.stderr)
        sys.exit(1)

    # Create decision engine
    scanner_config = config.get('scanners', {})
    engine = DecisionEngine(policy_path, scanner_config)

    # Create audit logger
    signing_key = config.get('signing_key')
    audit_logger = AuditLogger(audit_path, signing_key)

    # Create rate limiter
    rate_config = config.get('rate_limiting', {})
    rate_limiter = RateLimiter(
        default_limit=rate_config.get('default_limit', 100),
        window_seconds=rate_config.get('window_seconds', 60),
        per_tool_limits=rate_config.get('per_tool_limits', {})
    )

    # Create HITL server
    hitl_timeout = config.get('hitl_timeout', 300)
    hitl_server = HITLServer(timeout_seconds=hitl_timeout)

    # Start HITL server in background
    import threading
    hitl_thread = threading.Thread(
        target=lambda: uvicorn.run(
            hitl_server.app,
            host='0.0.0.0',
            port=hitl_port,
            log_level='warning'
        ),
        daemon=True
    )
    hitl_thread.start()

    print(f"AEGIS Firewall started", file=sys.stderr)
    print(f"HITL interface: http://localhost:{hitl_port}", file=sys.stderr)
    print(f"Policy: {policy_path}", file=sys.stderr)
    print(f"Audit log: {audit_path}", file=sys.stderr)

    # Export verify key
    verify_key = audit_logger.export_verify_key()
    print(f"Verify key: {verify_key}", file=sys.stderr)

    # Decision callback for proxy
    def check_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Check rate limit first
        agent_id = arguments.get('_agent_id', 'default')
        rate_check = rate_limiter.check_limit(agent_id, tool_name)

        if not rate_check['allowed']:
            decision = {
                'action': 'deny',
                'reason': f"Rate limit exceeded: {rate_check['current']}/{rate_check['limit']}",
                'tool_name': tool_name
            }
            audit_logger.log_decision(decision, {'tool_name': tool_name, 'arguments': arguments})
            return decision

        # Run decision engine
        decision = engine.evaluate(tool_name, arguments, {'agent_id': agent_id})

        # Log to audit trail
        audit_logger.log_decision(decision, {'tool_name': tool_name, 'arguments': arguments})

        return decision

    # Escalation callback
    def handle_escalation(message: Dict[str, Any], decision: Dict[str, Any]) -> bool:
        print(f"\n[ESCALATION] Tool call requires approval: {decision['tool_name']}", file=sys.stderr)
        print(f"[ESCALATION] Reason: {decision['reason']}", file=sys.stderr)
        print(f"[ESCALATION] Check HITL interface at http://localhost:{hitl_port}", file=sys.stderr)

        # Request approval
        approved = hitl_server.request_approval(message, decision)

        if approved:
            print(f"[ESCALATION] Approved by human", file=sys.stderr)
        else:
            print(f"[ESCALATION] Denied or timeout", file=sys.stderr)

        return approved

    # Create and run proxy
    proxy = MCPProxy(
        server_command=server_command,
        decision_callback=check_tool_call,
        escalation_callback=handle_escalation,
        response_scan=config.get('response_scanning', True)
    )

    try:
        proxy.run()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        proxy.stop()


def verify_audit_log(log_path: str, verify_key: Optional[str]):
    """
    Verify audit log integrity.

    Args:
        log_path: Path to audit log
        verify_key: Optional verification key
    """
    from .audit import AuditVerifier

    verifier = AuditVerifier(log_path)
    result = verifier.verify(verify_key)

    print(f"Audit Log Verification: {log_path}")
    print(f"Status: {'VALID' if result['valid'] else 'INVALID'}")
    print(f"Total entries: {result['total_entries']}")
    print(f"Verified entries: {result['verified_entries']}")

    if result['errors']:
        print(f"\nErrors found: {len(result['errors'])}")
        for error in result['errors'][:10]:  # Show first 10
            print(f"  - {error['type']}: {error['message']}")
    else:
        print("\nNo errors found. Audit log is intact.")

    sys.exit(0 if result['valid'] else 1)


def show_stats(log_path: str):
    """
    Show audit log statistics.

    Args:
        log_path: Path to audit log
    """
    from .audit import AuditVerifier

    verifier = AuditVerifier(log_path)
    stats = verifier.get_statistics()

    if 'error' in stats:
        print(f"Error: {stats['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Audit Log Statistics: {log_path}")
    print(f"Total entries: {stats['total_entries']}")

    if stats['total_entries'] > 0:
        print(f"\nEvent types:")
        for event_type, count in stats['event_types'].items():
            print(f"  {event_type}: {count}")

        from datetime import datetime
        first_time = datetime.fromtimestamp(stats['first_timestamp'])
        last_time = datetime.fromtimestamp(stats['last_timestamp'])

        print(f"\nTime range:")
        print(f"  First: {first_time}")
        print(f"  Last: {last_time}")
        print(f"  Span: {stats['time_span_seconds']:.1f} seconds")


if __name__ == '__main__':
    main()
