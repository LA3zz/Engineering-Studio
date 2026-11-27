"""Lexer for the Engineering Studio v1 MATLAB-like subset. Tokens only; no parser.

Token kinds
-----------
``NUMBER`` (value: float), ``IMAG`` (value: complex), ``IDENT``, ``KEYWORD``,
``STRING`` (single-quoted char array, value: str), ``DQSTRING`` (double-quoted, value: str),
``TRANSPOSE`` (text ``'`` or ``.'``), ``NEWLINE``, ``EOF``, and punctuation/operators whose
kind equals their text (``+ - * / \\ ^ .* ./ .\\ .^ == ~= < <= > >= & | && || ~ = @ : .``
and the brackets ``( ) [ ] { }``, ``,`` and ``;``).

Inside ``[]`` / ``{}`` the lexer inserts *synthetic* tokens (``Token.synthetic`` is True):
``,`` where whitespace separates two elements (``[1 -2]`` -> ``1 , - 2``; ``[1 - 2]`` is one
element) and ``;`` for a newline (row separator). Newlines elsewhere give ``NEWLINE``
(one per physical line break, blank lines included; the parser may collapse them).
``%`` comments, ``%{ ... %}`` block comments and ``...`` continuations produce no tokens;
a continuation counts as whitespace. Positions are 1-based (``SourceLoc``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engstudio.core.diagnostics import SourceLoc
from engstudio.core.errors import EngStudioError

KEYWORDS = frozenset(
    {
        "if", "elseif", "else", "end", "for", "while", "break", "continue", "return",
        "function", "switch", "case", "otherwise", "try", "catch",
    }
)


class LexError(EngStudioError):
    """Invalid character or malformed token/bracket structure."""

    code = "E_LEX"

    def __init__(self, message: str, location: SourceLoc | None = None) -> None:
        super().__init__(message)
        self.location = location

    def to_diagnostic(self, location: SourceLoc | None = None):  # type: ignore[override]
        return super().to_diagnostic(location or self.location)


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    loc: SourceLoc
    value: object = None
    space_before: bool = False
    synthetic: bool = False


_DIGITS = "0123456789"
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPERAND_END = frozenset(
    {"NUMBER", "IMAG", "IDENT", "STRING", "DQSTRING", "TRANSPOSE", ")", "]", "}"}
)
_TWO_CHAR = frozenset({".*", "./", ".\\", ".^", "==", "~=", "<=", ">=", "&&", "||"})
_ONE_CHAR = frozenset("+-*/\\^<>=&|~@:()[]{},;.")
_CLOSERS = {")": "(", "]": "[", "}": "{"}


def _is_ident_char(ch: str) -> bool:
    return ch.isascii() and (ch.isalnum() or ch == "_")


class _Lexer:
    def __init__(self, source: str, file: str | None) -> None:
        self.s = source.replace("\r\n", "\n").replace("\r", "\n")
        self.file = file
        self.i = 0
        self.line = 1
        self.line_start = 0
        self.bol = True  # only whitespace seen so far on this line
        self.tokens: list[Token] = []
        self.stack: list[tuple[str, SourceLoc]] = []

    # -- helpers -----------------------------------------------------------
    def _loc(self, pos: int | None = None) -> SourceLoc:
        p = self.i if pos is None else pos
        return SourceLoc(self.file, self.line, p - self.line_start + 1)

    def _emit(self, kind, text, loc, value=None, space=False, synthetic=False) -> None:
        self.tokens.append(Token(kind, text, loc, value, space, synthetic))
        self.bol = False

    def _top(self) -> str | None:
        return self.stack[-1][0] if self.stack else None

    def _in_matrix(self) -> bool:
        return self._top() in ("[", "{")

    def _prev_is_operand_end(self) -> bool:
        if not self.tokens:
            return False
        t = self.tokens[-1]
        if t.kind in _OPERAND_END:
            return True
        return t.kind == "KEYWORD" and t.text == "end" and bool(self.stack)

    def _starts_operand(self, c: str) -> bool:
        s, i = self.s, self.i
        if _is_ident_char(c):
            return True
        if c == ".":
            return i + 1 < len(s) and s[i + 1] in _DIGITS
        if c in "'\"([{@":
            return True
        if c == "~":
            return not s.startswith("~=", i)
        if c in "+-":
            nxt = s[i + 1] if i + 1 < len(s) else " "
            return nxt not in " \t\n="
        return False

    def _newline(self) -> None:
        top = self._top()
        loc = self._loc()
        if top in ("[", "{"):
            last = self.tokens[-1]
            if last.kind != ";" and last.kind not in ("[", "{"):
                self._emit(";", ";", loc, synthetic=True)
        elif top == "(":
            raise LexError("line break inside parentheses; use '...' to continue the line", loc)
        else:
            self._emit("NEWLINE", "\n", loc)
        self.i += 1
        self.line += 1
        self.line_start = self.i
        self.bol = True

    def _skip_space(self) -> bool:
        s, n = self.s, len(self.s)
        skipped = False
        while self.i < n:
            c = s[self.i]
            if c in " \t":
                self.i += 1
                skipped = True
            elif s.startswith("...", self.i):
                e = s.find("\n", self.i)
                if e == -1:
                    self.i = n
                else:
                    self.i = e + 1
                    self.line += 1
                    self.line_start = self.i
                skipped = True
                self.bol = False
            else:
                break
        return skipped

    def _comment(self) -> None:
        s, n = self.s, len(self.s)
        e = s.find("\n", self.i)
        e = n if e == -1 else e
        if self.bol and s[self.i:e].strip() == "%{":
            start = self._loc()
            depth = 0
            while True:
                e = s.find("\n", self.i)
                e = n if e == -1 else e
                text = s[self.i:e].strip()
                if text == "%{":
                    depth += 1
                elif text == "%}":
                    depth -= 1
                self.i = e
                if depth == 0:
                    return
                if e >= n:
                    raise LexError("unterminated block comment '%{'", start)
                self.i = e + 1
                self.line += 1
                self.line_start = self.i
        else:
            self.i = e

    # -- token readers -----------------------------------------------------
    def _number(self, space: bool) -> None:
        s, n, i = self.s, len(self.s), self.i
        loc = self._loc()
        j = i
        while j < n and s[j] in _DIGITS:
            j += 1
        if j < n and s[j] == "." and not (
            s.startswith("...", j) or (j + 1 < n and s[j + 1] in "*/\\^'")
        ):
            j += 1
            while j < n and s[j] in _DIGITS:
                j += 1
        if j < n and s[j] in "eE":
            k = j + 1
            if k < n and s[k] in "+-":
                k += 1
            if k < n and s[k] in _DIGITS:
                while k < n and s[k] in _DIGITS:
                    k += 1
                j = k
        value = float(s[i:j])
        kind = "NUMBER"
        if j < n and s[j] in "ij" and not (j + 1 < n and _is_ident_char(s[j + 1])):
            j += 1
            kind = "IMAG"
            value = complex(0.0, value)
        if j < n and _is_ident_char(s[j]):
            raise LexError(f"invalid number or identifier {s[i:j + 1]!r}", loc)
        self.i = j
        self._emit(kind, s[i:j], loc, value, space)

    def _string(self, quote: str, kind: str, space: bool) -> None:
        s, n, i = self.s, len(self.s), self.i
        loc = self._loc()
        j = i + 1
        buf: list[str] = []
        while True:
            if j >= n or s[j] == "\n":
                raise LexError("unterminated string", loc)
            ch = s[j]
            if ch == quote:
                if j + 1 < n and s[j + 1] == quote:
                    buf.append(quote)
                    j += 2
                    continue
                j += 1
                break
            buf.append(ch)
            j += 1
        self.i = j
        self._emit(kind, s[i:j], loc, "".join(buf), space)

    def _close(self, c: str) -> None:
        loc = self._loc()
        if not self.stack:
            raise LexError(f"unmatched {c!r}", loc)
        opener, oloc = self.stack[-1]
        if opener != _CLOSERS[c]:
            raise LexError(f"{c!r} does not match {opener!r} opened at {oloc}", loc)
        self.stack.pop()

    # -- main loop ---------------------------------------------------------
    def run(self) -> list[Token]:
        s, n = self.s, len(self.s)
        while True:
            space = self._skip_space()
            if self.i >= n:
                break
            c = s[self.i]
            if c == "\n":
                self._newline()
                continue
            if c == "%":
                self._comment()
                continue
            loc = self._loc()
            if (
                self._in_matrix()
                and space
                and self._prev_is_operand_end()
                and self._starts_operand(c)
            ):
                self._emit(",", ",", loc, space=True, synthetic=True)
            if c in _DIGITS or (c == "." and self.i + 1 < n and s[self.i + 1] in _DIGITS):
                self._number(space)
            elif _is_ident_char(c):
                m = _IDENT_RE.match(s, self.i)
                text = m.group(0)
                self.i = m.end()
                self._emit("KEYWORD" if text in KEYWORDS else "IDENT", text, loc, None, space)
            elif c == '"':
                self._string('"', "DQSTRING", space)
            elif c == "'":
                prev_ok = self._prev_is_operand_end() and self.tokens[-1].kind not in (
                    "STRING", "DQSTRING")
                if prev_ok and not (self._in_matrix() and space):
                    self.i += 1
                    self._emit("TRANSPOSE", "'", loc, None, space)
                else:
                    self._string("'", "STRING", space)
            elif s.startswith(".'", self.i):
                self.i += 2
                self._emit("TRANSPOSE", ".'", loc, None, space)
            elif s[self.i:self.i + 2] in _TWO_CHAR:
                text = s[self.i:self.i + 2]
                self.i += 2
                self._emit(text, text, loc, None, space)
            elif c in _ONE_CHAR:
                if c in "([{":
                    self.stack.append((c, loc))
                elif c in ")]}":
                    self._close(c)
                self.i += 1
                self._emit(c, c, loc, None, space)
            else:
                raise LexError(f"unexpected character {c!r}", loc)
        if self.stack:
            opener, oloc = self.stack[-1]
            raise LexError(f"unclosed {opener!r}", oloc)
        self.tokens.append(Token("EOF", "", self._loc()))
        return self.tokens


def tokenize(source: str, file: str | None = None) -> list[Token]:
    """Tokenize ``source``; the result always ends with an ``EOF`` token.

    Raises ``LexError`` (with ``.location``) on the first lexical error.
    """
    return _Lexer(source, file).run()
