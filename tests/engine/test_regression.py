"""Validation tests for engine.regression.

References: closed-form simple-regression formulas (Sxx, Sxy), exact polynomial/exponential
data, the Student-t table value t(0.975, 3 dof) = 3.182446, and cross-checks between the linear
and nonlinear fitters.
"""

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
from engstudio.engine import regression as rg

X5 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
Y5 = np.array([2.2, 2.8, 3.6, 4.5, 5.1])


def _simple_regression(x, y):
    n = x.size
    xb, yb = x.mean(), y.mean()
    sxx = np.sum((x - xb) ** 2)
    sxy = np.sum((x - xb) * (y - yb))
    slope = sxy / sxx
    icpt = yb - slope * xb
    rss = np.sum((y - icpt - slope * x) ** 2)
    s2 = rss / (n - 2)
    se_slope = math.sqrt(s2 / sxx)
    se_icpt = math.sqrt(s2 * (1.0 / n + xb**2 / sxx))
    r2 = 1.0 - rss / np.sum((y - yb) ** 2)
    return slope, icpt, se_slope, se_icpt, r2


# -- polyfit / linfit ------------------------------------------------------------------
def test_polyfit_exact_quadratic() -> None:
    x = np.linspace(-2, 3, 12)
    y = 1.5 * x**2 - 2.0 * x + 0.5
    r = rg.polyfit(x, y, 2)
    np.testing.assert_allclose(r.params, [1.5, -2.0, 0.5], atol=1e-11)
    assert r.r_squared == pytest.approx(1.0, abs=1e-12)
    assert np.max(np.abs(r.residuals)) < 1e-11
    assert r.dof == 9


def test_polyfit_line_matches_closed_form() -> None:
    slope, icpt, se_s, se_i, r2 = _simple_regression(X5, Y5)
    r = rg.polyfit(X5, Y5, 1)
    np.testing.assert_allclose(r.params, [slope, icpt], rtol=1e-12)
    np.testing.assert_allclose(r.stderr, [se_s, se_i], rtol=1e-10)
    assert r.r_squared == pytest.approx(r2, abs=1e-12)
    assert r.dof == 3
    np.testing.assert_allclose(r.covariance, r.covariance.T, atol=1e-15)
    np.testing.assert_allclose(np.sqrt(np.diag(r.covariance)), r.stderr)
    np.testing.assert_allclose(r.residuals, Y5 - (slope * X5 + icpt), atol=1e-13)


def test_polyfit_degree_zero_is_mean() -> None:
    r = rg.polyfit(X5, Y5, 0)
    assert r.params[0] == pytest.approx(Y5.mean(), abs=1e-13)


def test_polyfit_weighted_ignores_outlier() -> None:
    x = np.arange(8.0)
    y = 2.0 * x + 1.0
    y_bad = y.copy()
    y_bad[3] += 50.0
    w = np.ones(8)
    w[3] = 1e-14
    r = rg.polyfit(x, y_bad, 1, weights=w)
    np.testing.assert_allclose(r.params, [2.0, 1.0], atol=1e-6)


def test_weight_two_equals_duplicated_point() -> None:
    w = np.array([2.0, 1.0, 1.0, 1.0, 1.0])
    a = rg.polyfit(X5, Y5, 1, weights=w)
    b = rg.polyfit(np.append(X5, X5[0]), np.append(Y5, Y5[0]), 1)
    np.testing.assert_allclose(a.params, b.params, rtol=1e-12)


def test_polyfit_two_points_no_dof() -> None:
    r = rg.polyfit([0.0, 2.0], [1.0, 5.0], 1)
    np.testing.assert_allclose(r.params, [2.0, 1.0], atol=1e-13)
    assert r.dof == 0 and np.all(np.isnan(r.covariance))
    assert any(d.code == "NO_DEGREES_OF_FREEDOM" for d in r.diagnostics)


def test_polyfit_constant_y_r2_nan() -> None:
    r = rg.polyfit(X5, np.full(5, 3.0), 1)
    assert math.isnan(r.r_squared)
    assert any(d.code == "R2_UNDEFINED" for d in r.diagnostics)


def test_polyfit_rank_deficient() -> None:
    with pytest.raises(SingularMatrixError):
        rg.polyfit([1.0, 1.0, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0], 1)
    with pytest.raises(SingularMatrixError):
        rg.polyfit([1.0, 2.0, 1.0, 2.0], [1.0, 2.0, 3.0, 4.0], 2)  # only 2 distinct x


def test_polyfit_ill_conditioned_warning() -> None:
    x = np.linspace(3000.0, 3010.0, 30)
    r = rg.polyfit(x, 0.001 * x, 2)
    assert any(d.code == "ILL_CONDITIONED" for d in r.diagnostics)


