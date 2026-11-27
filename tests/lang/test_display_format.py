"""Tests for engstudio.lang.display (T3.4d): expected texts follow the documented rules of
the module (an approximation of MATLAB ``format short``); unparse is checked by round trip."""

import numpy as np
import pytest

from engstudio.core.errors import ValidationError
from engstudio.lang import ast as A
from engstudio.lang.display import (
    format_disp,
    format_value,
    handle_text,
    short_text,
    unparse,
)
from engstudio.lang.parser import parse
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    to_value,
)


def v(x):
    return to_value(x)


def expr(src):
    return parse(src).body[0].expr


def anon(src):
    node = expr(src)
    return FunctionHandle(params=node.params, body=node.body)


# ------------------------------------------------------------------- scalars
SCALARS = [
    (5, "5"), (-3, "-3"), (0, "0"), (123456789, "123456789"),
    (np.pi, "3.1416"), (0.5, "0.5000"), (0.05, "0.0500"), (-2.5, "-2.5000"),
    (31.4159265, "31.416"), (314.159265, "314.16"), (3141.59265, "3141.6"),
    (31415.9265, "31416"), (314159.265, "3.1416e+05"), (0.0005, "5.0000e-04"),
    (0.0012345, "0.0012"), (1e10, "1.0000e+10"),
    (float("nan"), "NaN"), (float("inf"), "Inf"), (float("-inf"), "-Inf"),
    (True, "1"), (False, "0"),
]


@pytest.mark.parametrize("value,text", SCALARS)
def test_real_scalars(value, text):
    assert format_value("x", v(value)) == f"x = {text}\n"


def test_complex_scalars():
    assert format_value("z", v(3 + 4j)) == "z = 3 + 4i\n"
    assert format_value("z", v(2 - 3j)) == "z = 2 - 3i\n"
    assert format_value("z", v(1j)) == "z = 0 + 1i\n"
    assert format_value("z", v(1.5 - 2.5j)) == "z = 1.5000 - 2.5000i\n"
    assert format_value("z", v(0.5 + 100.25j)) == "z = 0.50 + 100.25i\n"


# ------------------------------------------------------------------ matrices
def test_integer_matrices():
    assert format_value("A", v([[1, 2], [3, 4]])) == "A =\n\n     1     2\n     3     4\n\n"
    assert format_value("x", v([1, 2, 3])) == "x =\n\n     1     2     3\n\n"
    assert format_value("x", v([-1, 2])) == "x =\n\n    -1     2\n\n"
    assert format_value("x", v([100, 200])) == "x =\n\n   100   200\n\n"
    assert format_value("x", v([True, False])) == "x =\n\n     1     0\n\n"
    assert format_value("x", v([1, float("nan"), 3])) == "x =\n\n     1   NaN     3\n\n"


def test_non_integer_matrices():
    assert format_value("x", v([1.5, 2.5])) == "x =\n\n    1.5000    2.5000\n\n"
    assert format_value("x", v([10.5, 2.5])) == "x =\n\n   10.5000    2.5000\n\n"
    out = format_value("x", v([[1.5, 2.5], [3.5, -4.5]]))
    assert out == "x =\n\n    1.5000    2.5000\n    3.5000   -4.5000\n\n"
    assert format_value("x", v([1.5, float("nan")])) == "x =\n\n    1.5000       NaN\n\n"


def test_scale_factor_and_exponent_fallback():
    out = format_value("x", v([1000.5, 2.5]))
    assert out == "x =\n\n   1.0e+03 *\n\n    1.0005    0.0025\n\n"
    out = format_value("x", v([0.0005, 0.0003]))
    assert out == "x =\n\n   1.0e-04 *\n\n    5.0000    3.0000\n\n"
    out = format_value("x", v([0.5, 1e-7]))
    assert out == "x =\n\n   5.0000e-01   1.0000e-07\n\n"  # never prints a tiny entry as 0.0000


def test_complex_matrix():
    out = format_value("z", v([1 + 2j, 3 - 4j]))
    assert out == "z =\n\n   1 + 2i   3 - 4i\n\n"


