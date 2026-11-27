"""Validation tests for engine.optimize. Every reference minimum is derived analytically."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine import optimize as opt


def rosen(v):
    return (1.0 - v[0]) ** 2 + 100.0 * (v[1] - v[0] ** 2) ** 2


def rosen_grad(v):
    return [-2.0 * (1.0 - v[0]) - 400.0 * v[0] * (v[1] - v[0] ** 2),
            200.0 * (v[1] - v[0] ** 2)]


def quad(v):
    return (v[0] - 1.0) ** 2 + 3.0 * (v[1] + 2.0) ** 2  # minimum (1, -2), f = 0


def quad_grad(v):
    return [2.0 * (v[0] - 1.0), 6.0 * (v[1] + 2.0)]


# -- scalar ----------------------------------------------------------------------------
def test_scalar_quadratic() -> None:
    r = opt.minimize_scalar(lambda x: (x - 2.0) ** 2 + 1.0, 0.0, 5.0)
    assert r.x == pytest.approx(2.0, abs=1e-6)
    assert r.fun == pytest.approx(1.0, abs=1e-10)
    assert r.converged and r.nfev > 0


def test_scalar_cosine_minimum_at_pi() -> None:
    r = opt.minimize_scalar(math.cos, 2.0, 5.0)
    assert r.x == pytest.approx(math.pi, abs=1e-6)
    assert r.fun == pytest.approx(-1.0, abs=1e-12)


def test_scalar_minimum_at_boundary() -> None:
    r = opt.minimize_scalar(lambda x: x * x, 1.0, 3.0)
    assert r.x == pytest.approx(1.0, abs=1e-4)


def test_scalar_maxiter() -> None:
    with pytest.raises(ConvergenceError):
        opt.minimize_scalar(lambda x: (x - 2.0) ** 2, 0.0, 5.0, maxiter=2)


def test_scalar_validation() -> None:
    with pytest.raises(ValidationError):
        opt.minimize_scalar(None, 0.0, 1.0)
    with pytest.raises(ValidationError, match="a must be < b"):
        opt.minimize_scalar(math.cos, 1.0, 1.0)
    with pytest.raises(ValidationError):
        opt.minimize_scalar(lambda x: [1.0, 2.0], 0.0, 1.0)
    with pytest.raises(ValidationError):
        opt.minimize_scalar(lambda x: float("nan"), 0.0, 1.0)
    with pytest.raises(ValidationError):
        opt.minimize_scalar(math.cos, 0.0, 1.0, xtol=0.0)


# -- unconstrained ---------------------------------------------------------------------
def test_bfgs_quadratic_with_gradient() -> None:
    r = opt.minimize(quad, [5.0, 5.0], jac=quad_grad)
    np.testing.assert_allclose(r.x, [1.0, -2.0], atol=1e-6)
    assert r.fun < 1e-10 and r.converged and r.method == "BFGS"


def test_bfgs_rosenbrock_with_gradient() -> None:
    r = opt.minimize(rosen, [-1.2, 1.0], jac=rosen_grad, tol=1e-9)
    np.testing.assert_allclose(r.x, [1.0, 1.0], atol=1e-5)


def test_bfgs_rosenbrock_numeric_gradient() -> None:
    r = opt.minimize(rosen, [-1.2, 1.0], tol=1e-6)
    np.testing.assert_allclose(r.x, [1.0, 1.0], atol=1e-3)


def test_nelder_mead() -> None:
    r = opt.minimize(quad, [4.0, 3.0], method="Nelder-Mead", tol=1e-10)
    np.testing.assert_allclose(r.x, [1.0, -2.0], atol=1e-5)
    assert r.method == "Nelder-Mead"


def test_minimize_maxiter() -> None:
    with pytest.raises(ConvergenceError):
        opt.minimize(rosen, [-1.2, 1.0], maxiter=2)


def test_minimize_does_not_mutate_x0() -> None:
    x0 = np.array([5.0, 5.0])
    opt.minimize(quad, x0, jac=quad_grad)
    np.testing.assert_array_equal(x0, [5.0, 5.0])


# -- bounds and constraints ------------------------------------------------------------
def test_bounds_active() -> None:
    def f(v):
        return (v[0] - 3.0) ** 2 + (v[1] - 3.0) ** 2

    r = opt.minimize(f, [0.5, 0.5], bounds=[(0.0, 2.0), (0.0, 2.0)])
    np.testing.assert_allclose(r.x, [2.0, 2.0], atol=1e-6)
    assert r.fun == pytest.approx(2.0, abs=1e-6)
    assert r.method == "L-BFGS-B"


def test_bounds_one_sided_inactive() -> None:
    r = opt.minimize(quad, [0.0, 0.0], jac=quad_grad, bounds=[(0.0, None), (None, 0.0)])
    np.testing.assert_allclose(r.x, [1.0, -2.0], atol=1e-6)


def test_equality_constraint() -> None:
    """min x^2 + y^2 s.t. x + y = 1 -> (1/2, 1/2), f = 1/2 (Lagrange)."""
    r = opt.minimize(lambda v: v[0] ** 2 + v[1] ** 2, [2.0, -1.0],
                     constraints=[{"type": "eq", "fun": lambda v: v[0] + v[1] - 1.0}])
    np.testing.assert_allclose(r.x, [0.5, 0.5], atol=1e-6)
    assert r.fun == pytest.approx(0.5, abs=1e-8) and r.method == "SLSQP"


def test_inequality_constraints_projection() -> None:
    """min (x-1)^2 + (y-2.5)^2 over a polygon: projection of (1, 2.5) on x - 2y + 2 = 0
    is (1.4, 1.7), f = 0.8; other constraints are inactive there."""
    cons = [
        {"type": "ineq", "fun": lambda v: v[0] - 2.0 * v[1] + 2.0},
        {"type": "ineq", "fun": lambda v: -v[0] - 2.0 * v[1] + 6.0},
        {"type": "ineq", "fun": lambda v: -v[0] + 2.0 * v[1] + 2.0},
    ]
    r = opt.minimize(lambda v: (v[0] - 1.0) ** 2 + (v[1] - 2.5) ** 2, [2.0, 0.0],
                     bounds=[(0.0, None), (0.0, None)], constraints=cons)
    np.testing.assert_allclose(r.x, [1.4, 1.7], atol=1e-6)
    assert r.fun == pytest.approx(0.8, abs=1e-8)


def test_vector_valued_constraint() -> None:
    r = opt.minimize(lambda v: v[0] + v[1], [1.0, 1.0],
                     constraints=[{"type": "ineq", "fun": lambda v: [v[0] - 1.0, v[1] - 2.0]}])
    np.testing.assert_allclose(r.x, [1.0, 2.0], atol=1e-6)


def test_infeasible_constraints() -> None:
    cons = [{"type": "ineq", "fun": lambda v: v[0] - 2.0},
            {"type": "ineq", "fun": lambda v: 1.0 - v[0]}]
    with pytest.raises(ConvergenceError):
        opt.minimize(lambda v: v[0] ** 2, [0.0], constraints=cons)


def test_minimize_validation() -> None:
    with pytest.raises(ValidationError):
        opt.minimize(None, [1.0])
    with pytest.raises(ValidationError, match="NaN"):
        opt.minimize(quad, [float("nan"), 0.0])
    with pytest.raises(ValidationError):
        opt.minimize(lambda v: [1.0, 2.0], [1.0, 1.0])
    with pytest.raises(ValidationError, match="not supported"):
        opt.minimize(quad, [0.0, 0.0], method="Newton")
    with pytest.raises(DimensionError):
        opt.minimize(quad, [0.0, 0.0], bounds=[(0.0, 1.0)])
    with pytest.raises(ValidationError, match="within bounds"):
        opt.minimize(quad, [5.0, 0.0], bounds=[(0.0, 1.0), (None, None)])
    with pytest.raises(ValidationError, match="lower"):
        opt.minimize(quad, [0.5, 0.0], bounds=[(1.0, 0.0), (None, None)])
    with pytest.raises(ValidationError, match="BFGS"):
        opt.minimize(quad, [0.5, 0.0], bounds=[(0.0, 1.0), (None, None)], method="BFGS")
    with pytest.raises(ValidationError, match="SLSQP"):
        opt.minimize(quad, [0.5, 0.0], method="BFGS",
                     constraints=[{"type": "eq", "fun": lambda v: v[0]}])
    with pytest.raises(ValidationError, match="constraints"):
        opt.minimize(quad, [0.5, 0.0], constraints=[{"type": "lt", "fun": lambda v: v[0]}])
    with pytest.raises(ValidationError, match="jac"):
        opt.minimize(quad, [0.5, 0.0], jac=quad_grad, method="Nelder-Mead")
    with pytest.raises(DimensionError):
        opt.minimize(quad, [0.5, 0.0], jac=lambda v: [1.0, 2.0, 3.0])
    with pytest.raises(ValidationError, match="tol"):
        opt.minimize(quad, [0.5, 0.0], tol=0.0)


# -- linear programming ----------------------------------------------------------------
def test_linprog_vertex() -> None:
    """min -x - 2y s.t. x + y <= 4, 0 <= x, 0 <= y <= 3 -> vertex (1, 3), f = -7."""
    r = opt.linprog([-1.0, -2.0], A_ub=[[1.0, 1.0]], b_ub=[4.0],
                    bounds=[(0.0, None), (0.0, 3.0)])
    np.testing.assert_allclose(r.x, [1.0, 3.0], atol=1e-9)
    assert r.fun == pytest.approx(-7.0, abs=1e-9) and r.converged


def test_linprog_equality() -> None:
    """min x + y s.t. x + 2y = 4, x,y >= 0 -> (0, 2), f = 2."""
    r = opt.linprog([1.0, 1.0], A_eq=[[1.0, 2.0]], b_eq=[4.0],
                    bounds=[(0.0, None), (0.0, None)])
    np.testing.assert_allclose(r.x, [0.0, 2.0], atol=1e-9)
    assert r.fun == pytest.approx(2.0, abs=1e-9)


def test_linprog_default_bounds_are_free() -> None:
    r = opt.linprog([1.0], A_ub=[[-1.0]], b_ub=[5.0])  # x >= -5 only
    assert r.x[0] == pytest.approx(-5.0, abs=1e-9)


def test_linprog_infeasible_and_unbounded() -> None:
    with pytest.raises(ConvergenceError, match="infeasible"):
        opt.linprog([1.0], A_ub=[[1.0]], b_ub=[-1.0], bounds=[(0.0, None)])
    with pytest.raises(ConvergenceError, match="unbounded"):
        opt.linprog([-1.0])


def test_linprog_validation() -> None:
    with pytest.raises(ValidationError, match="together"):
        opt.linprog([1.0, 1.0], A_ub=[[1.0, 1.0]])
    with pytest.raises(DimensionError):
        opt.linprog([1.0, 1.0], A_ub=[[1.0, 1.0, 1.0]], b_ub=[1.0])
    with pytest.raises(DimensionError):
        opt.linprog([1.0, 1.0], A_ub=[[1.0, 1.0]], b_ub=[1.0, 2.0])
    with pytest.raises(DimensionError):
        opt.linprog([1.0, 1.0], bounds=[(0.0, 1.0)])
    with pytest.raises(ValidationError, match="NaN"):
        opt.linprog([1.0, float("nan")])
