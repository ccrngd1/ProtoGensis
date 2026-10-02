"""Shared fixtures. The autouse socket block guarantees every test is offline."""
import socket

import pytest

from coherencegate.store import InMemoryStore, SQLiteStore


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Block socket.connect for the duration of every test (AC #11)."""
    def guard(self, address):
        raise RuntimeError(f"network access blocked in tests: connect({address!r})")
    monkeypatch.setattr(socket.socket, "connect", guard)
    yield


@pytest.fixture(params=["memory", "sqlite"])
def store_factory(request, tmp_path):
    """Parametrized store factory covering both backends (AC #1)."""
    counter = {"n": 0}

    def make(init=None):
        if request.param == "memory":
            return InMemoryStore(init)
        counter["n"] += 1
        return SQLiteStore(str(tmp_path / f"store{counter['n']}.db"), init)

    make.backend = request.param
    return make
