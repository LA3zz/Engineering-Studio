"""Tabbed script editor with syntax highlighting."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPlainTextEdit, QTabWidget, QWidget

from engstudio.gui.calltip import CallTipController
from engstudio.gui.highlighter import ScriptHighlighter

__all__ = ["ScriptEditor", "ScriptTabs"]

_FILTER = "Scripts (*.m);;All files (*)"


class ScriptEditor(QPlainTextEdit):
    def __init__(
        self, path: Path | None = None, untitled_name: str = "untitled.m", theme: str = "light"
    ) -> None:
        super().__init__()
        self.path = path
        self.untitled_name = untitled_name
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.highlighter = ScriptHighlighter(self.document(), theme)
        self.calltip = CallTipController(self)  # plot(x, -> shows what comes next

    @property
    def display_name(self) -> str:
        return self.path.name if self.path else self.untitled_name


class ScriptTabs(QTabWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self._counter = 0
        self._theme = "light"
        self.tabCloseRequested.connect(lambda i: self.close_tab(i))
        self.new_script()

    # -- access ------------------------------------------------------------
    def editor(self, index: int) -> ScriptEditor | None:
        w = self.widget(index)
        return w if isinstance(w, ScriptEditor) else None

    def current_editor(self) -> ScriptEditor | None:
        return self.editor(self.currentIndex())

    def set_theme(self, name: str) -> None:
        """Re-colour syntax highlighting in every open script and in future ones."""
        self._theme = name
        for i in range(self.count()):
            e = self.editor(i)
            if e is not None:
                e.highlighter.set_theme(name)

    def _refresh(self, editor: ScriptEditor) -> None:
        i = self.indexOf(editor)
        if i >= 0:
            mark = "*" if editor.document().isModified() else ""
            self.setTabText(i, editor.display_name + mark)
            self.setTabToolTip(i, str(editor.path) if editor.path else "")

    # -- create/open ---------------------------------------------------------
    def _add(self, editor: ScriptEditor) -> ScriptEditor:
        editor.document().modificationChanged.connect(lambda _m, e=editor: self._refresh(e))
        self.setCurrentIndex(self.addTab(editor, editor.display_name))
        self._refresh(editor)
        return editor

    def new_script(self) -> ScriptEditor:
        self._counter += 1
        name = "untitled.m" if self._counter == 1 else f"untitled{self._counter}.m"
        return self._add(ScriptEditor(None, name, self._theme))

    def open_path(self, path: Path | str) -> bool:
        path = Path(path).resolve()
        for i in range(self.count()):
            e = self.editor(i)
            if e and e.path == path:
                self.setCurrentIndex(i)
                return True
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.warning(self, "Open failed", f"Cannot open {path}:\n{exc}")
            return False
        cur = self.current_editor()
        if cur and cur.path is None and not cur.document().isModified() \
                and not cur.toPlainText():
            editor = cur  # reuse a pristine untitled tab
            editor.path = path
        else:
            editor = self._add(ScriptEditor(path, theme=self._theme))
        editor.setPlainText(text)
        editor.document().setModified(False)
        self._refresh(editor)
        return True

    # -- save ----------------------------------------------------------------
    def _write(self, editor: ScriptEditor, path: Path) -> bool:
        try:
            path.write_text(editor.toPlainText(), encoding="utf-8", newline="\n")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Cannot save {path}:\n{exc}")
            return False
        editor.path = path
        editor.document().setModified(False)
        self._refresh(editor)
        return True

    def save(self, index: int | None = None) -> bool:
        i = self.currentIndex() if index is None else index
        editor = self.editor(i)
        if editor is None:
            return False
        if editor.path is None:
            return self.save_as(i)
        return self._write(editor, editor.path)

    def save_as(self, index: int | None = None) -> bool:
        i = self.currentIndex() if index is None else index
        editor = self.editor(i)
        if editor is None:
            return False
        start = str(editor.path or Path.cwd() / editor.display_name)
        name, _ = QFileDialog.getSaveFileName(self, "Save script as", start, _FILTER)
        if not name:
            return False
        path = Path(name)
        if path.suffix == "":
            path = path.with_suffix(".m")
        return self._write(editor, path)

    # -- close ---------------------------------------------------------------
    def _resolve_unsaved(self, index: int) -> bool:
        """True if the tab may be discarded (saved, or user chose Discard)."""
        editor = self.editor(index)
        if editor is None or not editor.document().isModified():
            return True
        self.setCurrentIndex(index)
        B = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self, "Unsaved changes", f"Save changes to {editor.display_name}?",
            B.Save | B.Discard | B.Cancel, B.Save,
        )
        if answer == B.Cancel:
            return False
        if answer == B.Save:
            return self.save(index)
        return True

    def close_tab(self, index: int) -> bool:
        if not self._resolve_unsaved(index):
            return False
        w = self.widget(index)
        self.removeTab(index)
        if w is not None:
            w.deleteLater()
        return True

    def maybe_close_all(self) -> bool:
        return all(self._resolve_unsaved(i) for i in range(self.count()))

    # -- session -------------------------------------------------------------
    def session(self) -> dict[str, object]:
        """Open saved scripts (in tab order) and the current one, for the next start-up.
        Untitled scripts are not remembered."""
        paths = [str(e.path) for i in range(self.count())
                 if (e := self.editor(i)) is not None and e.path is not None]
        cur = self.current_editor()
        return {"paths": paths, "current": str(cur.path) if cur and cur.path else None}

    def restore_session(self, state: object) -> int:
        """Reopen the scripts of ``session()``; files that no longer exist are skipped.
        Returns the number of scripts opened."""
        if not isinstance(state, dict):
            return 0
        paths = [p for p in state.get("paths", []) if isinstance(p, str) and Path(p).is_file()]
        opened = sum(1 for p in paths if self.open_path(p))
        current = state.get("current")
        if isinstance(current, str) and Path(current).is_file():
            self.open_path(current)
        return opened
