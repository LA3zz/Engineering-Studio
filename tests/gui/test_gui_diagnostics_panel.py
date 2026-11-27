"""Diagnostics panel (headless; skipped without PySide6)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from engstudio.app.kernel.protocol import Diagnostics, ExecutionFinished  # noqa: E402
from engstudio.app.kernel.stub import StubKernelClient  # noqa: E402
from engstudio.core.diagnostics import Diagnostic, SourceLoc  # noqa: E402
from engstudio.gui.diagnostic_log import SEVERITY_COLORS  # noqa: E402
from engstudio.gui.diagnostics_panel import DiagnosticsPanel  # noqa: E402
from engstudio.gui.kernel_bridge import KernelBridge  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402


def row(panel, r):
    return [panel.table.item(r, c).text() for c in range(5)]


def feed_mixed(panel):
    panel._on_event(Diagnostics(5, (
        Diagnostic("warning", "W1", "careful", None),
        Diagnostic("info", "I1", "fyi", SourceLoc("d/x.m", 2, 4)),
    )))


@pytest.fixture
def bridge():
    return KernelBridge(StubKernelClient())


@pytest.fixture
def panel(bridge):
    p = DiagnosticsPanel(bridge)
    yield p
    p.hide()
    p.deleteLater()


def test_empty_state(panel):
    assert panel.table.rowCount() == 0
    assert panel.status.text() == "0 of 0 shown"
    assert panel.filter_buttons["error"].text() == "Errors (0)"


def test_stub_error_appears_with_location_and_run(panel, bridge):
    rid = bridge.execute("bogus line")
    assert panel.table.rowCount() == 1
    r = row(panel, 0)
    assert (r[0], r[1], r[3], r[4]) == ("Error", "E_STUB", "line 1, col 1", f"#{rid}")
    assert "stub kernel" in r[2]
    assert panel.filter_buttons["error"].text() == "Errors (1)"


def test_diagnostics_accumulate_across_executions(panel, bridge):
    a = bridge.execute("bogus")
    b = bridge.execute("alsobogus 1 2")
    assert panel.table.rowCount() == 2
    assert [row(panel, i)[4] for i in range(2)] == [f"#{a}", f"#{b}"]


def test_other_events_and_empty_diagnostics_are_ignored(panel):
    panel._on_event(ExecutionFinished(1, "ok"))
    panel._on_event(Diagnostics(1, ()))
    assert panel.table.rowCount() == 0


def test_warning_and_info_rows(panel):
    feed_mixed(panel)
    assert [row(panel, i)[0] for i in range(2)] == ["Warning", "Info"]
    assert row(panel, 1)[3] == "x.m: line 2, col 4"
    assert row(panel, 0)[3] == ""
    assert panel.filter_buttons["warning"].text() == "Warnings (1)"
    assert panel.filter_buttons["info"].text() == "Info (1)"


def test_severity_filters(panel, bridge):
    bridge.execute("bogus")
    feed_mixed(panel)
    assert panel.table.rowCount() == 3
    panel.filter_buttons["error"].setChecked(False)
    assert [row(panel, i)[0] for i in range(panel.table.rowCount())] == ["Warning", "Info"]
    assert panel.status.text() == "2 of 3 shown"
    panel.filter_buttons["error"].setChecked(True)
    assert panel.table.rowCount() == 3


def test_clear_button_empties_everything(panel, bridge):
    bridge.execute("bogus")
    feed_mixed(panel)
    panel.clear_button.click()
    assert panel.table.rowCount() == 0 and panel.log.entries == ()
    assert panel.filter_buttons["error"].text() == "Errors (0)"


def test_double_click_on_a_located_row_emits_its_location(panel, bridge):
    bridge.execute("bogus")
    feed_mixed(panel)
    got = []
    panel.location_activated.connect(lambda f, ln, c: got.append((f, ln, c)))
    assert panel.activate_row(0)  # stub error: line 1, col 1, no file
    assert panel.activate_row(2)  # info with a file
    assert not panel.activate_row(1)  # warning without a location
    assert not panel.activate_row(-1) and not panel.activate_row(99)
    assert got == [(None, 1, 1), ("d/x.m", 2, 4)]
    panel.table.cellDoubleClicked.emit(0, 2)
    assert got[-1] == (None, 1, 1)


def test_theme_colours_severity_text_and_validates(panel, bridge):
    bridge.execute("bogus")
    panel.set_theme("dark")
    assert panel.table.item(0, 0).foreground().color().name() == SEVERITY_COLORS["dark"]["error"]
    panel.set_theme("light")
    assert panel.table.item(0, 0).foreground().color().name() == SEVERITY_COLORS["light"]["error"]
    with pytest.raises(ValueError):
        panel.set_theme("neon")
    assert panel.theme == "light"
    with pytest.raises(ValueError):
        DiagnosticsPanel(None, "neon")


def test_panel_without_a_kernel_still_works():
    p = DiagnosticsPanel(None)
    feed_mixed(p)
    assert p.table.rowCount() == 2
    p.deleteLater()


def test_main_window_integration():
    win = MainWindow(UiSettings(None), StubKernelClient())
    try:
        assert isinstance(win.docks["diagnostics"].widget(), DiagnosticsPanel)
        win.bridge.execute("oops")
        assert win.diagnostics_panel.table.rowCount() == 1
        win.set_theme("dark")
        colour = win.diagnostics_panel.table.item(0, 0).foreground().color().name()
        assert colour == SEVERITY_COLORS["dark"]["error"]
    finally:
        win.tabs.current_editor().document().setModified(False)
        win.close()
        win.deleteLater()
