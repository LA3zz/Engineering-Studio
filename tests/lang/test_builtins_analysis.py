"""Analysis builtins (B2b-4). References: exact linear/plane interpolation, closed-form minima,
a textbook LP, the MATLAB quantile rule by definition, and SciPy (independent implementation)
for the t-tests: x = [2.1 1.9 2.4 2.2 2.0 2.3], y = [1.7 1.9 2.0 1.6 1.8 2.1 1.5]."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_analysis import install_analysis
from engstudio.lang.builtins_core import install_core
from engstudio.lang.interp import Interpreter

X = "x = [2.1 1.9 2.4 2.2 2.0 2.3]; y = [1.7 1.9 2.0 1.6 1.8 2.1 1.5]; "
GRID = "[X,Y] = meshgrid(0:4, 0:4); Z = X + 2*Y; "


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    install_analysis(interp)
    interp.execute(code, None)
    return interp.workspace


def num(ws, name: str) -> float:
    return float(np.asarray(ws[name]).reshape(-1)[0])


def test_interp2_linear_forms():
    assert num(run(GRID + "v = interp2(X, Y, Z, 0.5, 1.5);"), "v") == pytest.approx(3.5)
    assert num(run(GRID + "v = interp2(0:4, 0:4, Z, 0.5, 1.5);"), "v") == pytest.approx(3.5)
    assert num(run("[X,Y] = meshgrid(1:3, 1:4); Z = X + 2*Y; v = interp2(Z, 1.5, 2.5);"),
               "v") == pytest.approx(6.5)


def test_interp2_methods_and_grid_queries():
    assert num(run(GRID + "v = interp2(X, Y, Z, 1.5, 2.5, 'cubic');"), "v") == pytest.approx(
        6.5, abs=1e-9)
    assert num(run(GRID + "v = interp2(X, Y, Z, 0.4, 1.2, 'nearest');"), "v") == 2.0
    v = run(GRID + "v = interp2(X, Y, Z, [0.5 1.5], [1; 2]);")["v"]
    assert np.allclose(v, [[2.5, 3.5], [4.5, 5.5]])


def test_interp2_outside_and_fill():
    with pytest.raises(EngStudioError):
        run(GRID + "v = interp2(X, Y, Z, 10, 1);")
    assert num(run(GRID + "v = interp2(X, Y, Z, 10, 1, 'linear', -1);"), "v") == -1.0
    assert math.isnan(num(run(GRID + "v = interp2(X, Y, Z, 10, 1, 'linear', NaN);"), "v"))
    with pytest.raises(EngStudioError):
        run(GRID + "v = interp2(X, Y, Z, 1, 1, 'spline');")


def test_fminbnd_and_fminunc():
    ws = run("[x, fv, fl] = fminbnd(@cos, 3, 4);")
    assert num(ws, "x") == pytest.approx(math.pi, abs=1e-6) and num(ws, "fv") == pytest.approx(-1)
    ws = run("[x, fv, fl] = fminunc(@(x) (x(1)-1)^2 + (x(2)+2)^2, [0; 0]);")
    assert np.allclose(ws["x"], [[1.0], [-2.0]], atol=1e-5) and ws["x"].shape == (2, 1)
    assert num(ws, "fl") in (1.0, 2.0)


def test_linprog_bounds_equality_and_infeasible():
    ws = run("[x, fv] = linprog([-1;-2], [1 1], 4, [], [], [0;0], [3;Inf]);")
    assert np.allclose(ws["x"], [[0.0], [4.0]], atol=1e-8) and num(ws, "fv") == pytest.approx(-8)
    ws = run("[x, fv] = linprog([1;1], [], [], [1 1], 2, [0;0], []);")
    assert num(ws, "fv") == pytest.approx(2.0)
    with pytest.raises(EngStudioError):
        run("x = linprog(1, [1;-1], [1;-2]);")


def test_quantile_prctile_rule_and_orientation():
    ws = run("q = quantile([1 2 3 4 5], [0.25 0.5]); p = prctile([1 2 3 4 5]', [25 50]);")
    assert np.allclose(ws["q"], [[1.75, 3.0]]) and np.allclose(ws["p"], [[1.75], [3.0]])
    ws = run("q = quantile([1 10; 2 20; 3 30; 4 40; 5 50], 0.5);")
    assert np.allclose(ws["q"], [[3.0, 30.0]])
    with pytest.raises(EngStudioError):
        run("q = prctile([1 2 3], 120);")


def test_ttest_matches_scipy():
    ws = run(X + "[h, p, ci, st] = ttest(x, 2.0); t = st.tstat; d = st.df; s = st.sd;")
    assert ws["h"].dtype == bool and not ws["h"][0, 0]
    assert num(ws, "p") == pytest.approx(0.10674552235509158, abs=1e-10)
    assert np.allclose(ws["ci"], [[1.953668569301968], [2.3463314306980325]], atol=1e-9)
    assert num(ws, "t") == pytest.approx(1.9639610121239364, abs=1e-10)
    assert num(ws, "d") == 5.0 and num(ws, "s") == pytest.approx(0.18708286933869703)


def test_ttest_tail_and_alpha():
    ws = run(X + "[h, p, ci] = ttest(x, 1.9, 'Tail', 'right');")
    assert ws["h"][0, 0] and num(ws, "p") == pytest.approx(0.011059233361164648, abs=1e-10)
    assert ws["ci"][0, 0] == pytest.approx(1.9960981383367302, abs=1e-9)
    assert math.isinf(ws["ci"][1, 0])
    assert run(X + "h = ttest(x, 'Alpha', 0.001);")["h"].dtype == bool
    with pytest.raises(EngStudioError):
        run(X + "h = ttest(x, 'Alpha', 2);")


def test_ttest2_equal_and_unequal_match_scipy():
    ws = run(X + "[h, p, ci, st] = ttest2(x, y); t = st.tstat; d = st.df;")
    assert num(ws, "p") == pytest.approx(0.01022701617080683, abs=1e-10)
    assert np.allclose(ws["ci"], [[0.10095748064968157], [0.599042519350319]], atol=1e-9)
    assert num(ws, "t") == pytest.approx(3.0932260404435565, abs=1e-9) and num(ws, "d") == 11.0
    ws = run(X + "[h, p, ci, st] = ttest2(x, y, 'Vartype', 'unequal'); d = st.df;")
    assert num(ws, "p") == pytest.approx(0.009575634869912253, abs=1e-10)
    assert np.allclose(ws["ci"], [[0.10390458565793653], [0.596095414342064]], atol=1e-9)
    assert num(ws, "d") == pytest.approx(10.993485342019543, abs=1e-8)
    assert ws["st"].get("sd").shape == (2, 1)


def test_ttest_errors():
    with pytest.raises(EngStudioError):
        run("h = ttest([1 2; 3 4]);")
    with pytest.raises(EngStudioError):
        run(X + "h = ttest2(x, y, 'Vartype', 'both');")
    with pytest.raises(EngStudioError):
        run(X + "h = ttest(x, 'Foo', 1);")
