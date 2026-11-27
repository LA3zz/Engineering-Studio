"""Call tips: while typing ``plot(x, `` a small box shows how the function can be called,
with the argument at the cursor in bold, and (for toolbox functions) what that argument means.

The function list comes from the kernel's ``ToolboxList`` event (``CATALOG``), so the GUI never
imports the engine. Works for the script editor (``QPlainTextEdit``) and the Command Window
input (``QLineEdit``).
"""

from __future__ import annotations

import html
import re
import textwrap
from collections.abc import Callable, Iterable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QPlainTextEdit, QWidget

from engstudio.app.function_help import split_forms
from engstudio.app.kernel.protocol import ToolboxFunction, ToolboxInfo

__all__ = ["CATALOG", "CallTipController", "FunctionCatalog", "call_context", "render_tip"]

_NAME_BEFORE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)$")
_VALUE_END = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_)]}.'")
MAX_FORMS = 6


class FunctionCatalog:
    """Function name -> ``ToolboxFunction`` (signature, help, argument docs)."""

    def __init__(self) -> None:
        self._entries: dict[str, ToolboxFunction] = {}

    def update(self, toolboxes: Iterable[ToolboxInfo]) -> None:
        self._entries = {fn.name: fn for tb in toolboxes for fn in tb.functions}

    def get(self, name: str) -> ToolboxFunction | None:
        return self._entries.get(name)

    def __len__(self) -> int:
        return len(self._entries)


CATALOG = FunctionCatalog()


def call_context(text: str) -> tuple[str, int] | None:
    """For the text before the cursor: (function name, zero-based argument index) of the
    innermost unfinished call, or None. ``[...]``/``{...}`` inside a call do not count as
    arguments; text in quotes and comments is skipped."""
    stack: list[list] = []  # [opening char, function name or "", commas]
    quote = ""
    prev = ""
    for idx, c in enumerate(text):
        if quote:
            if c == quote:
                quote = ""
                prev = c
            continue
        if c == "%":
            return None  # the cursor is inside a comment
        if c == '"':
            quote = c
        elif c == "'":
            if prev and prev in _VALUE_END:
                pass  # transpose
            else:
                quote = c
        elif c in "([{":
            m = _NAME_BEFORE.search(text[:idx]) if c == "(" else None
            stack.append([c, m.group(1) if m else "", 0])
        elif c in ")]}":
            if stack:
                stack.pop()
        elif c == "," and stack:
            stack[-1][2] += 1
        elif c == ";" and stack and stack[-1][0] == "(":
            pass
        elif c == "\n":
            prev = ""
            continue
        if not c.isspace():
            prev = c
    for opening, name, commas in reversed(stack):
        if opening == "(" and name:
            return name, commas
        if opening == "(":
            return None  # plain parentheses: (a + b)
    return None


def _split_args(inner: str) -> list[str]:
    out, depth, quote, cur = [], 0, False, ""
    for c in inner:
        if c == "'":
            quote = not quote
        elif not quote and c in "([{":
            depth += 1
        elif not quote and c in ")]}":
            depth -= 1
        if c == "," and depth == 0 and not quote:
            out.append(cur)
            cur = ""
            continue
        cur += c
    out.append(cur)
    return [a.strip() for a in out]


def _form_html(form: str, name: str, index: int) -> tuple[str, bool]:
    """A calling form with argument ``index`` in bold; and whether the form has it."""
    start = form.find(f"{name}(")
    if start < 0:
        return html.escape(form), False
    open_at = start + len(name)
    depth, close_at = 0, -1
    for k in range(open_at, len(form)):
        if form[k] == "(":
            depth += 1
        elif form[k] == ")":
            depth -= 1
            if depth == 0:
                close_at = k
                break
    if close_at < 0:
        return html.escape(form), False
    args = _split_args(form[open_at + 1:close_at])
    if args == [""]:
        args = []
    open_ended = bool(args) and args[0].startswith("...")  # plot(..., 'Name', value)
    has = index < len(args) or open_ended
    cells = []
    for k, a in enumerate(args):
        bold = k == index and not open_ended
        cells.append(f"<b><u>{html.escape(a)}</u></b>" if bold else html.escape(a))
    body = (html.escape(form[:open_at + 1]) + ", ".join(cells) + html.escape(form[close_at:]))
    return body, has


