"""GUI tests for K2: Run Script (F5), Run Selection or Line (F9), Stop (Shift+F5), running-state
tracking in KernelBridge and double-click-to-line from the Diagnostics panel.

Headless (offscreen); the window uses the in-process kernel: synchronous for exact assertions,
threaded for the Stop test.
"""

import contextlib
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from engstudio.app.kernel.inprocess import InProcessKernelClient
from engstudio.app.kernel.protocol import Diagnostics
from engstudio.app.kernel.stub import StubKernelClient
from engstudio.gui.kernel_bridge import KernelBridge
from engstudio.gui.main_window import MainWindow
from engstudio.gui.settings import UiSettings


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _pump(app, condition, timeout=20.0):
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, "timed out waiting for the GUI"
        app.processEvents()
        time.sleep(0.005)


@contextlib.contextmanager
def make_window(threaded=False):
    app = _app()
    client = InProcessKernelClient(threaded=threaded)
    window = MainWindow(UiSettings(None), client)
    try:
        yield app, window, client
    finally:
        for i in range(window.tabs.count()):
            editor = window.tabs.editor(i)
            if editor is not None:
                editor.document().setModified(False)
        window.close()
        window.deleteLater()


def _select_block(editor, number):
    cursor = QTextCursor(editor.document().findBlockByNumber(number))
    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def _last_entry(window):
    entries = window.diagnostics_panel.visible_entries()
    assert entries, "no diagnostics were recorded"
    return entries[-1]


# ------------------------------------------------------------------------ run
def test_run_script_runs_the_editor_text_and_announces_it():
    with make_window() as (_app_, window, client):
        editor = window.tabs.current_editor()
        editor.setPlainText("x = 3 + 4;\ny = x * 2")
        window.run_script()
        output = window.command_window.output.toPlainText()
        assert ">> run untitled.m" in output and "y = 14" in output
        assert {"x", "y"} <= set(client._interp.workspace.names())
        assert "Done" in window.statusBar().currentMessage()


def test_run_selection_runs_the_selection_or_the_current_line():
    with make_window() as (_app_, window, client):
        editor = window.tabs.current_editor()
        editor.setPlainText("a = 1;\nb = 2;\nc = 3;")
        _select_block(editor, 1)
        window.run_selection()
        assert set(client._interp.workspace.names()) == {"b"}
        editor.setTextCursor(QTextCursor(editor.document().findBlockByNumber(2)))
        window.run_selection()
        assert set(client._interp.workspace.names()) == {"b", "c"}


def test_nothing_to_run_does_not_call_the_kernel():
    with make_window() as (_app_, window, client):
        editor = window.tabs.current_editor()
        editor.setPlainText("   \n\nx = 1;")
        window.run_selection()  # the cursor is on a blank line
        assert client._interp.workspace.names() == []
        assert "Nothing to run" in window.statusBar().currentMessage()


def test_diagnostic_locations_match_the_editor():
    with make_window() as (_app_, window, _client):
        editor = window.tabs.current_editor()
        editor.setPlainText("x = 1;\ny = [1 2] * [3 4];")
        window.run_script()
        entry = _last_entry(window)
        assert (entry.file, entry.line, entry.col) == ("untitled.m", 2, 11)
        _select_block(editor, 1)
        window.run_selection()
        entry = _last_entry(window)
        assert (entry.line, entry.col) == (2, 11)


def test_selection_in_the_middle_of_a_line_keeps_columns():
    with make_window() as (_app_, window, _client):
        editor = window.tabs.current_editor()
        editor.setPlainText("a = 1; b = [1 2] * [3 4];")
        cursor = editor.textCursor()
        cursor.setPosition(7)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        window.run_selection()
        entry = _last_entry(window)
        assert (entry.line, entry.col) == (1, 18)  # the '*' in the full line


def test_a_saved_script_reports_its_path():
    with make_window() as (_app_, window, _client), tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "demo.m"
        path.write_text("y = [1 2] * [3 4];\n", encoding="utf-8")
        assert window.tabs.open_path(path)
        window.run_script()
        entry = _last_entry(window)
        assert entry.file == str(window.tabs.current_editor().path) and entry.line == 1


