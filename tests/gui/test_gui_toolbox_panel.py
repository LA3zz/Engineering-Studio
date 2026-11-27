"""Toolbox browser (G3.2). Headless (offscreen); skipped without PySide6."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from engstudio.app.kernel.client import KernelClient  # noqa: E402
from engstudio.app.kernel.stub import SAMPLE_TOOLBOXES, StubKernelClient  # noqa: E402
from engstudio.gui.kernel_bridge import KernelBridge  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402
from engstudio.gui.toolbox_panel import ToolboxPanel  # noqa: E402


def functions(panel):
    """name -> item for every function item."""
    out = {}
    for i in range(panel.tree.topLevelItemCount()):
        top = panel.tree.topLevelItem(i)
        for j in range(top.childCount()):
            child = top.child(j)
            out[child.text(0)] = child
    return out


def tops(panel):
    return [panel.tree.topLevelItem(i) for i in range(panel.tree.topLevelItemCount())]


@pytest.fixture
def panel():
    p = ToolboxPanel(KernelBridge(StubKernelClient()))
    yield p
    p.hide()
    p.deleteLater()


def test_populated_from_kernel(panel):
    assert len(tops(panel)) == len(SAMPLE_TOOLBOXES)
    expected = {f.name for tb in SAMPLE_TOOLBOXES for f in tb.functions}
    assert set(functions(panel)) == expected
    assert "sample" in tops(panel)[0].text(0).lower()
    assert str(len(SAMPLE_TOOLBOXES)) in panel.status.text()


def test_function_tooltip_has_signature_and_summary(panel):
    tip = functions(panel)["inv"].toolTip(0)
    assert "inv(A)" in tip and "Matrix inverse" in tip


def test_double_click_function_emits_name(panel):
    got = []
    panel.insert_requested.connect(got.append)
    panel.tree.itemDoubleClicked.emit(functions(panel)["trapz"], 0)
    assert got == ["trapz"]


def test_double_click_toolbox_emits_nothing(panel):
    got = []
    panel.insert_requested.connect(got.append)
    assert not panel.activate_item(tops(panel)[0])
    assert got == []


def test_filter_by_name_and_summary(panel):
    panel.filter_edit.setText("INV")  # case-insensitive
    items = functions(panel)
    assert [n for n, it in items.items() if not it.isHidden()] == ["inv"]
    assert tops(panel)[0].isHidden()  # control toolbox has no match
    assert not tops(panel)[1].isHidden()
    assert "1 of" in panel.status.text()
    panel.filter_edit.setText("eigenvalues")  # summary text
    assert [n for n, it in functions(panel).items() if not it.isHidden()] == ["eig"]


def test_filter_by_toolbox_name_shows_all_its_functions(panel):
    panel.filter_edit.setText("control")
    visible = {n for n, it in functions(panel).items() if not it.isHidden()}
    assert visible == {"bode", "step", "tf"}


def test_clearing_filter_restores_everything(panel):
    panel.filter_edit.setText("zzz-no-match")
    assert all(it.isHidden() for it in functions(panel).values())
    panel.filter_edit.setText("")
    assert not any(it.isHidden() for it in functions(panel).values())
    assert not any(t.isHidden() for t in tops(panel))


def test_without_bridge_shows_message():
    p = ToolboxPanel(None)
    assert p.tree.topLevelItemCount() == 0
    assert "No kernel" in p.status.text()
    p.refresh()  # must not raise
    p.deleteLater()


def test_unsupported_client_shows_message():
    class NoList(KernelClient):
        def execute(self, code: str) -> int:
            return 0

        def cancel(self, request_id: int) -> None:
            return None

        def shutdown(self) -> None:
            return None

    p = ToolboxPanel(KernelBridge(NoList()))
    assert p.tree.topLevelItemCount() == 0
    assert "not available" in p.status.text()
    p.deleteLater()


def test_main_window_integration():
    win = MainWindow(UiSettings(None), StubKernelClient())
    try:
        panel = win.docks["toolboxes"].widget()
        assert isinstance(panel, ToolboxPanel)
        assert panel.tree.topLevelItemCount() == len(SAMPLE_TOOLBOXES)
        panel.tree.itemDoubleClicked.emit(functions(panel)["inv"], 0)
        assert win.command_window.input.text() == "inv"
    finally:
        win.tabs.current_editor().document().setModified(False)
        win.close()
        win.deleteLater()
