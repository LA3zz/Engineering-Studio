"""Handle-based builtins (B2b-3). References are analytic: sqrt(2), pi/2, 9, sqrt(pi), exp(-1),
sin/cos of the harmonic oscillator, minima/roots known in closed form."""

import math

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_funcs import install_funcs
from engstudio.lang.interp import Interpreter


def run(code: str):
    interp = Interpreter()
    install_core(interp)
    install_funcs(interp)
    interp.execute(code, None)
    return interp.workspace


def num(ws, name: str) -> float:
    return float(np.asarray(ws[name]).reshape(-1)[0])


def test_fzero_bracket():
    assert num(run("x = fzero(@(x) x^2-2, [0 2]);"), "x") == pytest.approx(math.sqrt(2), abs=1e-10)


def test_fzero_search_from_scalar():
    assert num(run("x = fzero(@cos, 1);"), "x") == pytest.approx(math.pi / 2, abs=1e-10)


def test_fzero_outputs_and_name_text():
    ws = run("[x, fv, fl] = fzero('cos', [0 2]);")
    assert num(ws, "x") == pytest.approx(math.pi / 2, abs=1e-10)
    assert abs(num(ws, "fv")) < 1e-10 and num(ws, "fl") == 1.0


def test_fzero_no_sign_change_errors():
    with pytest.raises(EngStudioError):
        run("x = fzero(@(x) x^2+1, [0 2]);")
    with pytest.raises(EngStudioError):
        run("x = fzero(@(x) x^2+1, 0.5);")


def test_integral_polynomial_and_infinite():
    assert num(run("q = integral(@(x) x.^2, 0, 3);"), "q") == pytest.approx(9.0, abs=1e-8)
    ws = run("q = integral(@(x) exp(-x.^2), -Inf, Inf);")
    assert num(ws, "q") == pytest.approx(math.sqrt(math.pi), abs=1e-7)


def test_quad_quadgk_and_options():
    assert num(run("q = quad(@sin, 0, pi);"), "q") == pytest.approx(2.0, abs=1e-8)
    ws = run("[q, e] = quadgk(@(x) x, 0, 2, 'RelTol', 1e-10, 'AbsTol', 1e-12);")
    assert num(ws, "q") == pytest.approx(2.0, abs=1e-10) and num(ws, "e") >= 0
    with pytest.raises(EngStudioError):
        run("q = integral(@sin, 0, 1, 'Waypoints', 1);")


def test_integral2_rectangle():
    assert num(run("q = integral2(@(x,y) x.*y, 0, 1, 0, 2);"), "q") == pytest.approx(1.0, abs=1e-8)


def test_ode45_exponential_decay():
    ws = run("[t, y] = ode45(@(t,y) -y, [0 1], 1); yend = y(end); tend = t(end);")
    assert num(ws, "tend") == pytest.approx(1.0) and num(ws, "yend") == pytest.approx(
        math.exp(-1), abs=1e-5)


def test_ode45_oscillator_system_and_tspan_points():
    ws = run("[t, y] = ode45(@(t,y) [y(2); -y(1)], [0 pi/2 pi], [0; 1]); n = size(y, 2);"
             " m = numel(t); a = y(2,1); b = y(3,2);")
    assert num(ws, "n") == 2 and num(ws, "m") == 3
    assert num(ws, "a") == pytest.approx(1.0, abs=1e-4)  # sin(pi/2)
    assert num(ws, "b") == pytest.approx(-1.0, abs=1e-4)  # cos(pi)


def test_ode23_and_ode15s():
    ws = run("[t, y] = ode23(@(t,y) -y, [0 1], 1); a = y(end);")
    assert num(ws, "a") == pytest.approx(math.exp(-1), abs=1e-4)
    ws = run("[t, y] = ode15s(@(t,y) -50*y, [0 1], 1); a = y(end);")
    assert abs(num(ws, "a")) < 1e-6


def test_ode_needs_two_outputs_and_rejects_options():
    with pytest.raises(EngStudioError):
        run("ode45(@(t,y) -y, [0 1], 1);")
    with pytest.raises(EngStudioError):
        run("[t, y] = ode45(@(t,y) -y, [0 1], 1, 5);")


def test_fminsearch_quadratic_keeps_orientation():
    ws = run("[x, fv, fl] = fminsearch(@(x) (x(1)-1)^2 + (x(2)+2)^2, [0 0]);")
    assert np.allclose(ws["x"], [[1.0, -2.0]], atol=1e-4) and num(ws, "fl") == 1.0
    ws = run("x = fminsearch(@(x) (x(1)-1)^2 + (x(2)+2)^2, [0; 0]);")
    assert ws["x"].shape == (2, 1)


def test_fminsearch_rosenbrock():
    ws = run("x = fminsearch(@(x) 100*(x(2)-x(1)^2)^2 + (1-x(1))^2, [-1.2 1]);")
    assert np.allclose(ws["x"], [[1.0, 1.0]], atol=1e-4)


def test_fsolve_circle_line():
    ws = run("[x, fv] = fsolve(@(x) [x(1)^2+x(2)^2-4; x(1)-x(2)], [1; 1]);")
    assert np.allclose(ws["x"], [[math.sqrt(2)], [math.sqrt(2)]], atol=1e-8)
    assert np.allclose(ws["fv"], 0.0, atol=1e-8)


def test_too_many_outputs_and_bad_handle():
    with pytest.raises(EngStudioError):
        run("[a, b, c, d] = fzero(@cos, [0 2]);")
    with pytest.raises(EngStudioError):
        run("x = fzero(5, [0 2]);")
