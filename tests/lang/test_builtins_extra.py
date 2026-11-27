"""Tests for engstudio.lang.builtins_extra (B1b): structs, cells, cellfun/arrayfun, sets,
operator functions, random numbers and timing."""

import numpy as np
import pytest

from engstudio.core.errors import NotSupportedError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.interp import EvalError, Host, Interpreter
from engstudio.lang.values import CellArray, CharArray, FunctionHandle, StructValue


class Rec(Host):
    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)


def make():
    host = Rec()
    interp = Interpreter(host=host)
    install_core(interp)
    install_extra(interp)
    return interp, host


def run(src):
    interp, host = make()
    interp.execute(src)
    return interp.workspace, host


def val(expr):
    return run(f"r = {expr};")[0]["r"]


def check(actual, expected):
    expected = np.asarray(expected)
    assert isinstance(actual, np.ndarray), type(actual)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    if expected.dtype == bool:
        assert actual.dtype == bool
        np.testing.assert_array_equal(actual, expected)
    else:
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-14)


def text(v):
    assert isinstance(v, CharArray), type(v)
    return v.to_str()


def fails(src, fragment=""):
    with pytest.raises(EvalError) as info:
        run(src)
    assert fragment in str(info.value), str(info.value)
    return info.value


# ----------------------------------------------------------------- struct, cell
def test_struct_construction_and_access():
    ws, _ = run("s = struct('a', 1, 'b', 'x'); f = fieldnames(s); n = numfields(s); "
                "t = struct(); u = struct('a', {5});")
    s = ws["s"]
    assert isinstance(s, StructValue) and s.names() == ("a", "b")
    assert isinstance(ws["f"], CellArray) and ws["f"].shape == (2, 1)
    assert [text(x) for x in ws["f"].data.ravel()] == ["a", "b"]
    check(ws["n"], [[2]])
    assert ws["t"].names() == () and ws["u"].get("a")[0, 0] == 5.0


def test_struct_helpers():
    ws, _ = run("s = struct('a', 1, 'b', 2); r = rmfield(s, 'a'); g = getfield(s, 'b'); "
                "t = setfield(s, 'c', 3); e = fieldnames(struct());")
    assert ws["r"].names() == ("b",) and ws["s"].names() == ("a", "b")
    check(ws["g"], [[2]])
    assert ws["t"].names() == ("a", "b", "c")
    assert ws["e"].shape == (0, 1)


def test_isfield():
    ws, _ = run("s = struct('a', 1); x = isfield(s, 'a'); y = isfield(s, {'a', 'z'}); "
                "z = isfield(5, 'a'); w = isfield(s, 5);")
    check(ws["x"], [[True]])
    check(ws["y"], [[True, False]])
    check(ws["z"], [[False]])
    check(ws["w"], [[False]])


def test_struct_errors():
    fails("s = struct('a');", "field/value pairs")
    fails("s = struct('a', {1, 2});", "struct arrays")
    fails("s = struct('1bad', 1);", "invalid field name")
    fails("f = fieldnames(5);", "must be a struct")
    fails("s = rmfield(struct('a', 1), 'z');", "does not exist")
    with pytest.raises(EvalError) as info:
        run("s = struct('a', {1, 2});")
    assert isinstance(info.value.__cause__, NotSupportedError)


def test_cell_helpers():
    ws, _ = run("c = cell(2, 3); d = cell(2); k = iscellstr({'a', 'b'}); j = iscellstr({'a', 1}); "
                "m = cell2mat({1 2; 3 4}); n = cell2mat({[1 2], 3; [4 5], 6}); "
                "p = num2cell([1 2; 3 4]); q = cell2mat({});")
    assert ws["c"].shape == (2, 3) and ws["d"].shape == (2, 2)
    assert all(x.shape == (0, 0) for x in ws["c"].data.ravel())
    check(ws["k"], [[True]])
    check(ws["j"], [[False]])
    check(ws["m"], [[1, 2], [3, 4]])
    check(ws["n"], [[1, 2, 3], [4, 5, 6]])
    assert ws["p"].shape == (2, 2) and ws["p"].data[1, 0][0, 0] == 3.0
    assert ws["q"].shape == (0, 0)


