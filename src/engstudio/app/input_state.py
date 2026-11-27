"""Is Command Window input a complete statement, or does it need more lines? (K3)

``needs_more(code)`` is True when the text leaves a block (``if``, ``for``, ``while``,
``switch``, ``try``, ``function``) without its ``end``, a bracket unclosed, a block comment
(``%{``) unterminated, or ends with a ``...`` continuation. Everything else, including text
with real syntax errors, counts as complete so the kernel reports the error.

A ``function`` typed in the Command Window needs its own ``end``. Keywords inside brackets
(``x(end)``) are index forms and are not counted. Pure function of the text; no I/O.
"""

from __future__ import annotations

import re

from engstudio.lang.lexer import LexError, tokenize

__all__ = ["needs_more"]

_BLOCK_OPENERS = frozenset({"if", "for", "while", "switch", "try", "function"})
_OPEN = ("(", "[", "{")
_CLOSE = (")", "]", "}")
_CONTINUATION = re.compile(r"\.\.\.\s*$")


def _ends_with_continuation(code: str) -> bool:
    lines = [ln for ln in code.split("\n") if ln.strip()]
    if not lines:
        return False
    last = lines[-1]
    found = _CONTINUATION.search(last)
    return bool(found) and "%" not in last[:found.start()]


def needs_more(code: str) -> bool:
    """True if ``code`` is an incomplete statement or block."""
    if _ends_with_continuation(code):
        return True
    try:
        tokens = tokenize(code)
    except LexError as exc:
        message = str(exc)
        return "unclosed" in message or "unterminated block comment" in message
    except Exception:  # never let the checker break input
        return False
    depth = brackets = 0
    for tok in tokens:
        if tok.kind in _OPEN:
            brackets += 1
        elif tok.kind in _CLOSE:
            brackets -= 1
        elif tok.kind == "KEYWORD" and brackets == 0:
            if tok.text in _BLOCK_OPENERS:
                depth += 1
            elif tok.text == "end":
                depth -= 1
    return depth > 0
