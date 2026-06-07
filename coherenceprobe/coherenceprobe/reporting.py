"""Report generation in multiple formats (JSON, text, HTML)."""

import json
from pathlib import Path
from typing import Literal

from .models import CoherenceReport, ContradictionPair
from .scoring import (
    rank_agents_by_coherence,
    get_most_problematic_agent,
    summarize_contradictions_by_type,
)


def format_report(
    report: CoherenceReport,
    format: Literal["json", "text", "html"] = "text"
) -> str:
    """Format coherence report in the specified format.

    Args:
        report: Coherence report to format
        format: Output format (json, text, or html)

    Returns:
        Formatted report as string
    """
    if format == "json":
        return format_json(report)
    elif format == "text":
        return format_text(report)
    elif format == "html":
        return format_html(report)
    else:
        raise ValueError(f"Unknown format: {format}")


def format_json(report: CoherenceReport) -> str:
    """Format report as JSON.

    Args:
        report: Coherence report

    Returns:
        JSON string
    """
    return report.model_dump_json(indent=2)


def format_text(report: CoherenceReport) -> str:
    """Format report as human-readable text.

    Args:
        report: Coherence report

    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("COHERENCE PROBE REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Overall score
    score_emoji = "✅" if report.score >= 0.8 else "⚠️" if report.score >= 0.5 else "❌"
    lines.append(f"Overall Coherence Score: {report.score:.3f} {score_emoji}")
    lines.append(f"Total Agents: {report.total_agents}")
    lines.append(f"Total Claims: {report.total_claims}")
    lines.append(f"Contradictions Found: {len(report.contradictions)}")
    lines.append("")

    # Contradiction summary by type
    if report.contradictions:
        type_counts = summarize_contradictions_by_type(report.contradictions)
        lines.append("Contradictions by Type:")
        for ctype, count in sorted(type_counts.items()):
            lines.append(f"  - {ctype.capitalize()}: {count}")
        lines.append("")

    # Agent ranking
    if report.agent_scores:
        lines.append("Agent Coherence Ranking:")
        ranked = rank_agents_by_coherence(report)
        for i, (agent, coherence) in enumerate(ranked, 1):
            incoherence = report.agent_scores[agent]
            status = "✓" if coherence >= 0.9 else "⚠" if coherence >= 0.7 else "✗"
            lines.append(f"  {i}. {agent:20s} {status}  (coherence: {coherence:.3f}, incoherence: {incoherence:.3f})")
        lines.append("")

    # Most problematic agent
    if report.agent_scores:
        problematic = get_most_problematic_agent(report)
        if problematic and problematic[1] > 0.0:
            lines.append(f"Most Problematic Agent: {problematic[0]} (incoherence: {problematic[1]:.3f})")
            lines.append("")

    # Detailed contradictions
    if report.contradictions:
        lines.append("=" * 70)
        lines.append("DETAILED CONTRADICTIONS")
        lines.append("=" * 70)
        lines.append("")

        for i, contradiction in enumerate(report.contradictions, 1):
            lines.append(f"Contradiction #{i} ({contradiction.contradiction_type}, confidence: {contradiction.confidence:.3f})")
            lines.append(f"  Agent A: {contradiction.claim_a.agent}")
            lines.append(f"    Claim: {contradiction.claim_a.text}")
            lines.append(f"  Agent B: {contradiction.claim_b.agent}")
            lines.append(f"    Claim: {contradiction.claim_b.text}")
            if contradiction.explanation:
                lines.append(f"  Explanation: {contradiction.explanation}")
            lines.append("")

    # Metadata
    if report.metadata:
        lines.append("=" * 70)
        lines.append("METADATA")
        lines.append("=" * 70)
        for key, value in report.metadata.items():
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_html(report: CoherenceReport) -> str:
    """Format report as HTML.

    Args:
        report: Coherence report

    Returns:
        HTML string
    """
    html_parts = []

    # HTML header
    html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CoherenceProbe Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .score-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .score-value {
            font-size: 48px;
            font-weight: bold;
            color: #667eea;
        }
        .score-good { color: #10b981; }
        .score-warning { color: #f59e0b; }
        .score-bad { color: #ef4444; }
        .agent-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .agent-table th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }
        .agent-table td {
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }
        .contradiction {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #ef4444;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .contradiction-type {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .type-logical { background: #fee2e2; color: #991b1b; }
        .type-factual { background: #fed7aa; color: #9a3412; }
        .type-temporal { background: #e0e7ff; color: #3730a3; }
        .claim {
            margin: 10px 0;
            padding: 10px;
            background: #f9fafb;
            border-radius: 4px;
        }
        .agent-name {
            font-weight: bold;
            color: #667eea;
        }
    </style>
</head>
<body>
""")

    # Header
    html_parts.append(f"""
    <div class="header">
        <h1>🔍 CoherenceProbe Report</h1>
        <p>Multi-Agent Coherence Analysis</p>
    </div>
""")

    # Score card
    score_class = "score-good" if report.score >= 0.8 else "score-warning" if report.score >= 0.5 else "score-bad"
    html_parts.append(f"""
    <div class="score-card">
        <h2>Overall Coherence Score</h2>
        <div class="score-value {score_class}">{report.score:.3f}</div>
        <p>Total Agents: {report.total_agents} | Total Claims: {report.total_claims} | Contradictions: {len(report.contradictions)}</p>
    </div>
""")

    # Contradiction summary
    if report.contradictions:
        type_counts = summarize_contradictions_by_type(report.contradictions)
        html_parts.append("""
    <div class="score-card">
        <h2>Contradictions by Type</h2>
        <ul>
""")
        for ctype, count in sorted(type_counts.items()):
            html_parts.append(f"            <li><strong>{ctype.capitalize()}:</strong> {count}</li>\n")
        html_parts.append("""        </ul>
    </div>
""")

    # Agent ranking
    if report.agent_scores:
        html_parts.append("""
    <div class="score-card">
        <h2>Agent Coherence Ranking</h2>
        <table class="agent-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Agent</th>
                    <th>Coherence Score</th>
                    <th>Incoherence Score</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
""")
        ranked = rank_agents_by_coherence(report)
        for i, (agent, coherence) in enumerate(ranked, 1):
            incoherence = report.agent_scores[agent]
            status = "✓" if coherence >= 0.9 else "⚠" if coherence >= 0.7 else "✗"
            score_class = "score-good" if coherence >= 0.9 else "score-warning" if coherence >= 0.7 else "score-bad"
            html_parts.append(f"""
                <tr>
                    <td>{i}</td>
                    <td class="agent-name">{agent}</td>
                    <td class="{score_class}">{coherence:.3f}</td>
                    <td>{incoherence:.3f}</td>
                    <td>{status}</td>
                </tr>
""")
        html_parts.append("""
            </tbody>
        </table>
    </div>
""")

    # Detailed contradictions
    if report.contradictions:
        html_parts.append("""
    <div class="score-card">
        <h2>Detailed Contradictions</h2>
    </div>
""")
        for i, contradiction in enumerate(report.contradictions, 1):
            type_class = f"type-{contradiction.contradiction_type}"
            html_parts.append(f"""
    <div class="contradiction">
        <h3>Contradiction #{i} <span class="contradiction-type {type_class}">{contradiction.contradiction_type}</span></h3>
        <p><strong>Confidence:</strong> {contradiction.confidence:.3f}</p>
        <div class="claim">
            <span class="agent-name">{contradiction.claim_a.agent}</span>: {contradiction.claim_a.text}
        </div>
        <div class="claim">
            <span class="agent-name">{contradiction.claim_b.agent}</span>: {contradiction.claim_b.text}
        </div>
""")
            if contradiction.explanation:
                html_parts.append(f"""
        <p><strong>Explanation:</strong> {contradiction.explanation}</p>
""")
            html_parts.append("""
    </div>
""")

    # HTML footer
    html_parts.append("""
</body>
</html>
""")

    return "".join(html_parts)


def save_report(report: CoherenceReport, output_path: str | Path, format: str = None) -> None:
    """Save report to file.

    Args:
        report: Coherence report
        output_path: Output file path
        format: Format (json, text, html). If None, inferred from file extension
    """
    output_path = Path(output_path)

    # Infer format from extension if not specified
    if format is None:
        extension = output_path.suffix.lower()
        if extension == ".json":
            format = "json"
        elif extension == ".html":
            format = "html"
        else:
            format = "text"

    # Format and save
    content = format_report(report, format)
    output_path.write_text(content)