def test_deal():
    ws, _ = run("[a, b] = deal(1, 2); [c, d] = deal(7); e = deal(9);")
    check(ws["a"], [[1]])
    check(ws["b"], [[2]])
    check(ws["c"], [[7]])
    check(ws["d"], [[7]])
    check(ws["e"], [[9]])
    fails("[a, b] = deal(1, 2, 3);", "number of outputs")


# ------------------------------------------------------------ cellfun / arrayfun
UNIFORM_CASES = [
    ("cellfun(@numel, {'ab', 'c', ''})", [[2, 1, 0]]),
    ("cellfun('isempty', {1, [], 'a', ''})", [[False, True, False, True]]),
    ("cellfun(@(x) x*2, {1, 2, 3})", [[2, 4, 6]]),
    ("cellfun(@(a, b) a + b, {1, 2}, {10, 20})", [[11, 22]]),
    ("cellfun(@(x) x*2, {1, 2; 3, 4})", [[2, 4], [6, 8]]),
    ("cellfun(@numel, {})", np.zeros((0, 0))),
    ("cellfun(@plus, {1, 2}, {3, 4})", [[4, 6]]),
    ("arrayfun(@(x) x^2, [1 2 3])", [[1, 4, 9]]),
    ("arrayfun(@(x) x^2, [1 2; 3 4])", [[1, 4], [9, 16]]),
    ("arrayfun(@(c) numel(c{1}), {'ab', 'c'})", [[2, 1]]),
    ("arrayfun(@(c) double(c), 'ab')", [[97, 98]]),
    ("arrayfun(@times, [1 2 3], [4 5 6])", [[4, 10, 18]]),
    ("arrayfun(@(x) x > 1, [1 2 3])", [[False, True, True]]),
    ("cellfun(@(x) -1, {1, 2}, 'ErrorHandler', @(e, x) 0)", [[-1, -1]]),
    ("cellfun(@(x) error('bad'), {1, 2}, 'ErrorHandler', @(e, x) -1)", [[-1, -1]]),
    ("cellfun(@(x) error('Mod:id', 'boom'), {1, 2}, 'ErrorHandler', @(e, x) e.index)", [[1, 2]]),
]


@pytest.mark.parametrize("expr,expected", UNIFORM_CASES)
def test_uniform_results(expr, expected):
    check(val(expr), expected)


def test_multiple_outputs_and_non_uniform_results():
    ws, _ = run("[m, i] = cellfun(@max, {[1 5 2], [7 3]}); c = cellfun(@upper, {'a', 'b'}, "
                "'UniformOutput', false); d = arrayfun(@(x) x*[1 1], [1 2], 'UniformOutput', 0);")
    check(ws["m"], [[5, 7]])
    check(ws["i"], [[2, 1]])
    assert isinstance(ws["c"], CellArray) and [text(x) for x in ws["c"].data.ravel()] == ["A", "B"]
    assert ws["d"].shape == (1, 2)
    check(ws["d"].data[0, 1], [[2, 2]])


def test_error_handler_receives_message_and_identifier():
    ws, _ = run("r = cellfun(@(x) error('Mod:id', 'boom %d', x), {7}, 'UniformOutput', false, "
                "'ErrorHandler', @(e, x) {e.message, e.identifier}); m = r{1}{1}; i = r{1}{2};")
    assert text(ws["m"]) == "boom 7" and text(ws["i"]) == "Mod:id"


def test_functions_without_output_and_user_functions():
    _, host = run("cellfun(@disp, {1, 2});")
    assert "".join(host.written) == "1\n2\n"
    ws, _ = run("function y = twice(x), y = 2*x; end\nr = arrayfun(@twice, [1 2 3]); "
                "s = cellfun(@twice, {4, 5});")
    check(ws["r"], [[2, 4, 6]])
    check(ws["s"], [[8, 10]])


