"""K2: Run / Run Selection / Stop, running-state tracking, click-to-line, docs.

Exact-match edits of gui/main_window.py, gui/command_window.py, app/kernel/client.py and
app/kernel/stub.py (idempotent). Run at the project root.
"""
from pathlib import Path

ROOT = Path(".")
SRC = ROOT / "src" / "engstudio"
D = ROOT / "docs" / "project"

MAIN_METHODS = '''    def _on_kernel_event(self, event: object) -> None:
        if isinstance(event, FigureUpdate):
            self.show_figure(event.figure)
        elif isinstance(event, ExecutionFinished):
            text = {"ok": "Done", "error": "Finished with errors", "cancelled": "Stopped"}
            self.statusBar().showMessage(text.get(event.status, "Done"), 4000)

    # -- running code -------------------------------------------------------------
    def run_script(self) -> None:
        """Run the text of the current script tab (unsaved edits included)."""
        editor = self.tabs.current_editor()
        if editor is None:
            self.statusBar().showMessage("No script to run", 3000)
            return
        self._run_text(editor.toPlainText(), self._file_id(editor), editor.display_name)

    def run_selection(self) -> None:
        """Run the selected text, or the current line when nothing is selected.

        The code is padded with blank lines (and spaces) so that line and column numbers in
        diagnostics match the editor.
        """
        editor = self.tabs.current_editor()
        if editor is None:
            self.statusBar().showMessage("No script to run", 3000)
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            start = min(cursor.anchor(), cursor.position())
            block = editor.document().findBlock(start)
            text = cursor.selection().toPlainText()
            prefix = "\\n" * block.blockNumber() + " " * (start - block.position())
        else:
            block = cursor.block()
            text = block.text()
            prefix = "\\n" * block.blockNumber()
        if not text.strip():
            self.statusBar().showMessage("Nothing to run", 3000)
            return
        self._run_text(prefix + text, self._file_id(editor), f"{editor.display_name} (selection)")

    def stop_execution(self) -> None:
        if self.bridge is not None:
            self.bridge.cancel_running()
            self.statusBar().showMessage("Stopping...", 3000)

    @staticmethod
    def _file_id(editor) -> str:
        return str(editor.path) if editor.path else editor.untitled_name

    def _run_text(self, code: str, file_id: str, label: str) -> None:
        if self.bridge is None:
            self.statusBar().showMessage("No kernel connected", 3000)
            return
        if self.command_window is not None:
            self.docks["command"].show()
            self.command_window.echo(f">> run {label}")
        self.statusBar().showMessage(f"Running {label}...")
        try:
            self.bridge.execute(code, file_id)
        except EngStudioError as exc:
            self.statusBar().showMessage(f"Cannot run: {exc}", 5000)

    def _on_running_changed(self, running: bool) -> None:
        self.act_stop.setEnabled(running)
        self.act_run.setEnabled(not running)
        self.act_run_selection.setEnabled(not running)

    def _find_editor(self, file_id: str):
        for i in range(self.tabs.count()):
            editor = self.tabs.editor(i)
            if editor is None:
                continue
            if editor.path is not None and str(editor.path) == file_id:
                return editor
            if editor.path is None and editor.untitled_name == file_id:
                return editor
        return None

    def _open_location(self, file: object, line: int, col: int) -> None:
        """Show ``line``/``col`` of a script (opens the file when it is not open yet)."""
        if file is None:
            return  # the error came from a Command Window line: there is nothing to open
        file_id = str(file)
        editor = self._find_editor(file_id)
        if editor is None and Path(file_id).is_file():
            self.tabs.open_path(file_id)
            editor = self._find_editor(str(Path(file_id).resolve()))
        if editor is None:
            return
        self.tabs.setCurrentWidget(editor)
        block = editor.document().findBlockByNumber(max(line - 1, 0))
        if not block.isValid():  # a line past the end: go to the last line
            block = editor.document().lastBlock()
        column = min(max(col - 1, 0), max(block.length() - 1, 0))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + column)
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        editor.setFocus()
'''

