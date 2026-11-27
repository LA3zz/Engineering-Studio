"""matlabFunction (closes B2b-5): symbolic expression -> element-wise anonymous function."""

import math

import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_extra import install_extra
from engstudio.lang.builtins_funcs import install_funcs
from engstudio.lang.builtins_sym import install_sym
from engstudio.lang.interp import Interpreter


def run(code):
    it = Interpreter()
    install_core(it)
    install_extra(it)
    install_funcs(it)
    install_sym(it)
    it.execute(to_function_syntax(code), None)
    return it.workspace


def test_vectorized_handle_and_default_variable_order():
    ws = run("syms x y\nf = x^2*sin(y) + exp(-x); h = matlabFunction(f);"
             " v = h([1 2], [0 pi/2]); s = func2str(h);")
    assert ws["v"].ravel().tolist() == pytest.approx([math.exp(-1), 4 + math.exp(-2)])
    assert ws["s"].to_str().replace(" ", "").startswith("@(x,y)")


def test_vars_option_sets_argument_order():
    ws = run("syms x y\ng = matlabFunction(x - 2*y, 'Vars', {y, x}); w = g(1, 10);")
    assert ws["w"].item() == 8


def test_handles_work_with_numeric_solvers():
    ws = run("syms x\nr = fzero(matlabFunction(x^2 - 2), [0 2]);"
             " q = integral(matlabFunction(x^2), 0, 3);")
    assert ws["r"].item() == pytest.approx(math.sqrt(2))
    assert ws["q"].item() == pytest.approx(9)


@pytest.mark.parametrize("code, text", [
    ("syms x y\nmatlabFunction(x*y, 'Vars', {x})", "missing y"),
    ("syms x\nmatlabFunction(x == 1)", "equation"),
    ("syms x\nmatlabFunction(x, 'File', 'f')", "Vars"),
])
def test_errors(code, text):
    with pytest.raises(EngStudioError, match=text):
        run(code)
