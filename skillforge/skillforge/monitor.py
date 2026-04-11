"""
Stage 1: Monitor - Parse PreCog logs, cluster failures, check skill inventory.
"""
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
import hashlib

from .models import SkillGap, FailureType, PipelineConfig


class PreCogLogParser:
    """Parse structured PreCog session output for failure signals."""

    FAILURE_PATTERNS = {
        FailureType.ERROR: [
            r"ERROR:",
            r"Exception",
            r"Traceback",
            r"failed with error",
        ],
        FailureType.RETRY_EXCEEDED: [
            r"retry.*exceeded",
            r"max.*retries",
            r"too many attempts",
        ],
        FailureType.USER_CORRECTION: [
            r"user corrected",
            r"user override",
            r"manual intervention",
        ],
        FailureType.TIMEOUT: [
            r"timeout",
            r"timed out",
            r"deadline exceeded",
        ],
        FailureType.INVALID_OUTPUT: [
            r"invalid.*output",
            r"malformed.*response",
            r"parse.*failed",
        ],
    }

    def __init__(self, config: PipelineConfig):
        self.config = config

    def parse_log_file(self, log_path: Path) -> List[Dict]:
        """Parse a PreCog log file and extract failure events."""
        failures = []

        if not log_path.exists():
            return failures

        with open(log_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Try to parse as JSON first
                try:
                    event = json.loads(line)
                    if self._is_failure_event(event):
                        failures.append({
                            'line_num': line_num,
                            'event': event,
                            'raw_line': line
                        })
                except json.JSONDecodeError:
                    # Try pattern matching on raw text
                    failure_type = self._detect_failure_type(line)
                    if failure_type:
                        failures.append({
                            'line_num': line_num,
                            'event': {
                                'type': 'failure',
                                'failure_type': failure_type.value,
                                'message': line,
                                'timestamp': datetime.now().isoformat()
                            },
                            'raw_line': line
                        })

        return failures

    def _is_failure_event(self, event: Dict) -> bool:
        """Check if a parsed event represents a failure."""
        if event.get('type') == 'failure':
            return True
        if event.get('level') in ['ERROR', 'CRITICAL']:
            return True
        if event.get('status') in ['failed', 'error']:
            return True
        return False

    def _detect_failure_type(self, line: str) -> Optional[FailureType]:
        """Detect failure type from raw log line."""
        for failure_type, patterns in self.FAILURE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return failure_type
        return None

    def extract_context(self, failure: Dict) -> str:
        """Extract meaningful context from a failure event."""
        event = failure.get('event', {})

        # Extract task context
        task_type = event.get('task_type', 'unknown')
        agent_name = event.get('agent', 'unknown')
        message = event.get('message', failure.get('raw_line', ''))

        # Truncate long messages
        if len(message) > 200:
            message = message[:200] + '...'

        return f"[{agent_name}] {task_type}: {message}"


class FailureClusterer:
    """Group similar failures by task type using keyword similarity."""

    def __init__(self, similarity_threshold: float = 0.6):
        self.similarity_threshold = similarity_threshold

    def cluster_failures(self, failures: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster failures by similarity."""
        clusters = defaultdict(list)

        for failure in failures:
            cluster_id = self._compute_cluster_id(failure)
            clusters[cluster_id].append(failure)

        return dict(clusters)

    def _compute_cluster_id(self, failure: Dict) -> str:
        """Compute a cluster ID based on failure characteristics."""
        event = failure.get('event', {})

        # Extract key features for clustering
        task_type = event.get('task_type', 'unknown')
        failure_type = event.get('failure_type', 'unknown')
        agent = event.get('agent', 'unknown')

        # Extract key words from message
        message = event.get('message', failure.get('raw_line', ''))
        keywords = self._extract_keywords(message)

        # Create cluster signature
        signature = f"{agent}_{task_type}_{failure_type}_{keywords}"

        # Hash to create stable cluster ID
        return hashlib.md5(signature.encode()).hexdigest()[:8]

    def _extract_keywords(self, text: str) -> str:
        """Extract key words from text for clustering."""
        # Remove common words and extract meaningful terms
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter out common words
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if w not in stopwords and len(w) > 3]

        # Take top 3 keywords by length (rough importance metric)
        keywords = sorted(keywords, key=len, reverse=True)[:3]

        return '_'.join(keywords)


class SkillInventoryChecker:
    """Compare failure clusters against existing skills directory."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.skills_cache = {}

    def load_existing_skills(self) -> Dict[str, Dict]:
        """Load and cache existing SKILL.md files."""
        skills_dir = Path(self.config.skills_dir)

        if not skills_dir.exists():
            return {}

        skills = {}
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    with open(skill_md, 'r') as f:
                        content = f.read()
                        metadata = self._parse_skill_metadata(content)
                        skills[skill_dir.name] = {
                            'name': skill_dir.name,
                            'metadata': metadata,
                            'content': content
                        }
                except Exception as e:
                    print(f"Warning: Could not parse {skill_md}: {e}")

        self.skills_cache = skills
        return skills

    def _parse_skill_metadata(self, content: str) -> Dict:
        """Extract metadata from SKILL.md frontmatter."""
        metadata = {}

        # Look for YAML frontmatter
        if content.startswith('---'):
            try:
                end_marker = content.find('---', 3)
                if end_marker > 0:
                    frontmatter = content[3:end_marker].strip()
                    for line in frontmatter.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
            except Exception:
                pass

        return metadata

    def check_coverage(self, cluster: List[Dict]) -> bool:
        """Check if a failure cluster is covered by existing skills."""
        if not self.skills_cache:
            self.load_existing_skills()

        # Extract task characteristics from cluster
        cluster_features = self._extract_cluster_features(cluster)

        # Check against each existing skill
        for skill_name, skill_data in self.skills_cache.items():
            if self._skill_covers_cluster(skill_data, cluster_features):
                return True

        return False

    def _extract_cluster_features(self, cluster: List[Dict]) -> Dict:
        """Extract key features from a failure cluster."""
        task_types = set()
        failure_types = set()
        keywords = set()

        for failure in cluster:
            event = failure.get('event', {})
            task_types.add(event.get('task_type', 'unknown'))
            failure_types.add(event.get('failure_type', 'unknown'))

            message = event.get('message', failure.get('raw_line', ''))
            msg_keywords = re.findall(r'\b\w{4,}\b', message.lower())
            keywords.update(msg_keywords[:5])

        return {
            'task_types': task_types,
            'failure_types': failure_types,
            'keywords': keywords
        }

    def _skill_covers_cluster(self, skill_data: Dict, cluster_features: Dict) -> bool:
        """Check if a skill appears to cover the failure cluster."""
        skill_content = skill_data['content'].lower()
        metadata = skill_data['metadata']

        # Check description for keyword matches
        description = metadata.get('description', '')

        # Count keyword matches
        matches = 0
        for keyword in cluster_features['keywords']:
            if keyword in skill_content or keyword in description.lower():
                matches += 1

        # Consider covered if >50% keywords match
        if matches > len(cluster_features['keywords']) * 0.5:
            return True

        return False


class MockLogGenerator:
    """Generate synthetic PreCog failure logs for testing."""

    def generate_mock_failures(self, count: int = 10) -> List[Dict]:
        """Generate mock failure events."""
        failures = []

        mock_scenarios = [
            {
                'agent': 'PreCog',
                'task_type': 'code_generation',
                'failure_type': 'error',
                'message': 'Failed to generate valid Python code: SyntaxError'
            },
            {
                'agent': 'PreCog',
                'task_type': 'file_parsing',
                'failure_type': 'invalid_output',
                'message': 'Could not parse JSON configuration file'
            },
            {
                'agent': 'PreCog',
                'task_type': 'api_call',
                'failure_type': 'timeout',
                'message': 'API request to external service timed out after 30s'
            },
            {
                'agent': 'PreCog',
                'task_type': 'test_execution',
                'failure_type': 'retry_exceeded',
                'message': 'Test suite failed after 3 retry attempts'
            },
            {
                'agent': 'PreCog',
                'task_type': 'dependency_resolution',
                'failure_type': 'error',
                'message': 'Could not resolve package dependency: version conflict'
            },
        ]

        for i in range(count):
            scenario = mock_scenarios[i % len(mock_scenarios)]
            failures.append({
                'line_num': i + 1,
                'event': {
                    'type': 'failure',
                    'timestamp': datetime.now().isoformat(),
                    **scenario
                },
                'raw_line': json.dumps(scenario)
            })

        return failures


class Monitor:
    """Main Monitor stage coordinator."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.parser = PreCogLogParser(config)
        self.clusterer = FailureClusterer()
        self.inventory_checker = SkillInventoryChecker(config)

    def run(self, log_path: Optional[Path] = None) -> List[SkillGap]:
        """Run the Monitor stage."""
        # Parse failures
        if self.config.mock_mode or log_path is None:
            mock_gen = MockLogGenerator()
            failures = mock_gen.generate_mock_failures(10)
        else:
            failures = self.parser.parse_log_file(log_path)

        if not failures:
            return []

        # Cluster similar failures
        clusters = self.clusterer.cluster_failures(failures)

        # Convert clusters to SkillGaps
        gaps = []
        for cluster_id, cluster_failures in clusters.items():
            # Check if covered by existing skills
            if self.inventory_checker.check_coverage(cluster_failures):
                continue  # Skip if already covered

            # Extract gap information
            failure_context = self.parser.extract_context(cluster_failures[0])

            # Determine failure type (use most common)
            failure_types = [f['event'].get('failure_type', 'unknown')
                           for f in cluster_failures]
            failure_type_str = max(set(failure_types), key=failure_types.count)

            try:
                failure_type = FailureType(failure_type_str)
            except ValueError:
                failure_type = FailureType.UNKNOWN

            # Extract affected agents
            agents = list(set(f['event'].get('agent', 'unknown')
                            for f in cluster_failures))

            gap = SkillGap(
                failure_context=failure_context,
                failure_type=failure_type,
                frequency=len(cluster_failures),
                affected_agents=agents,
                cluster_id=cluster_id,
                timestamp=datetime.now()
            )
            gaps.append(gap)

        # Limit to max_gaps_per_run
        gaps = sorted(gaps, key=lambda g: g.frequency, reverse=True)
        return gaps[:self.config.max_gaps_per_run]
