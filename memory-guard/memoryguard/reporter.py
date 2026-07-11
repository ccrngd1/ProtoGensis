"""Report generation for scan results."""

import json
from typing import Dict, Any
from datetime import datetime


def generate_markdown_report(results: Dict[str, Any], output_path: str) -> None:
    """Generate a Markdown report of scan results."""
    summary = results["summary"]
    flagged = results["flagged_entries"]

    lines = [
        "# MemoryGuard Scan Report",
        f"\n**Generated:** {datetime.now().isoformat()}",
        f"\n## Summary\n",
        f"- **Entries Scanned:** {summary['entries_scanned']}",
        f"- **Entries Flagged:** {summary['entries_flagged']}",
        f"- **High Risk:** {summary['high_risk']} (≥70)",
        f"- **Medium Risk:** {summary['medium_risk']} (40-69)",
        f"- **Low Risk:** {summary['low_risk']} (<40)",
    ]

    if flagged:
        lines.append("\n## Flagged Entries\n")

        for entry in flagged:
            risk_level = "🔴 HIGH" if entry["max_risk_score"] >= 70 else "🟡 MEDIUM" if entry["max_risk_score"] >= 40 else "🟢 LOW"
            lines.append(f"### {entry['entry_id']} - {risk_level} (Score: {entry['max_risk_score']})\n")
            lines.append(f"**Categories:** {', '.join(entry['categories'])}\n")
            lines.append("**Detections:**\n")

            for detection in entry["detections"]:
                lines.append(f"- [{detection['risk_score']}] {detection['reason']}")

            lines.append("")
    else:
        lines.append("\n## ✅ No Issues Detected\n")
        lines.append("All memory entries passed security checks.")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))


def generate_json_report(results: Dict[str, Any], output_path: str) -> None:
    """Generate a JSON report of scan results."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": results["summary"],
        "flagged_entries": results["flagged_entries"]
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
