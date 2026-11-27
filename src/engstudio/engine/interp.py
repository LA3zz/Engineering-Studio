"""Interpolation of sampled data (E5).

``interp1`` (1-D) methods: ``linear``, ``nearest``, ``previous``, ``next``, ``pchip`` (monotone
cubic, no overshoot), ``spline`` (cubic, not-a-knot as in MATLAB) and ``natural`` (cubic,
zero second derivative at the ends). ``interp2`` interpolates on a rectangular grid:
``linear`` (bilinear), ``nearest`` and ``cubic`` (global tensor-product cubic spline,
>= 4 points per axis, no extrapolation).

Differences from MATLAB: the default for queries outside the data range is ``extrap="error"``
(MATLAB returns NaN silently); use ``"nan"``, ``"clamp"`` (nearest end value) or
``"extrapolate"`` explicitly. ``x`` must be strictly increasing. The step methods
(``nearest``/``previous``/``next``) extrapolate as a constant. ``interp2`` evaluates at the
point pairs (xq[i], yq[i]) and ``z`` has shape (len(y), len(x)), the ``meshgrid`` layout.
Scalar queries return a ``float``; array queries return an array of the query's shape.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import interpolate

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector

__all__ = ["interp1", "interp2"]

_METHODS_1D = ("linear", "nearest", "previous", "next", "pchip", "spline", "natural")
_METHODS_2D = ("linear", "nearest", "cubic")
_EXTRAP = ("error", "nan", "clamp", "extrapolate")


def _check_choice(value: str, allowed: tuple[str, ...], name: str) -> None:
    if value not in allowed:
        raise ValidationError(f"{name}: {value!r} is not supported; use one of {allowed}")


def _grid_axis(a: ArrayLike, name: str, minimum: int) -> NDArray:
    v = as_vector(a, name, allow_complex=False)
    if v.size < minimum:
        raise ValidationError(f"{name}: need at least {minimum} points, got {v.size}")
    if not np.all(np.diff(v) > 0):
        raise ValidationError(f"{name}: must be strictly increasing (no duplicates)")
    return v


def _query(q: ArrayLike, name: str) -> tuple[NDArray, tuple[int, ...]]:
    shape = np.shape(q)
    return as_vector(np.asarray(q).reshape(-1), name, allow_complex=False), shape


def _finish(out: NDArray, shape: tuple[int, ...]) -> float | NDArray:
    return float(out[0]) if shape == () else out.reshape(shape)


def _apply_range(
    q: NDArray, lo: NDArray, hi: NDArray, extrap: str, name: str
) -> tuple[NDArray, NDArray]:
    """Return (query points to evaluate, mask of points to set to NaN afterwards)."""
    outside = (q < lo) | (q > hi)
    if not np.any(outside):
        return q, np.zeros(q.shape, dtype=bool)
    if extrap == "error":
        rows = outside.any(axis=1) if q.ndim > 1 else outside
        k = int(np.flatnonzero(rows)[0])
        raise ValidationError(
            f"{name}: query point {k} is outside the data range; "
            "use extrap='nan', 'clamp' or 'extrapolate' to allow it")
    if extrap == "extrapolate":
        return q, np.zeros(q.shape, dtype=bool)
    return np.clip(q, lo, hi), (outside if extrap == "nan" else np.zeros(q.shape, dtype=bool))


# -- 1-D -------------------------------------------------------------------------------
def _eval_1d(x: NDArray, y: NDArray, q: NDArray, method: str) -> NDArray:
    n = x.size
    if method == "linear":
        lo = np.clip(np.searchsorted(x, q, side="right") - 1, 0, n - 2)
        t = (q - x[lo]) / (x[lo + 1] - x[lo])
        return (1.0 - t) * y[lo] + t * y[lo + 1]
    if method in ("nearest", "previous", "next"):
        qc = np.clip(q, x[0], x[-1])
        if method == "previous":
            idx = np.clip(np.searchsorted(x, qc, side="right") - 1, 0, n - 1)
        elif method == "next":
            idx = np.clip(np.searchsorted(x, qc, side="left"), 0, n - 1)
        else:
            lo = np.clip(np.searchsorted(x, qc, side="right") - 1, 0, n - 2)
            idx = np.where(qc - x[lo] >= x[lo + 1] - qc, lo + 1, lo)  # ties go up, as MATLAB
        return y[idx]
    if method == "pchip":
        return np.asarray(interpolate.PchipInterpolator(x, y, extrapolate=True)(q))
    bc = "not-a-knot" if method == "spline" else "natural"
    return np.asarray(interpolate.CubicSpline(x, y, bc_type=bc, extrapolate=True)(q))


def interp1(
    x: ArrayLike, y: ArrayLike, xq: ArrayLike, *, method: str = "linear", extrap: str = "error",
) -> float | NDArray:
    """Interpolate samples ``(x, y)`` at the query points ``xq``."""
    _check_choice(method, _METHODS_1D, "method")
    _check_choice(extrap, _EXTRAP, "extrap")
    xv = _grid_axis(x, "x", 2)
    yv = as_vector(y, "y", allow_complex=False, length=xv.size)
    q, shape = _query(xq, "xq")
    qe, nan_mask = _apply_range(q, xv[0], xv[-1], extrap, "interp1")
    out = _eval_1d(xv, yv, qe, method)
    out = np.where(nan_mask, np.nan, out)
    return _finish(out, shape)


# -- 2-D -------------------------------------------------------------------------------
def interp2(
    x: ArrayLike, y: ArrayLike, z: ArrayLike, xq: ArrayLike, yq: ArrayLike, *,
    method: str = "linear", extrap: str = "error",
) -> float | NDArray:
    """Interpolate ``z[j, i] = f(x[i], y[j])`` at the point pairs ``(xq, yq)``."""
    _check_choice(method, _METHODS_2D, "method")
    _check_choice(extrap, _EXTRAP, "extrap")
    if method == "cubic" and extrap == "extrapolate":
        raise ValidationError("interp2: method='cubic' cannot extrapolate; use 'clamp' or 'nan'")
    minimum = 4 if method == "cubic" else 2
    xv = _grid_axis(x, "x", minimum)
    yv = _grid_axis(y, "y", minimum)
    zm = as_matrix(z, "z", allow_complex=False)
    if zm.shape != (yv.size, xv.size):
        raise DimensionError(
            f"z must have shape (len(y), len(x)) = ({yv.size}, {xv.size}), got {zm.shape}")
    qx, shape = _query(xq, "xq")
    qy, shape_y = _query(yq, "yq")
    if shape != shape_y:
        raise DimensionError(f"xq and yq must have the same shape, got {shape} and {shape_y}")
    lo = np.array([xv[0], yv[0]])
    hi = np.array([xv[-1], yv[-1]])
    pts = np.column_stack([qx, qy])
    pts, nan_mask = _apply_range(pts, lo, hi, extrap, "interp2")
    if method == "cubic":
        # global tensor-product spline (FITPACK, interpolating); it clamps outside the grid
        spl = interpolate.RectBivariateSpline(yv, xv, zm, kx=3, ky=3, s=0)
        out = np.asarray(spl.ev(pts[:, 1], pts[:, 0]))
    else:
        rgi = interpolate.RegularGridInterpolator(
            (yv, xv), zm, method=method, bounds_error=False, fill_value=None)
        out = np.asarray(rgi(pts[:, ::-1]))
    out = np.where(nan_mask.any(axis=1), np.nan, out)
    return _finish(out, shape)