# ------------------------------------------------------------- click-to-line
def test_double_click_target_selects_the_line_and_column():
    with make_window() as (_app_, window, _client):
        first = window.tabs.current_editor()
        first.setPlainText("one\ntwo three\nfour")
        window.tabs.new_script()
        assert window.tabs.current_editor() is not first
        window.diagnostics_panel.location_activated.emit("untitled.m", 2, 5)
        assert window.tabs.current_editor() is first
        cursor = first.textCursor()
        assert (cursor.blockNumber(), cursor.columnNumber()) == (1, 4)
        window.diagnostics_panel.location_activated.emit("untitled.m", 3, 99)
        assert (first.textCursor().blockNumber(), first.textCursor().columnNumber()) == (2, 4)
        window.diagnostics_panel.location_activated.emit("untitled.m", 99, 1)
        assert first.textCursor().blockNumber() == 2  # clamped to the last line


def test_unknown_or_missing_files_are_ignored():
    with make_window() as (_app_, window, _client):
        before = window.tabs.count()
        window.diagnostics_panel.location_activated.emit(None, 1, 1)
        window.diagnostics_panel.location_activated.emit("no_such_file.m", 1, 1)
        assert window.tabs.count() == before


def test_a_file_that_is_not_open_gets_opened():
    with make_window() as (_app_, window, _client), tempfile.TemporaryDirectory() as folder:
        path = (Path(folder) / "other.m").resolve()
        path.write_text("x = 1;\ny = 2;\n", encoding="utf-8")
        window.diagnostics_panel.location_activated.emit(str(path), 2, 1)
        editor = window.tabs.current_editor()
        assert editor.path == path and editor.textCursor().blockNumber() == 1


# ---------------------------------------------------------------- stop / state
def test_stop_cancels_a_running_loop_and_restores_the_buttons():
    with make_window(threaded=True) as (app, window, _client):
        window.tabs.current_editor().setPlainText("while 1, end")
        assert not window.act_stop.isEnabled() and window.act_run.isEnabled()
        window.run_script()
        _pump(app, lambda: window.act_stop.isEnabled())
        assert not window.act_run.isEnabled() and not window.act_run_selection.isEnabled()
        window.stop_execution()
        _pump(app, lambda: not window.act_stop.isEnabled())
        assert window.act_run.isEnabled() and window.act_run_selection.isEnabled()
        assert "Stopped" in window.statusBar().currentMessage()


def test_bridge_tracks_running_requests():
    app = _app()
    client = InProcessKernelClient(threaded=True)
    bridge = KernelBridge(client)
    states = []
    bridge.running_changed.connect(states.append)
    try:
        assert not bridge.running
        rid = bridge.execute("while 1, end")
        assert bridge.running and states == [True]
        bridge.cancel_running()
        _pump(app, lambda: not bridge.running)
        assert states == [True, False] and rid == 1
        bridge.execute("x = 1;")
        _pump(app, lambda: not bridge.running)
        assert states == [True, False, True, False]
    finally:
        bridge.shutdown()


def test_bridge_with_a_synchronous_client_never_reports_running():
    _app()
    bridge = KernelBridge(InProcessKernelClient(threaded=False))
    states = []
    bridge.running_changed.connect(states.append)
    try:
        bridge.execute("x = 1;")
        assert not bridge.running and states == []
    finally:
        bridge.shutdown()


def test_bridge_passes_the_file_name_to_the_kernel():
    _app()
    for client in (InProcessKernelClient(threaded=False), StubKernelClient()):
        bridge = KernelBridge(client)
        events = []
        bridge.event.connect(events.append)
        try:
            bridge.execute("this is not valid code(", "demo.m")
            diagnostics = [d for e in events if isinstance(e, Diagnostics) for d in e.items]
            assert diagnostics and diagnostics[0].location.file == "demo.m"
            bridge.execute("y = ;")  # without a file name the location has none
            diagnostics = [d for e in events if isinstance(e, Diagnostics) for d in e.items]
            assert diagnostics[-1].location.file is None
        finally:
            bridge.shutdown()


def test_command_window_echo_appends_a_line():
    with make_window() as (_app_, window, _client):
        window.command_window.echo(">> hello")
        window.command_window.echo("second\n")
        assert window.command_window.output.toPlainText().endswith(">> hello\nsecond\n")