def _wrap(prefix_html: str, text: str, width: int = 90) -> str:
    lines = textwrap.wrap(text, width) or [""]
    return prefix_html + "<br>".join(html.escape(line) for line in lines)


def render_tip(entry: ToolboxFunction, index: int) -> str:
    forms = split_forms(entry.signature) if entry.signature else [f"{entry.name}(...)"]
    rows = [_form_html(f, entry.name, index) for f in forms]
    fitting = [h for h, has in rows if has]
    others = [h for h, has in rows if not has]
    shown = (fitting + [f"<span style='color:gray'>{h}</span>" for h in others])[:MAX_FORMS]
    parts = ["<br>".join(f"<code>{h}</code>" for h in shown)]
    if entry.params and index < len(entry.params) and index < len(entry.param_docs):
        doc = entry.param_docs[index]
        parts.append(_wrap(f"<b>{html.escape(entry.params[index])}</b>: ", doc))
    elif entry.params and index >= len(entry.params):
        parts.append(f"<span style='color:#b00'>{html.escape(entry.name)} takes at most "
                     f"{len(entry.params)} inputs</span>")
    elif entry.summary:
        parts.append(_wrap("", entry.summary))
    return "<br>".join(parts)


class CallTipController(QObject):
    """Shows the call tip for ``widget`` as the user types or moves the cursor."""

    def __init__(self, widget: QWidget, catalog: FunctionCatalog | None = None,
                 above: bool = False) -> None:
        super().__init__(widget)
        self._widget = widget
        self._catalog = catalog if catalog is not None else CATALOG
        self._above = above
        # Owned by the widget (deleted with it) but shown as its own tool-tip window.
        self.label = QLabel(widget, Qt.WindowType.ToolTip)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(False)  # forms stay on one line; descriptions wrap at 90
        self.label.setMargin(6)
        self.label.setStyleSheet("QLabel { background: palette(tooltip-base); "
                                 "color: palette(tooltip-text); "
                                 "border: 1px solid palette(mid); }")
        self._text: Callable[[], str]
        self._rect: Callable[[], QRect]
        if isinstance(widget, QPlainTextEdit):
            self._text = lambda: widget.textCursor().block().text()[
                :widget.textCursor().positionInBlock()]
            self._rect = widget.cursorRect
            widget.cursorPositionChanged.connect(self.refresh)
        elif isinstance(widget, QLineEdit):
            self._text = lambda: widget.text()[:widget.cursorPosition()]
            self._rect = widget.cursorRect  # protected; callable on Python subclasses
            widget.cursorPositionChanged.connect(lambda *_: self.refresh())
            widget.textChanged.connect(lambda *_: self.refresh())
        else:
            raise TypeError("call tips need a QPlainTextEdit or a QLineEdit")
        widget.installEventFilter(self)

    def refresh(self) -> None:
        if not self._widget.hasFocus():
            self.label.hide()
            return
        ctx = call_context(self._text())
        entry = self._catalog.get(ctx[0]) if ctx else None
        if ctx is None or entry is None:
            self.label.hide()
            return
        self.label.setText(render_tip(entry, ctx[1]))
        self.label.adjustSize()
        r = self._rect()
        if self._above:
            pos = self._widget.mapToGlobal(QPoint(r.left(), r.top()))
            pos.setY(pos.y() - self.label.height() - 4)
        else:
            pos = self._widget.mapToGlobal(QPoint(r.left(), r.bottom() + 4))
        self.label.move(pos)
        self.label.show()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt override)
        kind = event.type()
        if kind in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate):
            self.label.hide()
        elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.label.hide()
        return False
