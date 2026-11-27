"""Workspace browser tests. Headless (offscreen); skipped without PySide6."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.app.kernel.protocol import Stdout, VariableInfo  # noqa: E402
from engstudio.app.kernel.stub import StubKernelClient  # noqa: E402
from engstudio.gui.kernel_bridge import KernelBridge  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402
from engstudio.gui.workspace_panel import WorkspaceModel, WorkspacePanel  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ws(qapp):
    bridge = KernelBridge(StubKernelClient())
    panel = WorkspacePanel(bridge)
    panel.show()
    yield panel
    panel.close()
    panel.deleteLater()


def shown_names(panel):
    return [panel.proxy.index(r, 0).data() for r in range(panel.proxy.rowCount())]


def select_name(panel, name):
    for r in range(panel.proxy.rowCount()):
        if panel.proxy.index(r, 0).data() == name:
            panel.view.selectRow(r)
            return
    raise AssertionError(f"{name} not shown")


def test_model_contents(qapp):
    m = WorkspaceModel()
    m.set_variables([VariableInfo("a", "double", (1, 1), "5"),
                     VariableInfo("M", "double", (3, 4), "<3x4 double>")])
    assert m.rowCount() == 2 and m.columnCount() == 4
    assert [m.index(1, c).data() for c in range(4)] == ["M", "double", "3x4", "<3x4 double>"]
    assert m.headerData(0, Qt.Orientation.Horizontal) == "Name"


def test_model_in_place_update_keeps_rows(qapp):
    m = WorkspaceModel()
    resets = []
    m.modelReset.connect(lambda: resets.append(1))
    m.set_variables([VariableInfo("a", "double", (1, 1), "1")])
    assert len(resets) == 1
    m.set_variables([VariableInfo("a", "double", (1, 1), "2")])
    assert len(resets) == 1 and m.index(0, 3).data() == "2"  # updated without reset
    m.set_variables([])
    assert len(resets) == 2 and m.rowCount() == 0


def test_table_follows_kernel_and_sorts_by_name(ws):
    ws.bridge.execute("z = 1;\na = 2.5;\nB = 3;")
    assert shown_names(ws) == ["a", "B", "z"]
    row = [ws.proxy.index(0, c).data() for c in range(4)]
    assert row == ["a", "double", "1x1", "2.5000"]
    assert ws.status.text() == "3 variables"


def test_value_update_keeps_selection(ws):
    ws.bridge.execute("a = 1;\nb = 2;")
    select_name(ws, "b")
    ws.bridge.execute("b = 99;")
    assert ws.selected_names() == ["b"]
    row = shown_names(ws).index("b")
    assert ws.proxy.index(row, 3).data() == "99"


def test_clear_selected(ws):
    ws.bridge.execute("a = 1;\nb = 2;\nc = 3;")
    assert not ws.act_clear_selected.isEnabled()
    select_name(ws, "b")
    assert ws.act_clear_selected.isEnabled()
    ws.act_clear_selected.trigger()
    assert shown_names(ws) == ["a", "c"]
    assert ws.status.text() == "2 variables"


def test_clear_all_and_action_state(ws):
    assert not ws.act_clear_all.isEnabled()
    ws.bridge.execute("a = 1;")
    assert ws.act_clear_all.isEnabled() and ws.status.text() == "1 variable"
    ws.act_clear_all.trigger()
    assert shown_names(ws) == [] and not ws.act_clear_all.isEnabled()


def test_filter(ws):
    ws.bridge.execute("alpha = 1;\nbeta = 2;\nAlfa = 3;")
    ws.filter.setText("AL")
    assert shown_names(ws) == ["Alfa", "alpha"]
    ws.filter.setText("")
    assert len(shown_names(ws)) == 3


def test_double_click_displays_variable(ws):
    ws.bridge.execute("q = 7;")
    got = []
    ws.bridge.event.connect(got.append)
    ws.view.doubleClicked.emit(ws.proxy.index(0, 0))
    out = "".join(e.text for e in got if isinstance(e, Stdout))
    assert out == "q =\n\n     7\n\n"


def test_no_kernel_disables_panel(qapp):
    p = WorkspacePanel(None)
    assert not p.isEnabled() and p.status.text() == "No kernel connected"
    p.clear_all()  # must not raise
    p.clear_selected()


def test_shutdown_kernel_reports_error(qapp):
    bridge = KernelBridge(StubKernelClient())
    p = WorkspacePanel(bridge)
    bridge.execute("a = 1;")
    bridge.shutdown()
    p.clear_all()
    assert p.status.text().startswith("Error:")


def test_main_window_integration(qapp):
    w = MainWindow(UiSettings(None), StubKernelClient())
    w.show()
    panel = w.docks["workspace"].widget()
    assert isinstance(panel, WorkspacePanel)
    w.command_window.input.setText("x = 5;")
    w.command_window.submit()
    assert shown_names(panel) == ["x"]
    w.command_window.input.setText("clear")
    w.command_window.submit()
    assert shown_names(panel) == []
    w.close()
