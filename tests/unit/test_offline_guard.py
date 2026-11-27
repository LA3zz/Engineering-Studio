"""The offline guard (tests/conftest.py) blocks external network access, allows loopback."""

import socket

import pytest


def test_connect_to_external_ip_blocked(blocked_attempts):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        with pytest.raises(RuntimeError, match="network access blocked"):
            s.connect(("203.0.113.1", 80))  # TEST-NET-3 (RFC 5737), never routable
        with pytest.raises(RuntimeError, match="network access blocked"):
            s.connect_ex(("198.51.100.7", 443))  # TEST-NET-2
    finally:
        s.close()
    assert len(blocked_attempts) == 2


def test_create_connection_blocked(blocked_attempts):
    with pytest.raises(RuntimeError, match="network access blocked"):
        socket.create_connection(("203.0.113.1", 80), timeout=1)
    assert blocked_attempts


def test_dns_lookup_blocked(blocked_attempts):
    with pytest.raises(RuntimeError, match="network access blocked"):
        socket.getaddrinfo("example.com", 80)
    with pytest.raises(RuntimeError, match="network access blocked"):
        socket.gethostbyname("example.org")
    assert len(blocked_attempts) == 2


def test_udp_sendto_blocked(blocked_attempts):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        with pytest.raises(RuntimeError, match="network access blocked"):
            s.sendto(b"x", ("203.0.113.1", 9))
    assert len(blocked_attempts) == 1


def test_private_lan_addresses_blocked(blocked_attempts):
    for host in ("10.0.0.1", "192.168.1.1", "0.0.0.0"):
        with pytest.raises(RuntimeError, match="network access blocked"):
            socket.getaddrinfo(host, 80)
    assert len(blocked_attempts) == 3


def test_attempt_recorded_even_if_swallowed(blocked_attempts):
    try:
        socket.getaddrinfo("swallowed.example", 80)
    except RuntimeError:
        pass  # code under test hides the error; the guard still records it
    assert len(blocked_attempts) == 1
    assert "swallowed.example" in blocked_attempts[0]


def test_loopback_names_allowed_in_lookups():
    for host in ("localhost", "127.0.0.1", "::1", "::ffff:127.0.0.1", None):
        try:
            socket.getaddrinfo(host, 80)
        except OSError:
            pass  # resolver quirks are irrelevant here; only the guard blocking would fail


def test_loopback_connection_works():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.settimeout(5)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(server.getsockname())
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                client.sendall(b"ping")
                assert conn.recv(4) == b"ping"
