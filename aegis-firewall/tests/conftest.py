"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_policy_file():
    """Create a temporary policy file for testing."""
    content = """
name: test_policy
description: Test policy
default_action: deny

rules:
  - name: block_high_severity
    tools: '*'
    min_severity: high
    action: deny
    reason: High severity blocked

  - name: allow_safe
    tools: '*'
    min_severity: none
    action: allow
    reason: No threats detected
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(content)
        path = f.name

    yield path

    os.unlink(path)


@pytest.fixture
def temp_audit_log():
    """Create a temporary audit log file."""
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as f:
        path = f.name

    yield path

    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_tool_arguments():
    """Sample tool arguments for testing."""
    return {
        "command": "echo hello",
        "args": ["world"],
        "nested": {
            "value": "test"
        }
    }
