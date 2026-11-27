"""Uncertainty propagation for a scalar measurement model y = f(x) (E12).

``propagate`` offers two methods:

- ``"linear"`` (GUM first-order law): u_c^2 = g^T U g, with sensitivities g from central
  differences (step ``eps**(1/3) * max(|x_i|, u_i)``, so tiny SI magnitudes are handled) and
  covariance U = D R D built from standard uncertainties ``ux`` and an optional correlation
  matrix ``corr``. The interval is ``y -+ k*u_c`` with k from ``coverage`` (normal quantile) or an
  explicit ``k``. A cheap curvature check warns (``UNC_NONLINEAR``) when the first-order result
  may be unreliable, e.g. when a sensitivity is zero but f is curved.
- ``"montecarlo"`` (GUM Supplement 1 style): inputs are drawn from a (multivariate) normal
  distribution, f is evaluated per sample (or once on an ``(n, n_inputs)`` array if
  ``vectorized=True``), the standard uncertainty is the sample standard deviation and the
  interval is the probabilistically symmetric ``coverage`` interval of the results.
  ``seed`` defaults to 0 so results are reproducible; ``seed=None`` uses fresh entropy.

``value`` is always f at the given input estimates. ``contributions[i] = |g_i| * ux[i]`` are
the individual input contributions; with correlated inputs they do not add in quadrature.
Inputs are assumed normally distributed with standard uncertainties ``ux`` (Type A/B alike).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import ndtri

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector

__all__ = ["UncertaintyResult", "propagate"]

EPS = float(np.finfo(float).eps)
MIN_SAMPLES = 100
FEW_SAMPLES = 10_000
MAX_SAMPLES = 5_000_000
MAX_CELLS = 50_000_000
NONLINEAR_RATIO = 0.1


@dataclass(frozen=True, eq=False)
class UncertaintyResult:
    value: float
    standard_uncertainty: float
    expanded_uncertainty: float
    interval: tuple[float, float]
    coverage: float
    sensitivities: NDArray
    contributions: NDArray
    method: str
    k: float | None = None
    n_samples: int = 0
    diagnostics: tuple[Diagnostic, ...] = ()


class _Model:
    """Validated scalar model: callable(f) -> real finite float."""

    def __init__(self, f: Callable, vectorized: bool) -> None:
        if not callable(f):
            raise ValidationError("f: expected a callable f(x)")
        self._f = f
        self._vec = vectorized

    def __call__(self, x: NDArray) -> float:
        out = self._f(x.reshape(1, -1) if self._vec else x)
        arr = np.asarray(out)
        if arr.size != 1 or arr.dtype.kind not in "biuf":
            raise ValidationError("f(x): must return a single real number")
        v = float(arr.reshape(-1)[0])
        if not math.isfinite(v):
            raise ValidationError(f"f(x): returned a non-finite value ({v}) at x = {x}")
        return v

    def batch(self, samples: NDArray) -> NDArray:
        if self._vec:
            arr = np.asarray(self._f(samples.copy()))
            if arr.dtype.kind not in "biuf" or arr.size != samples.shape[0]:
                raise ValidationError(
                    f"f(X): vectorized f must return one real value per row ({samples.shape[0]})")
            ys = arr.reshape(-1).astype(float)
        else:
            ys = np.empty(samples.shape[0])
            for i in range(samples.shape[0]):
                try:
                    ys[i] = self(samples[i].copy())
                except ValidationError as exc:
                    raise ValidationError(
                        f"{exc}; the model is undefined somewhere in the input distribution "
                        f"(sample {i})") from exc
        if not np.all(np.isfinite(ys)):
            bad = int(np.argmax(~np.isfinite(ys)))
            raise ValidationError(
                f"f: returned a non-finite value for sample {bad} (x = {samples[bad]}); the "
                "model is undefined somewhere in the input distribution")
        return ys


def _check_inputs(
    x: ArrayLike, ux: ArrayLike, corr: ArrayLike | None,
) -> tuple[NDArray, NDArray, NDArray]:
    xv = as_vector(x, "x", allow_complex=False)
    uv = as_vector(ux, "ux", allow_complex=False)
    if uv.size != xv.size:
        raise DimensionError(f"ux has {uv.size} values but x has {xv.size}")
    if np.any(uv < 0):
        raise ValidationError("ux: standard uncertainties must be >= 0")
    n = xv.size
    if corr is None:
        return xv, uv, np.diag(uv**2)
    r = as_matrix(corr, "corr", allow_complex=False, square=True)
    if r.shape[0] != n:
        raise DimensionError(f"corr must be {n}x{n} to match x, got {r.shape}")
    if not np.allclose(r, r.T, atol=1e-12, rtol=0) or not np.allclose(np.diag(r), 1.0, atol=1e-12):
        raise ValidationError("corr: must be symmetric with a unit diagonal")
    if np.any(np.abs(r) > 1 + 1e-12):
        raise ValidationError("corr: entries must lie in [-1, 1]")
    if np.linalg.eigvalsh(r).min() < -1e-10:
        raise ValidationError("corr: must be positive semidefinite")
    return xv, uv, uv.reshape(-1, 1) * r * uv.reshape(1, -1)


def _sensitivities(fn: _Model, xv: NDArray, uv: NDArray) -> NDArray:
    g = np.empty(xv.size)
    for i in range(xv.size):
        h = EPS ** (1 / 3) * (max(abs(xv[i]), uv[i]) or 1.0)
        hi, lo = xv.copy(), xv.copy()
        hi[i] += h
        lo[i] -= h
        g[i] = (fn(hi) - fn(lo)) / (2 * h)
    return g


def _curvature_check(
    fn: _Model, xv: NDArray, uv: NDArray, g: NDArray, y0: float,
) -> list[Diagnostic]:
    curved = []
    for i in range(xv.size):
        if uv[i] == 0:
            continue
        hi, lo = xv.copy(), xv.copy()
        hi[i] += uv[i]
        lo[i] -= uv[i]
        try:
            curv = abs(fn(hi) + fn(lo) - 2 * y0) / 2
        except ValidationError:
            return [Diagnostic("info", "UNC_CHECK_SKIPPED",
                               f"f is undefined at x[{i}] +- ux[{i}]; the first-order validity "
                               "check was skipped (consider method='montecarlo')")]
        if curv > NONLINEAR_RATIO * abs(g[i]) * uv[i] + 1e-12 * max(1.0, abs(y0)):
            curved.append(i)
    if curved:
        return [Diagnostic("warning", "UNC_NONLINEAR",
                           f"f is noticeably curved over +-ux for input(s) {curved}; the "
                           "first-order result may be inaccurate (compare method='montecarlo')")]
    return []


def propagate(
    f: Callable[[NDArray], float], x: ArrayLike, ux: ArrayLike, *, method: str = "linear",
    corr: ArrayLike | None = None, coverage: float = 0.95, k: float | None = None,
    n: int = 100_000, seed: int | None = 0, vectorized: bool = False,
) -> UncertaintyResult:
    """Propagate input standard uncertainties ``ux`` through the scalar model ``f(x)``."""
    if method not in ("linear", "montecarlo"):
        raise ValidationError("method: must be 'linear' or 'montecarlo'")
    xv, uv, cov = _check_inputs(x, ux, corr)
    p = np.asarray(coverage)
    if p.size != 1 or p.dtype.kind not in "biuf" or not 0.0 < float(p.reshape(-1)[0]) < 1.0:
        raise ValidationError("coverage: must be a probability strictly between 0 and 1")
    cover = float(p.reshape(-1)[0])
    if method == "montecarlo" and k is not None:
        raise ValidationError("k: only used by method='linear'")
    if k is not None:
        kk = np.asarray(k)
        if kk.size != 1 or kk.dtype.kind not in "biuf":
            raise ValidationError("k: must be a positive finite number")
        kval = float(kk.reshape(-1)[0])
        if not (math.isfinite(kval) and kval > 0):
            raise ValidationError("k: must be a positive finite number")
    if not isinstance(vectorized, bool):
        raise ValidationError("vectorized: must be True or False")
    fn = _Model(f, vectorized)
    y0 = fn(xv.copy())
    g = _sensitivities(fn, xv, uv)
    contrib = np.abs(g) * uv
    diags: list[Diagnostic] = []
    if corr is not None and method == "linear":
        diags.append(Diagnostic("info", "UNC_CORRELATED",
                                "inputs are correlated: contributions do not add in quadrature"))
    if method == "linear":
        u = math.sqrt(max(float(g @ cov @ g), 0.0))
        kf = float(k) if k is not None else float(ndtri((1 + cover) / 2))
        diags += _curvature_check(fn, xv, uv, g, y0)
        return UncertaintyResult(y0, u, kf * u, (y0 - kf * u, y0 + kf * u), cover, g, contrib,
                                 "linear", k=kf, diagnostics=tuple(diags))
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or not (
            MIN_SAMPLES <= n <= MAX_SAMPLES):
        raise ValidationError(f"n: must be an integer in {MIN_SAMPLES}..{MAX_SAMPLES}")
    n = int(n)
    if n * xv.size > MAX_CELLS:
        raise ValidationError(f"n * number of inputs must not exceed {MAX_CELLS}")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, (int, np.integer))
                             or seed < 0):
        raise ValidationError("seed: must be a non-negative integer or None")
    if seed is None:
        diags.append(Diagnostic("info", "UNC_UNSEEDED", "Monte Carlo ran without a seed; the "
                                "result is not reproducible"))
    if n < FEW_SAMPLES:
        diags.append(Diagnostic("warning", "UNC_FEW_SAMPLES",
                                f"only {n} samples; use at least {FEW_SAMPLES} for a coverage "
                                "interval"))
    rng = np.random.default_rng(seed)
    w, vecs = np.linalg.eigh(cov)
    chol = vecs * np.sqrt(np.clip(w, 0.0, None))
    samples = xv + rng.standard_normal((n, xv.size)) @ chol.T
    ys = fn.batch(samples)
    lo, hi = np.quantile(ys, [(1 - cover) / 2, (1 + cover) / 2])
    return UncertaintyResult(
        y0, float(np.std(ys, ddof=1)), float((hi - lo) / 2), (float(lo), float(hi)), cover, g,
        contrib, "montecarlo", n_samples=n, diagnostics=tuple(diags))