def test_cellfun_errors():
    fails("r = cellfun(@(x) [x x], {1, 2});", "Non-scalar in Uniform output")
    fails("r = cellfun(@(x) x, {1, true});", "different classes")
    fails("r = cellfun(@numel, [1 2]);", "must be cells")
    fails("r = cellfun(@(a, b) a + b, {1, 2}, {1});", "same size and shape")
    fails("r = cellfun(@numel);", "Not enough input arguments")
    fails("r = cellfun(5, {1});", "function handle or name")
    fails("r = cellfun(@(x) error('boom'), {1});", "boom")
    fails("[a, b] = cellfun(@(x) x, {1, 2});", "fewer outputs")
    fails("r = arrayfun(@(x) x, [1 2], [1 2 3]);", "same size and shape")


def test_feval_func2str_str2func():
    ws, _ = run("a = feval(@sin, 0); b = feval('cos', 0); c = feval(@(p, q) p + q, 1, 2); "
                "s1 = func2str(@sin); s2 = func2str(@(x) x + 1); f = str2func('sin'); "
                "g = str2func('@(x) x*2'); h = g(4); k = 10; m = str2func('@(x) x + k'); "
                "n = m(1); [lo, hi] = feval(@max, [3 9 2]);")
    check(ws["a"], [[0]])
    check(ws["b"], [[1]])
    check(ws["c"], [[3]])
    assert text(ws["s1"]) == "sin" and text(ws["s2"]) == "@(x) x + 1"
    assert isinstance(ws["f"], FunctionHandle) and ws["f"].name == "sin"
    check(ws["h"], [[8]])
    check(ws["n"], [[11]])
    check(ws["hi"], [[2]])
    fails("r = func2str(5);", "function handle")
    fails("r = str2func('@(x) x +');", "")
    fails("r = str2func('@(x) x; y = 1');", "one function handle")


# -------------------------------------------------------------------- sets
def test_unique_ismember_nnz():
    check(val("unique([3 1 2 1 3])"), [[1, 2, 3]])
    check(val("unique([3; 1; 3])"), [[1], [3]])
    check(val("unique([2 1; 1 3])"), [[1], [2], [3]])
    out = val("unique([1 NaN NaN])")
    assert out.shape == (1, 3) and out[0, 0] == 1 and np.isnan(out[0, 1:]).all()
    assert val("unique([])").shape == (0, 0)
    out = val("unique({'b', 'a', 'b'})")
    assert out.shape == (2, 1) and [text(x) for x in out.data.ravel()] == ["a", "b"]
    check(val("ismember(2, [1 2 3])"), [[True]])
    check(val("ismember([1 5], [1 2 3])"), [[True, False]])
    check(val("ismember('b', {'a', 'b'})"), [[True]])
    check(val("ismember({'a', 'z'}, {'a', 'b'})"), [[True, False]])
    ws, _ = run("[tf, loc] = ismember([3 1 9], [1 2 3 3]); "
                "[t2, l2] = ismember({'b', 'q'}, {'a', 'b'});")
    check(ws["tf"], [[True, True, False]])
    check(ws["loc"], [[3, 1, 0]])
    check(ws["l2"], [[2, 0]])
    check(val("nnz([1 0 2 0])"), [[2]])
    check(val("nnz([])"), [[0]])
    fails("[u, i] = unique([1 2]);", "only one output")


# ---------------------------------------------------------- operator functions
OPERATOR_CASES = [
    ("plus(1, 2)", [[3]]), ("plus(1, 2, 3)", [[6]]), ("minus(5, 2)", [[3]]),
    ("times([1 2], [3 4])", [[3, 8]]), ("mtimes([1 2; 3 4], [1; 1])", [[3], [7]]),
    ("rdivide([4 6], 2)", [[2, 3]]), ("ldivide(2, [4 6])", [[2, 3]]),
    ("power(2, [1 2 3])", [[2, 4, 8]]), ("mpower([1 1; 0 1], 2)", [[1, 2], [0, 1]]),
    ("eq([1 2], [1 3])", [[True, False]]), ("ne(1, 2)", [[True]]), ("lt(1, 2)", [[True]]),
    ("le(2, 2)", [[True]]), ("gt(1, 2)", [[False]]), ("ge(2, 3)", [[False]]),
    ("and([1 0], [1 1])", [[True, False]]), ("or([1 0], [0 0])", [[True, False]]),
    ("not([1 0])", [[False, True]]), ("uminus([1 -2])", [[-1, 2]]), ("uplus(3)", [[3]]),
    ("transpose([1 2; 3 4])", [[1, 3], [2, 4]]), ("ctranspose([1 + 1i, 2])", [[1 - 1j], [2]]),
    ("colon(1, 3)", [[1, 2, 3]]), ("colon(1, 2, 7)", [[1, 3, 5, 7]]),
    ("mldivide([2 0; 0 4], [2; 4])", [[1], [1]]), ("mrdivide([2 4], [2 0; 0 4])", [[1, 1]]),
]


