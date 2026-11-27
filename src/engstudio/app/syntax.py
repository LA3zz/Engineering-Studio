"""Language facts the GUI needs for syntax highlighting, without the GUI importing ``lang``."""

from __future__ import annotations

from engstudio.lang.lexer import KEYWORDS

__all__ = ["SYNTAX_KEYWORDS"]

SYNTAX_KEYWORDS: frozenset[str] = frozenset(KEYWORDS)
