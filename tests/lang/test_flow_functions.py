"""Tests for control flow, user functions, cancellation and stack frames in lang.interp (T3.5)."""

import sys
import threading

import numpy as np
import pytest

from engstudio.core.errors import ValidationError
from engstudio.lang.interp import Cancelled, EvalError, Host, Interpreter
from engstudio.lang.values import CellArray, CharArray, to_value


class Rec(Host):
    def __init__(self):
        self.shown = []

    def display(self, name, value):
        self.shown.append((name, value))


def _numel(args, nargout):
    v = args[0]
    return [float(v.size if isinstance(v, np.ndarray) else v.data.size)]


def _fail(args, nargout):
    raise ValidationError("custom failure")


def _sin(args, nargout):
    return [np.sin(args[0])]


FUNCS = {"numel": _numel, "fail": _fail, "sin": _sin}


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


# ------------------------------------------------------------------------- if
def test_if_elseif_else():
    src = "x = %d; if x < 3, r = 1; elseif x < 10, r = 2; else r = 3; end"
    for x, expected in ((1, 1), (5, 2), (50, 3)):
        it, _ = run(src % x)
        check(get(it, "r"), [[expected]])


def test_if_conditions_use_all_nonzero_rule():
    for cond, expected in (("[1 1 0]", 0), ("[1 1]", 1), ("[]", 0), ("'a'", 1), ("0", 0)):
        it, _ = run(f"r = 0; if {cond}, r = 1; end")
        check(get(it, "r"), [[expected]])


def test_if_condition_errors_have_locations():
    err = fails("if {1}, end", "Conversion to logical from cell")
    assert (err.location.line, err.location.col) == (1, 4)
    fails("if 0/0, end", "NaN")


def test_unmatched_if_runs_nothing():
    it, _ = run("x = 1; if 0, x = 2; elseif 0, x = 3; end")
    check(get(it, "x"), [[1]])


# ------------------------------------------------------------------------ for
def test_for_sum_and_final_value():
    it, _ = run("s = 0; for i = 1:10, s = s + i; end")
    check(get(it, "s"), [[55]])
    check(get(it, "i"), [[10]])


def test_for_break_and_continue():
    it, _ = run("s = 0; for i = 1:5, if i == 3, continue; end; s = s + i; end")
    check(get(it, "s"), [[12]])
    it, _ = run("s = 0; for i = 1:10, if i > 3, break; end; s = i; end")
    check(get(it, "s"), [[3]])
    it, _ = run("c = 0; for i = 1:3, for j = 1:3, if j == 2, break; end; c = c + 1; end; end")
    check(get(it, "c"), [[3]])


def test_for_iterates_over_columns():
    it, _ = run("acc = []; for c = [1 2; 3 4], acc(end+1) = c(1)*10 + c(2); end")
    check(get(it, "acc"), [[13, 24]])
    it, _ = run("n = 0; for e = {1, 'a'}, n = n + 1; last = e; end")
    check(get(it, "n"), [[2]])
    last = get(it, "last")
    assert isinstance(last, CellArray) and last.shape == (1, 1)
    assert last.data[0, 0] == CharArray.from_str("a")
    it, _ = run("t = ''; for ch = 'ab', t = [ch t]; end")
    assert get(it, "t") == CharArray.from_str("ba")
    it, _ = run("for i = 5, v = i; end")
    check(get(it, "v"), [[5]])


def test_for_with_no_columns_runs_zero_times():
    it, _ = run("for i = 1:0, x = 1; end")
    assert "x" not in it.workspace and get(it, "i").shape == (1, 0)
    it, _ = run("m = [1 2; 3 4]; for i = m(:, []), x = 1; end")
    assert "x" not in it.workspace


def test_for_displays_unsuppressed_statements_each_iteration():
    _, host = run("for i = 1:3\n  y = i\nend")
    assert [n for n, _ in host.shown] == ["y", "y", "y"]


