"""Tests for engstudio.lang.builtins_core (B1a): expected values are hand-computed or known
mathematical constants; behaviour follows the MATLAB documentation where the module says so."""

import math

import numpy as np
import pytest

from engstudio.lang.builtins_core import UserError, core_functions, format_text, install_core
from engstudio.lang.interp import EvalError, Host, Interpreter
from engstudio.lang.values import CharArray, to_value


class Rec(Host):
    def __init__(self):
        self.written = []
        self.diags = []

    def write(self, text):
        self.written.append(text)

    def diagnostic(self, diagnostic):
        self.diags.append(diagnostic)

    @property
    def text(self):
        return "".join(self.written)


def run(src):
    host = Rec()
    interp = Interpreter(host=host)
    install_core(interp)
    interp.execute(src)
    return interp, host


def val(expr, name="r"):
    interp, _ = run(f"{name} = {expr};")
    return interp.workspace[name]


def check(actual, expected):
    expected = np.asarray(expected)
    assert isinstance(actual, np.ndarray), type(actual)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    if expected.dtype == bool:
        assert actual.dtype == bool
        np.testing.assert_array_equal(actual, expected)
    else:
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-14)


def fails(src, fragment=""):
    with pytest.raises(EvalError) as info:
        run(src)
    assert fragment in str(info.value), str(info.value)
    return info.value


def text(v):
    assert isinstance(v, CharArray)
    return v.to_str()


Z = 1.3169578969248166  # acosh(2) = ln(2 + sqrt(3))