def test_polyfit_not_mutating_inputs() -> None:
    x, y = X5.copy(), Y5.copy()
    rg.polyfit(x, y, 2)
    np.testing.assert_array_equal(x, X5)
    np.testing.assert_array_equal(y, Y5)


def test_linfit_two_variables() -> None:
    a, b = np.meshgrid(np.arange(4.0), np.arange(3.0))
    a, b = a.ravel(), b.ravel()
    y = 1.0 + 2.0 * a + 3.0 * b
    r = rg.linfit(np.column_stack([np.ones_like(a), a, b]), y)
    np.testing.assert_allclose(r.params, [1.0, 2.0, 3.0], atol=1e-12)
    assert r.dof == 9


def test_linfit_basis_functions() -> None:
    """y = 2 sin(x) + 0.5 cos(x) recovered from exact samples."""
    x = np.linspace(0, 6, 25)
    r = rg.linfit(np.column_stack([np.sin(x), np.cos(x)]), 2 * np.sin(x) + 0.5 * np.cos(x))
    np.testing.assert_allclose(r.params, [2.0, 0.5], atol=1e-12)


def test_polyval() -> None:
    assert rg.polyval([2.0, -3.0, 1.0], 2.0) == pytest.approx(3.0)  # 2*4-6+1
    assert isinstance(rg.polyval([1.0, 0.0], 3.0), float)
    out = rg.polyval([1.0, 0.0, -1.0], np.array([0.0, 1.0, 2.0]))
    np.testing.assert_allclose(out, [-1.0, 0.0, 3.0])
    assert rg.polyval([1.0, 0.0], np.array([[1.0, 2.0], [3.0, 4.0]])).shape == (2, 2)


def test_validation_linear() -> None:
    with pytest.raises(ValidationError, match="deg"):
        rg.polyfit(X5, Y5, -1)
    with pytest.raises(ValidationError, match="deg"):
        rg.polyfit(X5, Y5, 1.5)
    with pytest.raises(ValidationError, match="at least"):
        rg.polyfit([1.0, 2.0], [1.0, 2.0], 2)
    with pytest.raises(DimensionError):
        rg.polyfit([1.0, 2.0, 3.0], [1.0, 2.0], 1)
    with pytest.raises(ValidationError, match="NaN"):
        rg.polyfit([1.0, 2.0, float("nan")], [1.0, 2.0, 3.0], 1)
    with pytest.raises(ValidationError, match="> 0"):
        rg.polyfit(X5, Y5, 1, weights=[1, 1, 1, 1, 0])
    with pytest.raises(DimensionError):
        rg.polyfit(X5, Y5, 1, weights=[1, 1, 1])
    with pytest.raises(ValidationError, match="complex"):
        rg.polyfit(X5, Y5 * 1j, 1)
    with pytest.raises(ValidationError, match="observations"):
        rg.linfit(np.ones((2, 3)), [1.0, 2.0])


# -- confidence intervals --------------------------------------------------------------
def test_confidence_intervals_t_table() -> None:
    r = rg.polyfit(X5, Y5, 1)  # dof = 3, t(0.975, 3) = 3.182446
    ci = rg.confidence_intervals(r)
    half = (ci[:, 1] - ci[:, 0]) / 2
    np.testing.assert_allclose(half / r.stderr, 3.182446, rtol=1e-6)
    np.testing.assert_allclose((ci[:, 0] + ci[:, 1]) / 2, r.params, rtol=1e-12)
    wide = rg.confidence_intervals(r, 0.99)
    assert np.all(wide[:, 1] - wide[:, 0] > ci[:, 1] - ci[:, 0])


def test_confidence_intervals_errors() -> None:
    r = rg.polyfit([0.0, 2.0], [1.0, 5.0], 1)
    with pytest.raises(ValidationError):
        rg.confidence_intervals(r)
    ok = rg.polyfit(X5, Y5, 1)
    for bad in (0.0, 1.0, 1.5, "a"):
        with pytest.raises(ValidationError):
            rg.confidence_intervals(ok, bad)


# -- nonlinear -------------------------------------------------------------------------
def _exp(x, a, k):
    return a * np.exp(-k * x)


def test_fit_curve_exact_exponential() -> None:
    x = np.linspace(0, 4, 20)
    r = rg.fit_curve(_exp, x, 2.0 * np.exp(-1.5 * x), [1.0, 1.0])
    np.testing.assert_allclose(r.params, [2.0, 1.5], rtol=1e-8)
    assert r.r_squared == pytest.approx(1.0, abs=1e-10)
    assert r.dof == 18 and r.nfev > 0 and r.method == "nonlinear least squares"