# ---------------------------------------------------------------------- while
def test_while_loops():
    it, _ = run("n = 5; f = 1; while n > 1, f = f * n; n = n - 1; end")
    check(get(it, "f"), [[120]])
    it, _ = run("n = 0; while 1, n = n + 1; if n > 3, break; end; end")
    check(get(it, "n"), [[4]])
    it, _ = run("n = 0; while 0, n = 1; end")
    check(get(it, "n"), [[0]])
    it, _ = run("n = 0; m = 0; while n < 5, n = n + 1; if n == 2, continue; end; m = m + 1; end")
    check(get(it, "m"), [[4]])


# --------------------------------------------------------------------- switch
def test_switch_numeric_string_cell_otherwise():
    num = "switch %d, case 1, r = 10; case 2, r = 20; otherwise, r = 99; end"
    for x, expected in ((1, 10), (2, 20), (7, 99)):
        it, _ = run(num % x)
        check(get(it, "r"), [[expected]])
    txt = "switch '%s', case 'a', r = 1; case {'b', 'c'}, r = 2; otherwise, r = 3; end"
    for word, expected in (("a", 1), ("c", 2), ("A", 3), ("zz", 3)):
        it, _ = run(txt % word)
        check(get(it, "r"), [[expected]])
    it, _ = run("switch 3, case {1, 2, 3}, r = 1; end")
    check(get(it, "r"), [[1]])


def test_switch_without_match_and_type_mismatch():
    it, _ = run("r = 0; switch 5, case 1, r = 1; end")
    check(get(it, "r"), [[0]])
    it, _ = run("r = 0; switch 1, case '1', r = 1; case 1, r = 2; end")
    check(get(it, "r"), [[2]])  # no fall-through and no cross-type match
    it, _ = run("r = 0; switch 'a', case 97, r = 1; otherwise, r = 2; end")
    check(get(it, "r"), [[2]])


def test_switch_subject_errors():
    fails("switch [1 2], case 1, end", "scalar or character vector")
    fails("switch {1}, case 1, end", "scalar or character vector")


# ------------------------------------------------------------------ try/catch
def test_try_catch_binds_message_and_identifier():
    it, _ = run("try, x = undefined_name; catch err, msg = err.message; id = err.identifier; end")
    assert get(it, "msg") == CharArray.from_str("Undefined function or variable 'undefined_name'.")
    assert get(it, "id") == CharArray.from_str("E_EVAL")
    it, _ = run("try, fail(); catch err, msg = err.message; end")
    assert get(it, "msg") == CharArray.from_str("custom failure")


def test_try_catch_details():
    it, _ = run("try, a = 1; fail(); b = 2; catch, c = 3; end")
    check(get(it, "a"), [[1]])
    assert "b" not in it.workspace
    check(get(it, "c"), [[3]])
    it, _ = run("try, x = 1; catch, x = 2; end")
    check(get(it, "x"), [[1]])
    fails("try, fail(); catch, fail(); end", "custom failure")
    it, _ = run("last = 0; for i = 1:5, try, if i == 2, break; end; catch, end; last = i; end")
    check(get(it, "last"), [[1]])
    it, _ = run("n = 0; for i = 1:3, try, fail(); catch, n = n + 1; continue; end; n = 100; end")
    check(get(it, "n"), [[3]])


def test_break_continue_return_at_top_level():
    fails("break", "only valid inside a loop")
    fails("continue", "only valid inside a loop")
    it, _ = run("x = 1; return; x = 2;")
    check(get(it, "x"), [[1]])
    fails("function f(), break; end\nf()", "only valid inside a loop")


# ----------------------------------------------------------- user functions
def test_function_definition_and_call_order():
    it, _ = run("function y = sq(x)\n y = x^2;\nend\nr = sq(4);")
    check(get(it, "r"), [[16]])
    it, _ = run("r = sq(5);\nfunction y = sq(x)\n y = x^2;\nend")  # defined after use
    check(get(it, "r"), [[25]])