VALUE_CASES = [
    # constants
    ("pi", [[math.pi]]), ("e", [[math.e]]), ("Inf", [[math.inf]]), ("-Inf", [[-math.inf]]),
    ("eps", [[2.220446049250313e-16]]), ("true", [[True]]), ("false", [[False]]),
    ("2*pi", [[2 * math.pi]]), ("1i*1i", [[-1]]),
    # constructors
    ("zeros(2, 3)", np.zeros((2, 3))), ("ones(2)", np.ones((2, 2))),
    ("zeros(0, 3)", np.zeros((0, 3))),
    ("zeros([2 3])", np.zeros((2, 3))), ("zeros(-1)", np.zeros((0, 0))),
    ("zeros(2, 'double')", np.zeros((2, 2))),
    ("eye(2, 3)", [[1, 0, 0], [0, 1, 0]]), ("eye(2)", [[1, 0], [0, 1]]),
    ("linspace(0, 1, 5)", [[0, 0.25, 0.5, 0.75, 1]]), ("linspace(1, 2, 1)", [[2]]),
    ("linspace(0, 1, 0)", np.zeros((1, 0))), ("logspace(0, 2, 3)", [[1, 10, 100]]),
    ("repmat([1 2], 2, 2)", [[1, 2, 1, 2], [1, 2, 1, 2]]), ("repmat([1 2], [1 2])", [[1, 2, 1, 2]]),
    ("repmat(5, 2)", [[5, 5], [5, 5]]),
    ("reshape(1:6, 2, 3)", [[1, 3, 5], [2, 4, 6]]),
    ("reshape(1:6, [], 2)", [[1, 4], [2, 5], [3, 6]]),
    ("reshape(1:6, [3 2])", [[1, 4], [2, 5], [3, 6]]),
    ("reshape(1:6, 3, [])", [[1, 4], [2, 5], [3, 6]]),
    ("diag([1 2 3])", np.diag([1.0, 2, 3])), ("diag([1 2; 3 4])", [[1], [4]]),
    ("diag([1 2], 1)", [[0, 1, 0], [0, 0, 2], [0, 0, 0]]),
    ("triu([1 2 3; 4 5 6; 7 8 9])", [[1, 2, 3], [0, 5, 6], [0, 0, 9]]),
    ("tril([1 2 3; 4 5 6; 7 8 9], -1)", [[0, 0, 0], [4, 0, 0], [7, 8, 0]]),
    ("horzcat([1 2], 3)", [[1, 2, 3]]), ("vertcat([1 2], [3 4])", [[1, 2], [3, 4]]),
    # size and type
    ("size([1 2 3; 4 5 6])", [[2, 3]]), ("size([1 2 3; 4 5 6], 2)", [[3]]),
    ("size(zeros(2, 3), 3)", [[1]]),
    ("numel([1 2; 3 4])", [[4]]), ("length(zeros(3, 5))", [[5]]), ("length([])", [[0]]),
    ("ndims(5)", [[2]]),
    ("isempty(zeros(0, 3))", [[True]]), ("isempty(1)", [[False]]), ("isscalar(5)", [[True]]),
    ("isscalar([1 2])", [[False]]), ("isvector([1 2 3])", [[True]]),
    ("isvector([1 2; 3 4])", [[False]]),
    ("isrow([1 2 3])", [[True]]), ("iscolumn([1; 2])", [[True]]), ("issquare(eye(3))", [[True]]),
    ("isnumeric(5)", [[True]]), ("isnumeric(true)", [[False]]), ("isnumeric('a')", [[False]]),
    ("isreal(1 + 2i)", [[False]]), ("isreal('a')", [[True]]), ("iscomplex(1i)", [[True]]),
    ("islogical(true)", [[True]]), ("ischar('a')", [[True]]), ("iscell({})", [[True]]),
    ("isstruct(5)", [[False]]), ("is_function_handle(@sin)", [[True]]),
    ("isa(1, 'double')", [[True]]), ("isa(1, 'numeric')", [[True]]),
    ("isa(true, 'numeric')", [[False]]),
    ("isa(1, 'float')", [[True]]), ("isa('a', 'char')", [[True]]),
    ("double('a')", [[97]]), ("double(true)", [[1]]), ("logical([1 0 2])", [[True, False, True]]),
    ("isequal([1 2], [1 2])", [[True]]), ("isequal(1, 2)", [[False]]),
    ("isequal('a', 'a')", [[True]]),
    ("isequal(1, 1, 1)", [[True]]), ("isequal(1, 1, 2)", [[False]]),
    ("isequal([1 2], [1 2 3])", [[False]]),
    # elementwise math
    ("abs([-1 2 -3])", [[1, 2, 3]]), ("abs(3 + 4i)", [[5]]), ("sqrt(16)", [[4]]),
    ("sqrt(-4)", [[2j]]), ("sqrt([4 -9])", [[2, 3j]]), ("exp(1)", [[math.e]]),
    ("log(exp(2))", [[2]]), ("log(-1)", [[math.pi * 1j]]), ("log2(8)", [[3]]),
    ("log10(1000)", [[3]]),
    ("sin(pi/2)", [[1]]), ("cos(0)", [[1]]), ("tan(pi/4)", [[1]]), ("asin(1)", [[math.pi / 2]]),
    ("acos(1)", [[0]]), ("atan(1)", [[math.pi / 4]]), ("sinh(0)", [[0]]), ("cosh(0)", [[1]]),
    ("tanh(0)", [[0]]), ("asin(2)", [[math.pi / 2 - Z * 1j]]), ("acos(2)", [[Z * 1j]]),
    ("acos(-2)", [[math.pi - Z * 1j]]), ("asin(-2)", [[-math.pi / 2 + Z * 1j]]),
    ("asin([0.5 1])", [[math.asin(0.5), math.pi / 2]]),
    ("floor([-2.5 2.5])", [[-3, 2]]), ("ceil([-2.5 2.5])", [[-2, 3]]),
    ("round([2.5 -2.5 0.5 1.4])", [[3, -3, 1, 1]]), ("fix([-2.7 2.7])", [[-2, 2]]),
    ("sign([-3 0 2])", [[-1, 0, 1]]), ("floor(2.7 + 3.2i)", [[2 + 3j]]),
    ("mod(-1, 3)", [[2]]), ("mod(5, 0)", [[5]]), ("mod(5.5, 2)", [[1.5]]),
    ("mod([-3 -2 -1 0 1], 3)", [[0, 1, 2, 0, 1]]), ("rem(-1, 3)", [[-1]]),
    ("rem(5, 0)", [[math.nan]]),
    ("atan2(1, 1)", [[math.pi / 4]]), ("hypot(3, 4)", [[5]]), ("real(3 + 4i)", [[3]]),
    ("imag(3 + 4i)", [[4]]), ("conj(3 + 4i)", [[3 - 4j]]), ("angle(1i)", [[math.pi / 2]]),
    ("isnan([1 NaN])", [[False, True]]), ("isinf([1 Inf -Inf])", [[False, True, True]]),
    ("isfinite([1 Inf NaN])", [[True, False, False]]),
    # reductions
    ("sum([1 2 3])", [[6]]), ("sum([1 2; 3 4])", [[4, 6]]), ("sum([1 2; 3 4], 2)", [[3], [7]]),
    ("sum([])", [[0]]), ("sum(zeros(0, 3))", [[0, 0, 0]]), ("sum([true true])", [[2]]),
    ("prod([1 2 3 4])", [[24]]), ("prod([])", [[1]]), ("mean([1 2 3 4])", [[2.5]]),
    ("mean([1 2; 3 4])", [[2, 3]]), ("mean([])", [[math.nan]]),
    ("mean([1 2; 3 4], 2)", [[1.5], [3.5]]),
    ("cumsum([1 2 3])", [[1, 3, 6]]), ("cumsum([1 2; 3 4])", [[1, 2], [4, 6]]),
    ("cumprod([1 2 3 4])", [[1, 2, 6, 24]]), ("any([0 0 1])", [[True]]), ("any([0 0])", [[False]]),
    ("all([1 1])", [[True]]), ("all([1 0])", [[False]]), ("any([])", [[False]]),
    ("all([])", [[True]]),
    ("any([0 1; 0 0])", [[False, True]]),
    ("max([3 1 4 1 5])", [[5]]), ("min([3 1 4])", [[1]]), ("max([1 NaN 3])", [[3]]),
    ("max([NaN NaN])", [[math.nan]]), ("max([1 5 3], [4 2 6])", [[4, 5, 6]]),
    ("max([1 2; 3 0])", [[3, 2]]), ("max([1 2; 3 0], [], 2)", [[2], [3]]),
    ("max(3, [1 5])", [[3, 5]]),
    ("min(NaN, 2)", [[2]]), ("max([])", np.zeros((0, 0))), ("min([4 2; 1 3], [], 1)", [[1, 2]]),
    ("sort([3 1 2])", [[1, 2, 3]]), ("sort([3 1 2], 'descend')", [[3, 2, 1]]),
    ("sort([2 1; 1 3])", [[1, 1], [2, 3]]), ("sort([2 1; 1 3], 2)", [[1, 2], [1, 3]]),
    ("sort([3 NaN 1])", [[1, 3, math.nan]]), ("sort([3 NaN 1], 'descend')", [[math.nan, 3, 1]]),
    ("sort([3; 1; 2])", [[1], [2], [3]]),
    ("find([0 1 0 1])", [[2, 4]]), ("find([0; 1; 1])", [[2], [3]]),
    ("find([0 1; 1 1])", [[2], [3], [4]]),
    ("find([0 0])", np.zeros((1, 0))), ("find(0)", np.zeros((0, 0))),
    ("find([1 1 1], 2)", [[1, 2]]),
    ("find(zeros(2, 2))", np.zeros((0, 1))),
    ("diff([1 4 9 16])", [[3, 5, 7]]), ("diff([1 4 9 16], 2)", [[2, 2]]),
    ("diff([1 2; 4 8])", [[3, 6]]),
    ("diff(5)", np.zeros((0, 0))), ("fliplr([1 2 3])", [[3, 2, 1]]), ("flipud([1; 2])", [[2], [1]]),
    # linear algebra
    ("inv([2 0; 0 4])", [[0.5, 0], [0, 0.25]]), ("inv([1 2; 3 4])", [[-2, 1], [1.5, -0.5]]),
    ("det([1 2; 3 4])", [[-2]]), ("det(eye(3))", [[1]]), ("trace([1 2; 3 4])", [[5]]),
    ("rank([1 2; 2 4])", [[1]]), ("rank(eye(3))", [[3]]), ("cond(eye(2))", [[1]]),
    ("cond([1 0; 0 4])", [[4]]), ("rcond(eye(2))", [[1]]), ("norm([3 4])", [[5]]),
    ("norm([1 2; 3 4], 'fro')", [[math.sqrt(30)]]), ("norm([1 2; 3 4], 1)", [[6]]),
    ("norm([1 2; 3 4], Inf)", [[7]]), ("norm([1 2; 3 4])", [[5.464985704219043]]),
    ("norm([3 4], 1)", [[7]]), ("norm([3 4], Inf)", [[4]]), ("norm([3 4], 'inf')", [[4]]),
    ("dot([1 2 3], [4 5 6])", [[32]]), ("cross([1 0 0], [0 1 0])", [[0, 0, 1]]),
    ("cross([1; 0; 0], [0; 1; 0])", [[0], [0], [1]]),
    # formatting results
    ("double(sprintf('%d', 42))", [[52, 50]]),
]