@pytest.mark.parametrize("expr,expected", OPERATOR_CASES)
def test_operator_functions(expr, expected):
    check(val(expr), expected)


def test_operator_function_errors():
    fails("r = minus(1, 2, 3);", "Too many input arguments")
    fails("r = plus(1);", "Not enough input arguments")
    fails("r = plus([1 2], [1 2 3]);", "incompatible sizes")


# ------------------------------------------------------------------- random
def test_rng_makes_results_reproducible():
    ws, _ = run("rng(5); a = rand(1, 3); rng(5); b = rand(1, 3); rng(6); c = rand(1, 3); "
                "rng(5); x = randn(2, 2); rng(5); y = randn(2, 2); rng(7); p = randperm(6); "
                "rng(7); q = randperm(6);")
    np.testing.assert_array_equal(ws["a"], ws["b"])
    assert not np.array_equal(ws["a"], ws["c"])
    np.testing.assert_array_equal(ws["x"], ws["y"])
    np.testing.assert_array_equal(ws["p"], ws["q"])


def test_random_shapes_and_ranges():
    ws, _ = run("rng(1); a = rand(3); b = rand([2 4]); c = rand(100, 1); d = randn(10000, 1); "
                "e = randi(10, 1, 200); f = randi([5 7], 1, 100); g = randperm(5); "
                "h = randperm(5, 2); k = randi(1, 2, 2); l = rand();")
    assert ws["a"].shape == (3, 3) and ws["b"].shape == (2, 4) and ws["l"].shape == (1, 1)
    assert ws["c"].min() >= 0 and ws["c"].max() < 1
    assert abs(ws["d"].mean()) < 0.05 and abs(ws["d"].std() - 1) < 0.05
    assert set(np.unique(ws["e"])) <= set(range(1, 11)) and len(np.unique(ws["e"])) > 5
    assert set(np.unique(ws["f"])) == {5.0, 6.0, 7.0}
    np.testing.assert_array_equal(np.sort(ws["g"]), [[1, 2, 3, 4, 5]])
    assert ws["h"].shape == (1, 2) and len(set(ws["h"].ravel())) == 2
    np.testing.assert_array_equal(ws["k"], np.ones((2, 2)))


def test_rng_modes_and_random_errors():
    run("rng('default'); rng('shuffle'); rng(0);")
    ws, _ = run("rng('default'); a = rand(1, 2); rng('default'); b = rand(1, 2);")
    np.testing.assert_array_equal(ws["a"], ws["b"])
    fails("rng(-1)", "non-negative")
    fails("rng('bogus')", "seed")
    fails("r = randi(0);", "positive integer")
    fails("r = randi([5 1]);", "upper limit")
    fails("r = randi([1 2 3]);", "scalar or [min max]")
    fails("r = randperm(3, 5);", "at most N")
    fails("r = rand(1.5);", "integer")


def test_each_interpreter_has_its_own_random_stream():
    first, _ = make()
    second, _ = make()
    first.execute("rng(3); a = rand(1, 3);")
    second.execute("rng(3); b = rand(1, 3);")
    np.testing.assert_array_equal(first.workspace["a"], second.workspace["b"])
    first.execute("a2 = rand(1, 3);")
    second.execute("rng(3); b2 = rand(1, 3);")
    np.testing.assert_array_equal(second.workspace["b2"], first.workspace["a"])


# ------------------------------------------------------------------- timing
def test_tic_toc():
    ws, host = run("tic; t = toc; t0 = tic; e = toc(t0); toc;")
    assert 0 <= ws["t"][0, 0] < 5 and 0 <= ws["e"][0, 0] < 5
    assert "".join(host.written).startswith("Elapsed time is ")
    assert "".join(host.written).endswith(" seconds.\n")
    fails("t = toc;", "Call TIC before TOC")
