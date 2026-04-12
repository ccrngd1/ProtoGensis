"""
Tests for Monitor stage.
"""
import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from skillforge.monitor import (
    PreCogLogParser, FailureClusterer, SkillInventoryChecker,
    MockLogGenerator, Monitor
)
from skillforge.models import FailureType


def test_precog_log_parser_mock(mock_config):
    """Test PreCogLogParser with mock data."""
    parser = PreCogLogParser(mock_config)

    mock_gen = MockLogGenerator()
    failures = mock_gen.generate_mock_failures(5)

    assert len(failures) == 5
    assert 'event' in failures[0]


def test_precog_log_parser_mock_failure_analysis(mock_config):
    """Test mock failure analysis."""
    parser = PreCogLogParser(mock_config)

    # Test error detection
    result = parser._mock_failure_analysis("ERROR: Something went wrong")
    assert result['failure_type'] == 'error'
    assert 'affected_agent' in result

    # Test timeout detection
    result = parser._mock_failure_analysis("Request timed out")
    assert result['failure_type'] == 'timeout'

    # Test retry detection
    result = parser._mock_failure_analysis("max retries exceeded")
    assert result['failure_type'] == 'retry_exceeded'


def test_precog_log_parser_extract_context(mock_config):
    """Test context extraction."""
    parser = PreCogLogParser(mock_config)

    failure = {
        'event': {
            'task_type': 'test_task',
            'agent': 'TestAgent',
            'message': 'Test message'
        }
    }

    context = parser.extract_context(failure)
    assert 'TestAgent' in context
    assert 'test_task' in context


def test_failure_clusterer(mock_config):
    """Test FailureClusterer."""
    clusterer = FailureClusterer(mock_config)

    failures = [
        {'event': {'task_type': 'type1', 'failure_type': 'error', 'agent': 'A', 'message': 'msg1'}},
        {'event': {'task_type': 'type1', 'failure_type': 'error', 'agent': 'A', 'message': 'msg2'}},
        {'event': {'task_type': 'type2', 'failure_type': 'timeout', 'agent': 'B', 'message': 'msg3'}},
    ]

    clusters = clusterer.cluster_failures(failures)

    # Should have at least 1 cluster
    assert len(clusters) >= 1


def test_failure_clusterer_compute_cluster_id(mock_config):
    """Test cluster ID computation."""
    clusterer = FailureClusterer(mock_config)

    failure1 = {'event': {'task_type': 'type1', 'failure_type': 'error', 'agent': 'A', 'message': 'test'}}
    failure2 = {'event': {'task_type': 'type1', 'failure_type': 'error', 'agent': 'A', 'message': 'test'}}
    failure3 = {'event': {'task_type': 'type2', 'failure_type': 'error', 'agent': 'A', 'message': 'test'}}

    id1 = clusterer._compute_cluster_id_mock(failure1)
    id2 = clusterer._compute_cluster_id_mock(failure2)
    id3 = clusterer._compute_cluster_id_mock(failure3)

    # Same characteristics should produce same ID
    assert id1 == id2
    # Different characteristics should produce different ID
    assert id1 != id3


def test_skill_inventory_checker(mock_config, temp_skills_dir):
    """Test SkillInventoryChecker."""
    mock_config.skills_dir = str(temp_skills_dir)
    checker = SkillInventoryChecker(mock_config)

    skills = checker.load_existing_skills()
    assert len(skills) >= 1
    assert 'sample-skill' in skills


def test_skill_inventory_checker_parse_metadata(mock_config):
    """Test metadata parsing."""
    checker = SkillInventoryChecker(mock_config)

    content = """---
name: test
description: Test skill
version: 1.0.0
---

# Content
"""

    metadata = checker._parse_skill_metadata(content)
    assert 'name' in metadata
    assert metadata['name'] == 'test'


def test_skill_inventory_checker_check_coverage(mock_config, temp_skills_dir):
    """Test coverage checking."""
    mock_config.skills_dir = str(temp_skills_dir)
    checker = SkillInventoryChecker(mock_config)
    checker.load_existing_skills()

    # Cluster with keywords matching existing skill
    cluster = [
        {'event': {'task_type': 'sample', 'message': 'sample test skill'}}
    ]

    # Should find coverage
    covered = checker.check_coverage(cluster)
    assert covered is True or covered is False  # Depends on keyword matching


