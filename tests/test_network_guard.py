import socket

import pytest
from conftest import NetworkBlocked


def test_guard_blocks_remote_hosts():
    """Broken case: without the conftest guard this connect would leave the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    with pytest.raises(NetworkBlocked):
        s.connect(("93.184.216.34", 80))
    s.close()


def test_guard_allows_localhost():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    c = socket.socket()
    c.settimeout(1)
    c.connect(("127.0.0.1", srv.getsockname()[1]))
    c.close()
    srv.close()
