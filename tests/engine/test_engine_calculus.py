"""Calculus tests against analytic values (derivations in comments)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine import calculus as ca


# -- derivative ------------------------------------------------------------------------
def test_first_derivative_central():
    assert ca.derivative(lambda x: x**3, 2.0) == pytest.approx(12.0, rel=1e-8)
    assert ca.derivative(math.sin, 0.7) == pytest.approx(math.cos(0.7), abs=1e-9)
    assert ca.derivative(math.exp, 1.0) == pytest.approx(math.e, rel=1e-9)
    assert ca.derivative(lambda x: x**2, 0.0) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("method", ["forward", "backward"])
def test_first_derivative_one_sided(method):
    assert ca.derivative(math.exp, 1.0, method=method) == pytest.approx(math.e, rel=1e-8)
    # sqrt(x) at 1: forward stencil only uses points >= 1, so it stays in the domain
    assert ca.derivative(math.sqrt, 1.0, method="forward") == pytest.approx(0.5, rel=1e-8)


def test_second_derivative():
    assert ca.derivative(math.sin, 0.7, order=2) == pytest.approx(-math.sin(0.7), abs=1e-6)
    assert ca.derivative(lambda x: x**3, 2.0, order=2) == pytest.approx(12.0, rel=1e-6)
    for method in ("forward", "backward"):
        assert ca.derivative(math.exp, 1.0, order=2, method=method) == pytest.approx(
            math.e, rel=1e-5)


def test_explicit_step_and_errors():
    assert ca.derivative(lambda x: x**2, 3.0, h=1e-3) == pytest.approx(6.0, rel=1e-9)
    with pytest.raises(ValidationError):
        ca.derivative(math.sin, 1.0, h=-1e-3)
    with pytest.raises(ValidationError):
        ca.derivative(math.sin, 1.0, order=3)
    with pytest.raises(ValidationError):
        ca.derivative(math.sin, 1.0, method="x")
    with pytest.raises(ValidationError):
        ca.derivative("not callable", 1.0)
    with pytest.raises(ValidationError):
        ca.derivative(lambda x: float("nan"), 1.0)
    with pytest.raises(ValidationError):
        ca.derivative(lambda x: 1j * x, 1.0)
    with pytest.raises(ValidationError):
        ca.derivative(math.sin, float("inf"))


def test_gradient_and_jacobian():
    # f = x^2 + 3 y^2 -> (2x, 6y) = (2, 12) at (1, 2)
    g = ca.gradient(lambda v: v[0] ** 2 + 3 * v[1] ** 2, [1.0, 2.0])
    assert g == pytest.approx(np.array([2.0, 12.0]), rel=1e-8)
    # f = [x y, x + y^2] at (2, 3): [[y, x], [1, 2y]] = [[3, 2], [1, 6]]
    j = ca.jacobian(lambda v: [v[0] * v[1], v[0] + v[1] ** 2], [2.0, 3.0])
    assert j.shape == (2, 2)
    assert j == pytest.approx(np.array([[3.0, 2.0], [1.0, 6.0]]), rel=1e-8)
    with pytest.raises(ValidationError):
        ca.gradient(lambda v: v, [1.0, 2.0])      # returns a vector, not a scalar


def test_derivative_data_nonuniform_quadratic_exact():
    x = np.array([0.0, 0.5, 1.5, 2.0, 3.5])
    assert ca.derivative_data(x, x**2) == pytest.approx(2 * x, abs=1e-12)
    with pytest.raises(ValidationError):
        ca.derivative_data([0, 1], [0, 1])
    with pytest.raises(ValidationError):
        ca.derivative_data([0, 2, 1], [0, 1, 2])
    with pytest.raises(DimensionError):
        ca.derivative_data([0, 1, 2], [0, 1])


# -- quad / dblquad --------------------------------------------------------------------
def test_quad_analytic():
    assert ca.quad(math.sin, 0, math.pi).value == pytest.approx(2.0, abs=1e-12)
    assert ca.quad(lambda x: x**2, 0, 1).value == pytest.approx(1 / 3, abs=1e-12)
    assert ca.quad(lambda x: math.exp(-x), 0, math.inf).value == pytest.approx(1.0, abs=1e-8)
    gauss = ca.quad(lambda x: math.exp(-x * x), -math.inf, math.inf)
    assert gauss.value == pytest.approx(math.sqrt(math.pi), abs=1e-8)
    # integrable endpoint singularity: int_0^1 x^(-1/2) dx = 2
    assert ca.quad(lambda x: x ** -0.5, 0, 1).value == pytest.approx(2.0, abs=1e-6)


def test_quad_result_fields_and_orientation():
    r = ca.quad(math.sin, 0, math.pi)
    assert r.converged and r.diagnostics == () and r.nfev > 0 and r.error_estimate < 1e-8
    assert ca.quad(math.sin, math.pi, 0).value == pytest.approx(-2.0, abs=1e-12)
    zero = ca.quad(math.sin, 1, 1)
    assert zero.value == 0.0 and zero.nfev == 0


def test_quad_not_converged_reports_warning():
    r = ca.quad(lambda x: math.sin(100 * x), 0, 10, limit=1)
    assert not r.converged
    assert r.diagnostics and r.diagnostics[0].severity == "warning"


def test_quad_errors():
    with pytest.raises(ValidationError):
        ca.quad(math.sin, 0, float("nan"))
    with pytest.raises(ValidationError):
        ca.quad(math.sin, 0, 1, rtol=-1)
    with pytest.raises(ValidationError):
        ca.quad(lambda x: float("nan"), 0, 1)
    with pytest.raises(ValidationError):
        ca.quad(math.sin, 0, 1, limit=0)


def test_dblquad_analytic():
    # int_0^1 int_0^2 x y dy dx = (1/2)(2) = 1
    assert ca.dblquad(lambda x, y: x * y, 0, 1, 0, 2).value == pytest.approx(1.0, abs=1e-10)
    # int_0^pi int_0^pi sin x sin y = 2 * 2 = 4
    r = ca.dblquad(lambda x, y: math.sin(x) * math.sin(y), 0, math.pi, 0, math.pi)
    assert r.value == pytest.approx(4.0, abs=1e-9) and r.converged


# -- sampled data ----------------------------------------------------------------------
def test_trapz_exact_for_linear_and_error_law():
    x = np.linspace(0, 1, 11)
    assert ca.trapz(x, x) == pytest.approx(0.5, abs=1e-14)
    # int_0^pi sin = 2; trapezoid error = -(h^2/12)(f'(b) - f'(a)) = h^2/6, so T = 2 - h^2/6
    n = 1001
    xs = np.linspace(0, math.pi, n)
    h = math.pi / (n - 1)
    assert ca.trapz(np.sin(xs), xs) == pytest.approx(2 - h * h / 6, abs=1e-10)
    assert ca.trapz([1.0, 1.0, 1.0], dx=0.5) == pytest.approx(1.0)


def test_simpson():
    x = np.linspace(0, 1, 11)                       # odd sample count: exact for cubics
    assert ca.simpson(x**3, x) == pytest.approx(0.25, abs=1e-14)
    xs = np.linspace(0, math.pi, 101)
    s = ca.simpson(np.sin(xs), xs)
    assert abs(s - 2.0) < 5e-8                      # error ~ 2 h^4 / 180 ~ 1.1e-8
    assert abs(s - 2.0) < abs(ca.trapz(np.sin(xs), xs) - 2.0)


def test_cumtrapz():
    x = np.linspace(0, 1, 6)
    c = ca.cumtrapz(x, x)                           # linear integrand: exact x^2 / 2
    assert c == pytest.approx(x**2 / 2, abs=1e-14)
    assert c[0] == 0.0 and c.size == x.size


def test_sample_validation():
    with pytest.raises(DimensionError):
        ca.trapz([1, 2, 3], [0, 1])
    with pytest.raises(ValidationError):
        ca.trapz([1])
    with pytest.raises(ValidationError):
        ca.trapz([1, 2, 3], [0, 2, 1])
    with pytest.raises(ValidationError):
        ca.trapz([1, np.nan, 3])
    with pytest.raises(ValidationError):
        ca.trapz([1, 2], dx=0)
