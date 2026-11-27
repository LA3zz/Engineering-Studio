"""G4 patch: syntax highlighting in editor_tabs.py and theme switching in main_window.py
(exact-match, idempotent). Run from the project root: python patches\\apply_g4_patch.py"""

from __future__ import annotations

import sys
from pathlib import Path

GUI = Path(sys.argv[1] if len(sys.argv) > 1 else "src/engstudio/gui")

_QT_WIDGETS_IMPORT = (
    "from PySide6.QtWidgets import "
    "QFileDialog, QMessageBox, QPlainTextEdit, QTabWidget, QWidget\n"
)
_INIT_SIG = 'path: Path | None = None, untitled_name: str = "untitled.m"'
_INIT_OLD = f"    def __init__(self, {_INIT_SIG}) -> None:\n"
_INIT_NEW = f'    def __init__(\n        self, {_INIT_SIG}, theme: str = "light"\n    ) -> None:\n'

EDITOR = [
    ('"""Tabbed script editor (plain text for now; syntax highlighting arrives in G4)."""\n',
     '"""Tabbed script editor with syntax highlighting."""\n'),
    (_QT_WIDGETS_IMPORT,
     _QT_WIDGETS_IMPORT + "\nfrom engstudio.gui.highlighter import ScriptHighlighter\n"),
    (_INIT_OLD, _INIT_NEW),
    ('        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)\n',
     '        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)\n'
     "        self.highlighter = ScriptHighlighter(self.document(), theme)\n"),
    ("        self._counter = 0\n",
     "        self._counter = 0\n        self._theme = \"light\"\n"),
    ("        return self._add(ScriptEditor(None, name))\n",
     "        return self._add(ScriptEditor(None, name, self._theme))\n"),
    ("            editor = self._add(ScriptEditor(path))\n",
     "            editor = self._add(ScriptEditor(path, theme=self._theme))\n"),
    ("    def _refresh(self, editor: ScriptEditor) -> None:\n",
     "    def set_theme(self, name: str) -> None:\n"
     '        """Re-colour syntax highlighting in every open script and in future ones."""\n'
     "        self._theme = name\n"
     "        for i in range(self.count()):\n"
     "            e = self.editor(i)\n"
     "            if e is not None:\n"
     "                e.highlighter.set_theme(name)\n\n"
     "    def _refresh(self, editor: ScriptEditor) -> None:\n"),
]
MAIN = [
    ("        self.theme = name\n        self._theme_actions[name].setChecked(True)\n",
     "        self.theme = name\n        self.tabs.set_theme(name)\n"
     "        self._theme_actions[name].setChecked(True)\n"),
]


def patch(name: str, edits: list[tuple[str, str]]) -> None:
    path = GUI / name
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in edits:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if new in text:
            continue  # already applied
        if text.count(old) != 1:
            sys.exit(f"{name}: expected text not found exactly once:\n{old}")
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {name}")


patch("editor_tabs.py", EDITOR)
patch("main_window.py", MAIN)
