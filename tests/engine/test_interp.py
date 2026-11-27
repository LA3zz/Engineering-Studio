"""Validation tests for engine.interp. References are exact polynomials and known properties."""

from __future__ import annotations

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine import interp

X = np.array([0.0, 0.5, 1.5, 2.0, 3.5, 4.0])  # deliberately uneven spacing
ALL_1D = ["linear", "nearest", "previous", "next", "pchip", "spline", "natural"]


@pytest.mark.parametrize("method", ALL_1D)
def test_exact_at_nodes(method) -> None:
    y = np.sin(X)
    np.testing.assert_allclose(interp.interp1(X, y, X, method=method), y, atol=1e-14)


def test_linear_exact_on_line() -> None:
    q = np.array([0.1, 0.9, 1.75, 3.3, 3.99])
    np.testing.assert_allclose(interp.interp1(X, 3 * X - 2, q), 3 * q - 2, atol=1e-13)


@pytest.mark.parametrize("method", ["pchip", "spline", "natural"])
def test_cubic_methods_exact_on_lines(method) -> None:
    q = np.linspace(0, 4, 17)
    np.testing.assert_allclose(interp.interp1(X, 2 * X + 1, q, method=method), 2 * q + 1,
                               atol=1e-12)


def test_spline_exact_on_cubic_polynomial() -> None:
    """Not-a-knot spline reproduces any cubic exactly."""
    def p(t):
        return 0.5 * t**3 - 2 * t**2 + t - 4

    q = np.linspace(0, 4, 41)
    np.testing.assert_allclose(interp.interp1(X, p(X), q, method="spline"), p(q), atol=1e-11)


def test_natural_spline_has_zero_end_curvature_effect() -> None:
    """For a quadratic the natural spline is NOT exact (end curvature forced to 0)."""
    q = np.array([0.1])
    exact = q**2
    got = interp.interp1(X, X**2, q, method="natural")
    assert abs(float(got[0]) - float(exact[0])) > 1e-4


def test_spline_accuracy_on_sine() -> None:
    xs = np.linspace(0, 1, 11)
    q = np.linspace(0, 1, 101)
    err = np.max(np.abs(interp.interp1(xs, np.sin(xs), q, method="spline") - np.sin(q)))
    assert err < 1e-5  # bound ~ 5*h^4*max|f''''|/384 = 1.3e-6


def test_pchip_is_monotone_without_overshoot() -> None:
    xs = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    ys = np.array([0.0, 0.0, 0.1, 5.0, 5.0, 5.0])  # steep step: splines would overshoot
    q = np.linspace(0, 5, 501)
    v = interp.interp1(xs, ys, q, method="pchip")
    assert np.all(np.diff(v) >= -1e-12)
    assert v.min() >= -1e-12 and v.max() <= 5.0 + 1e-12


def test_step_methods() -> None:
    xs = np.array([0.0, 1.0, 2.0])
    ys = np.array([10.0, 20.0, 40.0])
    q = np.array([0.2, 0.7, 1.0, 1.4, 1.6])
    np.testing.assert_array_equal(interp.interp1(xs, ys, q, method="previous"),
                                  [10, 10, 20, 20, 20])
    np.testing.assert_array_equal(interp.interp1(xs, ys, q, method="next"),
                                  [20, 20, 20, 40, 40])
    np.testing.assert_array_equal(interp.interp1(xs, ys, q, method="nearest"),
                                  [10, 20, 20, 20, 40])
    assert interp.interp1(xs, ys, 0.5, method="nearest") == 20.0  # tie goes up


def test_scalar_in_scalar_out_and_shape_kept() -> None:
    v = interp.interp1([0, 1], [0, 2], 0.25)
    assert isinstance(v, float) and v == pytest.approx(0.5)
    out = interp.interp1([0, 1], [0, 2], np.array([[0.0, 0.5], [0.25, 1.0]]))
    assert out.shape == (2, 2)
    np.testing.assert_allclose(out, [[0, 1], [0.5, 2]])


def test_out_of_range_modes() -> None:
    xs, ys = [0.0, 1.0, 2.0], [0.0, 1.0, 4.0]
    with pytest.raises(ValidationError, match="outside the data range"):
        interp.interp1(xs, ys, [0.5, 2.5])
    n = interp.interp1(xs, ys, [-1.0, 0.5, 3.0], extrap="nan")
    assert np.isnan(n[0]) and np.isnan(n[2]) and n[1] == pytest.approx(0.5)
    np.testing.assert_allclose(interp.interp1(xs, ys, [-1.0, 3.0], extrap="clamp"), [0.0, 4.0])
    np.testing.assert_allclose(interp.interp1(xs, ys, [-1.0, 3.0], extrap="extrapolate"),
                               [-1.0, 7.0])  # end-segment lines: slopes 1 and 3


def test_spline_extrapolation_of_exact_cubic() -> None:
    xs = np.linspace(0, 2, 6)
    v = interp.interp1(xs, xs**3, [2.5], method="spline", extrap="extrapolate")
    assert v[0] == pytest.approx(2.5**3, abs=1e-9)


def test_inputs_not_mutated() -> None:
    xs, ys, q = X.copy(), np.sin(X), np.array([0.3, 2.2])
    snap = (xs.copy(), ys.copy(), q.copy())
    interp.interp1(xs, ys, q, method="spline")
    for a, b in zip((xs, ys, q), snap, strict=True):
        np.testing.assert_array_equal(a, b)


