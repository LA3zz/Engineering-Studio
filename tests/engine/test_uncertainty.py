"""E12 tests: engine.uncertainty against closed-form GUM results and Monte Carlo statistics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.uncertainty import UncertaintyResult, propagate


def _codes(res):
    return [d.code for d in res.diagnostics]


# -- first-order law: closed forms --------------------------------------------------------
def test_sum_of_independent_inputs():
    """y = x1 + x2: u = sqrt(u1^2 + u2^2) (GUM 5.1.2, unit sensitivities)."""
    res = propagate(lambda v: v[0] + v[1], [10.0, 20.0], [0.3, 0.4])
    assert isinstance(res, UncertaintyResult) and res.method == "linear"
    assert res.value == 30.0
    assert res.standard_uncertainty == pytest.approx(0.5, rel=1e-8)
    assert np.allclose(res.sensitivities, [1.0, 1.0], atol=1e-8)
    assert np.allclose(res.contributions, [0.3, 0.4], rtol=1e-8)
    assert math.hypot(*res.contributions) == pytest.approx(res.standard_uncertainty, rel=1e-8)


def test_product_relative_uncertainties_add_in_quadrature():
    """y = x1 x2: (u/y)^2 = (u1/x1)^2 + (u2/x2)^2 (GUM 5.1.6)."""
    x1, x2, u1, u2 = 5.0, 8.0, 0.05, 0.2
    res = propagate(lambda v: v[0] * v[1], [x1, x2], [u1, u2])
    expected = x1 * x2 * math.hypot(u1 / x1, u2 / x2)
    assert res.standard_uncertainty == pytest.approx(expected, rel=1e-8)


def test_power_law():
    """y = x^3: u = 3 x^2 u_x."""
    res = propagate(lambda v: v[0] ** 3, 2.0, 0.01)
    assert res.standard_uncertainty == pytest.approx(3 * 4.0 * 0.01, rel=1e-8)


def test_parallel_resistors():
    """Rp = R1 R2 / (R1 + R2): dRp/dR1 = (R2/(R1+R2))^2, symmetric for R2."""
    r1, r2, u = 100.0, 200.0, 1.0
    res = propagate(lambda v: v[0] * v[1] / (v[0] + v[1]), [r1, r2], [u, u])
    g1, g2 = (r2 / (r1 + r2)) ** 2, (r1 / (r1 + r2)) ** 2
    assert res.value == pytest.approx(200.0 / 3.0, rel=1e-14)
    assert np.allclose(res.sensitivities, [g1, g2], rtol=1e-7)
    assert res.standard_uncertainty == pytest.approx(math.hypot(g1, g2), rel=1e-7)


def test_difference_with_correlation():
    """y = x1 - x2: u^2 = u1^2 + u2^2 - 2 r u1 u2 (GUM 5.2.2)."""
    u1, u2, r = 0.3, 0.5, 0.6
    res = propagate(lambda v: v[0] - v[1], [10.0, 7.0], [u1, u2], corr=[[1, r], [r, 1]])
    assert res.standard_uncertainty == pytest.approx(
        math.sqrt(u1**2 + u2**2 - 2 * r * u1 * u2), rel=1e-8)
    assert "UNC_CORRELATED" in _codes(res)


def test_perfect_correlation_cancels():
    res = propagate(lambda v: v[0] - v[1], [5.0, 5.0], [0.2, 0.2], corr=[[1, 1], [1, 1]])
    assert res.standard_uncertainty == pytest.approx(0.0, abs=1e-8)


def test_small_si_magnitudes_and_zero_estimate():
    """Step size follows the scale of the input, not a fixed 1.0."""
    nano = propagate(lambda v: 2.0 * v[0], 1e-9, 1e-11)
    assert nano.standard_uncertainty == pytest.approx(2e-11, rel=1e-6)
    at_zero = propagate(lambda v: math.sin(v[0]), 0.0, 0.01)
    assert at_zero.standard_uncertainty == pytest.approx(0.01, rel=1e-6)


def test_zero_uncertainties_and_interval():
    res = propagate(lambda v: v[0] ** 2, 3.0, 0.0)
    assert res.standard_uncertainty == 0.0 and res.interval == (9.0, 9.0)
    assert np.allclose(res.sensitivities, [6.0], rtol=1e-7)


def test_coverage_factor_and_interval():
    res = propagate(lambda v: v[0], 10.0, 0.5)
    assert res.k == pytest.approx(1.959964, abs=1e-6)  # normal quantile for 95 %
    assert res.expanded_uncertainty == pytest.approx(res.k * 0.5, rel=1e-8)
    assert res.interval == (pytest.approx(10 - res.k * 0.5), pytest.approx(10 + res.k * 0.5))
    two = propagate(lambda v: v[0], 10.0, 0.5, k=2.0)
    assert two.k == 2.0 and two.expanded_uncertainty == pytest.approx(1.0, rel=1e-8)
    wide = propagate(lambda v: v[0], 10.0, 0.5, coverage=0.9973)
    assert wide.k == pytest.approx(3.0, abs=5e-3)  # three-sigma coverage


def test_inputs_not_mutated():
    x, ux = np.array([1.0, 2.0]), np.array([0.1, 0.1])
    keep = (x.copy(), ux.copy())

    def f(v):
        v[0] = 99.0  # user code mutating its argument must not matter
        return v[0] + v[1]

    propagate(f, x, ux)
    assert np.array_equal(x, keep[0]) and np.array_equal(ux, keep[1])


# -- validity warnings ---------------------------------------------------------------------
def test_nonlinearity_warning():
    big = propagate(lambda v: v[0] ** 2, 1.0, 0.5)
    assert "UNC_NONLINEAR" in _codes(big)
    small = propagate(lambda v: v[0] ** 2, 1.0, 0.01)
    assert "UNC_NONLINEAR" not in _codes(small)
    assert "UNC_NONLINEAR" not in _codes(propagate(lambda v: 3 * v[0] + v[1], [1, 2], [0.4, 0.4]))


def test_zero_sensitivity_but_curved_is_flagged():
    """y = x^2 at x = 0 has zero first-order uncertainty although y clearly varies."""
    res = propagate(lambda v: v[0] ** 2, 0.0, 0.1)
    assert res.standard_uncertainty == pytest.approx(0.0, abs=1e-9)
    assert "UNC_NONLINEAR" in _codes(res)


def test_check_skipped_when_model_undefined_nearby():
    def f(v):
        return float("nan") if v[0] < 0 else v[0]

    res = propagate(f, 0.1, 0.2)
    assert "UNC_CHECK_SKIPPED" in _codes(res)
    assert res.standard_uncertainty == pytest.approx(0.2, rel=1e-6)


# -- Monte Carlo -------------------------------------------------------------------------------
def test_montecarlo_matches_linear_for_linear_model():
    """Sum of normals is normal: sigma = 0.5 and the 95 % interval is value -+ 1.96 sigma."""
    res = propagate(lambda v: v[0] + v[1], [10.0, 20.0], [0.3, 0.4], method="montecarlo",
                    n=200_000)
    assert res.method == "montecarlo" and res.n_samples == 200_000 and res.k is None
    assert res.standard_uncertainty == pytest.approx(0.5, rel=0.01)  # std error ~0.16 %
    assert res.interval[0] == pytest.approx(30 - 1.959964 * 0.5, abs=0.02)
    assert res.interval[1] == pytest.approx(30 + 1.959964 * 0.5, abs=0.02)
    assert res.expanded_uncertainty == pytest.approx(1.959964 * 0.5, rel=0.02)
    assert res.value == 30.0


def test_montecarlo_captures_what_first_order_misses():
    """x ~ N(0, u): y = x^2 has std sqrt(2) u^2 exactly; the linear law gives 0."""
    u = 0.1
    lin = propagate(lambda v: v[0] ** 2, 0.0, u)
    mc = propagate(lambda v: v[0] ** 2, 0.0, u, method="montecarlo", n=200_000)
    assert lin.standard_uncertainty == pytest.approx(0.0, abs=1e-9)
    assert mc.standard_uncertainty == pytest.approx(math.sqrt(2) * u**2, rel=0.02)


def test_montecarlo_correlated_inputs():
    """y = x1 + x2: var = u1^2 + u2^2 + 2 r u1 u2."""
    u1, u2, r = 0.3, 0.4, 0.8
    res = propagate(lambda v: v[0] + v[1], [1.0, 2.0], [u1, u2], method="montecarlo",
                    corr=[[1, r], [r, 1]], n=200_000)
    assert res.standard_uncertainty == pytest.approx(
        math.sqrt(u1**2 + u2**2 + 2 * r * u1 * u2), rel=0.01)


def test_montecarlo_reproducible_with_seed():
    def run(seed):
        return propagate(lambda v: v[0] * v[1], [2.0, 3.0], [0.1, 0.2], method="montecarlo",
                         n=5000, seed=seed)

    a, b, c = run(7), run(7), run(8)
    assert a.standard_uncertainty == b.standard_uncertainty and a.interval == b.interval
    assert a.standard_uncertainty != c.standard_uncertainty
    assert "UNC_UNSEEDED" not in _codes(a)
    assert "UNC_UNSEEDED" in _codes(run(None))


def test_montecarlo_vectorized_equals_loop():
    kw = {"method": "montecarlo", "n": 5000, "seed": 3}
    loop = propagate(lambda v: v[0] * v[1], [2.0, 3.0], [0.1, 0.2], **kw)
    vec = propagate(lambda X: X[:, 0] * X[:, 1], [2.0, 3.0], [0.1, 0.2], vectorized=True, **kw)
    assert vec.standard_uncertainty == pytest.approx(loop.standard_uncertainty, rel=1e-12)
    assert vec.interval == (pytest.approx(loop.interval[0]), pytest.approx(loop.interval[1]))
    assert vec.value == loop.value


def test_montecarlo_few_samples_warning_and_undefined_model():
    few = propagate(lambda v: v[0], 1.0, 0.1, method="montecarlo", n=500)
    assert "UNC_FEW_SAMPLES" in _codes(few)
    with pytest.raises(ValidationError, match="undefined somewhere"):
        propagate(lambda v: 1.0 if v[0] > 0 else float("nan"), 0.5, 1.0, method="montecarlo",
                  n=1000)


# -- validation ----------------------------------------------------------------------------------
@pytest.mark.parametrize("kwargs", [
    {"method": "taylor"}, {"coverage": 0.0}, {"coverage": 1.0}, {"coverage": 1.5},
    {"coverage": np.nan}, {"k": 0.0}, {"k": -2.0}, {"k": np.inf}, {"vectorized": 1},
])
def test_invalid_options(kwargs):
    with pytest.raises(ValidationError):
        propagate(lambda v: v[0], 1.0, 0.1, **kwargs)


@pytest.mark.parametrize("kwargs", [
    {"n": 99}, {"n": 5_000_001}, {"n": 1000.0}, {"n": True}, {"seed": -1}, {"seed": 1.5},
    {"seed": True}, {"k": 2.0},
])
def test_invalid_montecarlo_options(kwargs):
    with pytest.raises(ValidationError):
        propagate(lambda v: v[0], 1.0, 0.1, method="montecarlo", **kwargs)


def test_invalid_inputs():
    def model(v):
        return float(np.sum(v))

    with pytest.raises(DimensionError):
        propagate(model, [1.0, 2.0], [0.1])
    with pytest.raises(ValidationError, match=">= 0"):
        propagate(model, [1.0, 2.0], [0.1, -0.1])
    for bad in ([np.nan, 1.0], [np.inf, 1.0], [], ["a", "b"]):
        with pytest.raises(ValidationError):
            propagate(model, bad, [0.1, 0.1])
        with pytest.raises(ValidationError):
            propagate(model, [1.0, 2.0], bad)
    with pytest.raises(ValidationError, match="callable"):
        propagate("f", 1.0, 0.1)  # type: ignore[arg-type]


@pytest.mark.parametrize("corr", [
    [[1, 0.5], [0.4, 1]],
    [[2, 0], [0, 1]],
    [[1, 1.2], [1.2, 1]],
    [[1, 0, 0]],
])
def test_invalid_correlation_matrix(corr):
    with pytest.raises(ValidationError):
        propagate(lambda v: float(np.sum(v)), [1.0, 2.0], [0.1, 0.1], corr=corr)


def test_correlation_not_positive_semidefinite_and_wrong_size():
    bad = [[1, 0.9, -0.9], [0.9, 1, 0.9], [-0.9, 0.9, 1]]
    with pytest.raises(ValidationError, match="semidefinite"):
        propagate(lambda v: float(np.sum(v)), [1.0] * 3, [0.1] * 3, corr=bad)
    with pytest.raises(DimensionError):
        propagate(lambda v: float(np.sum(v)), [1.0, 2.0], [0.1, 0.1], corr=np.eye(3))


def test_model_output_errors():
    for bad in (lambda v: [1.0, 2.0], lambda v: 1j, lambda v: "x", lambda v: float("nan"),
                lambda v: float("inf")):
        with pytest.raises(ValidationError):
            propagate(bad, 1.0, 0.1)
    with pytest.raises(ValidationError, match="one real value per row"):
        propagate(lambda X: np.ones(X.shape[0] if X.shape[0] == 1 else 3), 1.0, 0.1,
                  method="montecarlo", n=1000, vectorized=True)
