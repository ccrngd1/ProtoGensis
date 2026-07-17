"""Shared test fixtures / paths."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CLEAN = FIXTURES / "clean"
MALICIOUS = FIXTURES / "malicious"


@pytest.fixture(scope="session")
def clean_dir() -> Path:
    return CLEAN


@pytest.fixture(scope="session")
def malicious_dir() -> Path:
    return MALICIOUS