def test_interp1_validation() -> None:
    with pytest.raises(ValidationError, match="strictly increasing"):
        interp.interp1([0, 1, 1], [0, 1, 2], 0.5)
    with pytest.raises(ValidationError, match="strictly increasing"):
        interp.interp1([2, 1, 0], [0, 1, 2], 0.5)
    with pytest.raises(ValidationError, match="at least 2"):
        interp.interp1([0], [1], 0.0)
    with pytest.raises(DimensionError):
        interp.interp1([0, 1, 2], [0, 1], 0.5)
    with pytest.raises(ValidationError, match="not supported"):
        interp.interp1([0, 1], [0, 1], 0.5, method="cubic")
    with pytest.raises(ValidationError, match="not supported"):
        interp.interp1([0, 1], [0, 1], 0.5, extrap="zero")
    with pytest.raises(ValidationError, match="NaN"):
        interp.interp1([0, 1], [0, 1], float("nan"))
    with pytest.raises(ValidationError, match="NaN"):
        interp.interp1([0, 1], [0, float("inf")], 0.5)
    with pytest.raises(ValidationError, match="complex"):
        interp.interp1([0, 1], [0, 1j], 0.5)


# -- 2-D -------------------------------------------------------------------------------
XG = np.array([0.0, 1.0, 2.5, 3.0, 4.0])
YG = np.array([-1.0, 0.0, 1.0, 2.0, 3.5])
XX, YY = np.meshgrid(XG, YG)  # z[j, i] = f(x[i], y[j])


def test_bilinear_exact_on_plane_and_bilinear_surface() -> None:
    qx = np.array([0.3, 1.7, 3.9, 2.75])
    qy = np.array([-0.5, 0.2, 3.0, 1.5])
    plane = interp.interp2(XG, YG, 2 * XX + 3 * YY + 1, qx, qy)
    np.testing.assert_allclose(plane, 2 * qx + 3 * qy + 1, atol=1e-12)
    xy = interp.interp2(XG, YG, XX * YY, qx, qy)
    np.testing.assert_allclose(xy, qx * qy, atol=1e-12)


def test_cubic_exact_on_tensor_cubic() -> None:
    def f(x, y):
        return x**3 - 2 * x * y**2 + y**3 + x * y - 5

    qx = np.array([0.3, 1.7, 3.9, 2.75])
    qy = np.array([-0.5, 0.2, 3.0, 1.5])
    got = interp.interp2(XG, YG, f(XX, YY), qx, qy, method="cubic")
    np.testing.assert_allclose(got, f(qx, qy), atol=1e-9)


def test_interp2_nearest_and_nodes() -> None:
    z = XX + 10 * YY
    assert interp.interp2(XG, YG, z, 1.0, 0.0, method="nearest") == pytest.approx(1.0)
    assert interp.interp2(XG, YG, z, 1.1, 0.1, method="nearest") == pytest.approx(1.0)
    np.testing.assert_allclose(interp.interp2(XG, YG, z, XX.ravel(), YY.ravel()), z.ravel(),
                               atol=1e-12)


def test_interp2_axis_orientation() -> None:
    """z[j, i] pairs x[i] with y[j]: use an asymmetric function to catch a swap."""
    z = 1.0 * XX + 100.0 * YY
    assert interp.interp2(XG, YG, z, 4.0, -1.0) == pytest.approx(4.0 - 100.0)
    assert interp.interp2(XG, YG, z, 0.0, 3.5) == pytest.approx(350.0)


def test_interp2_shape_and_range_modes() -> None:
    z = XX + YY
    qx = np.array([[0.5, 1.0], [2.0, 9.0]])
    qy = np.array([[0.5, 1.0], [2.0, 0.0]])
    with pytest.raises(ValidationError, match="outside the data range"):
        interp.interp2(XG, YG, z, qx, qy)
    n = interp.interp2(XG, YG, z, qx, qy, extrap="nan")
    assert n.shape == (2, 2) and np.isnan(n[1, 1]) and n[0, 0] == pytest.approx(1.0)
    c = interp.interp2(XG, YG, z, qx, qy, extrap="clamp")
    assert c[1, 1] == pytest.approx(4.0 + 0.0)
    e = interp.interp2(XG, YG, z, qx, qy, extrap="extrapolate")
    assert e[1, 1] == pytest.approx(9.0, abs=1e-12)  # plane extends linearly


def test_interp2_validation() -> None:
    z = XX + YY
    with pytest.raises(DimensionError, match="shape"):
        interp.interp2(XG, YG[:4], z, 1.0, 1.0)
    with pytest.raises(DimensionError, match="same shape"):
        interp.interp2(XG, YG, z, [1.0, 2.0], [1.0])
    with pytest.raises(ValidationError, match="strictly increasing"):
        interp.interp2(XG[::-1], YG, z, 1.0, 1.0)
    with pytest.raises(ValidationError, match="at least 4"):
        interp.interp2([0, 1, 2], [0, 1, 2, 3], np.zeros((4, 3)), 1.0, 1.0, method="cubic")
    with pytest.raises(ValidationError, match="not supported"):
        interp.interp2(XG, YG, z, 1.0, 1.0, method="spline")
    with pytest.raises(ValidationError, match="cannot extrapolate"):
        interp.interp2(XG, YG, z, 1.0, 1.0, method="cubic", extrap="extrapolate")
    with pytest.raises(ValidationError, match="NaN"):
        interp.interp2(XG, YG, z, float("nan"), 1.0)
