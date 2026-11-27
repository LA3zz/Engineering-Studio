"""One running Engineering Studio per user: a second launch (desktop shortcut, "Open with" on
an .m file) hands its file names to the window that is already open and exits, instead of
starting a second, slow copy of the application.

Uses a ``QLocalServer`` named per user. ``try_forward(paths)`` returns True when another
instance received the paths; otherwise the caller starts normally and calls ``listen``.
"""

from __future__ import annotations

import getpass
import json
from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

__all__ = ["SingleInstance", "server_name"]

_TIMEOUT_MS = 1500


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # no user name available: still one name per machine
        user = "user"
    return "engstudio-" + "".join(c for c in user if c.isalnum())[:40]


class SingleInstance(QObject):
    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name or server_name()
        self._server: QLocalServer | None = None
        self._on_paths: Callable[[list[str]], None] | None = None
        self._sockets: list[QLocalSocket] = []

    def try_forward(self, paths: list[str]) -> bool:
        """Send ``paths`` to a running instance; True if one answered."""
        sock = QLocalSocket()
        sock.connectToServer(self.name)
        if not sock.waitForConnected(_TIMEOUT_MS):
            return False
        sock.write(json.dumps(paths).encode("utf-8") + b"\n")
        sock.flush()
        sock.waitForBytesWritten(_TIMEOUT_MS)
        if sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
            sock.waitForDisconnected(300)  # let the receiver read before we hang up
        sock.disconnectFromServer()
        return True

    def listen(self, on_paths: Callable[[list[str]], None]) -> bool:
        """Accept paths from later launches; ``on_paths`` runs in the GUI thread."""
        self._on_paths = on_paths
        QLocalServer.removeServer(self.name)  # stale socket of a crashed instance
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        return self._server.listen(self.name)

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    def _accept(self) -> None:
        assert self._server is not None
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            buf = bytearray()

            done = [False]

            def read(sock: QLocalSocket = sock, buf: bytearray = buf, done: list = done) -> None:
                if done[0]:
                    return
                buf.extend(bytes(sock.readAll()))
                if buf.endswith(b"\n"):
                    done[0] = True
                    try:
                        paths = json.loads(buf.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        paths = []
                    if self._on_paths is not None and isinstance(paths, list):
                        self._on_paths([str(p) for p in paths])
                    sock.disconnectFromServer()

            sock.readyRead.connect(read)
            sock.disconnected.connect(read)  # the sender may hang up before we read
            self._sockets.append(sock)
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            read()

    def _drop(self, sock: QLocalSocket) -> None:
        if sock in self._sockets:
            self._sockets.remove(sock)
            sock.deleteLater()