def test_wide_matrix_is_split_into_column_chunks():
    out = format_value("D", v(np.arange(1, 31)))
    assert "  Columns 1 through 13\n" in out
    assert "  Columns 14 through 26\n" in out
    assert "  Columns 27 through 30\n" in out
    assert all(len(line) <= 80 for line in out.splitlines())
    rows = [
        line for line in out.splitlines()
        if line.strip() and "Column" not in line and "=" not in line
    ]
    assert [int(t) for line in rows for t in line.split()] == list(range(1, 31))
    assert "  Column 27\n" in format_value("D", v(np.arange(1, 28)))


def test_empty_numeric():
    assert format_value("x", v(np.zeros((0, 0)))) == "x = []\n"
    assert format_value("x", v(np.zeros((1, 0)))) == "x = 1x0 empty double\n"
    assert format_value("x", v(np.zeros((0, 3), dtype=bool))) == "x = 0x3 empty logical\n"


# --------------------------------------------------------------- char / cell
def test_char():
    assert format_value("s", CharArray.from_str("hello")) == "s = hello\n"
    assert format_value("s", CharArray.from_str("")) == "s = ''\n"
    two = CharArray(np.array([["a", "b"], ["c", "d"]], dtype="<U1"))
    assert format_value("s", two) == "s =\n\nab\ncd\n\n"


def test_cell():
    c = CellArray.from_rows([[1, "a"], [[1, 2, 3], True]])
    expected = (
        "c =\n\n  2x2 cell array\n\n"
        "    {[1]}" + " " * 11 + "{'a'}\n"
        "    {1x3 double}    {[1]}\n\n"
    )
    assert format_value("c", c) == expected
    nested = CellArray.from_rows([[CellArray.from_rows([[1, 2]]), StructValue({"a": 1})]])
    assert "{1x2 cell}    {1x1 struct}" in format_value("c", nested)
    handles = CellArray.from_rows([[FunctionHandle(name="sin"), []]])
    assert "{@sin}    {[]}" in format_value("c", handles)
    assert format_value("c", CellArray.empty(0, 0)) == "c = {}\n"
    assert format_value("c", CellArray.empty(0, 3)) == "c = 0x3 empty cell array\n"


def test_struct():
    s = StructValue({
        "a": 1, "b": "hi", "c": [1, 2, 3], "d": CellArray.from_rows([[1, 2]]),
        "e": StructValue({"z": 1}), "f": [], "g": 2.5, "h": FunctionHandle(name="cos"),
    })
    expected = (
        "s =\n\n  struct with fields:\n\n"
        "    a: 1\n    b: 'hi'\n    c: [1x3 double]\n    d: {1x2 cell}\n"
        "    e: [1x1 struct]\n    f: []\n    g: 2.5000\n    h: @cos\n\n"
    )
    assert format_value("s", s) == expected


def test_function_handles():
    assert format_value("f", FunctionHandle(name="sin")) == (
        "f =\n\n  function_handle with value:\n\n    @sin\n\n")
    assert format_value("f", anon("@(x) x.^2 + 1")) == (
        "f =\n\n  function_handle with value:\n\n    @(x) x.^2 + 1\n\n")
    assert handle_text(anon("@(a, b) a*b")) == "@(a, b) a * b"
    assert handle_text(anon("@() 42")) == "@() 42"


def test_non_values_are_rejected():
    with pytest.raises(ValidationError):
        format_value("x", 5)
    with pytest.raises(ValidationError):
        format_disp("text")


# ---------------------------------------------------------------------- disp
def test_disp():
    assert format_disp(v(5)) == "5\n"
    assert format_disp(v(np.pi)) == "3.1416\n"
    assert format_disp(v([[1, 2], [3, 4]])) == "     1     2\n     3     4\n"
    assert format_disp(v(3 + 4j)) == "3 + 4i\n"
    assert format_disp(v(np.zeros((0, 0)))) == ""
    assert format_disp(CharArray.from_str("hi")) == "hi\n"
    assert format_disp(CharArray.from_str("")) == "\n"
    assert format_disp(CellArray.empty(0, 0)) == "{}\n"
    assert format_disp(CellArray.from_rows([[1]])).startswith("  1x1 cell array\n")
    assert format_disp(StructValue({"a": 1})) == "  struct with fields:\n\n    a: 1\n"
    assert format_disp(anon("@(x) -x")) == "@(x) -x\n"


