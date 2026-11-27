"""Numerical differentiation and integration (E3).

Accuracy notes (double precision, smooth functions):
- ``derivative`` uses 3-point second-order formulas with step ``eps**(1/3) * max(1, |x|)``
  (first derivative, ~1e-10 relative) or ``eps**(1/4) * max(1, |x|)`` (second derivative,
  ~1e-6 relative). Forward/backward variants use one-sided second-order stencils.
- Integrands and functions must return real finite scalars; complex values are not supported.
- ``quad``/``dblquad`` wrap SciPy QUADPACK; if it reports trouble the result is still returned
  with ``converged=False`` and a warning diagnostic. ``a > b`` gives the negated integral.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import integrate
from scipy.integrate import IntegrationWarning

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.validation import as_vector

__all__ = [
    "IntegrateResult", "cumtrapz", "derivative", "derivative_data", "dblquad", "gradient",
    "jacobian", "quad", "simpson", "trapz",
]

EPS = float(np.finfo(float).eps)


@dataclass(frozen=True, eq=False)
class IntegrateResult:
    value: float
    error_estimate: float
    nfev: int
    converged: bool
    diagnostics: tuple[Diagnostic, ...] = ()


# -- helpers -------------------------------------------------------------------------
def _real_scalar(x: object, name: str) -> float:
    arr = np.asarray(x)
    if arr.size != 1 or arr.dtype.kind not in "biuf":
        raise ValidationError(f"{name}: expected a real scalar")
    v = float(arr.reshape(-1)[0])
    if not np.isfinite(v):
        raise ValidationError(f"{name}: must be finite (got {v})")
    return v


class _Scalar:
    """Wraps a user function: checks it returns a real finite scalar, counts calls."""

    def __init__(self, f: object, name: str) -> None:
        if not callable(f):
            raise ValidationError(f"{name}: expected a callable")
        self._f = f
        self._name = name
        self.calls = 0

    def __call__(self, *args: float) -> float:
        self.calls += 1
        value = self._f(*args)  # type: ignore[operator]
        arr = np.asarray(value)
        if arr.size != 1 or arr.dtype.kind not in "biuf":
            raise ValidationError(f"{self._name}{args}: must return a real scalar")
        v = float(arr.reshape(-1)[0])
        if not np.isfinite(v):
            raise ValidationError(f"{self._name}{args}: returned non-finite value {v}")
        return v


def _step(h: float | None, x0: float, order: int) -> float:
    if h is None:
        return (EPS ** (1 / 3) if order == 1 else EPS ** 0.25) * max(1.0, abs(x0))
    step = _real_scalar(h, "h")
    if step <= 0:
        raise ValidationError("h: must be positive")
    return step


def _tol(value: float, name: str) -> float:
    v = _real_scalar(value, name)
    if v < 0:
        raise ValidationError(f"{name}: must be >= 0")
    return v


# -- differentiation -----------------------------------------------------------------
def derivative(
    f: Callable[[float], float], x: float, *, order: int = 1, h: float | None = None,
    method: str = "central",
) -> float:
    """First or second derivative of scalar ``f`` at ``x`` by finite differences."""
    if order not in (1, 2):
        raise ValidationError("order must be 1 or 2")
    if method not in ("central", "forward", "backward"):
        raise ValidationError("method must be 'central', 'forward' or 'backward'")
    fn = _Scalar(f, "f")
    x0 = _real_scalar(x, "x")
    step = _step(h, x0, order)
    if method == "central":
        if order == 1:
            return (fn(x0 + step) - fn(x0 - step)) / (2 * step)
        return (fn(x0 + step) - 2 * fn(x0) + fn(x0 - step)) / step**2
    s = 1.0 if method == "forward" else -1.0
    f0, f1, f2 = fn(x0), fn(x0 + s * step), fn(x0 + 2 * s * step)
    if order == 1:
        return s * (-3 * f0 + 4 * f1 - f2) / (2 * step)
    f3 = fn(x0 + 3 * s * step)
    return (2 * f0 - 5 * f1 + 4 * f2 - f3) / step**2


def _vector_point(x: ArrayLike) -> NDArray:
    return as_vector(x, "x", allow_complex=False)


def gradient(f: Callable[[NDArray], float], x: ArrayLike) -> NDArray:
    """Gradient of scalar ``f(x)`` (x a 1-D array) by central differences."""
    fn = _Scalar(f, "f")
    x0 = _vector_point(x)
    g = np.empty_like(x0)
    for i in range(x0.size):
        h = EPS ** (1 / 3) * max(1.0, abs(x0[i]))
        hi, lo = x0.copy(), x0.copy()
        hi[i] += h
        lo[i] -= h
        g[i] = (fn(hi) - fn(lo)) / (2 * h)
    return g


def jacobian(f: Callable[[NDArray], ArrayLike], x: ArrayLike) -> NDArray:
    """Jacobian (m x n) of vector function ``f: R^n -> R^m`` by central differences."""
    if not callable(f):
        raise ValidationError("f: expected a callable")
    x0 = _vector_point(x)
    cols = []
    for i in range(x0.size):
        h = EPS ** (1 / 3) * max(1.0, abs(x0[i]))
        hi, lo = x0.copy(), x0.copy()
        hi[i] += h
        lo[i] -= h
        fhi = as_vector(f(hi), "f(x)", allow_complex=False)
        flo = as_vector(f(lo), "f(x)", allow_complex=False, length=fhi.size)
        cols.append((fhi - flo) / (2 * h))
    return np.column_stack(cols)


def derivative_data(x: ArrayLike, y: ArrayLike) -> NDArray:
    """Derivative of sampled data: second-order accurate, including edges and uneven spacing.

    ``x`` must be strictly increasing with at least 3 points.
    """
    xv = as_vector(x, "x", allow_complex=False)
    yv = as_vector(y, "y", allow_complex=False, length=xv.size)
    if xv.size < 3:
        raise ValidationError("derivative_data needs at least 3 points")
    if not np.all(np.diff(xv) > 0):
        raise ValidationError("x must be strictly increasing")
    return np.gradient(yv, xv, edge_order=2)


# -- integration of functions --------------------------------------------------------
def _run_quad(call: Callable[[], tuple[float, float]], fn: _Scalar) -> IntegrateResult:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", IntegrationWarning)
        value, err = call()
    messages = [str(w.message).strip() for w in caught
                if issubclass(w.category, IntegrationWarning)]
    diags = tuple(
        Diagnostic(severity="warning", code="INTEGRATION_WARNING", message=f"quad: {m}")
        for m in messages)
    if not np.isfinite(value):
        raise ValidationError("integral is not finite (divergent or invalid integrand)")
    return IntegrateResult(float(value), float(err), fn.calls, not messages, diags)


def quad(
    f: Callable[[float], float], a: float, b: float, *, rtol: float = 1.49e-8,
    atol: float = 1.49e-8, limit: int = 200,
) -> IntegrateResult:
    """Adaptive integral of scalar ``f`` over [a, b]; limits may be +-inf."""
    fn = _Scalar(f, "f")
    lo, hi = _limit(a, "a"), _limit(b, "b")
    rt, at = _tol(rtol, "rtol"), _tol(atol, "atol")
    if not isinstance(limit, int) or limit < 1:
        raise ValidationError("limit must be a positive integer")
    if lo == hi:
        return IntegrateResult(0.0, 0.0, 0, True)
    return _run_quad(lambda: integrate.quad(fn, lo, hi, epsabs=at, epsrel=rt, limit=limit), fn)


def dblquad(
    f: Callable[[float, float], float], x0: float, x1: float, y0: float, y1: float, *,
    rtol: float = 1.49e-8, atol: float = 1.49e-8,
) -> IntegrateResult:
    """Integral of ``f(x, y)`` over the rectangle [x0, x1] x [y0, y1] (finite limits)."""
    fn = _Scalar(f, "f")
    xs = [_real_scalar(v, n) for v, n in ((x0, "x0"), (x1, "x1"), (y0, "y0"), (y1, "y1"))]
    rt, at = _tol(rtol, "rtol"), _tol(atol, "atol")
    return _run_quad(
        lambda: integrate.dblquad(lambda y, x: fn(x, y), xs[0], xs[1], xs[2], xs[3],
                                  epsabs=at, epsrel=rt), fn)


def _limit(v: float, name: str) -> float:
    arr = np.asarray(v)
    if arr.size != 1 or arr.dtype.kind not in "biuf" or np.isnan(float(arr.reshape(-1)[0])):
        raise ValidationError(f"{name}: expected a real number or +-inf")
    return float(arr.reshape(-1)[0])


# -- integration of sampled data -----------------------------------------------------
def _samples(y: ArrayLike, x: ArrayLike | None, dx: float) -> tuple[NDArray, NDArray | None, float]:
    yv = as_vector(y, "y", allow_complex=False)
    if yv.size < 2:
        raise ValidationError("y: need at least 2 samples")
    xv = None
    if x is not None:
        xv = as_vector(x, "x", allow_complex=False)
        if xv.size != yv.size:
            raise DimensionError(f"x has {xv.size} points but y has {yv.size}")
        if not np.all(np.diff(xv) > 0):
            raise ValidationError("x must be strictly increasing")
    step = _real_scalar(dx, "dx")
    if step <= 0:
        raise ValidationError("dx: must be positive")
    return yv, xv, step


def trapz(y: ArrayLike, x: ArrayLike | None = None, dx: float = 1.0) -> float:
    """Trapezoidal rule; ``x`` optional (then uniform spacing ``dx``)."""
    yv, xv, step = _samples(y, x, dx)
    return float(integrate.trapezoid(yv, x=xv) if xv is not None
                 else integrate.trapezoid(yv, dx=step))


def simpson(y: ArrayLike, x: ArrayLike | None = None, dx: float = 1.0) -> float:
    """Simpson's rule (SciPy's handling of an even number of samples)."""
    yv, xv, step = _samples(y, x, dx)
    return float(integrate.simpson(yv, x=xv) if xv is not None
                 else integrate.simpson(yv, dx=step))


def cumtrapz(y: ArrayLike, x: ArrayLike | None = None, dx: float = 1.0) -> NDArray:
    """Cumulative trapezoidal integral; same length as ``y``, first value 0."""
    yv, xv, step = _samples(y, x, dx)
    if xv is not None:
        return integrate.cumulative_trapezoid(yv, x=xv, initial=0.0)
    return integrate.cumulative_trapezoid(yv, dx=step, initial=0.0)
