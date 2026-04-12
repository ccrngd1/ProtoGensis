"""
Stage 1: Monitor - Parse PreCog logs, cluster failures, check skill inventory.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
import hashlib

try:
    import boto3
except ImportError:
    boto3 = None

from .models import SkillGap, FailureType, PipelineConfig


class PreCogLogParser:
    """Parse structured PreCog session output for failure signals using LLM."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        if not config.mock_mode and boto3:
            self.bedrock = boto3.client(
                'bedrock-runtime',
                region_name=config.bedrock_region
            )
        else:
            self.bedrock = None

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
                    # Use LLM to analyze raw text
                    failure_info = self._analyze_failure_with_llm(line)
                    if failure_info:
                        failures.append({
                            'line_num': line_num,
                            'event': {
                                'type': 'failure',
                                'failure_type': failure_info.get('failure_type', 'unknown'),
                                'agent': failure_info.get('affected_agent', 'unknown'),
                                'task_type': failure_info.get('task_context', 'unknown'),
                                'message': failure_info.get('normalized_description', line),
                                'severity': failure_info.get('severity', 'medium'),
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

    def _analyze_failure_with_llm(self, log_chunk: str) -> Optional[Dict]:
        """Analyze log chunk using LLM to extract failure information."""
        if self.config.mock_mode or self.bedrock is None:
            return self._mock_failure_analysis(log_chunk)

        try:
            prompt = f"""Analyze this log line and extract failure information. Return ONLY valid JSON.

Log: {log_chunk[:500]}

Extract:
- failure_type: one of [error, retry_exceeded, user_correction, timeout, invalid_output, unknown]
- affected_agent: name of agent or component
- task_context: brief description of what was being attempted
- severity: one of [low, medium, high, critical]
- normalized_description: concise summary of the failure

Return JSON only, no explanation."""

            response = self.bedrock.invoke_model(
                modelId="us.amazon.nova-lite-v1:0",
                body=json.dumps({
                    "messages": [{"role": "user", "content": prompt}],
                    "inferenceConfig": {
                        "temperature": 0.0,
                        "maxTokens": 300
                    }
                })
            )

            result = json.loads(response['body'].read())
            content = result.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '{}')

            # Parse JSON from response
            failure_info = json.loads(content.strip())
            return failure_info

        except Exception as e:
            # Fall back to mock on error
            return self._mock_failure_analysis(log_chunk)

    def _mock_failure_analysis(self, log_chunk: str) -> Dict:
        """Generate synthetic failure analysis for mock mode."""
        # Simple heuristic-based mock that doesn't use regex patterns
        lower_log = log_chunk.lower()

        if 'error' in lower_log or 'exception' in lower_log:
            failure_type = 'error'
            severity = 'high'
        elif 'timeout' in lower_log or 'timed out' in lower_log:
            failure_type = 'timeout'
            severity = 'medium'
        elif 'retry' in lower_log or 'retries' in lower_log:
            failure_type = 'retry_exceeded'
            severity = 'medium'
        elif 'invalid' in lower_log or 'malformed' in lower_log:
            failure_type = 'invalid_output'
            severity = 'medium'
        else:
            failure_type = 'unknown'
            severity = 'low'

        return {
            'failure_type': failure_type,
            'affected_agent': 'PreCog',
            'task_context': 'automated_task',
            'severity': severity,
            'normalized_description': log_chunk[:200]
        }

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
    """Group similar failures using LLM semantic similarity."""

    def __init__(self, config: PipelineConfig, similarity_threshold: float = 0.6):
        self.config = config
        self.similarity_threshold = similarity_threshold
        if not config.mock_mode and boto3:
            self.bedrock = boto3.client(
                'bedrock-runtime',
                region_name=config.bedrock_region
            )
        else:
            self.bedrock = None

    def cluster_failures(self, failures: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster failures by similarity."""
        clusters = defaultdict(list)

        for failure in failures:
            cluster_id = self._compute_cluster_id(failure)
            clusters[cluster_id].append(failure)

        return dict(clusters)

    def _compute_cluster_id(self, failure: Dict) -> str:
        """Compute a cluster ID using LLM semantic similarity."""
        if self.config.mock_mode or self.bedrock is None:
            return self._compute_cluster_id_mock(failure)

        event = failure.get('event', {})
        message = event.get('message', failure.get('raw_line', ''))
        task_type = event.get('task_type', 'unknown')
        failure_type = event.get('failure_type', 'unknown')
        agent = event.get('agent', 'unknown')

        # Use LLM to generate semantic cluster key
        try:
            prompt = f"""Analyze this failure and assign it to a semantic cluster. Return a short cluster key (2-4 words, lowercase, underscore-separated) that captures the root cause category.

Failure type: {failure_type}
Task: {task_type}
Agent: {agent}
Message: {message[:200]}

Examples of good cluster keys: "api_timeout", "json_parse_error", "dependency_conflict", "syntax_error", "permission_denied"

Return ONLY the cluster key, no explanation."""

            response = self.bedrock.invoke_model(
                modelId="us.amazon.nova-lite-v1:0",
                body=json.dumps({
                    "messages": [{"role": "user", "content": prompt}],
                    "inferenceConfig": {
                        "temperature": 0.0,
                        "maxTokens": 50
                    }
                })
            )

            result = json.loads(response['body'].read())
            cluster_key = result.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '').strip().lower()

            # Clean and validate cluster key
            cluster_key = cluster_key.replace(' ', '_')
            cluster_key = ''.join(c for c in cluster_key if c.isalnum() or c == '_')

            if cluster_key and len(cluster_key) > 0:
                return cluster_key[:50]  # Limit length
            else:
                # Fallback to hash-based ID
                return self._compute_cluster_id_mock(failure)

        except Exception:
            # Fall back to mock on error
            return self._compute_cluster_id_mock(failure)

    def _compute_cluster_id_mock(self, failure: Dict) -> str:
        """Compute cluster ID in mock mode using simple hashing."""
        event = failure.get('event', {})

        # Extract key features for clustering
        task_type = event.get('task_type', 'unknown')
        failure_type = event.get('failure_type', 'unknown')
        agent = event.get('agent', 'unknown')

        # Create cluster signature (no keyword extraction, simpler)
        message = event.get('message', failure.get('raw_line', ''))
        signature = f"{agent}_{task_type}_{failure_type}_{message[:50]}"

        # Hash to create stable cluster ID
        return hashlib.md5(signature.encode()).hexdigest()[:8]


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
        self.clusterer = FailureClusterer(config)
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
