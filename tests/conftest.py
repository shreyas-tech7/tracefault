"""Test guard: any socket connection to a host that is not local fails the test."""

import socket

import pytest

LOCAL = {"localhost", "127.0.0.1", "::1"}
_real_connect = socket.socket.connect


class NetworkBlocked(RuntimeError):
    pass


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if self.family == socket.AF_UNIX or host in LOCAL:
        return _real_connect(self, address)
    raise NetworkBlocked(f"test tried to reach {host!r}; tests must run offline")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    yield
