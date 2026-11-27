"""Test-wide offline guard.

Project requirement: Engineering Studio never needs the network. During the whole test
session every attempt to reach a non-loopback host (connect, DNS lookup, UDP send) is blocked
and recorded. A test that makes such an attempt FAILS at teardown, even if the code under
test swallowed the exception. Loopback (127.0.0.0/8, ::1, localhost) stays allowed so local
IPC can be tested.
"""

from __future__ import annotations

import ipaddress
import socket

import pytest

_attempts: list[str] = []


class NetworkBlockedError(RuntimeError):
    """Raised when code tries to reach a non-loopback host during tests."""


def _is_loopback(host) -> bool:
    if host is None:
        return True  # getaddrinfo(None, port) resolves to the local machine
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.rstrip(".").lower() == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False  # a hostname that needs DNS
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_loopback


def _host_of(address):
    return address[0] if isinstance(address, tuple) and address else None


def _block(what: str, host) -> None:
    _attempts.append(f"{what} {host!r}")
    raise NetworkBlockedError(f"network access blocked in tests: {what} {host!r}")


@pytest.fixture(scope="session", autouse=True)
def _offline_guard():
    mp = pytest.MonkeyPatch()
    sock = socket.socket

    real_connect, real_connect_ex, real_sendto = sock.connect, sock.connect_ex, sock.sendto
    real_getaddrinfo = socket.getaddrinfo
    real_gethostbyname, real_gethostbyname_ex = socket.gethostbyname, socket.gethostbyname_ex

    def connect(self, address):
        host = _host_of(address)
        if host is not None and not _is_loopback(host):
            _block("connect to", address)
        return real_connect(self, address)

    def connect_ex(self, address):
        host = _host_of(address)
        if host is not None and not _is_loopback(host):
            _block("connect_ex to", address)
        return real_connect_ex(self, address)

    def sendto(self, data, *args):
        host = _host_of(args[-1]) if args else None
        if host is not None and not _is_loopback(host):
            _block("sendto", args[-1])
        return real_sendto(self, data, *args)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_loopback(host):
            _block("DNS lookup of", host)
        return real_getaddrinfo(host, *args, **kwargs)

    def gethostbyname(host):
        if not _is_loopback(host):
            _block("DNS lookup of", host)
        return real_gethostbyname(host)

    def gethostbyname_ex(host):
        if not _is_loopback(host):
            _block("DNS lookup of", host)
        return real_gethostbyname_ex(host)

    mp.setattr(sock, "connect", connect)
    mp.setattr(sock, "connect_ex", connect_ex)
    mp.setattr(sock, "sendto", sendto)
    mp.setattr(socket, "getaddrinfo", getaddrinfo)
    mp.setattr(socket, "gethostbyname", gethostbyname)
    mp.setattr(socket, "gethostbyname_ex", gethostbyname_ex)
    yield
    mp.undo()


@pytest.fixture(autouse=True)
def _no_network_attempts():
    _attempts.clear()
    yield
    if _attempts:
        found = ", ".join(_attempts)
        _attempts.clear()
        pytest.fail(f"network access attempted during test: {found}", pytrace=False)


@pytest.fixture(autouse=True)
def _restore_working_folder():
    """cd, the Current Folder panel and examples change the working folder; undo it."""
    import os

    before = os.getcwd()
    yield
    if os.getcwd() != before:
        os.chdir(before)


@pytest.fixture
def blocked_attempts():
    """For tests that deliberately trigger the guard: the recorded attempts (cleared after)."""
    yield _attempts
    _attempts.clear()
