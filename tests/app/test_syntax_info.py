"""app.syntax exposes the language keywords to the GUI (G4)."""

from __future__ import annotations

from engstudio.app.syntax import SYNTAX_KEYWORDS
from engstudio.lang.lexer import KEYWORDS


def test_keywords_match_the_lexer():
    assert isinstance(SYNTAX_KEYWORDS, frozenset)
    assert SYNTAX_KEYWORDS
    assert all(isinstance(k, str) and k for k in SYNTAX_KEYWORDS)
    assert set(SYNTAX_KEYWORDS) == set(KEYWORDS)
