"""Offline guarantee (AC #17): block socket.connect for every test, autouse."""

import socket

import pytest


class _NetworkBlocked(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def deny(self, *args, **kwargs):
        raise _NetworkBlocked("network access is blocked in the memdoc test suite")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(
                            _NetworkBlocked("network access is blocked")))
    yield
