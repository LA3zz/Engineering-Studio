"""Descriptive statistics, correlation, confidence intervals and t-tests (E8).

All functions take 1-D real data (scalars, rows and columns are flattened; NaN/Inf rejected).
Differences from NumPy/MATLAB, deliberately:
- ``var``/``std``/``cov``/``zscore`` use ``ddof=1`` (sample, as MATLAB) and *raise* when
  ``n - ddof <= 0`` instead of returning 0 or NaN.
- ``skewness``/``kurtosis`` are the biased (population-moment) estimators, kurtosis not
  excess (normal = 3), as MATLAB's default; both raise for zero variance.
- ``quantile`` supports ``method="linear"`` (NumPy / R-7) and ``method="matlab"`` (points at
  (i - 0.5)/n, flat beyond the first/last point).
- t-tests compute the statistic, degrees of freedom and p-value directly (Welch's
  unequal-variance test is the default for two samples). ``alternative`` is ``"two-sided"``,
  ``"greater"`` or ``"less"``. Normality of the data is assumed, not tested.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats as _st

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ValidationError
from engstudio.engine.validation import as_vector

__all__ = [
    "CorrResult", "Summary", "TestResult", "confidence_interval_mean", "cov", "histogram", "iqr",
    "kurtosis", "mean", "median", "pearsonr", "quantile", "rms", "sem", "skewness", "std",
    "summary", "t_quantile", "ttest_1samp", "ttest_ind", "ttest_paired", "var",
    "zscore",
]

_ALTERNATIVES = ("two-sided", "greater", "less")


@dataclass(frozen=True, eq=False)
class TestResult:
    __test__ = False  # not a pytest class

    statistic: float
    p_value: float
    dof: float
    diagnostics: tuple[Diagnostic, ...] = ()
    method: str = ""


@dataclass(frozen=True, eq=False)
class CorrResult:
    r: float
    p_value: float
    n: int


@dataclass(frozen=True, eq=False)
class Summary:
    n: int
    mean: float
    std: float
    sem: float
    min: float
    q1: float
    median: float
    q3: float
    max: float


# -- helpers -------------------------------------------------------------------------
def _vec(x: ArrayLike, name: str = "x") -> NDArray:
    return as_vector(x, name, allow_complex=False)


def _ddof(ddof: int, n: int, what: str) -> int:
    if isinstance(ddof, bool) or ddof not in (0, 1):
        raise ValidationError("ddof must be 0 or 1")
    if n - ddof <= 0:
        raise ValidationError(f"{what}: needs at least {ddof + 1} value(s) for ddof={ddof}, "
                              f"got {n}")
    return int(ddof)


def _level(level: float) -> float:
    lv = np.asarray(level)
    if lv.size != 1 or lv.dtype.kind not in "biuf" or not 0.0 < float(lv) < 1.0:
        raise ValidationError("level must be a number in (0, 1)")
    return float(lv)


def _p_value(t: float, dof: float, alternative: str) -> float:
    if alternative not in _ALTERNATIVES:
        raise ValidationError(f"alternative must be one of {_ALTERNATIVES}")
    if alternative == "two-sided":
        return float(2.0 * _st.t.sf(abs(t), dof))
    return float(_st.t.sf(t, dof) if alternative == "greater" else _st.t.cdf(t, dof))


def _central(x: NDArray, order: int) -> float:
    return float(np.mean((x - x.mean()) ** order))


# -- descriptive ---------------------------------------------------------------------
def mean(x: ArrayLike) -> float:
    return float(np.mean(_vec(x)))


def median(x: ArrayLike) -> float:
    return float(np.median(_vec(x)))


def var(x: ArrayLike, ddof: int = 1) -> float:
    v = _vec(x)
    return float(np.var(v, ddof=_ddof(ddof, v.size, "var")))


def std(x: ArrayLike, ddof: int = 1) -> float:
    v = _vec(x)
    return float(np.std(v, ddof=_ddof(ddof, v.size, "std")))


def sem(x: ArrayLike) -> float:
    """Standard error of the mean, ``s / sqrt(n)`` with the sample standard deviation."""
    v = _vec(x)
    return float(np.std(v, ddof=_ddof(1, v.size, "sem")) / math.sqrt(v.size))


def rms(x: ArrayLike) -> float:
    return float(np.sqrt(np.mean(_vec(x) ** 2)))


def skewness(x: ArrayLike) -> float:
    v = _vec(x)
    m2 = _central(v, 2)
    if m2 == 0.0:
        raise ValidationError("skewness: undefined for zero variance")
    return _central(v, 3) / m2**1.5


def kurtosis(x: ArrayLike) -> float:
    """Biased, non-excess kurtosis (a normal distribution has 3)."""
    v = _vec(x)
    m2 = _central(v, 2)
    if m2 == 0.0:
        raise ValidationError("kurtosis: undefined for zero variance")
    return _central(v, 4) / m2**2


def quantile(x: ArrayLike, q: ArrayLike, *, method: str = "linear") -> float | NDArray:
    """Quantile(s) ``q`` in [0, 1]; scalar ``q`` returns a float."""
    if method not in ("linear", "matlab"):
        raise ValidationError("method must be 'linear' or 'matlab'")
    v = np.sort(_vec(x))
    qs = as_vector(np.asarray(q).reshape(-1), "q", allow_complex=False)
    if np.any(qs < 0) or np.any(qs > 1):
        raise ValidationError("q: values must lie in [0, 1]")
    if method == "linear":
        out = np.quantile(v, qs)
    else:
        pts = (np.arange(1, v.size + 1) - 0.5) / v.size
        out = np.interp(qs, pts, v)
    return float(out[0]) if np.ndim(q) == 0 else out


def iqr(x: ArrayLike, *, method: str = "linear") -> float:
    q = quantile(x, [0.25, 0.75], method=method)
    return float(q[1] - q[0])


def zscore(x: ArrayLike, ddof: int = 1) -> NDArray:
    v = _vec(x)
    s = std(v, ddof)
    if s == 0.0:
        raise ValidationError("zscore: undefined for zero variance")
    return (v - v.mean()) / s


def summary(x: ArrayLike) -> Summary:
    v = _vec(x)
    q1, q2, q3 = (float(t) for t in np.quantile(v, [0.25, 0.5, 0.75]))
    return Summary(v.size, float(v.mean()), std(v), sem(v), float(v.min()), q1, q2, q3,
                   float(v.max()))


def histogram(
    x: ArrayLike, bins: int | ArrayLike = 10, *, range_: tuple[float, float] | None = None
) -> tuple[NDArray, NDArray]:
    """Counts and bin edges; the last bin includes its right edge. ``bins``: count or edges."""
    v = _vec(x)
    if np.ndim(bins) == 0:
        if isinstance(bins, bool) or not isinstance(bins, (int, np.integer)) or bins < 1:
            raise ValidationError("bins: expected a positive integer or a vector of edges")
        edges: int | NDArray = int(bins)
    else:
        edges = as_vector(bins, "bins", allow_complex=False)
        if edges.size < 2 or not np.all(np.diff(edges) > 0):
            raise ValidationError("bins: edges must be strictly increasing (at least 2)")
    counts, e = np.histogram(v, bins=edges, range=range_)
    return counts, e


# -- two variables -------------------------------------------------------------------
def _pair(x: ArrayLike, y: ArrayLike) -> tuple[NDArray, NDArray]:
    xv = _vec(x, "x")
    return xv, as_vector(y, "y", allow_complex=False, length=xv.size)


def cov(x: ArrayLike, y: ArrayLike, ddof: int = 1) -> float:
    xv, yv = _pair(x, y)
    d = _ddof(ddof, xv.size, "cov")
    return float(np.sum((xv - xv.mean()) * (yv - yv.mean())) / (xv.size - d))


def pearsonr(x: ArrayLike, y: ArrayLike) -> CorrResult:
    """Pearson correlation coefficient with a two-sided p-value (H0: rho = 0, n >= 3)."""
    xv, yv = _pair(x, y)
    n = xv.size
    if n < 3:
        raise ValidationError("pearsonr: needs at least 3 pairs")
    dx, dy = xv - xv.mean(), yv - yv.mean()
    denom = math.sqrt(float(np.sum(dx**2) * np.sum(dy**2)))
    if denom == 0.0:
        raise ValidationError("pearsonr: undefined when x or y is constant")
    r = float(np.clip(np.sum(dx * dy) / denom, -1.0, 1.0))
    if abs(r) == 1.0:
        return CorrResult(r, 0.0, n)
    t = r * math.sqrt((n - 2) / (1.0 - r * r))
    return CorrResult(r, _p_value(t, n - 2, "two-sided"), n)


# -- inference ---------------------------------------------------------------------------
def confidence_interval_mean(x: ArrayLike, level: float = 0.95) -> tuple[float, float, float]:
    """``(mean, lower, upper)``: Student-t interval for the population mean."""
    lv = _level(level)
    v = _vec(x)
    s = sem(v)
    half = float(_st.t.ppf(0.5 + lv / 2.0, v.size - 1)) * s
    m = float(v.mean())
    return m, m - half, m + half


def ttest_1samp(
    x: ArrayLike, popmean: float = 0.0, *, alternative: str = "two-sided"
) -> TestResult:
    """One-sample t-test of ``mean(x) == popmean``."""
    v = _vec(x)
    mu = as_vector(popmean, "popmean", allow_complex=False, length=1)[0]
    s = sem(v)
    if s == 0.0:
        raise ValidationError("ttest_1samp: undefined for zero variance")
    t = (float(v.mean()) - float(mu)) / s
    dof = v.size - 1
    return TestResult(t, _p_value(t, dof, alternative), float(dof), (), "one-sample t")


def ttest_paired(
    x: ArrayLike, y: ArrayLike, *, alternative: str = "two-sided"
) -> TestResult:
    """Paired t-test on the differences ``x - y``."""
    xv, yv = _pair(x, y)
    res = ttest_1samp(xv - yv, 0.0, alternative=alternative)
    return TestResult(res.statistic, res.p_value, res.dof, (), "paired t")


def ttest_ind(
    x: ArrayLike, y: ArrayLike, *, equal_var: bool = False, alternative: str = "two-sided"
) -> TestResult:
    """Two-sample t-test (Welch by default; pooled variance if ``equal_var=True``)."""
    xv, yv = _vec(x, "x"), _vec(y, "y")
    n1, n2 = xv.size, yv.size
    v1 = var(xv)
    v2 = var(yv)
    diff = float(xv.mean() - yv.mean())
    if equal_var:
        dof = float(n1 + n2 - 2)
        pooled = ((n1 - 1) * v1 + (n2 - 1) * v2) / dof
        se = math.sqrt(pooled * (1.0 / n1 + 1.0 / n2))
        method = "two-sample t (pooled variance)"
    else:
        a, b = v1 / n1, v2 / n2
        se = math.sqrt(a + b)
        dof = (a + b) ** 2 / (a**2 / (n1 - 1) + b**2 / (n2 - 1)) if se > 0 else 0.0
        method = "Welch t"
    if se == 0.0:
        raise ValidationError("ttest_ind: undefined when both samples have zero variance")
    t = diff / se
    return TestResult(t, _p_value(t, dof, alternative), dof, (), method)


def t_quantile(p: float, dof: float) -> float:
    """Student-t quantile (inverse CDF) for probability ``p`` in (0, 1) and ``dof`` > 0."""
    pv = np.asarray(p)
    dv = np.asarray(dof)
    if pv.size != 1 or pv.dtype.kind not in "biuf" or not 0.0 < float(pv) < 1.0:
        raise ValidationError("p must be a number in (0, 1)")
    if dv.size != 1 or dv.dtype.kind not in "biuf" or not float(dv) > 0.0:
        raise ValidationError("dof must be a positive number")
    return float(_st.t.ppf(float(pv), float(dv)))
