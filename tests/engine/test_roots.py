"""Validation tests for engine.roots. Reference values are analytic or standard constants."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import (
    ConvergenceError,
    DimensionError,
    SingularMatrixError,
    ValidationError,
)
from engstudio.engine import roots

SQRT2 = math.sqrt(2.0)
DOTTIE = 0.7390851332151607  # unique real root of cos(x) = x (known constant)


def sq2(x: float) -> float:
    return x * x - 2.0


# -- scalar ----------------------------------------------------------------------------
@pytest.mark.parametrize("method", [roots.bisect, roots.brentq])
def test_bracketing_sqrt2(method) -> None:
    r = method(sq2, 0.0, 2.0)
    assert r.converged
    assert r.root == pytest.approx(SQRT2, abs=1e-12)
    assert r.residual < 1e-11
    assert r.nfev > 0


@pytest.mark.parametrize("method", [roots.bisect, roots.brentq])
def test_bracketing_dottie_and_swapped_bounds(method) -> None:
    r = method(lambda x: math.cos(x) - x, 1.0, 0.0)  # bounds given in reverse order
    assert r.root == pytest.approx(DOTTIE, abs=1e-12)


@pytest.mark.parametrize("method", [roots.bisect, roots.brentq])
def test_bracket_endpoint_is_root(method) -> None:
    r = method(lambda x: x - 1.0, 1.0, 3.0)
    assert r.root == 1.0 and r.iterations == 0 and r.residual == 0.0


@pytest.mark.parametrize("method", [roots.bisect, roots.brentq])
def test_no_sign_change(method) -> None:
    with pytest.raises(ValidationError, match="no sign change"):
        method(lambda x: x * x + 1.0, -1.0, 1.0)


def test_bisect_iteration_count_is_logarithmic() -> None:
    r = roots.bisect(sq2, 0.0, 2.0, rtol=1e-6, atol=1e-6)
    assert r.iterations <= math.ceil(math.log2(2.0 / 1e-6)) + 1


def test_bisect_maxiter() -> None:
    with pytest.raises(ConvergenceError) as ei:
        roots.bisect(sq2, 0.0, 2.0, maxiter=5)
    assert ei.value.iterations == 5
    assert ei.value.last_estimate is not None


def test_brentq_maxiter() -> None:
    with pytest.raises(ConvergenceError):
        roots.brentq(lambda x: x**9, -1.0, 2.0, maxiter=2)


def test_newton_analytic_and_numeric_derivative() -> None:
    a = roots.newton(sq2, 1.0, fprime=lambda x: 2 * x)
    b = roots.newton(sq2, 1.0)
    assert a.root == pytest.approx(SQRT2, abs=1e-12)
    assert b.root == pytest.approx(SQRT2, abs=1e-9)
    assert a.iterations <= 8  # quadratic convergence


def test_newton_dottie() -> None:
    r = roots.newton(lambda x: math.cos(x) - x, 0.5, fprime=lambda x: -math.sin(x) - 1.0)
    assert r.root == pytest.approx(DOTTIE, abs=1e-12)


def test_newton_exact_start_and_zero_derivative() -> None:
    assert roots.newton(lambda x: x - 3.0, 3.0).iterations == 0
    with pytest.raises(ConvergenceError, match="zero derivative"):
        roots.newton(lambda x: x * x + 1.0, 0.0, fprime=lambda x: 2 * x)


def test_newton_divergence_detected() -> None:
    with pytest.raises(ConvergenceError):
        roots.newton(lambda x: math.atan(x), 3.0, fprime=lambda x: 1 / (1 + x * x), maxiter=20)


def test_secant() -> None:
    r = roots.secant(sq2, 1.0, 2.0)
    assert r.root == pytest.approx(SQRT2, abs=1e-12)
    r = roots.secant(lambda x: math.cos(x) - x, 0.0, 1.0)
    assert r.root == pytest.approx(DOTTIE, abs=1e-12)


def test_secant_errors() -> None:
    with pytest.raises(ValidationError):
        roots.secant(sq2, 1.0, 1.0)
    with pytest.raises(ConvergenceError, match="flat"):
        roots.secant(lambda x: 1.0, 0.0, 1.0)


def test_multiple_root_converges_loosely() -> None:
    r = roots.newton(lambda x: (x - 1.0) ** 2, 3.0, fprime=lambda x: 2 * (x - 1.0),
                     rtol=1e-8, atol=1e-8)
    assert r.root == pytest.approx(1.0, abs=1e-6)


# -- scalar input validation -------------------------------------------------------------
def test_scalar_input_validation() -> None:
    with pytest.raises(ValidationError):
        roots.bisect(None, 0.0, 1.0)
    with pytest.raises(ValidationError):
        roots.bisect(sq2, 0.0, 0.0)
    with pytest.raises(ValidationError):
        roots.bisect(sq2, 0.0, float("nan"))
    with pytest.raises(ValidationError):
        roots.bisect(sq2, 0.0, 2.0, atol=0.0)
    with pytest.raises(ValidationError):
        roots.bisect(sq2, 0.0, 2.0, rtol=1e-20)
    with pytest.raises(ValidationError):
        roots.bisect(sq2, 0.0, 2.0, maxiter=0)
    with pytest.raises(ValidationError):
        roots.newton(lambda x: [1.0, 2.0], 0.0)
    with pytest.raises(ValidationError):
        roots.newton(lambda x: 1j, 0.0)
    with pytest.raises(ValidationError):
        roots.newton(lambda x: float("inf"), 0.0)
    with pytest.raises(ValidationError):
        roots.newton(sq2, "a")


# -- polynomials -------------------------------------------------------------------------
def test_poly_real_roots() -> None:
    r = roots.polyroots([1, -6, 11, -6])  # (x-1)(x-2)(x-3)
    np.testing.assert_allclose(r.root, [1.0, 2.0, 3.0], atol=1e-12)
    assert r.residual < 1e-9
    assert not np.iscomplexobj(r.root)


def test_poly_complex_pair() -> None:
    r = roots.polyroots([1, 0, 1])  # x^2 + 1
    np.testing.assert_allclose(r.root, [-1j, 1j], atol=1e-14)


def test_poly_quadratic_formula() -> None:
    r = roots.polyroots([2, -3, -5]).root  # 2x^2-3x-5 = (2x-5)(x+1)
    np.testing.assert_allclose(r, [-1.0, 2.5], atol=1e-14)


def test_poly_leading_zeros_and_zero_roots() -> None:
    np.testing.assert_allclose(roots.polyroots([0, 0, 1, -4]).root, [4.0])
    np.testing.assert_allclose(roots.polyroots([1, -3, 2, 0]).root, [0.0, 1.0, 2.0], atol=1e-12)


def test_poly_constant_and_all_zero() -> None:
    assert roots.polyroots([5.0]).root.size == 0
    with pytest.raises(ValidationError):
        roots.polyroots([0.0, 0.0])


def test_poly_complex_coefficients() -> None:
    r = roots.polyroots([1, -(1 + 1j)]).root  # x - (1+i)
    np.testing.assert_allclose(r, [1 + 1j])


def test_poly_unit_circle_roots_of_unity() -> None:
    r = roots.polyroots([1, 0, 0, 0, 0, -1]).root  # x^5 = 1
    np.testing.assert_allclose(np.abs(r), np.ones(5), atol=1e-14)
    np.testing.assert_allclose(r**5, np.ones(5), atol=1e-13)


def test_poly_repeated_root_accuracy_limit() -> None:
    r = roots.polyroots([1, -4, 6, -4, 1]).root  # (x-1)^4, accuracy ~ eps**(1/4)
    np.testing.assert_allclose(r, np.ones(4), atol=1e-3)


def test_poly_validation() -> None:
    with pytest.raises(ValidationError):
        roots.polyroots([1.0, float("nan")])
    with pytest.raises(ValidationError):
        roots.polyroots([])
    with pytest.raises(DimensionError):
        roots.polyroots([[1, 2], [3, 4]])


# -- systems -----------------------------------------------------------------------------
def test_fsolve_circle_line() -> None:
    def f(v):
        return [v[0] ** 2 + v[1] ** 2 - 1.0, v[0] - v[1]]

    r = roots.fsolve(f, [1.0, 0.5])
    np.testing.assert_allclose(r.root, [SQRT2 / 2, SQRT2 / 2], atol=1e-10)
    assert r.converged and r.residual < 1e-10 and r.method == "damped Newton"


def test_fsolve_sum_product() -> None:
    # x + y = 3, x*y = 2 -> (1, 2) or (2, 1)
    r = roots.fsolve(lambda v: [v[0] + v[1] - 3.0, v[0] * v[1] - 2.0], [0.5, 2.5])
    np.testing.assert_allclose(sorted(r.root), [1.0, 2.0], atol=1e-9)


def test_fsolve_analytic_jacobian_matches_numeric() -> None:
    def f(v):
        return [v[0] ** 2 + v[1] ** 2 - 4.0, v[0] * v[1] - 1.0]

    def jac(v):
        return [[2 * v[0], 2 * v[1]], [v[1], v[0]]]

    a = roots.fsolve(f, [2.0, 0.3], jac=jac)
    b = roots.fsolve(f, [2.0, 0.3])
    np.testing.assert_allclose(a.root, b.root, atol=1e-8)
    assert abs(a.root[0] ** 2 + a.root[1] ** 2 - 4.0) < 1e-10


def test_fsolve_linear_system_one_step() -> None:
    a = np.array([[3.0, 1.0], [1.0, 2.0]])
    b = np.array([9.0, 8.0])  # solution (2, 3)
    r = roots.fsolve(lambda v: a @ np.asarray(v) - b, [0.0, 0.0])
    np.testing.assert_allclose(r.root, [2.0, 3.0], atol=1e-9)


def test_fsolve_scalar_as_system() -> None:
    r = roots.fsolve(lambda v: [v[0] ** 3 - 8.0], [3.0])
    assert r.root[0] == pytest.approx(2.0, abs=1e-8)


def test_fsolve_does_not_mutate_x0() -> None:
    x0 = np.array([1.0, 0.5])
    keep = x0.copy()
    roots.fsolve(lambda v: [v[0] - 0.2, v[1] - 0.3], x0)
    np.testing.assert_array_equal(x0, keep)


def test_fsolve_singular_jacobian() -> None:
    with pytest.raises(SingularMatrixError):
        roots.fsolve(lambda v: [v[0] ** 2, v[1]], [0.0, 1.0])


def test_fsolve_no_root_stalls() -> None:
    with pytest.raises(ConvergenceError):
        roots.fsolve(lambda v: [v[0] ** 2 + 1.0], [1.0])


def test_fsolve_maxiter() -> None:
    with pytest.raises(ConvergenceError):
        roots.fsolve(lambda v: [math.atan(v[0]) - 0.5], [1.0], maxiter=1)


def test_fsolve_validation() -> None:
    with pytest.raises(ValidationError):
        roots.fsolve(None, [1.0])
    with pytest.raises(DimensionError):
        roots.fsolve(lambda v: [v[0], v[0]], [1.0])  # 2 equations, 1 unknown
    with pytest.raises(DimensionError):
        roots.fsolve(lambda v: [v[0]], [1.0], jac=lambda v: [[1.0, 0.0]])
    with pytest.raises(ValidationError):
        roots.fsolve(lambda v: [v[0]], [float("nan")])
