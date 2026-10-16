"""Shared fixtures. All tests are offline: socket.connect is blocked."""

import os
import socket
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policygate import guard  # noqa: E402


@pytest.fixture(autouse=True)
def _guard_roots_isolated():
    """Audit hooks cannot be uninstalled, so a guard-installing test would
    otherwise leave its protected roots active and block a later test's
    subprocess calls (e.g. the host tests spawning
    `python -m policygate.cli ... --root /root/.openclaw` from a .venv path
    the guard would match against a registered root). Clear the registered
    roots after every test; a test that needs the guard installs it (and its
    roots) itself, and install() re-registers the always-protected roots.
    Real CLI use is unaffected: nothing outside the test suite resets."""
    yield
    guard._reset_registered_roots()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(self, *a, **k):
        raise RuntimeError("network access is blocked in the policygate test suite")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


def pytest_collection_modifyitems(config, items):
    host_enabled = os.environ.get("PG_HOST_TESTS") == "1" and os.access(
        "/root/.openclaw", os.R_OK
    )
    skip_host = pytest.mark.skip(reason="host test: needs PG_HOST_TESTS=1 and readable /root/.openclaw")
    for item in items:
        if "host" in item.keywords and not host_enabled:
            item.add_marker(skip_host)