def test_fit_curve_noisy_within_stderr() -> None:
    rng = np.random.default_rng(0)
    x = np.linspace(0, 4, 60)
    y = 2.0 * np.exp(-1.5 * x) + rng.normal(0.0, 0.02, x.size)
    r = rg.fit_curve(_exp, x, y, [1.0, 1.0])
    assert np.all(np.abs(r.params - [2.0, 1.5]) < 5 * r.stderr)
    assert 0.9 < r.r_squared <= 1.0
    ci = rg.confidence_intervals(r, 0.999)
    assert ci[0, 0] < 2.0 < ci[0, 1] and ci[1, 0] < 1.5 < ci[1, 1]


def test_fit_curve_matches_linear_fit_for_a_line() -> None:
    def line(x, m, c):
        return m * x + c

    nl = rg.fit_curve(line, X5, Y5, [0.0, 0.0])
    li = rg.polyfit(X5, Y5, 1)
    np.testing.assert_allclose(nl.params, li.params, rtol=1e-7)
    np.testing.assert_allclose(nl.covariance, li.covariance, rtol=1e-5)
    assert nl.r_squared == pytest.approx(li.r_squared, abs=1e-9)


def test_fit_curve_absolute_sigma_covariance() -> None:
    def line(x, m, c):
        return m * x + c

    y = 2.0 * X5 + 1.0
    r = rg.fit_curve(line, X5, y, [0.0, 0.0], sigma=np.full(5, 0.1), absolute_sigma=True)
    a = np.column_stack([X5, np.ones(5)])
    np.testing.assert_allclose(r.covariance, 0.01 * np.linalg.inv(a.T @ a), rtol=1e-6)
    relative = rg.fit_curve(line, X5, y, [0.0, 0.0], sigma=np.full(5, 0.1))
    assert np.max(np.abs(relative.covariance)) < 1e-12  # exact data: residual-scaled


def test_fit_curve_bounds_active() -> None:
    def prop(x, a):
        return a * x

    r = rg.fit_curve(prop, X5, 2.0 * X5, [0.5], bounds=([0.0], [1.0]))
    assert r.params[0] == pytest.approx(1.0, abs=1e-8)
    free = rg.fit_curve(prop, X5, 2.0 * X5, [0.5], bounds=(0.0, 10.0))
    assert free.params[0] == pytest.approx(2.0, abs=1e-8)


def test_fit_curve_non_identifiable_parameters_warn() -> None:
    def redundant(x, a, b):
        return (a + b) * x  # only the sum a + b is determined

    y = 2.0 * X5 + np.array([0.1, -0.1, 0.05, -0.05, 0.0])
    r = rg.fit_curve(redundant, X5, y, [0.3, 0.2])
    assert any(d.code == "PARAMETERS_NOT_IDENTIFIABLE" for d in r.diagnostics)
    well = rg.fit_curve(_exp, X5, 2.0 * np.exp(-0.3 * X5) + 0.01 * np.sin(7 * X5), [1.0, 0.1])
    assert not any(d.code == "PARAMETERS_NOT_IDENTIFIABLE" for d in well.diagnostics)


def test_fit_curve_maxfev_raises() -> None:
    x = np.linspace(0, 4, 20)
    with pytest.raises(ConvergenceError):
        rg.fit_curve(_exp, x, 2.0 * np.exp(-1.5 * x), [10.0, -3.0], maxfev=2)


def test_fit_curve_validation() -> None:
    x = np.linspace(0, 4, 10)
    y = 2.0 * np.exp(-1.5 * x)
    with pytest.raises(ValidationError):
        rg.fit_curve(None, x, y, [1.0, 1.0])
    with pytest.raises(DimensionError):
        rg.fit_curve(_exp, x, y[:5], [1.0, 1.0])
    with pytest.raises(ValidationError, match="shape"):
        rg.fit_curve(lambda xx, a, k: a, x, y, [1.0, 1.0])
    with pytest.raises(ValidationError, match="at least"):
        rg.fit_curve(_exp, x[:1], y[:1], [1.0, 1.0])
    with pytest.raises(ValidationError, match="within bounds"):
        rg.fit_curve(_exp, x, y, [1.0, 1.0], bounds=([2.0, 0.0], [3.0, 5.0]))
    with pytest.raises(ValidationError, match="lower"):
        rg.fit_curve(_exp, x, y, [1.0, 1.0], bounds=([2.0, 0.0], [1.0, 5.0]))
    with pytest.raises(ValidationError, match="> 0"):
        rg.fit_curve(_exp, x, y, [1.0, 1.0], sigma=np.zeros(10))
    with pytest.raises(ValidationError, match="maxfev"):
        rg.fit_curve(_exp, x, y, [1.0, 1.0], maxfev=0)
    with pytest.raises(ValidationError, match="NaN"):
        rg.fit_curve(_exp, x, y, [float("nan"), 1.0])
