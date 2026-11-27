"""Main window tests. Run headless (offscreen); skipped if PySide6 is not installed."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402
from engstudio.gui.theme import DARK, LIGHT  # noqa: E402

DOCK_IDS = {"folder", "toolboxes", "workspace", "docs", "command", "diagnostics"}
# Docks tabbed behind a base dock are only "visible" while their tab is current, so
# visibility is asserted on the base docks, or per tab group.
BASES = ("folder", "workspace", "command")
GROUPS = (("folder", "toolboxes"), ("workspace", "docs"), ("command", "diagnostics"))


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp):
    w = MainWindow(UiSettings(None))
    w.show()
    qapp.processEvents()
    yield w
    for i in range(w.tabs.count()):
        w.tabs.widget(i).document().setModified(False)
    w.close()
    w.deleteLater()


def test_docks_created_and_visible(win):
    assert set(win.docks) == DOCK_IDS
    names = [d.objectName() for d in win.docks.values()]
    assert len(set(names)) == len(names)
    for dock_id in BASES:
        assert win.docks[dock_id].isVisible()


def test_menus_present(win):
    titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
    assert titles == ["File", "View", "Run", "Help"]


def test_visibility_toggle_and_reset(win, qapp):
    cmd = win.docks["command"]
    cmd.toggleViewAction().trigger()
    qapp.processEvents()
    assert not cmd.isVisible()
    win.reset_layout()
    qapp.processEvents()
    assert cmd.isVisible()


def test_hide_and_show_all(win, qapp):
    win.set_all_panels(False)
    qapp.processEvents()
    assert not any(d.isVisible() for d in win.docks.values())
    win.set_all_panels(True)
    qapp.processEvents()
    for group in GROUPS:
        assert any(win.docks[i].isVisible() for i in group), group


def test_theme_switch(win, qapp):
    win.set_theme("dark")
    assert win.theme == "dark" and DARK.window in qapp.styleSheet()
    assert win.settings.get("theme") == "dark"
    win.toggle_theme()
    assert win.theme == "light" and LIGHT.window in qapp.styleSheet()
    with pytest.raises(ValueError):
        win.set_theme("nope")


def test_layout_and_theme_persist(qapp):
    settings = UiSettings(None)
    w1 = MainWindow(settings)
    w1.show()
    w1.docks["workspace"].toggleViewAction().trigger()
    w1.set_theme("dark")
    w1.close()
    w2 = MainWindow(settings)
    w2.show()
    qapp.processEvents()
    assert w2.theme == "dark"
    assert w2.layout_restored
    assert not w2.docks["workspace"].isVisible()
    w2.close()


def test_corrupt_saved_state_falls_back_to_default(qapp):
    settings = UiSettings(None)
    settings.set_bytes("window_state", b"garbage")
    settings.set_bytes("window_geometry", b"garbage")
    settings.set("layout_version", 1)
    w = MainWindow(settings)
    w.show()
    qapp.processEvents()
    assert not w.layout_restored
    assert all(w.docks[i].isVisible() for i in BASES)
    w.close()


def test_script_tabs_new_edit_title(win):
    assert win.tabs.count() == 1
    win.new_script()
    assert win.tabs.count() == 2
    ed = win.tabs.current_editor()
    ed.insertPlainText("x = 1;")
    assert win.tabs.tabText(win.tabs.currentIndex()).endswith("*")


def test_open_edit_save_roundtrip(win, tmp_path):
    p = tmp_path / "demo.m"
    p.write_text("a = 1;\n", encoding="utf-8")
    assert win.tabs.open_path(p)
    assert win.tabs.count() == 1  # pristine untitled tab was reused
    ed = win.tabs.current_editor()
    assert ed.toPlainText() == "a = 1;\n" and ed.path == p.resolve()
    ed.setPlainText("a = 2;\n")
    assert win.tabs.save()
    raw = p.read_bytes()
    assert raw == b"a = 2;\n" and not raw.startswith(b"\xef\xbb\xbf")
    assert not ed.document().isModified()
    assert win.tabs.open_path(p) and win.tabs.count() == 1  # already open -> focus only


def test_about_text_is_current():
    from engstudio.gui.main_window import about_text
    from engstudio.version import __version__
    text = about_text()
    assert __version__ in text and "G1" not in text and "not connected" not in text
    assert "python-control" in text and "Not affiliated with MathWorks" in text
