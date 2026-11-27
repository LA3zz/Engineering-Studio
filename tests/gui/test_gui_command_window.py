"""Command Window + kernel bridge tests. Headless (offscreen); skipped without PySide6."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.app.kernel.stub import StubKernelClient  # noqa: E402
from engstudio.core.errors import EngStudioError  # noqa: E402
from engstudio.gui.command_window import CommandWindow  # noqa: E402
from engstudio.gui.kernel_bridge import KernelBridge  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def cw(qapp):
    client = StubKernelClient()
    w = CommandWindow(KernelBridge(client))
    w.show()
    yield w
    w.close()
    w.deleteLater()


def run(cw, text):
    cw.input.setText(text)
    cw.submit()


def text_of(cw):
    return cw.output.toPlainText()


def test_bridge_forwards_events(qapp):
    client = StubKernelClient()
    bridge = KernelBridge(client)
    got = []
    bridge.event.connect(got.append)
    bridge.execute("x = 1;")
    assert [type(e).__name__ for e in got] == ["WorkspaceSummary", "ExecutionFinished"]
    bridge.shutdown()
    bridge.shutdown()  # idempotent
    with pytest.raises(EngStudioError):
        bridge.execute("x = 2;")


def test_submit_shows_echo_and_output(cw):
    run(cw, "x = 5")
    out = text_of(cw)
    assert ">> x = 5" in out and "x =" in out and "5" in out
    assert cw.input.text() == ""
    assert cw.history.items() == ["x = 5"]


def test_semicolon_hides_output(cw):
    run(cw, "x = 5;")
    assert text_of(cw).strip() == ">> x = 5;"


def test_error_is_red(cw):
    run(cw, "y = x + 1")
    assert "Error:" in text_of(cw)
    cursor = cw.output.document().find("Error:")
    c = cursor.charFormat().foreground().color()
    assert c.red() > c.green() and c.red() > c.blue()


def test_clc_clears_output_but_keeps_history(cw):
    run(cw, "x = 5")
    run(cw, "clc")
    assert text_of(cw) == ""
    assert cw.history.items() == ["x = 5", "clc"]


def test_blank_input_ignored(cw):
    run(cw, "   ")
    assert text_of(cw) == "" and cw.history.items() == []


def test_enter_key_and_run_button(cw):
    cw.input.setText("a = 1;")
    QTest.keyClick(cw.input, Qt.Key.Key_Return)
    cw.input.setText("b = 2;")
    cw.run_button.click()
    assert cw.history.items() == ["a = 1;", "b = 2;"]


def test_history_keys(cw):
    run(cw, "a = 1;")
    run(cw, "b = 2;")
    cw.input.setText("typing")
    QTest.keyClick(cw.input, Qt.Key.Key_Up)
    assert cw.input.text() == "b = 2;"
    QTest.keyClick(cw.input, Qt.Key.Key_Up)
    assert cw.input.text() == "a = 1;"
    QTest.keyClick(cw.input, Qt.Key.Key_Down)
    assert cw.input.text() == "b = 2;"
    QTest.keyClick(cw.input, Qt.Key.Key_Down)
    assert cw.input.text() == "typing"
    QTest.keyClick(cw.input, Qt.Key.Key_Escape)
    assert cw.input.text() == ""


def test_no_kernel_disables_input(qapp):
    w = CommandWindow(None)
    assert not w.input.isEnabled() and not w.run_button.isEnabled()
    w.input.setText("x = 1")
    w.submit()
    assert w.output.toPlainText() == "" and w.history.items() == []


def test_shutdown_kernel_reports_error_without_crashing(qapp):
    bridge = KernelBridge(StubKernelClient())
    w = CommandWindow(bridge)
    bridge.shutdown()
    run(w, "x = 1")
    assert "Error:" in w.output.toPlainText()


def test_output_is_bounded(cw):
    assert 0 < cw.output.maximumBlockCount() <= 100000


def test_main_window_integration_and_history_persistence(qapp):
    settings = UiSettings(None)
    client = StubKernelClient()
    w1 = MainWindow(settings, client)
    w1.show()
    assert w1.command_window is not None
    w1.command_window.input.setText("q = 3;")
    w1.command_window.submit()
    w1.clear_command()
    assert w1.command_window.output.toPlainText() == ""
    w1.close()
    assert settings.get("command_history") == ["q = 3;"]
    with pytest.raises(EngStudioError):
        client.execute("x = 1;")  # window shut the client down on close
    w2 = MainWindow(settings, StubKernelClient())
    assert w2.command_window.history.items() == ["q = 3;"]
    w2.close()


def test_main_window_without_kernel_still_works(qapp):
    w = MainWindow(UiSettings(None))
    w.show()
    assert w.command_window is not None and not w.command_window.input.isEnabled()
    w.close()
