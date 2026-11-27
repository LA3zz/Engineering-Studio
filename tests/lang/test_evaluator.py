"""Tests for engstudio.lang.interp (T3.4c): evaluator, workspace, calls, errors, locations."""

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.lang import ast as A
from engstudio.lang.interp import EvalError, Host, Interpreter, Workspace
from engstudio.lang.lexer import LexError
from engstudio.lang.parser import ParseError, parse
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    to_value,
)


class Rec(Host):
    def __init__(self):
        self.shown = []
        self.diags = []

    def display(self, name, value):
        self.shown.append((name, value))

    def diagnostic(self, diagnostic):
        self.diags.append(diagnostic)

    @property
    def names(self):
        return [n for n, _ in self.shown]


def _sin(args, nargout):
    return [np.sin(args[0])]


def _numel(args, nargout):
    return [float(args[0].size)]


def _minmax(args, nargout):
    return [args[0].min(), args[0].max()]


def _add2(args, nargout):
    return [args[0] + args[1]]


def _pi(args, nargout):
    return [np.pi]


def _nothing(args, nargout):
    return []


def _nout(args, nargout):
    return [float(nargout)] * max(nargout, 1)


def _hilb(args, nargout):
    k = int(args[0][0, 0])
    return [np.array([[1.0 / (i + j + 1) for j in range(k)] for i in range(k)])]


def _ones(args, nargout):
    return [np.ones((int(args[0][0, 0]), int(args[1][0, 0])))]


def _fail(args, nargout):
    raise ValidationError("custom failure")


FUNCS = {
    "sin": _sin, "numel": _numel, "minmax": _minmax, "add2": _add2, "pi": _pi,
    "nothing": _nothing, "nout": _nout, "hilb": _hilb, "ones": _ones, "fail": _fail,
}


def run(src, **extra):
    host = Rec()
    interp = Interpreter(functions={**FUNCS, **extra}, host=host)
    interp.execute(src)
    return interp, host


def get(interp, name):
    return interp.workspace[name]


def check(actual, expected):
    expected = np.asarray(expected, dtype=float)
    assert isinstance(actual, np.ndarray)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=1e-15)


def fails(src, fragment="", **extra):
    with pytest.raises(EvalError) as info:
        run(src, **extra)
    assert fragment in str(info.value), str(info.value)
    return info.value


# ------------------------------------------------------------- arithmetic
def test_scalar_arithmetic():
    it, _ = run("x = 1 + 2*3; y = (1+2)*3^2; z = -2^2; w = 2^-1; q = 7/2;")
    check(get(it, "x"), [[7]])
    check(get(it, "y"), [[27]])
    check(get(it, "z"), [[-4]])
    check(get(it, "w"), [[0.5]])
    check(get(it, "q"), [[3.5]])


def test_matrix_operations():
    it, _ = run("A = [1 2; 3 4]; B = A*A'; C = A.*A; D = A.'; E = A + [10; 20];")
    check(get(it, "B"), [[5, 11], [11, 25]])
    check(get(it, "C"), [[1, 4], [9, 16]])
    check(get(it, "D"), [[1, 3], [2, 4]])
    check(get(it, "E"), [[11, 12], [23, 24]])


def test_left_division_solves_linear_system():
    # [1 2;3 4]\[5;6] = [-4; 4.5]: -4 + 9 = 5 and -12 + 18 = 6
    it, _ = run("x = [1 2; 3 4] \\ [5; 6]; y = [5 6] / [1 2; 3 4];")
    check(get(it, "x"), [[-4], [4.5]])
    check(get(it, "y"), [[-1, 2]])


def test_ranges_and_logicals():
    it, _ = run("n = 3; r = 1:n; s = 10:-5:0; t = (1:5) > 2; u = ~t;")
    check(get(it, "r"), [[1, 2, 3]])
    check(get(it, "s"), [[10, 5, 0]])
    assert get(it, "t").dtype == np.bool_
    np.testing.assert_array_equal(get(it, "u"), [[True, True, False, False, False]])


