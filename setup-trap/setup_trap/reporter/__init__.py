"""Reporters: turn a ScanResult into human / machine / shareable output."""

from setup_trap.reporter.cli_reporter import render_cli, render_surface_cli
from setup_trap.reporter.html_reporter import render_html
from setup_trap.reporter.json_reporter import render_json

__all__ = ["render_cli", "render_surface_cli", "render_json", "render_html"]