@pytest.mark.parametrize("expr,expected", VALUE_CASES)
def test_values(expr, expected):
    check(val(expr), expected)


def test_multi_output_builtins():
    it, _ = run("[r, c] = size(zeros(4, 5)); [m, i] = max([1 5 5 2]); [s, k] = sort([2 1 2 1]); "
                "[sd, kd] = sort([2 1 2 1], 'descend'); [q, w] = find([0 1; 1 1]); "
                "[X, Y] = meshgrid(1:3, 10:10:20); [lo, j] = min([4 2 8; 1 9 0], [], 2);")
    ws = it.workspace
    check(ws["r"], [[4]])
    check(ws["c"], [[5]])
    check(ws["m"], [[5]])
    check(ws["i"], [[2]])
    check(ws["k"], [[2, 4, 1, 3]])
    check(ws["kd"], [[1, 3, 2, 4]])
    check(ws["sd"], [[2, 2, 1, 1]])
    check(ws["q"], [[2], [1], [2]])
    check(ws["w"], [[1], [2], [2]])
    check(ws["X"], [[1, 2, 3], [1, 2, 3]])
    check(ws["Y"], [[10, 10, 10], [20, 20, 20]])
    check(ws["lo"], [[2], [0]])
    check(ws["j"], [[2], [3]])


