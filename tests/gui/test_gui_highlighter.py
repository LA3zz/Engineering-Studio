"""Syntax highlighter and theme switching in the editor (headless; skipped without PySide6)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QTextCursor  # noqa: E402

from engstudio.gui.editor_tabs import ScriptEditor, ScriptTabs  # noqa: E402
from engstudio.gui.highlight_rules import SYNTAX_COLORS  # noqa: E402
from engstudio.gui.main_window import MainWindow  # noqa: E402
from engstudio.gui.settings import UiSettings  # noqa: E402


def block_formats(editor, number):
    """(start, length, colour) of the highlight ranges applied to one block."""
    block = editor.document().findBlockByNumber(number)
    return [(r.start, r.length, r.format.foreground().color().name())
            for r in block.layout().formats()]


@pytest.fixture
def editor():
    ed = ScriptEditor()
    yield ed
    ed.document().setModified(False)
    ed.hide()
    ed.deleteLater()


def test_default_theme_colours(editor):
    editor.setPlainText("x = 1 % hi")
    c = SYNTAX_COLORS["light"]
    assert sorted(block_formats(editor, 0)) == [(4, 1, c["number"]), (6, 4, c["comment"])]


def test_keywords_come_from_the_language(editor):
    from engstudio.app.syntax import SYNTAX_KEYWORDS

    word = sorted(SYNTAX_KEYWORDS)[0]
    editor.setPlainText(word)
    assert block_formats(editor, 0) == [(0, len(word), SYNTAX_COLORS["light"]["keyword"])]


def test_string_and_transpose(editor):
    editor.setPlainText("y = A' + 'ab'")
    c = SYNTAX_COLORS["light"]
    assert block_formats(editor, 0) == [(9, 4, c["string"])]


def test_block_comment_spans_lines(editor):
    editor.setPlainText("%{\nx = 1\n%}\ny = 2")
    c = SYNTAX_COLORS["light"]
    assert block_formats(editor, 1) == [(0, 5, c["comment"])]
    assert block_formats(editor, 3) == [(4, 1, c["number"])]


def test_editing_updates_following_lines(editor):
    editor.setPlainText("a = 1\nb = 2")
    c = SYNTAX_COLORS["light"]
    assert block_formats(editor, 1) == [(4, 1, c["number"])]
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.insertText("%{\n")  # opens a block comment above the second line
    assert block_formats(editor, 2) == [(0, 5, c["comment"])]


def test_set_theme_recolours_and_rejects_unknown(editor):
    editor.setPlainText("x = 1")
    editor.highlighter.set_theme("dark")
    assert editor.highlighter.theme == "dark"
    assert block_formats(editor, 0) == [(4, 1, SYNTAX_COLORS["dark"]["number"])]
    with pytest.raises(ValueError):
        editor.highlighter.set_theme("neon")
    assert editor.highlighter.theme == "dark"  # unchanged after the failed call


def test_tabs_apply_theme_to_existing_and_new_editors():
    tabs = ScriptTabs()
    try:
        tabs.new_script()
        tabs.set_theme("dark")
        assert [tabs.editor(i).highlighter.theme for i in range(tabs.count())] == ["dark"] * 2
        assert tabs.new_script().highlighter.theme == "dark"
    finally:
        for i in range(tabs.count()):
            tabs.editor(i).document().setModified(False)
        tabs.hide()
        tabs.deleteLater()


def test_opened_file_is_highlighted(tmp_path):
    f = tmp_path / "s.m"
    f.write_text("x = 3;\n", encoding="utf-8")
    tabs = ScriptTabs()
    try:
        tabs.set_theme("dark")
        assert tabs.open_path(f)
        ed = tabs.current_editor()
        assert block_formats(ed, 0) == [(4, 1, SYNTAX_COLORS["dark"]["number"])]
    finally:
        for i in range(tabs.count()):
            tabs.editor(i).document().setModified(False)
        tabs.hide()
        tabs.deleteLater()


def test_main_window_theme_switch_recolours_editors():
    win = MainWindow(UiSettings(None))
    try:
        win.set_theme("dark")
        assert win.tabs.current_editor().highlighter.theme == "dark"
        win.set_theme("light")
        assert win.tabs.current_editor().highlighter.theme == "light"
        win.tabs.new_script()
        assert win.tabs.current_editor().highlighter.theme == "light"
    finally:
        for i in range(win.tabs.count()):
            win.tabs.editor(i).document().setModified(False)
        win.close()
        win.deleteLater()