def test_complex_numbers():
    it, _ = run("z = 3 + 4i; w = z'; m = z*z;")
    assert get(it, "w")[0, 0] == 3 - 4j
    assert get(it, "m")[0, 0] == -7 + 24j


def test_char_operations():
    it, _ = run("s = 'abc'; t = [s 'def']; u = s(2); eq = s == 'abc';")
    assert get(it, "t") == CharArray.from_str("abcdef")
    assert get(it, "u") == CharArray.from_str("b")
    np.testing.assert_array_equal(get(it, "eq"), [[True, True, True]])


# ------------------------------------------------------------ display / ans
def test_display_rules_and_ans():
    it, host = run("x = 5\ny = 6;\nx\nx;\n3 + 4\nx + 1;\nz = x")
    assert host.names == ["x", "x", "ans", "z"]
    check(get(it, "ans"), [[6]])  # last unsuppressed or suppressed expression sets ans
    check(host.shown[2][1], [[7]])


def test_assignment_does_not_set_ans_and_variable_statement_keeps_it():
    it, _ = run("x = 5; x")
    assert "ans" not in it.workspace
    it, _ = run("x = 5; x(1)")
    check(get(it, "ans"), [[5]])


def test_multi_assign_displays_each_target_in_order():
    it, host = run("[lo, hi] = minmax([3 1 2])")
    assert host.names == ["lo", "hi"]
    check(get(it, "lo"), [[1]])
    check(get(it, "hi"), [[3]])


def test_nested_assignment_displays_root_variable():
    _, host = run("s.a = 1\nx(2) = 5\n")
    assert host.names == ["s", "x"]


# ----------------------------------------------------------------- indexing
def test_vector_indexing_with_end():
    it, _ = run("v = 10:10:50; a = v(end); b = v([1 end]); c = v(end-1:end); "
                "w = v(v > 25); h = v((end+1)/2);")
    check(get(it, "a"), [[50]])
    check(get(it, "b"), [[10, 50]])
    check(get(it, "c"), [[40, 50]])
    check(get(it, "w"), [[30, 40, 50]])
    check(get(it, "h"), [[30]])


def test_growth_deletion_and_masks():
    it, _ = run("v = 10:10:50; v(end+1) = 60; v(2) = []; m = v; m(m > 40) = 0;")
    check(get(it, "v"), [[10, 30, 40, 50, 60]])
    check(get(it, "m"), [[10, 30, 40, 0, 0]])


def test_matrix_indexing():
    it, _ = run("A = [1 2 3; 4 5 6]; r = A(2,:); c = A(:,1)'; e = A(end,end); n = A(end); "
                "A(1,2) = 20; B = A; B(:,1) = [];")
    check(get(it, "r"), [[4, 5, 6]])
    check(get(it, "c"), [[1, 4]])
    check(get(it, "e"), [[6]])
    check(get(it, "n"), [[6]])
    check(get(it, "A"), [[1, 20, 3], [4, 5, 6]])
    check(get(it, "B"), [[20, 3], [5, 6]])


def test_values_are_immutable_across_assignments():
    it, _ = run("A = [1 2 3]; B = A; B(1) = 99;")
    check(get(it, "A"), [[1, 2, 3]])
    check(get(it, "B"), [[99, 2, 3]])


def test_variable_shadows_function():
    it, _ = run("sin = [1 2 3]; a = sin(2);")
    check(get(it, "a"), [[2]])


# --------------------------------------------------------------- cells / structs
def test_cells():
    it, _ = run("c = {1, 'a'}; d = c{2}; c{3} = [1 2 3]; e = c{3}(2); m = [c{1} c{1}]; "
                "q = {c{1:2}}; k = c(2);")
    assert get(it, "d") == CharArray.from_str("a")
    check(get(it, "e"), [[2]])
    check(get(it, "m"), [[1, 1]])
    assert isinstance(get(it, "q"), CellArray) and get(it, "q").shape == (1, 2)
    assert isinstance(get(it, "k"), CellArray) and get(it, "k").shape == (1, 1)
    assert get(it, "c").shape == (1, 3)


