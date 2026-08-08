import sys

import pytest

from harness_guard.observe.sidefx import CanaryWorkspace


@pytest.fixture
def workspace():
    ws = CanaryWorkspace()
    try:
        yield ws
    finally:
        ws.cleanup()


@pytest.fixture
def vulnerable_cmd():
    return [sys.executable, "-m", "harness_guard.demo.vulnerable_harness"]


@pytest.fixture
def hardened_cmd():
    return [sys.executable, "-m", "harness_guard.demo.hardened_harness"]