# ------------------------------------------------------------------- unparse
UNPARSE = [
    ("1+2*3", "1 + 2 * 3"), ("(1+2)*3", "(1 + 2) * 3"), ("-x^2", "-x^2"),
    ("(-x)^2", "(-x)^2"), ("-(a+b)", "-(a + b)"), ("a-(b-c)", "a - (b - c)"),
    ("a-b-c", "a - b - c"), ("2^3^2", "2^3^2"), ("2^(3^2)", "2^(3^2)"),
    ("1:2:10", "1:2:10"), ("1:10", "1:10"), ("(1:3)'", "(1:3)'"), ("x(2:end)", "x(2:end)"),
    ("A(:,1)", "A(:, 1)"), ("c{1}.f(2)", "c{1}.f(2)"), ("[1 -2; 3 4]", "[1, -2; 3, 4]"),
    ("{1, 'a'}", "{1, 'a'}"), ("'it''s'", "'it''s'"), ('"a"', '"a"'), ("3i", "3i"),
    ("1.5", "1.5"), ("@(x) x+1", "@(x) x + 1"), ("@sin", "@sin"),
    ("a && b || c", "a && b || c"), ("a || b && c", "a || b && c"),
    ("(a || b) && c", "(a || b) && c"), ("~(a == b)", "~(a == b)"),
    ("x'", "x'"), ("x.'", "x.'"), ("f(x)(2)", "f(x)(2)"), ("a.^b'", "a.^b'"),
    ("a*-b", "a * -b"), ("2^-1", "2^(-1)"), ("[]", "[]"), ("{}", "{}"),
    ("(a+b)'", "(a + b)'"), ("(a+b).f", "(a + b).f"), ("@(x, y) x.*y", "@(x, y) x .* y"),
]


@pytest.mark.parametrize("src,text", UNPARSE)
def test_unparse_text(src, text):
    assert unparse(expr(src)) == text


ROUND_TRIP = [src for src, _ in UNPARSE] + [
    "x = [1 2; 3 4]", "a(end+1)", "[a -b]", "[a - b]", "{@(x) x+1, 2}",
    "1e-5 + 2.5e10", "a\\b", "a./b.\\c", "(a:b)(2)", "-a'", "~a & b | c",
    "f(1, 'x', [1 2], {3})", "s.a.b.c", "a < b == c", "x(:)'", "@(x) @(y) x + y",
]


@pytest.mark.parametrize("src", ROUND_TRIP)
def test_unparse_round_trips_through_the_parser(src):
    stmt = parse(src).body[0]
    tree = stmt.value if isinstance(stmt, A.Assign) else stmt.expr
    assert parse(unparse(tree)).body[0].expr == tree


def test_unparse_rejects_statements():
    with pytest.raises(ValueError):
        unparse(parse("break").body[0])


def test_short_text_previews():
    assert short_text(v(5)) == "5"
    assert short_text(v(np.pi)) == "3.1416"
    assert short_text(v(3 + 4j)) == "3 + 4i"
    assert short_text(v([1, 2, 3])) == "1x3 double"
    assert short_text(v(np.zeros((0, 0)))) == "[]"
    assert short_text(v([True, False])) == "1x2 logical"
    assert short_text(CharArray.from_str("hi")) == "'hi'"
    assert short_text(CharArray.from_str("a" * 100)).endswith("...'")
    assert len(short_text(CharArray.from_str("a" * 100))) <= 40
    two = CharArray(np.array([["a", "b"], ["c", "d"]], dtype="<U1"))
    assert short_text(two) == "2x2 char"
    assert short_text(CellArray.from_rows([[1, 2]])) == "1x2 cell"
    assert short_text(StructValue({"a": 1})) == "1x1 struct"
    assert short_text(FunctionHandle(name="sin")) == "@sin"
    assert short_text(anon("@(x) x.^2 + 1")) == "@(x) x.^2 + 1"
    long_handle = anon("@(x) x + 1111111111 + 2222222222 + 3333333333 + 4444444444")
    assert short_text(long_handle).endswith("...") and len(short_text(long_handle)) == 40
    with pytest.raises(ValidationError):
        short_text(5)
