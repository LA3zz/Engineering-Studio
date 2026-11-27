"""Scripts open at exit reopen at the next start (untitled and deleted files are skipped)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def names(win):
    return [win.tabs.editor(i).display_name for i in range(win.tabs.count())]


def test_open_scripts_come_back(app, tmp_path):
    a, b, c = (tmp_path / n for n in ("a.m", "b.m", "c.m"))
    for f in (a, b, c):
        f.write_text("x = 1;\n", encoding="utf-8")
    settings_file = tmp_path / "ui.json"
    w1 = MainWindow(UiSettings(settings_file))
    for f in (a, b, c):
        w1.tabs.open_path(f)
    w1.tabs.new_script()  # untitled: not remembered
    w1.tabs.open_path(b)  # current tab
    w1.close()
    w1.deleteLater()
    c.unlink()  # deleted since: skipped
    w2 = MainWindow(UiSettings(settings_file))
    try:
        assert names(w2) == ["a.m", "b.m"]
        assert w2.tabs.current_editor().display_name == "b.m"
        assert "x = 1" in w2.tabs.current_editor().toPlainText()
    finally:
        w2.close()
        w2.deleteLater()


def test_no_saved_session_gives_one_untitled_tab(app):
    w = MainWindow(UiSettings(None))
    try:
        assert names(w) == ["untitled.m"]
    finally:
        w.close()
        w.deleteLater()
