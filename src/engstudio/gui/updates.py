"""Help > Check for updates: asks GitHub for the newest release only when the user clicks it
(the application is otherwise fully offline). A newer version opens the release page in the
browser, where the user downloads the new installer; installing it upgrades in place.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QMessageBox, QWidget

__all__ = ["RELEASES_PAGE", "UpdateChecker", "is_newer", "parse_release"]

REPO = "LA3zz/Engineering-Studio"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"


def _version_tuple(text: str) -> tuple[int, ...] | None:
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text)
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def is_newer(latest: str, current: str) -> bool:
    """True if release tag ``latest`` (e.g. 'v0.7.0') is newer than ``current``."""
    a, b = _version_tuple(latest), _version_tuple(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def parse_release(payload: bytes) -> tuple[str, str]:
    """(tag, page URL) from GitHub's 'latest release' JSON; ValueError if unusable."""
    data = json.loads(payload.decode("utf-8"))
    tag = str(data.get("tag_name") or "")
    url = str(data.get("html_url") or RELEASES_PAGE)
    if not tag:
        raise ValueError("no tag in the release data")
    return tag, url


class UpdateChecker(QObject):
    finished = Signal(str, str)  # status ('newer' | 'current' | 'error'), detail

    def __init__(self, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current = current
        self._parent = parent
        self._net = QNetworkAccessManager(self)

    def check(self, show_result: bool = True) -> None:
        request = QNetworkRequest(QUrl(RELEASES_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"EngineeringStudio-update-check")
        request.setTransferTimeout(10000)
        reply = self._net.get(request)
        reply.finished.connect(lambda: self._done(reply, show_result))

    def _done(self, reply: QNetworkReply, show_result: bool) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            status, detail = "error", reply.errorString()
            if reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 404:
                status, detail = "current", "No release has been published yet."
        else:
            try:
                tag, url = parse_release(bytes(reply.readAll()))
                status, detail = ("newer", f"{tag}|{url}") if is_newer(tag, self.current) \
                    else ("current", tag)
            except (ValueError, UnicodeDecodeError) as exc:
                status, detail = "error", str(exc)
        reply.deleteLater()
        if show_result:
            self._show(status, detail)
        self.finished.emit(status, detail)

    def _show(self, status: str, detail: str) -> None:
        title = "Check for updates"
        if status == "newer":
            tag, url = detail.split("|", 1)
            answer = QMessageBox.question(
                self._parent, title,
                f"Engineering Studio {tag} is available (you have {self.current}).\n\n"
                "Open the download page? Run the new installer to upgrade; your settings "
                "and scripts are kept.")
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url))
        elif status == "current":
            QMessageBox.information(self._parent, title,
                                    f"You have the latest version ({self.current}).")
        else:
            QMessageBox.warning(self._parent, title,
                                f"Could not reach GitHub ({detail}).\nCheck your internet "
                                f"connection, or visit {RELEASES_PAGE}.")
