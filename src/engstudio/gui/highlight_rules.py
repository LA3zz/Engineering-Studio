"""Line tokenizer and colours for script syntax highlighting. Pure Python (no Qt).

Highlights keywords, comments (``%``, ``...`` continuation, ``%{ ... %}`` block comments),
strings (``'...'`` and ``"..."``) and numbers. It is a highlighter, not a parser: it never
reports errors. ``'`` after an identifier, number, ``)``, ``]``, ``}``, ``'`` or ``.`` is the
transpose operator, not the start of a string.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from typing import NamedTuple

__all__ = ["KINDS", "SYNTAX_COLORS", "Token", "tokenize_line"]

KINDS = ("keyword", "comment", "string", "number")


class Token(NamedTuple):
    start: int
    length: int
    kind: str


# Every colour is checked for WCAG contrast >= 4.5 against the theme's editor background
# (tests/gui/test_highlight_rules.py).
SYNTAX_COLORS: dict[str, dict[str, str]] = {
    "light": {"keyword": "#7a2e9a", "comment": "#5a6672", "string": "#a0400c",
              "number": "#0b6b4c"},
    "dark": {"keyword": "#c792ea", "comment": "#8b98a5", "string": "#e8a870",
             "number": "#7fd4a8"},
}

_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[ij]?")
_TRANSPOSE_PREV = frozenset(")]}'._")


def _is_word_start(c: str) -> bool:
    return c.isascii() and (c.isalpha() or c == "_")


def _is_word_char(c: str) -> bool:
    return c.isascii() and (c.isalnum() or c == "_")


def _scan_string(text: str, i: int, quote: str) -> int:
    """Index just past the string starting at ``i`` (doubled quote = escaped quote)."""
    n = len(text)
    j = i + 1
    while j < n:
        if text[j] == quote:
            if j + 1 < n and text[j + 1] == quote:
                j += 2
                continue
            return j + 1
        j += 1
    return n  # unterminated: highlight to end of line


def tokenize_line(
    text: str, in_block: bool = False, keywords: Collection[str] = frozenset()
) -> tuple[list[Token], bool]:
    """Tokens of one line and the block-comment state for the next line."""
    n = len(text)
    if in_block:
        if text.strip() == "%}":
            in_block = False
        return ([Token(0, n, "comment")] if n else []), in_block
    if text.strip() == "%{":
        return [Token(0, n, "comment")], True

    tokens: list[Token] = []
    i = 0
    while i < n:
        c = text[i]
        if c == "%" or text.startswith("...", i):
            tokens.append(Token(i, n - i, "comment"))
            break
        if c == '"':
            j = _scan_string(text, i, '"')
            tokens.append(Token(i, j - i, "string"))
            i = j
        elif c == "'":
            prev = text[i - 1] if i > 0 else ""
            if prev and (_is_word_char(prev) or prev in _TRANSPOSE_PREV):
                i += 1  # transpose operator
            else:
                j = _scan_string(text, i, "'")
                tokens.append(Token(i, j - i, "string"))
                i = j
        elif c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = _NUMBER.match(text, i)
            end = m.end() if m else i + 1
            if text[i:end].endswith(".") and end < n and text[end] in "*/^\\'":
                end -= 1  # "2.^x" is 2 .^ x
            tokens.append(Token(i, end - i, "number"))
            i = end
        elif _is_word_start(c):
            j = i + 1
            while j < n and _is_word_char(text[j]):
                j += 1
            if text[i:j] in keywords and not (i > 0 and text[i - 1] == "."):
                tokens.append(Token(i, j - i, "keyword"))
            i = j
        else:
            i += 1
    return tokens, False