def test_functions_persist_between_executions():
    interp = Interpreter(functions=FUNCS)
    interp.execute("function y = sq(x), y = x^2; end")
    interp.execute("r = sq(3);")
    check(interp.workspace["r"], [[9]])


def test_multiple_outputs_and_no_outputs():
    it, _ = run("function [s, p] = sp(a, b), s = a + b; p = a * b; end\n[s, p] = sp(3, 4);")
    check(get(it, "s"), [[7]])
    check(get(it, "p"), [[12]])
    seen = []
    it, host = run("function show(x), disp(x); end\nshow(5)",
                   disp=lambda args, nargout: seen.append(float(args[0][0, 0])) or [])
    assert seen == [5.0] and "ans" not in it.workspace and host.shown == []
    it, _ = run("function [a, b] = two(), a = 1; b = 2; end\nx = two();")
    check(get(it, "x"), [[1]])


def test_nargin_nargout_varargin_varargout():
    it, _ = run("function [a, b] = f(x, y), a = nargin; b = nargout; end\n"
                "[p, q] = f(1); r = f();")
    check(get(it, "p"), [[1]])
    check(get(it, "q"), [[2]])
    check(get(it, "r"), [[0]])
    it, _ = run("function n = cnt(varargin), n = numel(varargin); end\n"
                "a = cnt(); b = cnt(1, 2, 3);")
    check(get(it, "a"), [[0]])
    check(get(it, "b"), [[3]])
    it, _ = run("function s = tail(a, varargin), s = varargin{1}; end\nr = tail(1, 7, 8);")
    check(get(it, "r"), [[7]])
    it, _ = run("function varargout = multi(), varargout{1} = 10; varargout{2} = 20; end\n"
                "[a, b] = multi();")
    check(get(it, "a"), [[10]])
    check(get(it, "b"), [[20]])
    fails("function varargout = multi(), varargout{1} = 10; end\n[a, b, c] = multi();",
          "Too many output arguments")
    it, _ = run("function varargout = pass(varargin), varargout = varargin; end\n"
                "[a, b] = pass(1, 2);")
    check(get(it, "b"), [[2]])


def test_recursion():
    fact = "function y = fact(n)\n if n <= 1, y = 1; else y = n * fact(n - 1); end\nend\n"
    it, _ = run(fact + "r = fact(10);")
    check(get(it, "r"), [[3628800]])
    fib = "function y = fib(n)\n if n < 2, y = n; else y = fib(n-1) + fib(n-2); end\nend\n"
    it, _ = run(fib + "r = fib(10);")
    check(get(it, "r"), [[55]])
    even = ("function y = ev(n), if n == 0, y = 1; else y = od(n - 1); end, end\n"
            "function y = od(n), if n == 0, y = 0; else y = ev(n - 1); end, end\n")
    it, _ = run(even + "a = ev(10); b = ev(7);")
    check(get(it, "a"), [[1]])
    check(get(it, "b"), [[0]])


def test_recursion_limit_and_python_limit_restored():
    before = sys.getrecursionlimit()
    fails("function r(n), r(n + 1); end\nr(1)", "Maximum recursion limit of 256 reached.")
    assert sys.getrecursionlimit() == before
    deep = "function y = s(n), if n == 0, y = 0; else y = 1 + s(n - 1); end, end\nr = s(200);"
    it, _ = run(deep)
    check(get(it, "r"), [[200]])
    assert sys.getrecursionlimit() == before


def test_function_scope_is_isolated():
    fails("g = 5;\nfunction y = h(), y = g; end\nr = h();", "Undefined function or variable 'g'")
    it, _ = run("function y = m(x), x(1) = 99; y = x; end\na = [1 2]; b = m(a);")
    check(get(it, "a"), [[1, 2]])
    check(get(it, "b"), [[99, 2]])
    it, _ = run("function f(), 3 + 4; end\nf()")
    assert "ans" not in it.workspace
    _, host = run("function f(), x = 3, end\nf()")
    assert [n for n, _ in host.shown] == ["x"]