def test_max_picks_first_of_equal_values_and_all_nan_index():
    it, _ = run("[m, i] = max([1 NaN 3 3]); [n, k] = max([NaN NaN]);")
    check(it.workspace["i"], [[3]])
    check(it.workspace["k"], [[1]])


def test_linspace_endpoint_is_exact_and_default_count():
    check(val("linspace(0, 0.3, 4)(end)"), [[0.3]])
    assert val("linspace(0, 10)").shape == (1, 100)


def test_class_names():
    for expr, name in (("1", "double"), ("1i", "double"), ("true", "logical"), ("'a'", "char"),
                       ("{}", "cell"), ("@sin", "function_handle")):
        assert text(val(f"class({expr})")) == name


def test_char_and_logical_conversions():
    assert text(val("char([72 105])")) == "Hi"
    assert text(val("char('x')")) == "x"
    fails("r = char(1.5);", "character codes")
    fails("r = logical(NaN);", "NaN")
    assert val("double('A')").dtype == np.float64


def test_arity_and_type_errors():
    fails("sin()", "Not enough input arguments")
    fails("sin(1, 2)", "Too many input arguments")
    fails("r = sin({});", "must be numeric")
    fails("r = mod(1, {});", "must be numeric")
    fails("r = mod([1 2 3], [1 2]);", "incompatible sizes")
    fails("r = max(1i, 2);", "complex")
    fails("r = max([1 2], 5, 2);", "must be []")
    fails("r = sum([1 2], 3);", "dimension must be 1 or 2")
    fails("r = zeros(1.5);", "integer")
    fails("r = zeros(2, 'int8');", "not supported")
    fails("r = reshape(1:6, 4, 2);", "Number of elements must not change")
    fails("r = reshape(1:6, [], 4);", "cannot be inferred")
    fails("r = sort([1 2], 'sideways');", "ascend")
    fails("r = size(1, 0);", "positive integer")
    fails("r = ones(2, 3, 2);", "2-D")


def test_linear_algebra_errors_and_warnings():
    fails("r = inv([1 2; 2 4]);", "singular")
    fails("r = inv([1 2 3]);", "square")
    fails("r = inv(1 + 2i);", "complex")
    fails("r = cross([1 2], [3 4]);", "3 elements")
    fails("r = dot([1 2], [3 4 5]);", "same number")
    _, host = run("n = 10; H = zeros(n); for i = 1:n, for j = 1:n, H(i, j) = 1/(i+j-1); end; end;"
                  " x = inv(H);")
    assert len(host.diags) == 1 and host.diags[0].code == "ILL_CONDITIONED"
    _, host = run("x = inv([2 0; 0 2]);")
    assert host.diags == []


