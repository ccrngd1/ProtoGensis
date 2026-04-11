"""
Feedback Tracker - Track skill deployments, success rates, and library health.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

from .models import PipelineConfig


class SkillTracker:
    """Log deployment metadata to JSONL file."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.db_path = Path(config.tracker_db_path)

    def log_deployment(self, deployment_metadata: Dict[str, Any]):
        """Log a skill deployment."""
        # Add timestamp if not present
        if 'timestamp' not in deployment_metadata:
            deployment_metadata['timestamp'] = datetime.now().isoformat()

        # Append to JSONL file
        with open(self.db_path, 'a') as f:
            f.write(json.dumps(deployment_metadata) + '\n')

    def get_deployments(
        self,
        skill_name: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve deployment records."""
        if not self.db_path.exists():
            return []

        deployments = []
        with open(self.db_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)

                    # Filter by skill name
                    if skill_name and record.get('skill_name') != skill_name:
                        continue

                    # Filter by date
                    if since:
                        record_time = datetime.fromisoformat(record['timestamp'])
                        if record_time < since:
                            continue

                    deployments.append(record)

                except json.JSONDecodeError:
                    continue

        return deployments

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get latest deployment info for a skill."""
        deployments = self.get_deployments(skill_name=skill_name)
        if not deployments:
            return None

        # Return most recent
        return sorted(deployments, key=lambda d: d['timestamp'], reverse=True)[0]


class SuccessRateTracker:
    """Track post-deployment success/failure per skill."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.tracker = SkillTracker(config)

    def log_usage(
        self,
        skill_name: str,
        success: bool,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log a skill usage event."""
        usage_metadata = {
            'event_type': 'usage',
            'skill_name': skill_name,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }

        self.tracker.log_deployment(usage_metadata)

    def get_success_rate(
        self,
        skill_name: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Calculate success rate for a skill."""
        since = datetime.now() - timedelta(days=days)

        # Get all usage events
        all_events = self.tracker.get_deployments(since=since)
        usage_events = [e for e in all_events
                       if e.get('event_type') == 'usage' and
                          e.get('skill_name') == skill_name]

        if not usage_events:
            return {
                'skill_name': skill_name,
                'total_uses': 0,
                'success_count': 0,
                'failure_count': 0,
                'success_rate': 0.0,
                'days': days
            }

        success_count = sum(1 for e in usage_events if e.get('success'))
        failure_count = len(usage_events) - success_count

        return {
            'skill_name': skill_name,
            'total_uses': len(usage_events),
            'success_count': success_count,
            'failure_count': failure_count,
            'success_rate': success_count / len(usage_events),
            'days': days
        }

    def get_all_success_rates(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get success rates for all skills."""
        since = datetime.now() - timedelta(days=days)

        # Get all usage events
        all_events = self.tracker.get_deployments(since=since)
        usage_events = [e for e in all_events if e.get('event_type') == 'usage']

        # Group by skill
        skill_events = defaultdict(list)
        for event in usage_events:
            skill_name = event.get('skill_name')
            if skill_name:
                skill_events[skill_name].append(event)

        # Calculate rates
        rates = []
        for skill_name, events in skill_events.items():
            success_count = sum(1 for e in events if e.get('success'))
            rates.append({
                'skill_name': skill_name,
                'total_uses': len(events),
                'success_count': success_count,
                'failure_count': len(events) - success_count,
                'success_rate': success_count / len(events),
                'days': days
            })

        return sorted(rates, key=lambda r: r['success_rate'], reverse=True)


class DriftDetector:
    """Flag skills where performance degrades."""

    def __init__(self, config: PipelineConfig, threshold: float = 0.3):
        self.config = config
        self.success_tracker = SuccessRateTracker(config)
        self.threshold = threshold  # 30% drop triggers drift alert

    def detect_drift(self, skill_name: str) -> Dict[str, Any]:
        """Detect performance drift for a skill."""
        # Compare recent performance vs. older baseline
        recent_rate = self.success_tracker.get_success_rate(skill_name, days=7)
        baseline_rate = self.success_tracker.get_success_rate(skill_name, days=30)

        if recent_rate['total_uses'] < 3:
            # Not enough recent data
            return {
                'skill_name': skill_name,
                'drift_detected': False,
                'reason': 'insufficient_recent_data'
            }

        if baseline_rate['total_uses'] < 5:
            # Not enough baseline data
            return {
                'skill_name': skill_name,
                'drift_detected': False,
                'reason': 'insufficient_baseline_data'
            }

        # Calculate drift
        recent_success = recent_rate['success_rate']
        baseline_success = baseline_rate['success_rate']
        drift = baseline_success - recent_success

        drift_detected = drift > self.threshold

        return {
            'skill_name': skill_name,
            'drift_detected': drift_detected,
            'recent_success_rate': recent_success,
            'baseline_success_rate': baseline_success,
            'drift_amount': drift,
            'recent_uses': recent_rate['total_uses'],
            'baseline_uses': baseline_rate['total_uses']
        }

    def detect_all_drift(self) -> List[Dict[str, Any]]:
        """Detect drift across all skills."""
        # Get all skills with usage data
        rates = self.success_tracker.get_all_success_rates(days=30)

        drift_reports = []
        for rate_info in rates:
            skill_name = rate_info['skill_name']
            drift_info = self.detect_drift(skill_name)
            if drift_info['drift_detected']:
                drift_reports.append(drift_info)

        return sorted(drift_reports, key=lambda d: d['drift_amount'], reverse=True)


class LibraryHealthReporter:
    """Generate library health reports."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.tracker = SkillTracker(config)
        self.success_tracker = SuccessRateTracker(config)
        self.drift_detector = DriftDetector(config)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive library health report."""
        # Count deployed skills
        deployments = self.tracker.get_deployments()
        skill_deployments = [d for d in deployments if d.get('event_type') != 'usage']

        unique_skills = set(d.get('skill_name') for d in skill_deployments
                          if d.get('skill_name'))

        # Get success rates
        success_rates = self.success_tracker.get_all_success_rates(days=30)

        # Calculate overall metrics
        total_uses = sum(r['total_uses'] for r in success_rates)
        total_successes = sum(r['success_count'] for r in success_rates)

        overall_success_rate = (total_successes / total_uses) if total_uses > 0 else 0.0

        # Detect drift
        drift_issues = self.drift_detector.detect_all_drift()

        # Calculate staleness (skills not used recently)
        stale_skills = []
        for skill in unique_skills:
            rate = self.success_tracker.get_success_rate(skill, days=30)
            if rate['total_uses'] == 0:
                stale_skills.append(skill)

        # Coverage estimate (very rough - would need more context)
        coverage_pct = min((len(unique_skills) / 50.0) * 100, 100.0)  # Assume 50 skills = 100% coverage

        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_active_skills': len(unique_skills),
                'total_deployments': len(skill_deployments),
                'total_uses_30d': total_uses,
                'overall_success_rate': overall_success_rate,
                'estimated_coverage_pct': coverage_pct,
            },
            'top_performers': success_rates[:10],
            'drift_alerts': drift_issues,
            'stale_skills': stale_skills,
            'health_score': self._calculate_health_score(
                overall_success_rate,
                len(drift_issues),
                len(stale_skills),
                len(unique_skills)
            )
        }

        return report

    def _calculate_health_score(
        self,
        success_rate: float,
        drift_count: int,
        stale_count: int,
        total_skills: int
    ) -> float:
        """Calculate overall library health score (0-1)."""
        # Success rate component (0-0.5)
        success_component = success_rate * 0.5

        # Drift component (0-0.25) - penalize drift
        drift_pct = drift_count / max(total_skills, 1)
        drift_component = max(0.25 - (drift_pct * 0.25), 0)

        # Staleness component (0-0.25) - penalize stale skills
        stale_pct = stale_count / max(total_skills, 1)
        stale_component = max(0.25 - (stale_pct * 0.25), 0)

        return success_component + drift_component + stale_component

    def print_report(self, report: Optional[Dict[str, Any]] = None):
        """Print human-readable report."""
        if report is None:
            report = self.generate_report()

        print("=" * 60)
        print("SKILLFORGE LIBRARY HEALTH REPORT")
        print("=" * 60)
        print()

        summary = report['summary']
        print(f"Total Active Skills: {summary['total_active_skills']}")
        print(f"Total Uses (30d): {summary['total_uses_30d']}")
        print(f"Overall Success Rate: {summary['overall_success_rate']:.1%}")
        print(f"Estimated Coverage: {summary['estimated_coverage_pct']:.0f}%")
        print(f"Health Score: {report['health_score']:.2f}")
        print()

        if report['top_performers']:
            print("Top Performers:")
            for perf in report['top_performers'][:5]:
                print(f"  - {perf['skill_name']}: {perf['success_rate']:.1%} "
                      f"({perf['total_uses']} uses)")
            print()

        if report['drift_alerts']:
            print(f"⚠️  Drift Alerts ({len(report['drift_alerts'])}):")
            for alert in report['drift_alerts'][:5]:
                print(f"  - {alert['skill_name']}: "
                      f"{alert['baseline_success_rate']:.1%} → {alert['recent_success_rate']:.1%} "
                      f"(drop: {alert['drift_amount']:.1%})")
            print()

        if report['stale_skills']:
            print(f"Stale Skills ({len(report['stale_skills'])}):")
            for skill in report['stale_skills'][:5]:
                print(f"  - {skill}")
            print()

        print("=" * 60)
