"""Regression and curve fitting (E6).

``linfit`` (general linear least squares, SVD), ``polyfit``/``polyval`` (highest power first, as in
MATLAB), ``fit_curve`` (nonlinear least squares, SciPy ``curve_fit``) and
``confidence_intervals`` (Student t). All fits return a ``FitResult``.

Statistics: with ``dof = n - p > 0`` the covariance is ``s^2 (A^T W A)^-1`` where ``s^2`` is the
(weighted) residual sum of squares over ``dof``; weights are therefore *relative*. With
``dof == 0`` (exact interpolation) the covariance and standard errors are NaN and an info
diagnostic is added. ``fit_curve`` with ``sigma`` and ``absolute_sigma=True`` treats ``sigma`` as
true standard deviations of ``y`` (covariance not rescaled by the residuals).

``residuals`` are always ``y - model`` (unweighted). ``r_squared`` is ``1 - SSres/SStot`` about
the (weighted) mean of ``y``, weighted when weights/sigma are given; it is NaN when ``y`` is
constant. For a model without a constant term it is not the usual coefficient of determination.
Rank-deficient designs raise ``SingularMatrixError``; a badly conditioned design (1/cond < 1e-12)
adds a warning (for polynomials, centre and scale ``x`` first).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import optimize, stats

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector, singular_error

__all__ = ["FitResult", "confidence_intervals", "fit_curve", "linfit", "polyfit", "polyval"]

EPS = float(np.finfo(float).eps)
ILL_CONDITIONED_RCOND = 1e-12


@dataclass(frozen=True, eq=False)
class FitResult:
    params: NDArray
    covariance: NDArray
    residuals: NDArray
    r_squared: float
    diagnostics: tuple[Diagnostic, ...] = ()
    stderr: NDArray | None = None
    dof: int = 0
    method: str = ""
    nfev: int = 0


# -- helpers -------------------------------------------------------------------------
def _positive_vector(a: ArrayLike, name: str, length: int) -> NDArray:
    v = as_vector(a, name, allow_complex=False, length=length)
    if not np.all(v > 0):
        raise ValidationError(f"{name}: all values must be > 0")
    return v


def _r_squared(
    y: NDArray, resid: NDArray, w: NDArray | None, diags: list[Diagnostic]
) -> float:
    if w is None:
        sst = float(np.sum((y - y.mean()) ** 2))
        ssr = float(np.sum(resid**2))
    else:
        mean = float(np.sum(w * y) / np.sum(w))
        sst = float(np.sum(w * (y - mean) ** 2))
        ssr = float(np.sum(w * resid**2))
    if sst == 0.0:
        diags.append(Diagnostic("info", "R2_UNDEFINED", "y is constant: r_squared is NaN"))
        return float("nan")
    return 1.0 - ssr / sst


def _no_dof(diags: list[Diagnostic]) -> None:
    diags.append(Diagnostic(
        "info", "NO_DEGREES_OF_FREEDOM",
        "as many parameters as data points: covariance and standard errors are NaN"))


# -- linear least squares ------------------------------------------------------------
def linfit(A: ArrayLike, y: ArrayLike, *, weights: ArrayLike | None = None) -> FitResult:
    """Least-squares solution of ``y ~ A @ beta`` (columns of ``A`` are the basis functions)."""
    am = as_matrix(A, "A", allow_complex=False)
    m, p = am.shape
    yv = as_vector(y, "y", allow_complex=False, length=m)
    if m < p:
        raise ValidationError(f"linfit: {p} parameters need at least {p} observations, got {m}")
    w = _positive_vector(weights, "weights", m) if weights is not None else None
    sw = np.sqrt(w) if w is not None else np.ones(m)
    aw, yw = am * sw[:, None], yv * sw
    u, s, vt = np.linalg.svd(aw, full_matrices=False)
    rc = float(s[-1] / s[0]) if s[0] > 0 else 0.0
    if s[0] == 0.0 or s[-1] <= max(m, p) * EPS * s[0]:
        raise singular_error("linfit: design matrix is rank deficient", rc)
    diags: list[Diagnostic] = []
    if rc < ILL_CONDITIONED_RCOND:
        diags.append(Diagnostic(
            "warning", "ILL_CONDITIONED",
            f"linfit: design matrix is badly conditioned (1/cond={rc:.3g}); "
            "centre and scale the inputs"))
    beta = vt.T @ ((u.T @ yw) / s)
    resid = yv - am @ beta
    dof = m - p
    if dof > 0:
        s2 = float(np.sum((resid * sw) ** 2)) / dof
        cov = (vt.T / s**2) @ vt * s2
    else:
        cov = np.full((p, p), np.nan)
        _no_dof(diags)
    r2 = _r_squared(yv, resid, w, diags)
    return FitResult(beta, cov, resid, r2, tuple(diags), np.sqrt(np.diag(cov)), dof,
                     "linear least squares (SVD)")


def polyfit(
    x: ArrayLike, y: ArrayLike, deg: int, *, weights: ArrayLike | None = None
) -> FitResult:
    """Fit a polynomial of degree ``deg``; ``params`` are highest power first."""
    if isinstance(deg, bool) or not isinstance(deg, (int, np.integer)) or deg < 0:
        raise ValidationError("deg must be a non-negative integer")
    xv = as_vector(x, "x", allow_complex=False)
    yv = as_vector(y, "y", allow_complex=False, length=xv.size)
    if xv.size < deg + 1:
        raise ValidationError(f"polyfit: degree {deg} needs at least {deg + 1} points, "
                              f"got {xv.size}")
    res = linfit(np.vander(xv, int(deg) + 1), yv, weights=weights)
    return FitResult(res.params, res.covariance, res.residuals, res.r_squared, res.diagnostics,
                     res.stderr, res.dof, "polynomial least squares (SVD)")


def polyval(p: ArrayLike, x: ArrayLike) -> float | NDArray:
    """Evaluate a polynomial (highest power first); scalar in, float out."""
    pv = as_vector(p, "p")
    xa = as_matrix(x, "x") if np.ndim(x) > 0 else as_vector(x, "x")
    out = np.polyval(pv, xa)
    if np.ndim(x) == 0:
        return complex(out[0]) if np.iscomplexobj(out) else float(out[0])
    return out.reshape(np.shape(x))


# -- nonlinear least squares ---------------------------------------------------------
def _bounds(bounds: tuple[ArrayLike, ArrayLike], p: int, p0: NDArray) -> tuple[NDArray, NDArray]:
    try:
        lo, hi = bounds
        lo_a = np.broadcast_to(np.asarray(lo, dtype=float), (p,)).copy()
        hi_a = np.broadcast_to(np.asarray(hi, dtype=float), (p,)).copy()
    except (TypeError, ValueError) as exc:
        raise DimensionError(f"bounds: expected (lower, upper), scalars or length {p}") from exc
    if np.any(np.isnan(lo_a)) or np.any(np.isnan(hi_a)):
        raise ValidationError("bounds: must not contain NaN")
    if not np.all(lo_a < hi_a):
        raise ValidationError("bounds: lower must be < upper for every parameter")
    if np.any(p0 < lo_a) or np.any(p0 > hi_a):
        raise ValidationError("p0: initial guess must lie within bounds")
    return lo_a, hi_a


def fit_curve(
    f: Callable[..., ArrayLike], x: ArrayLike, y: ArrayLike, p0: ArrayLike, *,
    sigma: ArrayLike | None = None, absolute_sigma: bool = False,
    bounds: tuple[ArrayLike, ArrayLike] | None = None, maxfev: int = 2000,
) -> FitResult:
    """Fit ``y ~ f(x, *params)`` by nonlinear least squares starting at ``p0``.

    ``f`` receives the whole ``x`` array and must return an array of the same shape as ``y``.
    Levenberg-Marquardt is used without bounds, trust-region reflective with bounds.
    """
    if not callable(f):
        raise ValidationError("f: expected a callable")
    xv = as_vector(x, "x", allow_complex=False)
    yv = as_vector(y, "y", allow_complex=False, length=xv.size)
    p0v = as_vector(p0, "p0", allow_complex=False)
    n, p = xv.size, p0v.size
    if n < p:
        raise ValidationError(f"fit_curve: {p} parameters need at least {p} points, got {n}")
    if isinstance(maxfev, bool) or not isinstance(maxfev, int) or maxfev < 1:
        raise ValidationError("maxfev must be a positive integer")
    sig = _positive_vector(sigma, "sigma", n) if sigma is not None else None

    def model(xx: NDArray, *pp: float) -> NDArray:
        out = np.asarray(f(xx, *pp))
        if out.dtype.kind not in "biuf" or out.shape != yv.shape:
            raise ValidationError(f"f must return a real array of shape {yv.shape}")
        return out.astype(float, copy=False)

    model(xv, *p0v)  # fail early with a clear message
    kwargs: dict[str, object] = {}
    if bounds is None:
        kwargs.update(method="lm", maxfev=maxfev)
    else:
        lo, hi = _bounds(bounds, p, p0v)
        kwargs.update(method="trf", bounds=(lo, hi), max_nfev=maxfev)
    diags: list[Diagnostic] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", optimize.OptimizeWarning)
        try:
            popt, pcov, info, msg, _ier = optimize.curve_fit(
                model, xv, yv, p0=p0v, sigma=sig, absolute_sigma=absolute_sigma,
                full_output=True, **kwargs)
        except RuntimeError as exc:
            raise ConvergenceError(f"fit_curve: {exc}", None, None) from exc
        except ValueError as exc:
            raise ValidationError(f"fit_curve: {exc}") from exc
    for w in caught:
        if issubclass(w.category, optimize.OptimizeWarning):
            diags.append(Diagnostic("warning", "COVARIANCE_UNDETERMINED", str(w.message)))
    cov = np.array(pcov, dtype=float)
    if not np.all(np.isfinite(cov)):
        cov = np.full((p, p), np.nan)
        if not any(d.code == "COVARIANCE_UNDETERMINED" for d in diags):
            diags.append(Diagnostic("warning", "COVARIANCE_UNDETERMINED",
                                    "covariance could not be estimated"))
    sd = np.sqrt(np.diag(cov))
    if p > 1 and np.all(np.isfinite(sd)) and np.all(sd > 0):
        corr = cov / np.outer(sd, sd)
        np.fill_diagonal(corr, 0.0)
        if np.max(np.abs(corr)) > 1.0 - 1e-6:
            diags.append(Diagnostic(
                "warning", "PARAMETERS_NOT_IDENTIFIABLE",
                "two parameters are almost perfectly correlated: they are probably not "
                "separately determined by the data; covariance and errors are unreliable"))
    dof = n - p
    if dof == 0 and not (absolute_sigma and sig is not None):
        _no_dof(diags)
    resid = yv - model(xv, *popt)
    r2 = _r_squared(yv, resid, None if sig is None else 1.0 / sig**2, diags)
    return FitResult(np.asarray(popt, dtype=float), cov, resid, r2, tuple(diags),
                     np.sqrt(np.diag(cov)), dof, "nonlinear least squares", int(info["nfev"]))


# -- statistics ------------------------------------------------------------------------
def confidence_intervals(result: FitResult, level: float = 0.95) -> NDArray:
    """Two-sided Student-t confidence intervals, shape (p, 2): ``params -/+ t * stderr``."""
    lv = np.asarray(level)
    if lv.size != 1 or lv.dtype.kind not in "biuf" or not 0.0 < float(lv) < 1.0:
        raise ValidationError("level must be a number in (0, 1)")
    if result.dof <= 0 or result.stderr is None or not np.all(np.isfinite(result.stderr)):
        raise ValidationError("confidence_intervals: no degrees of freedom or undefined "
                              "standard errors")
    t = float(stats.t.ppf(0.5 + float(lv) / 2.0, result.dof))
    half = t * result.stderr
    return np.column_stack([result.params - half, result.params + half])
