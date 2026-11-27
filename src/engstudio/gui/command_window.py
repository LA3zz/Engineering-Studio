"""Command Window: input line with history, output area, errors in colour.

Talks only to a ``KernelBridge`` (never to the engine). ``clc`` is handled locally.
Input is a single line for now; multi-line execution arrives with script running.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from engstudio.app.input_state import needs_more
from engstudio.app.kernel.protocol import Diagnostics, Stdout
from engstudio.core.errors import EngStudioError
from engstudio.gui.history import CommandHistory
from engstudio.gui.kernel_bridge import KernelBridge

__all__ = ["CommandWindow"]

MAX_OUTPUT_BLOCKS = 20000


class _InputLine(QLineEdit):
    cancelled = Signal()
    block_pasted = Signal(str)

    def __init__(self, history: CommandHistory) -> None:
        super().__init__()
        self._history = history

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        if key == Qt.Key.Key_Up:
            text = self._history.previous(self.text())
            if text is not None:
                self.setText(text)
            event.accept()
        elif key == Qt.Key.Key_Down:
            text = self._history.next()
            if text is not None:
                self.setText(text)
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self.clear()
            self._history.reset()
            self.cancelled.emit()
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Paste) and self._paste_multiline():
            event.accept()
        else:
            super().keyPressEvent(event)

    def _paste_multiline(self) -> bool:
        """Multi-line clipboard text runs as a block; one line pastes as usual."""
        body = QGuiApplication.clipboard().text().replace("\r\n", "\n").replace(
            "\r", "\n").strip("\n")
        if "\n" not in body:
            return False
        self.block_pasted.emit(body)
        return True


class CommandWindow(QWidget):
    def __init__(
        self,
        bridge: KernelBridge | None,
        history_items: Iterable[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.history = CommandHistory(history_items)
        self._pending: list[str] = []

        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(10)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(mono)
        self.output.setMaximumBlockCount(MAX_OUTPUT_BLOCKS)

        self.prompt = QLabel(">>")
        self.prompt.setFont(mono)
        self.input = _InputLine(self.history)
        self.input.setFont(mono)
        self.run_button = QPushButton("Run")

        row = QHBoxLayout()
        row.addWidget(self.prompt)
        row.addWidget(self.input, 1)
        row.addWidget(self.run_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.output, 1)
        layout.addLayout(row)
        self.setMinimumSize(200, 100)

        self.input.returnPressed.connect(self.submit)
        self.input.cancelled.connect(self.cancel_pending)
        self.input.block_pasted.connect(self.paste_block)
        self.run_button.clicked.connect(lambda _checked=False: self.submit())
        if bridge is None:
            self.input.setEnabled(False)
            self.run_button.setEnabled(False)
            self.input.setPlaceholderText("No kernel connected")
        else:
            bridge.event.connect(self._on_event)

    # -- public ----------------------------------------------------------------
    def focus_input(self) -> None:
        self.input.setFocus()

    def clear_output(self) -> None:
        self.output.clear()

    def echo(self, text: str) -> None:
        """Append a line in the input colour (used to announce script runs)."""
        line = text if text.endswith("\n") else text + "\n"
        self._append(line, self._fmt("link"))

    @property
    def pending_lines(self) -> tuple[str, ...]:
        """Lines of an unfinished block waiting for more input (empty when none)."""
        return tuple(self._pending)

    def submit(self) -> None:
        text = self.input.text()
        if self.bridge is None or (not text.strip() and not self._pending):
            return
        if text.strip():
            self.history.add(text)
        self.input.clear()
        if not self._pending and text.strip() == "clc":
            self.clear_output()
            return
        self._append(f"{'..' if self._pending else '>>'} {text}\n", self._fmt("link"))
        self._pending.append(text)
        if needs_more("\n".join(self._pending)):
            self._set_prompt(continuing=True)
            return
        self._run_pending()

    def paste_block(self, text: str) -> None:
        """Run multi-line text (a paste) as one block, complete or not."""
        if self.bridge is None:
            return
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return
        lines[0] = self.input.text() + lines[0]
        self.input.clear()
        for i, line in enumerate(lines):
            if line.strip():
                self.history.add(line)
            self._append(f"{'..' if i or self._pending else '>>'} {line}\n", self._fmt("link"))
        self._pending.extend(lines)
        self._run_pending()

    def cancel_pending(self) -> None:
        """Discard an unfinished block (Escape)."""
        if not self._pending:
            return
        self._pending.clear()
        self._set_prompt(continuing=False)
        self._append("Input cancelled.\n", self._fmt("text"))

    def _set_prompt(self, continuing: bool) -> None:
        self.prompt.setText("..." if continuing else ">>")

    def _run_pending(self) -> None:
        code = "\n".join(self._pending)
        self._pending.clear()
        self._set_prompt(continuing=False)
        try:
            self.bridge.execute(code)  # type: ignore[union-attr]
        except EngStudioError as exc:
            self._append(f"Error: {exc}\n", self._fmt("error"))

    # -- events ----------------------------------------------------------------
    def _on_event(self, event: object) -> None:
        if isinstance(event, Stdout):
            self._append(event.text, self._fmt("text"))
        elif isinstance(event, Diagnostics):
            for d in event.items:
                kind = {"error": "Error", "warning": "Warning"}.get(d.severity, "Info")
                role = d.severity if d.severity in ("error", "warning") else "text"
                self._append(f"{kind}: {d.message} [{d.code}]\n", self._fmt(role))

    # -- output helpers ----------------------------------------------------------
    def _fmt(self, role: str) -> QTextCharFormat:
        pal = self.palette()
        dark = pal.color(QPalette.ColorRole.Base).lightness() < 128
        colors = {
            "text": pal.color(QPalette.ColorRole.Text),
            "link": pal.color(QPalette.ColorRole.Link),
            "error": QColor("#ff6b6b" if dark else "#b42318"),
            "warning": QColor("#e0a030" if dark else "#8a5a00"),
        }
        fmt = QTextCharFormat()
        fmt.setForeground(colors[role])
        return fmt

    def _append(self, text: str, fmt: QTextCharFormat) -> None:
        bar = self.output.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2
        cursor = QTextCursor(self.output.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        if at_bottom:
            bar.setValue(bar.maximum())