def test_cs_lists_expand_in_matrices_and_calls():
    it, _ = run("c = {1, 2}; m = [c{:}]; r = add2(c{:});")
    check(get(it, "m"), [[1, 2]])
    check(get(it, "r"), [[3]])


def test_structs():
    it, _ = run("s.a = 1; s.b.c = 2; t = s.b.c; s.a = s.a + 1; s.list{2} = 5; x.y(3) = 7;")
    check(get(it, "t"), [[2]])
    check(get(it, "s").get("a"), [[2]])
    assert isinstance(get(it, "s").get("list"), CellArray)
    assert get(it, "s").get("list").shape == (1, 2)
    check(get(it, "x").get("y"), [[0, 0, 7]])
    assert isinstance(get(it, "s").get("b"), StructValue)


def test_cell_of_structs_and_handles():
    it, _ = run("c = {@(x) x + 1}; r = c{1}(2); d{2}.f = 3; g = d{2}.f;")
    check(get(it, "r"), [[3]])
    check(get(it, "g"), [[3]])


# ----------------------------------------------------------- short circuit
def test_short_circuit():
    it, _ = run("a = 0 && undefined_name; b = 1 || undefined_name; c = 1 && 2; d = 0 || 0;")
    for name, expected in (("a", False), ("b", True), ("c", True), ("d", False)):
        assert get(it, name).dtype == np.bool_
        assert bool(get(it, name)[0, 0]) is expected
    fails("x = [1 1] && 1;", "logical scalar")
    fails("x = 1 && undefined_name;", "Undefined function or variable 'undefined_name'")


# --------------------------------------------------------------- functions
def test_function_calls_and_zero_arg_functions():
    it, _ = run("a = sin(0); b = pi; c = pi + 1;")
    check(get(it, "a"), [[0]])
    check(get(it, "b"), [[np.pi]])
    check(get(it, "c"), [[np.pi + 1]])


def test_function_without_output():
    it, host = run("nothing()\nnothing")
    assert host.shown == [] and "ans" not in it.workspace
    fails("x = nothing();", "right-hand side produced no value")


def test_nargout_is_passed():
    it, _ = run("[a, b, c] = nout(); d = nout(); nout();")
    for name in ("a", "b", "c"):
        check(get(it, name), [[3]])
    check(get(it, "d"), [[1]])
    check(get(it, "ans"), [[0]])  # a statement call passes nargout=0 and keeps one value


def test_multiple_outputs_and_tilde():
    it, _ = run("[~, hi] = minmax([4 9 2]);")
    check(get(it, "hi"), [[9]])
    assert "lo" not in it.workspace
    fails("[a, b] = 5;", "Too many output arguments")
    fails("[a, b] = sin(1);", "Too many output arguments")


def test_function_errors_become_eval_errors_with_cause():
    err = fails("x = 1;\ny = fail(x);", "custom failure")
    assert isinstance(err.__cause__, ValidationError)
    assert (err.location.line, err.location.col) == (2, 5)


# --------------------------------------------------------- function handles
def test_anonymous_functions():
    it, _ = run("f = @(x) x.^2 + 1; y = f(3); g = @(x, y) x + y; z = g(1, 2); h = @() 42; w = h();")
    check(get(it, "y"), [[10]])
    check(get(it, "z"), [[3]])
    check(get(it, "w"), [[42]])
    assert isinstance(get(it, "f"), FunctionHandle) and get(it, "f").is_anonymous


def test_captured_variables_are_frozen_at_creation():
    it, _ = run("k = 2; g = @(x) k*x; k = 5; r = g(3);")
    check(get(it, "r"), [[6]])


def test_nested_anonymous_functions_and_named_handles():
    it, _ = run("adder = @(x) @(y) x + y; add3 = adder(3); r = add3(4); "
                "h = @sin; s = h(0); v = h([0 0]);")
    check(get(it, "r"), [[7]])
    check(get(it, "s"), [[0]])
    check(get(it, "v"), [[0, 0]])


