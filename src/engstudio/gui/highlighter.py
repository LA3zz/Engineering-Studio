"""Qt syntax highlighter for the script editor (rules live in ``highlight_rules``)."""

from __future__ import annotations

from collections.abc import Collection

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from engstudio.app.syntax import SYNTAX_KEYWORDS
from engstudio.gui.highlight_rules import KINDS, SYNTAX_COLORS, tokenize_line

__all__ = ["ScriptHighlighter"]

_IN_BLOCK = 1  # block state: inside a %{ ... %} comment (0 = normal)


class ScriptHighlighter(QSyntaxHighlighter):
    def __init__(
        self,
        document: QTextDocument,
        theme: str = "light",
        keywords: Collection[str] | None = None,
    ) -> None:
        super().__init__(document)
        self._keywords = frozenset(SYNTAX_KEYWORDS if keywords is None else keywords)
        self.theme = theme
        self._formats = self._build_formats(theme)

    @staticmethod
    def _build_formats(theme: str) -> dict[str, QTextCharFormat]:
        try:
            colors = SYNTAX_COLORS[theme]
        except KeyError:
            raise ValueError(
                f"unknown theme {theme!r}; expected one of {sorted(SYNTAX_COLORS)}"
            ) from None
        formats: dict[str, QTextCharFormat] = {}
        for kind in KINDS:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(colors[kind]))
            if kind == "keyword":
                fmt.setFontWeight(QFont.Weight.Bold)
            elif kind == "comment":
                fmt.setFontItalic(True)
            formats[kind] = fmt
        return formats

    def set_theme(self, name: str) -> None:
        self._formats = self._build_formats(name)  # raises ValueError before any change
        self.theme = name
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        formats = getattr(self, "_formats", None)
        if formats is None:
            return
        tokens, in_block = tokenize_line(
            text, self.previousBlockState() == _IN_BLOCK, self._keywords
        )
        for tok in tokens:
            self.setFormat(tok.start, tok.length, formats[tok.kind])
        self.setCurrentBlockState(_IN_BLOCK if in_block else 0)
