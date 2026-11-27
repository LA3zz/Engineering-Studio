"""to_function_syntax: commands followed by more statements on the same line."""

import pytest

from engstudio.app.kernel.inprocess import to_function_syntax


@pytest.mark.parametrize("code, expected", [
    ("clc", "clc()"),
    ("clear x y;", "clear('x', 'y');"),
    ("clear x % note", "clear('x')"),
    ("clc; x = 1", "clc(); x = 1"),
    ("clc, x = 2", "clc(), x = 2"),
    ("clear all; close all; clc", "clear('all'); close('all'); clc()"),
    ("syms x y; f = x*y", "syms('x', 'y'); f = x*y"),
    ("  syms t; % symbols", "  syms('t');"),
    ("x = 1; clc", "x = 1; clc"),
    ("syms = 3; y = 4", "syms = 3; y = 4"),
    ("format long", "format('long')"),
    ("a = 1\nclc; b = 2\nb", "a = 1\nclc(); b = 2\nb"),
])
def test_rewrite(code, expected):
    assert to_function_syntax(code) == expected
