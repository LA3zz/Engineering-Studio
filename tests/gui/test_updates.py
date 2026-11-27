"""Help > Check for Updates: version comparison, release parsing and the one-click update
(download, checksum, start). No internet: downloads use file:// URLs."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import hashlib  # noqa: E402
import json  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QUrl  # noqa: E402

from engstudio.gui.updates import (  # noqa: E402
    INSTALLER_ARGS,
    RELEASES_PAGE,
    Release,
    UpdateChecker,
    is_newer,
    parse_release,
)


@pytest.mark.parametrize("latest, current, newer", [
    ("v0.7.0", "0.6.0", True), ("0.6.1", "0.6.0", True), ("v1.0", "0.9.9", True),
    ("v0.6.0", "0.6.0", False), ("v0.5.9", "0.6.0", False), ("0.6", "0.6.0", False),
    ("v0.10.0", "0.9.0", True), ("nightly", "0.6.0", False), ("v0.7.0-beta", "0.6.0", True),
])
def test_is_newer(latest, current, newer):
    assert is_newer(latest, current) is newer


def test_parse_release_finds_the_installer_and_its_checksum():
    payload = json.dumps({
        "tag_name": "v0.8.2", "html_url": "https://github.com/x/y/releases/tag/v0.8.2",
        "assets": [
            {"name": "Engineering_Studio_User_Manual.pdf", "browser_download_url": "u/m"},
            {"name": "EngineeringStudio-Setup-0.8.2.exe", "size": 117_000_000,
             "browser_download_url": "u/setup", "digest": "sha256:" + "AB" * 32},
            {"name": "EngineeringStudio-Setup-0.8.2.exe.sha256", "browser_download_url": "u/s"},
        ]}).encode()
    r = parse_release(payload)
    assert (r.tag, r.installer_name, r.installer_url) == (
        "v0.8.2", "EngineeringStudio-Setup-0.8.2.exe", "u/setup")
    assert r.sha256 == "ab" * 32 and r.sha256_url == "u/s" and r.installer_size == 117_000_000
    bare = parse_release(json.dumps({"tag_name": "v1"}).encode())
    assert bare.page == RELEASES_PAGE and bare.installer_url == ""
    with pytest.raises(ValueError):
        parse_release(b"{}")


def test_installer_runs_silently_and_restarts_the_app():
    assert "/SILENT" in INSTALLER_ARGS and "/UPDATE" in INSTALLER_ARGS


@pytest.fixture
def setup_file(tmp_path):
    src = tmp_path / "server" / "EngineeringStudio-Setup-9.9.9.exe"
    src.parent.mkdir()
    src.write_bytes(b"MZ fake installer " * 1000)
    return src


_CHECKERS: list = []


@pytest.fixture(autouse=True)
def _delete_checkers():
    """Checkers own a QNetworkAccessManager (with worker threads): delete them while Qt runs,
    never leave them to Python's garbage collector (that aborts the process)."""
    yield
    from PySide6.QtCore import QCoreApplication, QEvent

    while _CHECKERS:
        _CHECKERS.pop().deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _checker(tmp_path, release, started):
    def launch(path):
        started.append(path)
        return True

    c = UpdateChecker("0.8.1", None, launcher=launch, download_dir=tmp_path / "dl")
    _CHECKERS.append(c)
    return c


def _release(src, **kw):
    return Release("v9.9.9", "page", src.name, QUrl.fromLocalFile(str(src)).toString(),
                   src.stat().st_size, **kw)


def test_download_verified_by_digest_then_started(qtbot, tmp_path, setup_file):
    started = []
    c = _checker(tmp_path, None, started)
    c.release = _release(setup_file, sha256=hashlib.sha256(setup_file.read_bytes()).hexdigest())
    with qtbot.waitSignal(c.installed, timeout=5000) as sig:
        c.download_and_install(interactive=False)
    got = tmp_path / "dl" / setup_file.name
    assert sig.args == [str(got)] and started == [got]
    assert got.read_bytes() == setup_file.read_bytes()


def test_download_verified_by_sha256_file(qtbot, tmp_path, setup_file):
    side = setup_file.with_name(setup_file.name + ".sha256")
    side.write_text(f"{hashlib.sha256(setup_file.read_bytes()).hexdigest()}  {setup_file.name}\n")
    started = []
    c = _checker(tmp_path, None, started)
    c.release = _release(setup_file, sha256_url=QUrl.fromLocalFile(str(side)).toString())
    with qtbot.waitSignal(c.installed, timeout=5000):
        c.download_and_install(interactive=False)
    assert len(started) == 1


def test_wrong_checksum_deletes_the_file_and_installs_nothing(qtbot, tmp_path, setup_file):
    started = []
    c = _checker(tmp_path, None, started)
    c.release = _release(setup_file, sha256="0" * 64)
    with qtbot.waitSignal(c.finished, timeout=5000) as sig:
        c.download_and_install(interactive=False)
    assert sig.args[0] == "error" and "does not match" in sig.args[1]
    assert started == [] and not (tmp_path / "dl" / setup_file.name).exists()


def test_release_without_checksum_is_refused(qtbot, tmp_path, setup_file):
    started = []
    c = _checker(tmp_path, None, started)
    c.release = _release(setup_file)
    with qtbot.waitSignal(c.finished, timeout=5000) as sig:
        c.download_and_install(interactive=False)
    assert sig.args[0] == "error" and "no checksum" in sig.args[1] and started == []


def test_missing_file_reports_an_error(qtbot, tmp_path, setup_file):
    started = []
    c = _checker(tmp_path, None, started)
    c.release = _release(setup_file, sha256="0" * 64)
    setup_file.unlink()
    with qtbot.waitSignal(c.finished, timeout=5000) as sig:
        c.download_and_install(interactive=False)
    assert sig.args[0] == "error" and started == []


def test_help_menu_has_check_for_updates(qtbot):
    from engstudio.app.kernel.stub import StubKernelClient
    from engstudio.gui.main_window import MainWindow
    from engstudio.gui.settings import UiSettings

    win = MainWindow(UiSettings(None), StubKernelClient())
    qtbot.addWidget(win)
    help_menu = next(a.menu() for a in win.menuBar().actions() if a.text() == "&Help")
    texts = [a.text() for a in help_menu.actions()]
    assert "Check for &Updates..." in texts and "&About" in texts