EDITS = {
    SRC / "gui" / "main_window.py": [
        ("from PySide6.QtGui import QAction, QActionGroup, QKeySequence\n",
         "from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QTextCursor\n"),
        ("from engstudio.app.kernel.protocol import FigureUpdate\n",
         "from engstudio.app.kernel.protocol import ExecutionFinished, FigureUpdate\n"),
        ("from engstudio.gui.command_window import CommandWindow\n",
         "from engstudio.core.errors import EngStudioError\n"
         "from engstudio.gui.command_window import CommandWindow\n"),
        ("        if self.bridge is not None:\n"
         "            self.bridge.event.connect(self._on_kernel_event)\n",
         "        if self.bridge is not None:\n"
         "            self.bridge.event.connect(self._on_kernel_event)\n"
         "            self.bridge.running_changed.connect(self._on_running_changed)\n"),
        ("        self.diagnostics_panel = (\n"
         "            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None\n"
         "        )\n",
         "        self.diagnostics_panel = (\n"
         "            diagnostics if isinstance(diagnostics, DiagnosticsPanel) else None\n"
         "        )\n"
         "        if self.diagnostics_panel is not None:\n"
         "            self.diagnostics_panel.location_activated.connect(self._open_location)\n"),
        ('        self.act_customize = self._action("&Customize...", self.customize_theme,\n'
         '                                          tip="Edit colours and save custom themes")\n',
         '        self.act_customize = self._action("&Customize...", self.customize_theme,\n'
         '                                          tip="Edit colours and save custom themes")\n'
         '        self.act_run = self._action("&Run Script", self.run_script, "F5",\n'
         '                                    P.SP_MediaPlay, tip="Run the current script")\n'
         '        self.act_run_selection = self._action(\n'
         '            "Run &Selection or Line", self.run_selection, "F9",\n'
         '            tip="Run the selected text, or the current line")\n'
         '        self.act_stop = self._action("S&top", self.stop_execution, "Shift+F5",\n'
         '                                     P.SP_MediaStop, tip="Stop the running code")\n'
         '        self.act_stop.setEnabled(False)\n'),
        ('        mb.addMenu("&Help").addAction(self.act_about)\n',
         '        run = mb.addMenu("&Run")\n'
         '        run.addActions([self.act_run, self.act_run_selection, self.act_stop])\n\n'
         '        mb.addMenu("&Help").addAction(self.act_about)\n'),
        ("        tb.addActions([self.act_new, self.act_open, self.act_save])\n"
         "        tb.addSeparator()\n",
         "        tb.addActions([self.act_new, self.act_open, self.act_save])\n"
         "        tb.addSeparator()\n"
         "        tb.addActions([self.act_run, self.act_stop])\n"
         "        tb.addSeparator()\n"),
        ("    def _on_kernel_event(self, event: object) -> None:\n"
         "        if isinstance(event, FigureUpdate):\n"
         "            self.show_figure(event.figure)\n",
         MAIN_METHODS),
    ],
    SRC / "gui" / "command_window.py": [
        ("    def clear_output(self) -> None:\n        self.output.clear()\n",
         "    def clear_output(self) -> None:\n        self.output.clear()\n\n"
         "    def echo(self, text: str) -> None:\n"
         '        """Append a line in the input colour (used to announce script runs)."""\n'
         '        line = text if text.endswith("\\n") else text + "\\n"\n'
         '        self._append(line, self._fmt("link"))\n'),
    ],
    SRC / "app" / "kernel" / "client.py": [
        ("    @abstractmethod\n    def execute(self, code: str) -> int:\n"
         '        """Run ``code``; returns the request id used in all resulting events."""\n',
         "    @abstractmethod\n    def execute(self, code: str, file: str | None = None) -> int:\n"
         '        """Run ``code``; returns the request id used in all resulting events.\n\n'
         "        ``file`` names the source (used as the file of diagnostic locations).\n"
         '        """\n'),
    ],
    SRC / "app" / "kernel" / "stub.py": [
        ("    def execute(self, code: str) -> int:\n",
         "    def execute(self, code: str, file: str | None = None) -> int:\n"),
        ("                loc = SourceLoc(None, lineno, 1)\n",
         "                loc = SourceLoc(file, lineno, 1)\n"),
    ],
    D / "TASKS.md": [
        ("eig, lu, qr, chol, svd (pending user run)",
         "eig, lu, qr, chol, svd (verified 2026-11-22)"),
        ("- [ ] K2 Run/F5 for the script editor, multi-line Command Window input, "
         "diagnostics click-to-line (needs main_window.py and the editor file)",
         "- [x] K2 Run Script (F5), Run Selection or Line (F9), Stop (Shift+F5), Run menu and "
         "toolbar, running-state tracking in KernelBridge, diagnostics double-click opens the "
         "line in the editor (pending user run)\n"
         "- [ ] K3 multi-line input in the Command Window (optional; needs a design decision "
         "because tests use the single-line input API)"),
    ],
    D / "HANDOFF.md": [
        ("Next in that series: K2 (Run/F5 in the script editor, multi-line Command Window "
         "input, Stop, diagnostics click-to-line; main_window.py is known, still needed: "
         "gui/editor_tabs.py and gui/diagnostics_panel.py), then B1b (strings, "
         "struct/cell, cellfun/arrayfun, random, tic/toc) and B2b (remaining engine "
         "bindings; attach the engine files).",
         "K2 done: `KernelClient.execute(code, file=None)` (file names the source in diagnostic "
         "locations); `KernelBridge` tracks pending requests (`running`, `running_changed`, "
         "`cancel_running()`); MainWindow has Run Script F5 (runs the editor text, unsaved "
         "edits included, file id = path or the untitled name), Run Selection or Line F9 "
         "(padded with blank lines/spaces so locations match the editor), Stop Shift+F5, a Run "
         "menu, toolbar buttons, and double-click on a located diagnostic opens that line "
         "(Command Window errors have no file and are ignored); CommandWindow.echo(). "
         "Command Window input is still one line. Next in that series: B1b (strings, "
         "struct/cell, cellfun/arrayfun, random, tic/toc) and B2b (remaining engine "
         "bindings; attach the engine files)."),
    ],
}
for path, pairs in EDITS.items():
    with open(path, newline="", encoding="utf-8") as fh:
        text = fh.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            print(f"{path.name}: already applied")
        elif old in text:
            text = text.replace(old, new, 1)
            print(f"{path.name}: patched")
        else:
            raise SystemExit(f"{path}: expected text not found: {old[:70]!r}")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)
