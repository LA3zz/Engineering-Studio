"""G3.1 Current Folder browser (headless)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.gui.folder_panel import SETTINGS_KEY, FolderPanel  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


_made: list[FolderPanel] = []


def make(settings: UiSettings | None = None) -> FolderPanel:
    p = FolderPanel(settings)
    _made.append(p)
    return p


@pytest.fixture(autouse=True)
def _dispose_panels():
    """Delete every panel (and its QFileSystemModel thread) before the next test."""
    yield
    while _made:
        p = _made.pop()
        p.hide()
        p.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.m").write_text("x = 1;\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")
    return tmp_path.resolve()


def test_default_is_cwd(app, tree, monkeypatch):
    monkeypatch.chdir(tree)
    assert make(UiSettings(None)).folder == tree


def test_saved_folder_restored(app, tree):
    s = UiSettings(None)
    s.set(SETTINGS_KEY, str(tree / "sub"))
    assert make(s).folder == tree / "sub"


def test_invalid_saved_folder_falls_back(app, tree, monkeypatch):
    monkeypatch.chdir(tree)
    s = UiSettings(None)
    s.set(SETTINGS_KEY, str(tree / "missing"))
    assert make(s).folder == tree
    s.set(SETTINGS_KEY, 42)
    assert make(s).folder == tree


def test_set_folder_persists_and_signals(app, tree):
    s = UiSettings(None)
    p = make(s)
    seen = []
    p.folder_changed.connect(seen.append)
    assert p.set_folder(tree / "sub")
    assert p.folder == tree / "sub"
    assert s.get(SETTINGS_KEY) == str(tree / "sub")
    assert seen == [str(tree / "sub")]
    assert p.path_edit.text() == str(tree / "sub")
    assert p.set_folder(tree / "sub") and len(seen) == 1  # same folder: no signal


def test_set_folder_invalid_keeps_state(app, tree):
    p = make(UiSettings(None))
    p.set_folder(tree)
    assert not p.set_folder(tree / "nope")
    assert not p.set_folder(tree / "a.m")
    assert p.folder == tree
    assert p.path_edit.text() == str(tree)


def test_tree_root_matches_folder(app, tree):
    p = make(UiSettings(None))
    p.set_folder(tree)
    assert Path(p.model.filePath(p.tree.rootIndex())).resolve() == tree


def test_go_up_and_button_state(app, tree):
    p = make(UiSettings(None))
    p.set_folder(tree / "sub")
    assert p.up_button.isEnabled()
    assert p.go_up() and p.folder == tree
    root = Path(tree.anchor)
    p.set_folder(root)
    assert not p.up_button.isEnabled()
    assert not p.go_up() and p.folder == root


def test_activate_folder_and_files(app, tree):
    p = make(UiSettings(None))
    p.set_folder(tree)
    opened = []
    p.open_file_requested.connect(opened.append)
    assert p.activate_path(tree / "a.m")
    assert opened == [str(tree / "a.m")]
    assert not p.activate_path(tree / "notes.txt")
    assert not p.activate_path(tree / "ghost.m")
    assert len(opened) == 1
    assert p.activate_path(tree / "sub") and p.folder == tree / "sub"


def test_double_click_signal_path(app, tree):
    p = make(UiSettings(None))
    p.set_folder(tree)
    idx = p.model.index(str(tree / "sub"))
    assert idx.isValid()
    p.tree.doubleClicked.emit(idx)
    assert p.folder == tree / "sub"


def test_path_edit_enter(app, tree):
    p = make(UiSettings(None))
    p.path_edit.setText(str(tree / "sub"))
    p.path_edit.returnPressed.emit()
    assert p.folder == tree / "sub"
    p.path_edit.setText(str(tree / "bad"))
    p.path_edit.returnPressed.emit()
    assert p.folder == tree / "sub" and p.path_edit.text() == str(tree / "sub")


def test_main_window_integration(app, tree):
    win = MainWindow(UiSettings(None))
    try:
        assert isinstance(win.docks["folder"].widget(), FolderPanel)
        win.folder_panel.open_file_requested.emit(str(tree / "a.m"))
        ed = win.tabs.current_editor()
        assert ed is not None and ed.path == tree / "a.m"
        assert "x = 1" in ed.toPlainText()
    finally:
        win.tabs.current_editor().document().setModified(False)
        win.close()
        win.deleteLater()