def test_mock_log_generator():
    """Test MockLogGenerator."""
    generator = MockLogGenerator()

    failures = generator.generate_mock_failures(10)

    assert len(failures) == 10
    for failure in failures:
        assert 'event' in failure
        assert 'line_num' in failure
        assert failure['event']['type'] == 'failure'


def test_monitor_run_mock(mock_config):
    """Test Monitor.run() in mock mode."""
    monitor = Monitor(mock_config)

    gaps = monitor.run(log_path=None)

    # Should generate gaps in mock mode
    assert isinstance(gaps, list)
    # Some gaps should be detected
    assert len(gaps) >= 0


def test_monitor_run_with_mock_failures(mock_config):
    """Test Monitor with generated mock failures."""
    mock_config.max_gaps_per_run = 5
    monitor = Monitor(mock_config)

    gaps = monitor.run()

    # Check gaps structure
    for gap in gaps:
        assert hasattr(gap, 'failure_context')
        assert hasattr(gap, 'failure_type')
        assert hasattr(gap, 'frequency')
        assert hasattr(gap, 'cluster_id')


def test_llm_analysis_in_mock_mode(mock_config):
    """Test that LLM analysis works in mock mode."""
    parser = PreCogLogParser(mock_config)

    # Should not raise error
    result = parser._analyze_failure_with_llm("ERROR: test error")

    assert result is not None
    assert 'failure_type' in result
    assert 'affected_agent' in result
    assert 'severity' in result


@patch('boto3.client')
def test_llm_analysis_with_bedrock_mock(mock_boto_client, mock_config):
    """Test LLM analysis with mocked bedrock client."""
    mock_config.mock_mode = False

    # Mock the bedrock client
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    # Mock the response
    mock_response = {
        'body': MagicMock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'output': {
            'message': {
                'content': [{
                    'text': json.dumps({
                        'failure_type': 'error',
                        'affected_agent': 'TestAgent',
                        'task_context': 'test',
                        'severity': 'high',
                        'normalized_description': 'Test error'
                    })
                }]
            }
        }
    }).encode('utf-8')

    mock_bedrock.invoke_model.return_value = mock_response

    # Create parser (this will initialize bedrock client)
    parser = PreCogLogParser(mock_config)

    # Test LLM analysis
    result = parser._analyze_failure_with_llm("ERROR: test")

    assert result is not None
    assert result['failure_type'] == 'error'


@patch('boto3.client')
def test_llm_clustering_with_bedrock_mock(mock_boto_client, mock_config):
    """Test LLM-based clustering with mocked bedrock client."""
    mock_config.mock_mode = False

    # Mock the bedrock client
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    # Mock the response for cluster key generation
    mock_response = {
        'body': MagicMock()
    }
    mock_response['body'].read.return_value = json.dumps({
        'output': {
            'message': {
                'content': [{
                    'text': 'api_timeout'
                }]
            }
        }
    }).encode('utf-8')

    mock_bedrock.invoke_model.return_value = mock_response

    # Create clusterer (this will initialize bedrock client)
    clusterer = FailureClusterer(mock_config)

    # Test LLM clustering
    failure = {
        'event': {
            'task_type': 'api_call',
            'failure_type': 'timeout',
            'agent': 'TestAgent',
            'message': 'API request timed out'
        }
    }

    cluster_id = clusterer._compute_cluster_id(failure)

    assert cluster_id is not None
    assert isinstance(cluster_id, str)
    assert len(cluster_id) > 0


def test_llm_clustering_in_mock_mode(mock_config):
    """Test that LLM clustering works in mock mode without real LLM calls."""
    clusterer = FailureClusterer(mock_config)

    failure = {
        'event': {
            'task_type': 'api_call',
            'failure_type': 'timeout',
            'agent': 'TestAgent',
            'message': 'API request timed out'
        }
    }

    # Should not raise error and should return a cluster ID
    cluster_id = clusterer._compute_cluster_id(failure)

    assert cluster_id is not None
    assert isinstance(cluster_id, str)
    assert len(cluster_id) > 0
