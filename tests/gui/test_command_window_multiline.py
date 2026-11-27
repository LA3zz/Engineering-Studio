"""Command Window multi-line input (K3). Headless (offscreen); skipped without PySide6."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from engstudio.app.kernel.client import KernelClient  # noqa: E402
from engstudio.app.kernel.inprocess import InProcessKernelClient  # noqa: E402
from engstudio.app.kernel.protocol import ExecutionFinished  # noqa: E402
from engstudio.gui.command_window import CommandWindow  # noqa: E402
from engstudio.gui.kernel_bridge import KernelBridge  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class Recorder(KernelClient):
    """Records the code it is asked to run."""

    def __init__(self) -> None:
        super().__init__()
        self.codes: list[str] = []

    def execute(self, code: str, file: str | None = None) -> int:
        self.codes.append(code)
        self._emit(ExecutionFinished(len(self.codes), "ok"))
        return len(self.codes)

    def cancel(self, request_id: int) -> None:
        pass

    def shutdown(self) -> None:
        pass


@pytest.fixture
def rec(qapp):
    client = Recorder()
    w = CommandWindow(KernelBridge(client))
    w.show()
    yield w, client
    w.close()
    w.deleteLater()


def type_line(w, text):
    w.input.setText(text)
    w.submit()


def test_block_waits_for_end_then_runs_once(rec):
    w, client = rec
    type_line(w, "for i = 1:3")
    assert client.codes == [] and w.prompt.text() == "..." and w.pending_lines == ("for i = 1:3",)
    type_line(w, "  disp(i)")
    assert client.codes == []
    type_line(w, "end")
    assert client.codes == ["for i = 1:3\n  disp(i)\nend"]
    assert w.prompt.text() == ">>" and w.pending_lines == ()
    out = w.output.toPlainText()
    assert ">> for i = 1:3" in out and ".. " in out


def test_single_line_still_runs_immediately(rec):
    w, client = rec
    type_line(w, "x = 5;")
    assert client.codes == ["x = 5;"] and w.pending_lines == ()


def test_one_line_block_and_open_bracket_and_continuation(rec):
    w, client = rec
    type_line(w, "for i=1:2, disp(i), end")
    assert client.codes == ["for i=1:2, disp(i), end"]
    type_line(w, "A = [1 2")
    assert len(client.codes) == 1 and w.prompt.text() == "..."
    type_line(w, "3 4];")
    assert client.codes[-1] == "A = [1 2\n3 4];"
    type_line(w, "y = 1 + ...")
    assert len(client.codes) == 2
    type_line(w, "2;")
    assert client.codes[-1] == "y = 1 + ...\n2;"


def test_blank_line_inside_a_block_is_kept(rec):
    w, client = rec
    type_line(w, "if true")
    type_line(w, "")
    type_line(w, "end")
    assert client.codes == ["if true\n\nend"]


def test_blank_line_without_block_is_ignored(rec):
    w, client = rec
    type_line(w, "   ")
    assert client.codes == [] and w.output.toPlainText() == ""


def test_escape_cancels_the_block(rec):
    w, client = rec
    type_line(w, "while true")
    w.input.setText("partial")
    QTest.keyClick(w.input, Qt.Key.Key_Escape)
    assert w.input.text() == "" and w.pending_lines == () and w.prompt.text() == ">>"
    assert "Input cancelled." in w.output.toPlainText()
    type_line(w, "x = 1;")
    assert client.codes == ["x = 1;"]


def test_history_holds_each_typed_line(rec):
    w, _ = rec
    type_line(w, "if true")
    type_line(w, "disp(1)")
    type_line(w, "end")
    assert w.history.items() == ["if true", "disp(1)", "end"]


def test_paste_block_runs_at_once_even_if_incomplete(rec):
    w, client = rec
    w.paste_block("a = 1;\r\nb = 2;\n\n")
    assert client.codes == ["a = 1;\nb = 2;"] and w.pending_lines == ()
    w.paste_block("\n\nfor i=1:2\n  disp(i)\n")  # no end: the parser will report it
    assert client.codes[-1] == "for i=1:2\n  disp(i)"
    assert w.history.items()[-2:] == ["for i=1:2", "  disp(i)"]


def test_paste_block_prepends_typed_text_and_ignores_empty(rec):
    w, client = rec
    w.input.setText("x = ")
    w.paste_block("1;\ny = 2;")
    assert client.codes == ["x = 1;\ny = 2;"] and w.input.text() == ""
    w.paste_block("\n \n")
    assert len(client.codes) == 1


def test_ctrl_v_with_multiline_clipboard_runs_a_block(rec):
    w, client = rec
    QGuiApplication.clipboard().setText("p = 1;\nq = 2;\n")
    w.input.setFocus()
    QTest.keyClick(w.input, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert client.codes == ["p = 1;\nq = 2;"]


def test_ctrl_v_with_single_line_pastes_normally(rec):
    w, client = rec
    QGuiApplication.clipboard().setText("abc")
    w.input.setFocus()
    QTest.keyClick(w.input, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert w.input.text() == "abc" and client.codes == []


def test_no_kernel_paste_is_ignored(qapp):
    w = CommandWindow(None)
    w.paste_block("a = 1;\nb = 2;")
    assert w.output.toPlainText() == "" and w.pending_lines == ()


def test_real_kernel_runs_a_typed_loop(qapp):
    client = InProcessKernelClient(threaded=False)
    w = CommandWindow(KernelBridge(client))
    for line in ("s = 0;", "for i = 1:4", "  s = s + i;", "end", "disp(s)"):
        type_line(w, line)
    assert "10" in w.output.toPlainText().split("disp(s)")[-1]
    w.deleteLater()
