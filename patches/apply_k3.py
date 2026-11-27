"""Apply K3: multi-line Command Window input (continuation prompt, Esc cancel, block paste)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "docs" / "project"

QTGUI_OLD = (
    "from PySide6.QtGui import QColor, QFontDatabase, QPalette, QTextCharFormat, "
    "QTextCursor\n"
)
QTGUI_NEW = (
    "from PySide6.QtGui import (\n    QColor,\n    QFontDatabase,\n    QGuiApplication,\n"
    "    QKeySequence,\n    QPalette,\n    QTextCharFormat,\n    QTextCursor,\n)\n"
)
KEYS_OLD = (
    "        elif key == Qt.Key.Key_Escape:\n"
    "            self.clear()\n"
    "            self._history.reset()\n"
    "            event.accept()\n"
    "        else:\n"
    "            super().keyPressEvent(event)\n"
)
KEYS_NEW = (
    "        elif key == Qt.Key.Key_Escape:\n"
    "            self.clear()\n"
    "            self._history.reset()\n"
    "            self.cancelled.emit()\n"
    "            event.accept()\n"
    "        elif event.matches(QKeySequence.StandardKey.Paste) and self._paste_multiline():\n"
    "            event.accept()\n"
    "        else:\n"
    "            super().keyPressEvent(event)\n"
    "\n"
    "    def _paste_multiline(self) -> bool:\n"
    "        \"\"\"Multi-line clipboard text runs as a block; one line pastes as usual.\"\"\"\n"
    "        body = QGuiApplication.clipboard().text().replace(\"\\r\\n\", \"\\n\").replace(\n"
    "            \"\\r\", \"\\n\").strip(\"\\n\")\n"
    "        if \"\\n\" not in body:\n"
    "            return False\n"
    "        self.block_pasted.emit(body)\n"
    "        return True\n"
)
SUBMIT_OLD = (
    "    def submit(self) -> None:\n"
    "        text = self.input.text()\n"
    "        if self.bridge is None or not text.strip():\n"
    "            return\n"
    "        self.history.add(text)\n"
    "        self.input.clear()\n"
    "        if text.strip() == \"clc\":\n"
    "            self.clear_output()\n"
    "            return\n"
    "        self._append(f\">> {text}\\n\", self._fmt(\"link\"))\n"
    "        try:\n"
    "            self.bridge.execute(text)\n"
    "        except EngStudioError as exc:\n"
    "            self._append(f\"Error: {exc}\\n\", self._fmt(\"error\"))\n"
)
SUBMIT_NEW = '''    @property
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
        self._append(f"{'..' if self._pending else '>>'} {text}\\n", self._fmt("link"))
        self._pending.append(text)
        if needs_more("\\n".join(self._pending)):
            self._set_prompt(continuing=True)
            return
        self._run_pending()

    def paste_block(self, text: str) -> None:
        """Run multi-line text (a paste) as one block, complete or not."""
        if self.bridge is None:
            return
        lines = text.replace("\\r\\n", "\\n").replace("\\r", "\\n").split("\\n")
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
            self._append(f"{'..' if i or self._pending else '>>'} {line}\\n", self._fmt("link"))
        self._pending.extend(lines)
        self._run_pending()

    def cancel_pending(self) -> None:
        """Discard an unfinished block (Escape)."""
        if not self._pending:
            return
        self._pending.clear()
        self._set_prompt(continuing=False)
        self._append("Input cancelled.\\n", self._fmt("text"))

    def _set_prompt(self, continuing: bool) -> None:
        self.prompt.setText("..." if continuing else ">>")

    def _run_pending(self) -> None:
        code = "\\n".join(self._pending)
        self._pending.clear()
        self._set_prompt(continuing=False)
        try:
            self.bridge.execute(code)  # type: ignore[union-attr]
        except EngStudioError as exc:
            self._append(f"Error: {exc}\\n", self._fmt("error"))
'''


def read(path: Path) -> str:
    with open(path, newline="", encoding="utf-8") as fh:
        return fh.read()


def edit(path: Path, pairs: list) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    changed = False
    for old, new in pairs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"{path.name}: expected exactly one match for:\n{old}")
        text = text.replace(old, new)
        changed = True
    if changed:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            fh.write(text)
    print(("patched: " if changed else "already patched: ") + path.name)


def append(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        print(f"SKIP (missing): {path}")
        return
    text = read(path)
    if marker in text:
        print(f"already patched: {path.name}")
        return
    nl = "\r\n" if "\r\n" in text else "\n"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text.rstrip() + nl + nl + block.replace("\n", nl) + nl)
    print(f"patched: {path.name}")


edit(ROOT / "src/engstudio/gui/command_window.py", [
    ("from PySide6.QtCore import Qt\n", "from PySide6.QtCore import Qt, Signal\n"),
    (QTGUI_OLD, QTGUI_NEW),
    ("from engstudio.app.kernel.protocol import Diagnostics, Stdout\n",
     "from engstudio.app.input_state import needs_more\n"
     "from engstudio.app.kernel.protocol import Diagnostics, Stdout\n"),
    ("class _InputLine(QLineEdit):\n    def __init__",
     "class _InputLine(QLineEdit):\n    cancelled = Signal()\n    block_pasted = Signal(str)\n\n"
     "    def __init__"),
    (KEYS_OLD, KEYS_NEW),
    ("        self.history = CommandHistory(history_items)\n",
     "        self.history = CommandHistory(history_items)\n"
     "        self._pending: list[str] = []\n"),
    ('        prompt = QLabel(">>")\n        prompt.setFont(mono)\n',
     '        self.prompt = QLabel(">>")\n        self.prompt.setFont(mono)\n'),
    ("        row.addWidget(prompt)\n", "        row.addWidget(self.prompt)\n"),
    ("        self.input.returnPressed.connect(self.submit)\n",
     "        self.input.returnPressed.connect(self.submit)\n"
     "        self.input.cancelled.connect(self.cancel_pending)\n"
     "        self.input.block_pasted.connect(self.paste_block)\n"),
    (SUBMIT_OLD, SUBMIT_NEW),
])
edit(D / "TASKS.md", [
    ("- [ ] K3 multi-line input in the Command Window (optional; needs a design decision "
     "because tests use the single-line input API)",
     "- [x] K3 multi-line Command Window input: continuation prompt `...`, Esc cancels, "
     "multi-line paste runs as a block (`app.input_state.needs_more`) (pending user run)"),
])
append(D / "CHANGELOG.md",
       "## K3 (2026-11-25)\n- Command Window: unfinished blocks/brackets/`...` continue on "
       "the next line (prompt `...`), Esc cancels, multi-line paste (Ctrl+V) runs as one block; "
       "`app.input_state.needs_more`. The single-line input API is unchanged.",
       "## K3 (2026-11-25)")
append(D / "TEST_STATUS.md",
       "## K3 (2026-11-25)\n- tests/app/test_input_state.py, "
       "tests/gui/test_command_window_multiline.py: PENDING user run.", "## K3 (2026-11-25)")
append(D / "HANDOFF.md",
       "## K3 (2026-11-25)\n- CommandWindow keeps `_pending` lines; `needs_more` (app.input_state) "
       "decides when a block is complete; `paste_block(text)` runs pasted text at once; Esc "
       "calls `cancel_pending`. Functions typed in the Command Window need their own `end`. "
       "Pending user run.", "## K3 (2026-11-25)")