def test_function_argument_and_output_errors():
    fails("function y = sq(x), y = x^2; end\nsq(1, 2)", "Too many input arguments")
    fails("function y = sq(x), y = x^2; end\n[a, b] = sq(2);", "Too many output arguments")
    fails("function y = bad(), end\nr = bad();", "Output argument 'y'")
    run("function y = bad(), end\nbad()")  # nargout=0: not an error
    fails("function show(), end\nx = show();", "Too many output arguments")


def test_early_return_and_end_in_function():
    src = "function y = early(x), y = 1; if x > 0, return; end; y = 2; end\n"
    it, _ = run(src + "a = early(1); b = early(-1);")
    check(get(it, "a"), [[1]])
    check(get(it, "b"), [[2]])
    it, _ = run("function y = lastel(v), y = v(end); end\nr = lastel([4 5 6]);")
    check(get(it, "r"), [[6]])


def test_name_resolution_order():
    it, _ = run("function y = sin(x), y = 42; end\nr = sin(0);")
    check(get(it, "r"), [[42]])  # user function beats registered function
    it, _ = run("function y = sq(x), y = x^2; end\nsq = [7 8 9]; r = sq(2);")
    check(get(it, "r"), [[8]])  # variable beats function
    it, _ = run("function y = five(), y = 5; end\nr = five + 1;")
    check(get(it, "r"), [[6]])
    it, _ = run("function y = sq(x), y = x^2; end\nv = 1:5; r = v(sq(2) - 1);")
    check(get(it, "r"), [[3]])


def test_handles_to_user_functions_and_python_call_api():
    it, _ = run("function y = sq(x), y = x^2; end\n"
                "h = @sq; r = h(3); g = @(t) sq(t) + 1; s = g(2);")
    check(get(it, "r"), [[9]])
    check(get(it, "s"), [[5]])
    out = it.call("sq", [to_value(3)])
    check(out[0], [[9]])
    out = it.call(get(it, "g"), [to_value(4)])
    check(out[0], [[17]])
    with pytest.raises(EvalError, match="Undefined function 'nope'"):
        it.call("nope", [])


def test_error_stack_frames():
    src = (
        "function a()\n  b();\nend\n"
        "function b()\n  c();\nend\n"
        "function c()\n  undefined_xyz;\nend\n"
        "a();\n"
    )
    err = fails(src, "Undefined function or variable 'undefined_xyz'")
    assert (err.location.line, err.location.col) == (8, 3)
    assert [(name, loc.line) for name, loc in err.stack] == [("c", 5), ("b", 2), ("a", 10)]


# ------------------------------------------------------------------- cancel
def _run_in_thread(interp, source):
    outcome = {}

    def target():
        try:
            interp.execute(source)
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=target)
    thread.start()
    return thread, outcome


@pytest.mark.parametrize("source", [
    "x = 0; while 1, x = x + 1; end",
    "while 1, end",
    "for i = 1:1e6, end",
    "function f(), while 1, end, end\nf()",
    "try, while 1, end; catch, y = 1; end",
])
def test_cancel_stops_loops_and_is_not_caught(source):
    interp = Interpreter(functions=FUNCS)
    thread, outcome = _run_in_thread(interp, source)
    threading.Event().wait(0.05)
    interp.cancel()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert isinstance(outcome.get("error"), Cancelled)
    assert "y" not in interp.workspace
    interp.execute("z = 1;")  # the cancel flag is reset by the next run
    check(interp.workspace["z"], [[1]])


def test_cancel_before_start_is_kept_when_reset_is_disabled():
    interp = Interpreter(functions=FUNCS)
    interp.cancel()
    with pytest.raises(Cancelled):
        interp.execute("x = 1;", reset_cancel=False)
    assert "x" not in interp.workspace
    interp.clear_cancel()
    interp.execute("x = 1;", reset_cancel=False)
    check(interp.workspace["x"], [[1]])
    interp.cancel()
    interp.execute("y = 2;")  # the default resets a stale cancel
    check(interp.workspace["y"], [[2]])
