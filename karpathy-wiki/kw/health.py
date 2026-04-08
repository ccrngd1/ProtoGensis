"""Health check agent for wiki quality assurance."""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set
from datetime import datetime
from .llm import BedrockLLM, HEALTH_CHECK_SYSTEM
from .db import Database
from .config import Config


class HealthChecker:
    """Audit wiki for quality issues."""

    def __init__(self, config: Config, db: Database, llm: BedrockLLM):
        """Initialize health checker.

        Args:
            config: Configuration object
            db: Database connection
            llm: LLM client
        """
        self.config = config
        self.db = db
        self.llm = llm

    def run_health_check(self) -> Dict[str, Any]:
        """Run a comprehensive health check on the wiki.

        Returns:
            Health check results dict
        """
        # Collect wiki state
        articles = self.db.get_all_articles()
        index_content = self._read_index()

        # Build article summaries
        article_summaries = self._build_article_summaries(articles)

        # Check for broken wikilinks
        broken_links = self._check_broken_links(articles)

        # Build health check prompt
        prompt = self._build_health_prompt(article_summaries, index_content)

        # Run LLM health check
        try:
            response = self.llm.complete(
                prompt, system=HEALTH_CHECK_SYSTEM, max_tokens=8192
            )

            # Parse issues from response
            llm_issues = self._parse_health_response(response)

        except Exception as e:
            llm_issues = [
                {
                    "type": "error",
                    "severity": "high",
                    "description": f"Health check LLM call failed: {e}",
                    "affected_articles": [],
                    "recommendation": "Retry health check",
                }
            ]

        # Combine with broken link checks
        all_issues = llm_issues + self._format_broken_links(broken_links)

        # Save health report
        report_path = self._save_health_report(all_issues)

        # Record in database
        self.db.add_health_report(
            report_path=str(report_path.relative_to(self.config.kb_root)),
            issues_found=len(all_issues),
        )

        return {
            "issues_found": len(all_issues),
            "report_path": str(report_path),
            "issues": all_issues,
        }

    def _read_index(self) -> str:
        """Read wiki index."""
        if self.config.index_path.exists():
            with open(self.config.index_path, "r", encoding="utf-8") as f:
                return f.read()
        return "No index found"

    def _build_article_summaries(self, articles: List[Dict[str, Any]]) -> str:
        """Build summary list of articles.

        Args:
            articles: List of article dicts

        Returns:
            Formatted summary text
        """
        summaries = []
        for article in articles:
            summary = f"- **{article['title']}** ({article['path']})"
            if article.get("tags"):
                summary += f" - Tags: {article['tags']}"
            if article.get("summary"):
                summary += f"\n  {article['summary']}"

            # Read first 500 chars of content
            try:
                full_path = self.config.kb_root / article["path"]
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Skip frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            content = parts[2]
                    preview = content[:500].strip()
                    summary += f"\n  Preview: {preview}..."
            except Exception:
                pass

            summaries.append(summary)

        return "\n\n".join(summaries)

    def _build_health_prompt(self, article_summaries: str, index_content: str) -> str:
        """Build health check prompt.

        Args:
            article_summaries: Article summary text
            index_content: Index content

        Returns:
            Formatted prompt
        """
        prompt = f"""Wiki Index:
{index_content}

---

Article Summaries:
{article_summaries}

---

Audit this wiki for:
1. **Contradictions**: Conflicting information between articles
2. **Coverage gaps**: Missing articles on related topics mentioned in existing articles
3. **Outdated claims**: Information that may be stale (consider the current date)
4. **Redundancy**: Overlapping articles that should be merged

For each issue, provide:
- type: contradiction | gap | outdated | redundancy
- severity: high | medium | low
- affected_articles: List of article paths involved
- description: Clear explanation of the issue
- recommendation: What should be done

Output a JSON array of issues. If no issues found, return an empty array []."""

        return prompt

    def _parse_health_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse health check response.

        Args:
            response: LLM response

        Returns:
            List of issue dicts
        """
        try:
            # Try to extract JSON from response
            # Look for JSON array
            json_match = re.search(r"\[\s*\{.*?\}\s*\]", response, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group(0))
                return issues

            # Try parsing entire response
            issues = json.loads(response)
            if isinstance(issues, list):
                return issues

        except json.JSONDecodeError:
            pass

        # Fallback: return a parse error issue
        return [
            {
                "type": "error",
                "severity": "low",
                "description": "Could not parse health check response",
                "affected_articles": [],
                "recommendation": "Review response manually",
            }
        ]

    def _check_broken_links(self, articles: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Check for broken wikilinks.

        Args:
            articles: List of article dicts

        Returns:
            Dict mapping article paths to sets of broken links
        """
        # Build set of valid article titles (without .md extension)
        valid_titles = set()
        for article in articles:
            path = Path(article["path"])
            valid_titles.add(path.stem)
            valid_titles.add(article["title"])

        broken_links = {}

        for article in articles:
            try:
                full_path = self.config.kb_root / article["path"]
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find all [[wikilinks]]
                links = re.findall(r"\[\[([^\]]+)\]\]", content)

                article_broken = set()
                for link in links:
                    # Check if link target exists
                    link_target = link.strip()
                    if link_target not in valid_titles:
                        article_broken.add(link_target)

                if article_broken:
                    broken_links[article["path"]] = article_broken

            except Exception:
                pass

        return broken_links

    def _format_broken_links(self, broken_links: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
        """Format broken links as health issues.

        Args:
            broken_links: Dict of broken links per article

        Returns:
            List of issue dicts
        """
        issues = []
        for article_path, links in broken_links.items():
            issues.append(
                {
                    "type": "broken_link",
                    "severity": "medium",
                    "affected_articles": [article_path],
                    "description": f"Broken wikilinks: {', '.join(links)}",
                    "recommendation": f"Create missing articles or fix links",
                }
            )
        return issues

    def _save_health_report(self, issues: List[Dict[str, Any]]) -> Path:
        """Save health report to file.

        Args:
            issues: List of issue dicts

        Returns:
            Path to saved report
        """
        # Create reports directory
        reports_dir = self.config.wiki_dir / "reports"
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        report_path = reports_dir / f"health-{timestamp}.md"

        # Format report
        report = f"""# Wiki Health Report
Generated: {datetime.utcnow().isoformat()}

## Summary
Total issues found: {len(issues)}

"""

        # Group by severity
        by_severity = {"high": [], "medium": [], "low": []}
        for issue in issues:
            severity = issue.get("severity", "low")
            if severity in by_severity:
                by_severity[severity].append(issue)

        for severity in ["high", "medium", "low"]:
            severity_issues = by_severity[severity]
            if severity_issues:
                report += f"\n## {severity.upper()} Severity ({len(severity_issues)})\n\n"
                for idx, issue in enumerate(severity_issues, 1):
                    report += f"### {idx}. {issue.get('type', 'unknown').title()}\n\n"
                    report += f"**Description:** {issue.get('description', 'N/A')}\n\n"

                    affected = issue.get("affected_articles", [])
                    if affected:
                        report += f"**Affected Articles:**\n"
                        for article in affected:
                            report += f"- [[{article}]]\n"
                        report += "\n"

                    rec = issue.get("recommendation", "N/A")
                    report += f"**Recommendation:** {rec}\n\n"
                    report += "---\n\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return report_path

    def get_latest_report(self) -> Dict[str, Any]:
        """Get the latest health report.

        Returns:
            Report metadata dict or empty dict
        """
        report = self.db.get_latest_health_report()
        if report:
            return report
        return {}