# --------------------------------------------------------------------- output
FORMAT_CASES = [
    ("%d, ", [1, 2, 3], "1, 2, 3, "), ("%d and %d", [1], "1 and "), ("a%db", [], "ab"),
    ("%d", [1.5], "1.500000e+00"), ("%s", [65], "A"), ("%s", [math.pi], "3.141593e+00"),
    ("%5s|%-5s|", ["ab", "cd"], "   ab|cd   |"), ("%%", [], "%"),
    ("%e", [12345.678], "1.234568e+04"),
    ("%g", [0.0001], "0.0001"), ("%x", [255], "ff"), ("\\n", [], "\n"), ("%d", [math.nan], "NaN"),
    ("%d", [math.inf], "Inf"), ("%.3f", [math.pi], "3.142"), ("%d %s", [5, "x"], "5 x"),
    ("%d,%d;", [np.array([[1, 2], [3, 4]])], "1,3;2,4;"), ("%c%c", ["hi"], "hi"),
    ("%d", ["a"], "97"),
    ("%5.1f|", [2.5], "  2.5|"), ("%+d", [5], "+5"),
    ("%05d", [42], "00042"), ("%i", [7], "7"), ("%s|", [""], "|"), ("hello", [1, 2], "hello"),
    ("%d %d\\n", [1, 2, 3, 4], "1 2\n3 4\n"), ("%s=%d ", ["a", 1, "b", 2], "a=1 b=2 "),
    ("%8.3e", [1234.5], "1.234e+03"),
    ("%c", [72], "H"), ("%s", ["abc", "def"], "abcdef"), ("%d", [-3], "-3"), ("%u", [3], "3"),
    ("%o", [8], "10"), ("%X", [255], "FF"), ("%G", [1e-10], "1E-10"), ("%5d|", [3], "    3|"),
    ("%-5d|", [3], "3    |"), ("%.2s", ["abcdef"], "ab"), ("[%s]", [True], "[\x01]"),
]


@pytest.mark.parametrize("fmt,args,expected", FORMAT_CASES)
def test_format_text(fmt, args, expected):
    values = [to_value(a) for a in args]
    assert format_text(fmt, values) == expected


def test_disp_fprintf_sprintf_through_the_interpreter():
    _, host = run("disp(5); disp([1 2; 3 4]); disp('hi'); fprintf('%5.2f|%s\\n', 3.14159, 'ab'); "
                  "fprintf(1, 'x=%d\\n', 7); fprintf('plain\\n'); disp([]);")
    assert host.text == "5\n     1     2\n     3     4\nhi\n 3.14|ab\nx=7\nplain\n"
    it, _ = run("s = sprintf('%d-%d', 1, 2);")
    assert text(it.workspace["s"]) == "1-2"
    fails("sprintf({})", "character vector")
    fails("sprintf('%d', {1})", "unsupported argument type")
    fails("fprintf()", "Not enough input arguments")


NUM2STR = [
    ("pi", "3.1416"), ("5", "5"), ("1234.56789", "1234.5679"), ("[1 2 3]", "1  2  3"),
    ("true", "1"), ("-0.5", "-0.5"), ("0.5", "0.5"), ("100", "100"), ("1e10", "10000000000"),
    ("123.456", "123.456"), ("NaN", "NaN"), ("-Inf", "-Inf"), ("'text'", "text"),
    ("3 + 4i", "3+4i"),
    ("[1.5 2.5]", "1.5  2.5"), ("[]", ""),
]


@pytest.mark.parametrize("expr,expected", NUM2STR)
def test_num2str(expr, expected):
    assert text(val(f"num2str({expr})")) == expected


def test_num2str_precision_and_format_and_matrix():
    assert text(val("num2str(pi, 8)")) == "3.1415927"
    assert text(val("num2str(2.5, '%6.2f')")) == "  2.50"
    m = val("num2str([1 2; 3 4])")
    assert m.shape == (2, 4) and "".join(m.data[0]) == "1  2" and "".join(m.data[1]) == "3  4"


# --------------------------------------------------------------- error / warning
def test_error_builtin():
    err = fails("error('boom')", "boom")
    assert isinstance(err.__cause__, UserError)
    fails("error('x=%d', 3)", "x=3")
    fails("error('100% sure')", "100% sure")
    it, _ = run("try, error('Mod:id', 'Value %d', 5); "
                "catch e, m = e.message; i = e.identifier; end")
    assert text(it.workspace["m"]) == "Value 5"
    assert text(it.workspace["i"]) == "Mod:id"
    it, _ = run("try, error('plain message'); catch e, i = e.identifier; end")
    assert text(it.workspace["i"]) == ""  # MATLAB: no identifier given -> empty
    fails("error()", "Not enough input arguments")


def test_warning_builtin():
    _, host = run("warning('careful %d', 2); warning('A:b', 'named'); warning('off', 'all');")
    assert [(d.severity, d.code, d.message) for d in host.diags] == [
        ("warning", "W_USER", "careful 2"), ("warning", "A:b", "named")]


def test_core_functions_tables_are_independent_and_host_defaults_are_silent():
    interp = Interpreter()
    first = core_functions(interp)
    del first["sin"]
    assert "sin" in core_functions(interp)
    Interpreter(host=Host())  # the default host ignores write()
    plain = Interpreter()
    install_core(plain)
    plain.execute("disp(1); warning('x');")  # nothing raised, nothing printed
    assert Host().write("x") is None
