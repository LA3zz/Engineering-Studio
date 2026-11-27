"""Workspace panel Save.../Load... buttons send save/load to the kernel."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.app.kernel.protocol import VariableInfo, WorkspaceSummary  # noqa: E402
from engstudio.gui.workspace_panel import WorkspacePanel  # noqa: E402


class FakeBridge(QObject):
    event = Signal(object)

    def __init__(self):
        super().__init__()
        self.sent: list[str] = []

    def execute(self, code: str) -> int:
        self.sent.append(code)
        return len(self.sent)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_save_and_load_buttons(app, qtbot):
    bridge = FakeBridge()
    p = WorkspacePanel(bridge)
    qtbot.addWidget(p)
    assert not p.save_button.isEnabled()  # nothing to save yet
    bridge.event.emit(WorkspaceSummary(1, (VariableInfo("a", "double", (1, 1), "1"),
                                           VariableInfo("b", "double", (1, 1), "2"))))
    assert p.save_button.isEnabled() and p.load_button.isEnabled()
    p.save_workspace(r"C:\data\it's.mat")
    assert bridge.sent[-1] == r"save('C:\data\it''s.mat')"
    p.view.selectRow(0)
    p.save_workspace("x.mat")
    assert bridge.sent[-1] == "save('x.mat', 'a')"
    p.load_workspace("y.mat")
    assert bridge.sent[-1] == "load('y.mat')"
