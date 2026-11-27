"""Symbolic values and builtins (B2b-5). References are exact algebra/calculus: d/dx(x^2+3sin x),
int x^2 = x^3/3, int_0^3 x^2 = 9, lim sin(x)/x = 1, Taylor of e^x, L{sin 2t} = 2/(s^2+4),
L^-1{1/(s^2+1)} = sin t, roots of x^2 = 4, the system x+y=3, x-y=1 -> (2, 1)."""

import numpy as np
import pytest

from engstudio.app.kernel.inprocess import to_function_syntax
from engstudio.core.errors import EngStudioError
from engstudio.engine import symbolic as sy
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_sym import display_text, install_sym, preview_text
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import SymValue

SYMS = "syms('x', 'y', 't', 's'); "


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    install_sym(interp)
    interp.execute(code, None)
    return interp.workspace


def num(ws, name: str) -> float:
    return float(np.asarray(ws[name]).reshape(-1)[0])


def text(ws, name: str) -> str:
    return ws[name].to_str()


def test_syms_and_class():
    ws = run(SYMS + "f = x^2 + 1; c = class(f); c2 = class(x);")
    assert isinstance(ws["x"], SymValue) and text(ws, "c") == "sym" and text(ws, "c2") == "sym"


def test_command_syntax_rewrite():
    assert to_function_syntax("syms x y") == "syms('x', 'y')"
    assert to_function_syntax("  syms t;") == "  syms('t');"
    assert to_function_syntax("syms = 3") == "syms = 3"


def test_diff_symbolic_and_orders():
    ws = run(SYMS + "f = x^2 + 3*sin(x); g = diff(f, x); h = diff(x^4, x, 2); k = diff(f);")
    assert sy.equivalent(ws["g"].expr, "2*x + 3*cos(x)")
    assert sy.equivalent(ws["h"].expr, "12*x^2") and sy.equivalent(ws["k"].expr, ws["g"].expr)


def test_numeric_diff_still_works_and_text_form():
    assert np.allclose(run("d = diff([1 4 9]);")["d"], [[3.0, 5.0]])
    assert sy.equivalent(run("g = diff('x^3', 'x');")["g"].expr, "3*x^2")


def test_int_indefinite_definite_and_infinite():
    ws = run(SYMS + "a = int(x^2, x); b = int(x^2, x, 0, 3); c = double(b); "
             "d = int(exp(-x), x, 0, Inf); e = double(d);")
    assert sy.equivalent(ws["a"].expr, "x^3/3") and num(ws, "c") == pytest.approx(9.0)
    assert num(ws, "e") == pytest.approx(1.0)


def test_limit_and_taylor():
    ws = run(SYMS + "a = limit(sin(x)/x, x, 0); b = taylor(exp(x), x, 'Order', 4); "
             "c = limit(1/x, x, 0, 'right'); d = limit(x^2, x, Inf);")
    assert num(run(SYMS + "a = double(limit(sin(x)/x, x, 0));"), "a") == pytest.approx(1.0)
    assert sy.equivalent(ws["b"].expr, "1 + x + x^2/2 + x^3/6")
    oo = sy.parse("oo").expr
    assert ws["c"].expr.expr == oo and ws["d"].expr.expr == oo
    with pytest.raises(EngStudioError):
        run(SYMS + "a = limit(1/x, x, 0);")


def test_solve_forms():
    ws = run(SYMS + "r = solve(x^2 == 4, x); a = double(r); "
             "u = solve(2*x - 4, x); b = double(u); n = solve('x^2 = 9', 'x'); m = double(n); "
             "e = solve(x^2 + 1 == 0, x); k = numel(e);")
    assert np.allclose(ws["a"], [[-2.0], [2.0]]) and num(ws, "b") == 2.0
    assert np.allclose(ws["m"], [[-3.0], [3.0]]) and num(ws, "k") == 2
    ws = run(SYMS + "q = solve(x + 1 - x, x);")
    assert np.asarray(ws["q"]).size == 0


def test_solve_system_struct():
    ws = run(SYMS + "r = solve({x + y == 3, x - y == 1}, {x, y}); "
             "a = double(r.x); b = double(r.y);")
    assert num(ws, "a") == pytest.approx(2.0) and num(ws, "b") == pytest.approx(1.0)
    with pytest.raises(EngStudioError):
        run(SYMS + "r = solve({x + y == 3}, x);")


