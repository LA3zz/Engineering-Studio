"""Tests for engstudio.lang.builtins_text (B1b): string functions.

Expected values follow the MATLAB documentation (for example the documented ``strrep`` example
with overlapping matches) or are obvious by hand.
"""

import numpy as np
import pytest

from engstudio.core.errors import NotSupportedError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.interp import EvalError, Interpreter
from engstudio.lang.values import CellArray, CharArray


def run(src):
    interp = Interpreter()
    install_core(interp)
    install_extra(interp)
    interp.execute(src)
    return interp.workspace


def val(expr):
    return run(f"r = {expr};")["r"]


def text(v):
    assert isinstance(v, CharArray), type(v)
    return v.to_str()


def fails(expr, fragment=""):
    with pytest.raises(EvalError) as info:
        run(f"r = {expr};")
    assert fragment in str(info.value), str(info.value)


BOOL_CASES = [
    ("strcmp('abc', 'abc')", [[True]]), ("strcmp('abc', 'abd')", [[False]]),
    ("strcmp('abc', 'ABC')", [[False]]), ("strcmpi('abc', 'ABC')", [[True]]),
    ("strcmp('', '')", [[True]]), ("strcmp('a', 5)", [[False]]),
    ("strcmp({'a', 'b'}, 'a')", [[True, False]]), ("strcmp('a', {'a', 'b'})", [[True, False]]),
    ("strcmp({'a', 'b'}, {'a', 'c'})", [[True, False]]),
    ("strncmp('hello', 'help', 3)", [[True]]), ("strncmp('hello', 'help', 4)", [[False]]),
    ("strncmp('ab', 'abc', 3)", [[False]]), ("strncmpi('HELlo', 'help', 3)", [[True]]),
    ("contains('hello', 'ell')", [[True]]), ("contains('hello', 'xyz')", [[False]]),
    ("contains({'abc', 'xyz'}, 'b')", [[True, False]]), ("contains('abc', {'x', 'c'})", [[True]]),
    ("contains('ABC', 'b', 'IgnoreCase', true)", [[True]]), ("contains('ABC', 'b')", [[False]]),
    ("startsWith('hello', 'he')", [[True]]), ("endsWith('hello', 'lo')", [[True]]),
    ("startsWith({'ab', 'ba'}, 'a')", [[True, False]]), ("endsWith('hello', 'he')", [[False]]),
    ("isspace('a b')", [[False, True, False]]), ("isletter('a1')", [[True, False]]),
    ("isdigit('a1b2')", [[False, True, False, True]]), ("isspace(5)", [[False]]),
]


@pytest.mark.parametrize("expr,expected", BOOL_CASES)
def test_boolean_results(expr, expected):
    out = val(expr)
    assert out.dtype == np.bool_
    np.testing.assert_array_equal(out, np.array(expected))


TEXT_CASES = [
    ("upper('abC')", "ABC"), ("lower('ABc')", "abc"), ("strtrim('  hi  ')", "hi"),
    ("strtrim(sprintf('\\t x \\n'))", "x"), ("strrep('a-b-c', '-', '+')", "a+b+c"),
    ("strrep('abc', '', 'x')", "abc"), ("strrep('abab', 'ab', 'XY')", "XYXY"),
    ("strrep('abc 2 def 22 ghi 222 jkl 2222', '22', '*')", "abc 2 def * ghi ** jkl ***"),
    ("strrep('aaa', 'aa', 'b')", "bb"), ("strcat('a ', 'b ', 'c')", "abc"),
    ("strjoin({'a', 'b', 'c'}, ', ')", "a, b, c"), ("strjoin({'a', 'b'})", "a b"),
    ("strjoin(strsplit('a b  c'), '-')", "a-b-c"),
    ("strjoin(strsplit('a,b,,c', ','), '|')", "a|b|c"),
    ("strjoin(strsplit('a,b,,c', ',', 'CollapseDelimiters', false), '|')", "a|b||c"),
    ("strjoin(strsplit('a-b+c', {'-', '+'}), '|')", "a|b|c"),
    ("strjoin(strsplit('abc', ''), '|')", "abc"), ("int2str(2.5)", "3"), ("int2str(-2.5)", "-3"),
    ("int2str([1.4 2.6])", "1  3"), ("blanks(3)", "   "), ("blanks(0)", ""),
    ("mat2str([1 2; 3 4.5])", "[1 2;3 4.5]"), ("mat2str(5)", "5"),
    ("mat2str([true false])", "[true false]"), ("mat2str('it''s')", "'it''s'"),
    ("mat2str(zeros(0, 3))", "zeros(0,3)"), ("mat2str(pi, 4)", "3.142"),
    ("mat2str(1 + 2i)", "1+2i"), ("mat2str([1; 2])", "[1;2]"),
]


@pytest.mark.parametrize("expr,expected", TEXT_CASES)
def test_text_results(expr, expected):
    assert text(val(expr)) == expected


def test_cell_arguments_map_over_the_elements():
    out = val("upper({'ab', 'c'})")
    assert isinstance(out, CellArray) and out.shape == (1, 2)
    assert [text(x) for x in out.data.ravel()] == ["AB", "C"]
    out = val("strtrim({' a ', 'b '})")
    assert [text(x) for x in out.data.ravel()] == ["a", "b"]
    out = val("strrep({'aa', 'ba'}, 'a', 'x')")
    assert [text(x) for x in out.data.ravel()] == ["xx", "bx"]
    out = val("strsplit('a b c')")
    assert out.shape == (1, 3)


def test_strfind():
    np.testing.assert_array_equal(val("strfind('abcabc', 'bc')"), [[2, 5]])
    np.testing.assert_array_equal(val("strfind('aaa', 'aa')"), [[1, 2]])
    assert val("strfind('abc', 'x')").shape == (0, 0)
    assert val("strfind('abc', '')").shape == (0, 0)


def test_str2double():
    cases = [("'3.5'", 3.5), ("'1e3'", 1000), ("'1,200'", 1200), ("'  42  '", 42),
             ("'Inf'", np.inf), ("'-inf'", -np.inf), ("'-7'", -7)]
    for src, expected in cases:
        np.testing.assert_allclose(val(f"str2double({src})"), [[expected]])
    for src in ("'abc'", "''", "5", "'1_000'", "'0x10'", "'1 2'"):
        assert np.isnan(val(f"str2double({src})")[0, 0]), src
    np.testing.assert_allclose(val("str2double({'3.5', 'x', '1e3'})")[0, [0, 2]], [3.5, 1000])
    assert np.isnan(val("str2double({'3.5', 'x'})")[0, 1])
    z = val("str2double('1+2i')")
    assert z.dtype == np.complex128 and z[0, 0] == 1 + 2j


def test_text_function_errors():
    fails("upper(5)", "character vector")
    fails("strrep('a', 1, 'b')", "character vector")
    fails("strsplit(5)", "character vector")
    fails("strjoin('abc')", "cell array of strings")
    fails("strjoin({1, 2})", "character vector")
    fails("strcmp('a')", "Not enough input arguments")
    fails("strcmp({'a', 'b'}, {'a'})", "same size")
    fails("contains('a', 'b', 'Bogus', true)", "unknown option")
    fails("contains('a', 'b', 'IgnoreCase')", "name/value pairs")
    fails("blanks(-1)", "non-negative")
    fails("mat2str({1})", "unsupported")
    fails("strcat({'a'}, 'b')", "not supported")
    with pytest.raises(EvalError) as info:
        run("r = upper(['ab'; 'cd']);")
    assert isinstance(info.value.__cause__, NotSupportedError)
