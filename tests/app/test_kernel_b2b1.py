"""Command-syntax rewriting added with B2b-1 (close, format short g)."""

from engstudio.app.kernel.inprocess import to_function_syntax


def test_close_all_becomes_call():
    assert to_function_syntax("close all") == "close('all')"


def test_format_short_g_becomes_call():
    assert to_function_syntax("format short g") == "format('short', 'g')"