def test_handle_errors():
    fails("f = @(x) x; f(1, 2)", "Too many input arguments")
    fails("h = @nope; h(1)", "Undefined function 'nope'")
    fails("f = @(x) y_undefined; f(1)", "Undefined function or variable 'y_undefined'")


def test_recursion_limit():
    interp = Interpreter(functions=FUNCS, max_depth=2)
    with pytest.raises(EvalError, match="Maximum recursion limit of 2"):
        interp.execute("f = @(x) x; g = @(x) f(x); h = @(x) g(x); h(1)")
    ok = Interpreter(functions=FUNCS)
    ok.execute("f = @(x) x; g = @(x) f(x); h = @(x) g(x); r = h(1);")
    check(ok.workspace["r"], [[1]])


# --------------------------------------------------------------- diagnostics
def test_ill_conditioned_division_reports_a_warning():
    it, host = run("x = hilb(10) \\ ones(10, 1);")
    assert get(it, "x").shape == (10, 1)
    assert len(host.diags) == 1 and host.diags[0].code == "ILL_CONDITIONED"
    _, host = run("x = [2 0; 0 2] \\ [1; 1];")
    assert host.diags == []


# -------------------------------------------------------------------- errors
def test_error_locations():
    err = fails("y = [1 2 3] * [4 5 6];", "matrix multiplication")
    assert isinstance(err.__cause__, DimensionError)
    assert (err.location.line, err.location.col) == (1, 13)  # the '*' operator
    err = fails("x = undefined_thing + 1", "Undefined function or variable 'undefined_thing'")
    assert (err.location.line, err.location.col) == (1, 5)
    err = fails("a = 1;\nb = a(5);", "must not exceed 1")
    assert (err.location.line, err.location.col) == (2, 5)
    err = fails("v = 1:3;\n\nv(0)", "positive integers")
    assert err.location.line == 3


def test_more_runtime_errors():
    fails("x = 1; x.y", "Dot indexing")
    fails("c = {1,2}; x = c{[]};", "but there were 0 results")
    fails("c = {1,2}; x = c{:} + 1;", "but there were 2 results")
    it, _ = run("c = {7, 8}; x = c{:};")
    check(get(it, "x"), [[7]])  # assignment takes the first element of a comma-separated list
    fails("x = f(end);", "'end' is only valid", f=_pi)
    fails("A = [1 2; 3 4]; A(3, 1)", "position 1 exceeds array bounds")
    fails("x = {1} + 1;", "undefined for cell")


def test_syntax_errors_propagate_from_execute():
    interp = Interpreter(functions=FUNCS)
    with pytest.raises(ParseError):
        interp.execute("x = * 3")
    with pytest.raises(LexError):
        interp.execute("x = (1 + 2")


def test_run_accepts_a_parsed_program():
    interp = Interpreter(functions=FUNCS)
    interp.run(parse("x = 2 + 3;"))
    check(interp.workspace["x"], [[5]])
    assert isinstance(parse("x = 1;"), A.Program)


# ----------------------------------------------------------------- workspace
def test_workspace_api():
    ws = Workspace()
    ws["a"] = to_value(1)
    ws["s"] = CharArray.from_str("hi")
    assert ws.names() == ["a", "s"] and len(ws) == 2 and "a" in ws
    assert ws.summary() == [("a", "double", (1, 1)), ("s", "char", (1, 2))]
    ws.clear("a", "missing")
    assert ws.names() == ["s"]
    ws.clear()
    assert len(ws) == 0
    with pytest.raises(ValidationError):
        ws["1bad"] = to_value(1)
    with pytest.raises(ValidationError):
        ws["x"] = 5
    del_ws = Workspace()
    del_ws["q"] = to_value(2)
    del del_ws["q"]
    assert "q" not in del_ws


def test_interpreter_uses_a_shared_workspace():
    ws = Workspace()
    ws["seed"] = to_value(10)
    interp = Interpreter(workspace=ws, functions=FUNCS)
    interp.execute("y = seed * 2;")
    check(ws["y"], [[20]])