def test_simplify_expand_factor_subs():
    ws = run(SYMS + "a = simplify((x^2 - 1)/(x - 1)); b = expand((x + 1)^2); c = factor(x^2 - 1); "
             "d = subs(x^2 + y, x, 3); e = double(subs(d, y, 1)); "
             "f = subs(x + y, {x, y}, {1, 2}); g = double(f);")
    assert sy.equivalent(ws["a"].expr, "x + 1") and sy.equivalent(ws["b"].expr, "x^2 + 2*x + 1")
    assert sy.equivalent(ws["c"].expr, "x^2 - 1") and num(ws, "e") == 10.0 and num(ws, "g") == 3.0


def test_laplace_and_inverse():
    ws = run(SYMS + "F = laplace(sin(2*t), t, s); v = double(subs(F, s, 1)); "
             "g = ilaplace(1/(s^2 + 1), s, t); w = double(subs(g, t, pi/2));")
    assert num(ws, "v") == pytest.approx(2.0 / 5.0, abs=1e-12)
    assert num(ws, "w") == pytest.approx(1.0, abs=1e-12)
    ws = run(SYMS + "F = laplace(exp(-3*t)); G = ilaplace(F);")
    assert sy.equivalent(ws["G"].expr, "exp(-3*t)")


def test_arithmetic_and_elementary_functions():
    ws = run(SYMS + "a = 2*x + x/4; b = double(subs(a, x, 4)); c = -x + x; d = x^2 / x; "
             "h = simplify(sin(x)^2 + cos(x)^2); e = double(h); r = sqrt(x)^2; "
             "z = double(exp(sym(0))); s1 = sin(0);")
    assert num(ws, "b") == 9.0 and num(ws, "e") == pytest.approx(1.0) and num(ws, "z") == 1.0
    assert sy.equivalent(ws["c"].expr, "0") and sy.equivalent(ws["d"].expr, "x")
    assert sy.equivalent(ws["r"].expr, "x") and num(ws, "s1") == 0.0


def test_char_latex_symvar_sym():
    ws = run(SYMS + "f = x^2 + 1; s1 = char(f); l = latex(f); v = symvar(x*y + 1); n = numel(v); "
             "q = sym('x + 2'); w = double(sym(7));")
    assert text(ws, "s1") == "x^2 + 1" and text(ws, "l") == "x^{2} + 1"
    assert num(ws, "n") == 2 and sy.equivalent(ws["q"].expr, "x + 2") and num(ws, "w") == 7.0


def test_equation_object_and_isequal():
    ws = run(SYMS + "e = (x == 2); f = isequal(x + 1, x + 1);")
    assert isinstance(ws["e"], SymValue) and bool(np.asarray(ws["f"]).all())


def test_errors_are_clear_not_silent():
    for code in (
        SYMS + "a = x + [1 2];", SYMS + "a = [x y];", SYMS + "a = x < 1;",
        SYMS + "a = double(x);", SYMS + "a = 1/(x - x);", "syms('x', 'real');",
        "syms('sin');", SYMS + "a = int(1/x, x, -1, 1);", SYMS + "a = solve({x}, x);",
        SYMS + "a = subs(x, 1, 2);", SYMS + "a = taylor(x, x, 'Foo', 1);",
    ):
        with pytest.raises(EngStudioError):
            run(code)


def test_display_and_preview():
    f = SymValue(sy.parse("x^2 + 1"))
    assert display_text("f", f) == "f =\nx^2 + 1\n\n"
    assert preview_text(f) == "x^2 + 1"
    long_text = preview_text(SymValue(sy.parse("+".join(f"x{i}" for i in range(30)))))
    assert len(long_text) == 40 and long_text.endswith("...")
    assert display_text("a", np.array([[5.0]])).startswith("a =")


def test_numeric_code_unaffected():
    ws = run("a = sin(0); b = [1 2 3] * 2; c = double(true); d = abs(-3); e = char(72); "
             "g = 'ab'; f = {1, 2};")
    assert num(ws, "a") == 0.0 and np.allclose(ws["b"], [[2, 4, 6]]) and num(ws, "d") == 3.0


def test_cell_of_syms_displays_and_previews():
    ws = run(SYMS + "r = solve(x^2 == 4, x);")
    out = display_text("r", ws["r"])
    assert "2x1 cell array" in out and "{[-2]}" in out and "{[2]}" in out
    assert preview_text(ws["r"])
    assert SymValue(sy.parse("x")).shape == (1, 1)
