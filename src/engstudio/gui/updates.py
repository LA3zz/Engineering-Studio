"""Help > Check for Updates: asks GitHub for the newest release only when the user clicks it
(the application is otherwise fully offline).

When a newer version exists the user can:
- **Download and install** (one click): the installer attached to the release is downloaded
  to a temporary folder with a progress bar, its SHA-256 is checked against the checksum
  GitHub reports for the file (or the attached ``.sha256`` file), Engineering Studio closes
  normally (unsaved scripts are still offered for saving) and the installer runs silently with
  ``/UPDATE``; it upgrades in place, keeps settings and scripts, and restarts the app. A file
  whose checksum does not match is deleted and never run.
- **Open the download page** in the browser (the previous behaviour).
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

__all__ = ["INSTALLER_ARGS", "RELEASES_PAGE", "Release", "UpdateChecker", "is_newer",
           "parse_release", "sha256_of"]

REPO = "LA3zz/Engineering-Studio"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
# Inno Setup: progress window only, no questions; /UPDATE makes the installer restart the app.
INSTALLER_ARGS = ["/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                  "/UPDATE"]
_SETUP = re.compile(r"^EngineeringStudio-Setup-[\w.\-]+\.exe$", re.IGNORECASE)


@dataclass(frozen=True)
class Release:
    tag: str
    page: str
    installer_name: str = ""
    installer_url: str = ""
    installer_size: int = 0
    sha256: str = ""  # from GitHub's asset digest; empty if unknown
    sha256_url: str = ""  # the attached .sha256 file, used when there is no digest


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


def parse_release(payload: bytes) -> Release:
    """The release and its installer asset from GitHub's 'latest release' JSON; ValueError if
    unusable. A release without an installer is still returned (download page only)."""
    data = json.loads(payload.decode("utf-8"))
    tag = str(data.get("tag_name") or "")
    page = str(data.get("html_url") or RELEASES_PAGE)
    if not tag:
        raise ValueError("no tag in the release data")
    assets = [a for a in data.get("assets") or [] if isinstance(a, dict)]
    setup = next((a for a in assets if _SETUP.match(str(a.get("name", "")))), None)
    if setup is None:
        return Release(tag, page)
    name = str(setup["name"])
    digest = str(setup.get("digest") or "")
    sha = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else ""
    side = next((a for a in assets if str(a.get("name", "")).lower() == f"{name}.sha256".lower()),
                None)
    return Release(tag, page, name, str(setup.get("browser_download_url") or ""),
                   int(setup.get("size") or 0), sha,
                   str(side.get("browser_download_url") or "") if side else "")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _sha_from_text(text: str) -> str:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    return m.group(1).lower() if m else ""


def _launch(installer: Path) -> bool:
    return bool(QProcess.startDetached(str(installer), INSTALLER_ARGS)[0])


class UpdateChecker(QObject):
    finished = Signal(str, str)  # status ('newer' | 'current' | 'error'), detail
    installed = Signal(str)  # path of the verified installer that was started

    def __init__(self, current: str, parent: QWidget | None = None,
                 launcher: Callable[[Path], bool] = _launch,
                 download_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.current = current
        self.release: Release | None = None
        self._parent = parent
        self._launch = launcher
        self._dir = download_dir or Path(tempfile.gettempdir()) / "EngineeringStudio-update"
        self._net = QNetworkAccessManager(self)
        self._progress: QProgressDialog | None = None

    # ------------------------------------------------------------------- check
    def _request(self, url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"EngineeringStudio-update-check")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        return request

    def check(self, show_result: bool = True) -> None:
        request = self._request(RELEASES_API)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setTransferTimeout(10000)
        reply = self._net.get(request)
        reply.finished.connect(lambda: self._done(reply, show_result))

    def _done(self, reply: QNetworkReply, show_result: bool) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            status, detail = "error", reply.errorString()
            if reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 404:
                status, detail = "error", ("no public release found (the release page may be "
                                           "private or not published yet)")
        else:
            try:
                self.release = parse_release(bytes(reply.readAll()))
                tag = self.release.tag
                status, detail = ("newer", tag) if is_newer(tag, self.current) \
                    else ("current", tag)
            except (ValueError, UnicodeDecodeError, KeyError, TypeError) as exc:
                status, detail = "error", str(exc)
        reply.deleteLater()
        if show_result:
            self._show(status, detail)
        self.finished.emit(status, detail)

    def _show(self, status: str, detail: str) -> None:
        title = "Check for updates"
        if status == "newer" and self.release is not None:
            rel = self.release
            box = QMessageBox(self._parent)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle(title)
            box.setText(f"Engineering Studio {rel.tag} is available (you have {self.current}).")
            install = None
            if rel.installer_url:
                mb = rel.installer_size / 1e6
                box.setInformativeText(
                    f"Download and install it now ({mb:.0f} MB)? Engineering Studio closes, the "
                    "update installs and the program starts again. Your settings and scripts "
                    "are kept.")
                install = box.addButton("Download and install",
                                        QMessageBox.ButtonRole.AcceptRole)
            page = box.addButton("Open download page", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(install or page)
            box.exec()
            if install is not None and box.clickedButton() is install:
                self.download_and_install()
            elif box.clickedButton() is page:
                QDesktopServices.openUrl(QUrl(rel.page))
        elif status == "current":
            QMessageBox.information(self._parent, title,
                                    f"You have the latest version ({self.current}).")
        else:
            QMessageBox.warning(self._parent, title,
                                f"Could not reach GitHub ({detail}).\nCheck your internet "
                                f"connection, or visit {RELEASES_PAGE}.")

    # ------------------------------------------------------------------ install
    def download_and_install(self, interactive: bool = True) -> None:
        """Download the installer of ``self.release``, verify it and start it."""
        rel = self.release
        if rel is None or not rel.installer_url:
            self._fail("this release has no installer attached", interactive)
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / rel.installer_name
        if interactive:
            self._progress = QProgressDialog("Downloading the update...", "Cancel", 0, 100,
                                             self._parent)
            self._progress.setWindowTitle("Engineering Studio update")
            self._progress.setMinimumDuration(0)
            self._progress.setAutoClose(False)
            self._progress.setValue(0)
        reply = self._net.get(self._request(rel.installer_url))
        if self._progress is not None:
            self._progress.canceled.connect(reply.abort)
            reply.downloadProgress.connect(self._on_progress)
        reply.finished.connect(lambda: self._downloaded(reply, target, interactive))

    def _on_progress(self, received: int, total: int) -> None:
        if self._progress is not None and total > 0:
            self._progress.setValue(int(100 * received / total))

    def _downloaded(self, reply: QNetworkReply, target: Path, interactive: bool) -> None:
        cancelled = reply.error() == QNetworkReply.NetworkError.OperationCanceledError
        error = "" if reply.error() == QNetworkReply.NetworkError.NoError else reply.errorString()
        data = bytes(reply.readAll()) if not error else b""
        reply.deleteLater()
        if cancelled:
            self._close_progress()
            return
        if error:
            self._fail(f"the download failed ({error})", interactive)
            return
        target.write_bytes(data)
        rel = self.release
        if rel is not None and rel.sha256:
            self._verify_and_start(target, rel.sha256, interactive)
        elif rel is not None and rel.sha256_url:
            side = self._net.get(self._request(rel.sha256_url))
            side.finished.connect(lambda: self._checksum_file(side, target, interactive))
        else:
            target.unlink(missing_ok=True)
            self._fail("the release has no checksum, so the download cannot be verified",
                       interactive)

    def _checksum_file(self, reply: QNetworkReply, target: Path, interactive: bool) -> None:
        text = bytes(reply.readAll()).decode("ascii", "replace") \
            if reply.error() == QNetworkReply.NetworkError.NoError else ""
        reply.deleteLater()
        expected = _sha_from_text(text)
        if not expected:
            target.unlink(missing_ok=True)
            self._fail("the checksum file could not be read", interactive)
            return
        self._verify_and_start(target, expected, interactive)

    def _verify_and_start(self, target: Path, expected: str, interactive: bool) -> None:
        if sha256_of(target) != expected.lower():
            target.unlink(missing_ok=True)
            self._fail("the downloaded file does not match its checksum and was deleted; "
                       "nothing was installed", interactive)
            return
        self._close_progress()
        parent = self._parent
        if interactive and parent is not None and not parent.close():
            QMessageBox.information(None, "Engineering Studio update",
                                    "The update was not installed because Engineering Studio "
                                    "stayed open. Choose Help > Check for Updates again when "
                                    "you are ready.")
            return
        if not self._launch(target):
            self._fail("the installer could not be started", interactive)
            return
        self.installed.emit(str(target))

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None

    def _fail(self, reason: str, interactive: bool) -> None:
        self._close_progress()
        self.finished.emit("error", reason)
        if interactive:
            QMessageBox.warning(self._parent, "Engineering Studio update",
                                f"The update could not be installed: {reason}.\n\nYou can "
                                f"download the installer from {RELEASES_PAGE}.")
