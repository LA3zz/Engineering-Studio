"""Root finding and equation solving (E4).

Scalar methods: ``bisect`` (robust, linear), ``brentq`` (bracketing, SciPy), ``newton``
(optional analytic derivative, else central difference) and ``secant``. ``polyroots`` uses the
companion-matrix eigenvalues (NumPy), highest power first as in MATLAB. ``fsolve`` solves square
nonlinear systems by damped Newton with a finite-difference (or user) Jacobian.

Conventions: convergence of scalar iterations means ``|dx| <= atol + rtol * |x|``. Failure to
converge raises ``ConvergenceError``; a bracket without sign change raises ``ValidationError``.
Functions must return real finite scalars (systems: real finite vectors). The residual is always
re-evaluated at the returned root. Multiple roots converge slowly (Newton: linearly) and are
inherently ill-conditioned: ``polyroots`` of ``(x-1)^n`` is accurate only to ~eps**(1/n).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import optimize

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine import calculus, linalg
from engstudio.engine.validation import as_vector

__all__ = ["RootResult", "bisect", "brentq", "fsolve", "newton", "polyroots", "secant"]

EPS = float(np.finfo(float).eps)


@dataclass(frozen=True, eq=False)
class RootResult:
    """``root`` is a float (scalar methods), a vector (``fsolve``) or complex roots (poly)."""

    root: float | NDArray
    converged: bool
    iterations: int
    residual: float
    diagnostics: tuple[Diagnostic, ...] = ()
    method: str = ""
    nfev: int = 0


# -- helpers -------------------------------------------------------------------------
def _real(x: object, name: str) -> float:
    arr = np.asarray(x)
    if arr.size != 1 or arr.dtype.kind not in "biuf":
        raise ValidationError(f"{name}: expected a real scalar")
    v = float(arr.reshape(-1)[0])
    if not np.isfinite(v):
        raise ValidationError(f"{name}: must be finite (got {v})")
    return v


class _Fn:
    """Checks that the user function returns a real finite scalar; counts calls."""

    def __init__(self, f: object, name: str = "f") -> None:
        if not callable(f):
            raise ValidationError(f"{name}: expected a callable")
        self._f, self._name, self.calls = f, name, 0

    def __call__(self, x: float) -> float:
        self.calls += 1
        arr = np.asarray(self._f(float(x)))  # type: ignore[operator]
        if arr.size != 1 or arr.dtype.kind not in "biuf":
            raise ValidationError(f"{self._name}({x:g}): must return a real scalar")
        v = float(arr.reshape(-1)[0])
        if not np.isfinite(v):
            raise ValidationError(f"{self._name}({x:g}): returned non-finite value {v}")
        return v


def _tols(rtol: float, atol: float, maxiter: int) -> tuple[float, float, int]:
    rt, at = _real(rtol, "rtol"), _real(atol, "atol")
    if rt < 4 * EPS:
        raise ValidationError(f"rtol: must be >= 4*eps ({4 * EPS:.3g})")
    if at <= 0:
        raise ValidationError("atol: must be > 0")
    if isinstance(maxiter, bool) or not isinstance(maxiter, int) or maxiter < 1:
        raise ValidationError("maxiter must be a positive integer")
    return rt, at, maxiter


def _bracket(fn: _Fn, a: float, b: float) -> tuple[float, float, float, float]:
    lo, hi = _real(a, "a"), _real(b, "b")
    if lo == hi:
        raise ValidationError("a and b must differ")
    if lo > hi:
        lo, hi = hi, lo
    flo, fhi = fn(lo), fn(hi)
    if flo != 0.0 and fhi != 0.0 and (flo > 0) == (fhi > 0):
        raise ValidationError(
            f"no sign change on [{lo:g}, {hi:g}]: f(a)={flo:.6g}, f(b)={fhi:.6g}")
    return lo, hi, flo, fhi


# -- scalar methods ------------------------------------------------------------------
def bisect(
    f: Callable[[float], float], a: float, b: float, *, rtol: float = 1e-12,
    atol: float = 1e-14, maxiter: int = 200,
) -> RootResult:
    """Bisection on [a, b]; requires f(a) and f(b) of opposite sign (or an exact zero)."""
    rt, at, mi = _tols(rtol, atol, maxiter)
    fn = _Fn(f)
    lo, hi, flo, fhi = _bracket(fn, a, b)
    if flo == 0.0:
        return RootResult(lo, True, 0, 0.0, (), "bisect", fn.calls)
    if fhi == 0.0:
        return RootResult(hi, True, 0, 0.0, (), "bisect", fn.calls)
    for it in range(1, mi + 1):
        mid = 0.5 * (lo + hi)
        fm = fn(mid)
        if fm == 0.0 or 0.5 * (hi - lo) <= at + rt * abs(mid):
            return RootResult(mid, True, it, abs(fm), (), "bisect", fn.calls)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    raise ConvergenceError(f"bisect: no convergence in {mi} iterations", mi, 0.5 * (lo + hi))


def brentq(
    f: Callable[[float], float], a: float, b: float, *, rtol: float = 1e-12,
    atol: float = 1e-14, maxiter: int = 100,
) -> RootResult:
    """Brent's method (SciPy ``brentq``) on a sign-changing bracket [a, b]."""
    rt, at, mi = _tols(rtol, atol, maxiter)
    fn = _Fn(f)
    lo, hi, flo, fhi = _bracket(fn, a, b)
    if flo == 0.0 or fhi == 0.0:
        r = lo if flo == 0.0 else hi
        return RootResult(r, True, 0, 0.0, (), "brentq", fn.calls)
    x, info = optimize.brentq(fn, lo, hi, xtol=at, rtol=rt, maxiter=mi, full_output=True,
                              disp=False)
    if not info.converged:
        raise ConvergenceError(f"brentq: no convergence in {mi} iterations", info.iterations, x)
    return RootResult(float(x), True, int(info.iterations), abs(fn(x)), (), "brentq", fn.calls)


def newton(
    f: Callable[[float], float], x0: float, *, fprime: Callable[[float], float] | None = None,
    rtol: float = 1e-12, atol: float = 1e-14, maxiter: int = 100,
) -> RootResult:
    """Newton's method. Without ``fprime`` a central-difference derivative is used."""
    rt, at, mi = _tols(rtol, atol, maxiter)
    fn = _Fn(f)
    dfn = _Fn(fprime, "fprime") if fprime is not None else None
    x = _real(x0, "x0")
    for it in range(1, mi + 1):
        fx = fn(x)
        if fx == 0.0:
            return RootResult(x, True, it - 1, 0.0, (), "newton", fn.calls + _calls(dfn))
        d = dfn(x) if dfn is not None else calculus.derivative(fn, x)
        if d == 0.0:
            raise ConvergenceError(f"newton: zero derivative at x={x:.6g}", it, x)
        dx = fx / d
        x_new = x - dx
        if not np.isfinite(x_new):
            raise ConvergenceError("newton: iterate diverged", it, x)
        x = x_new
        if abs(dx) <= at + rt * abs(x):
            return RootResult(x, True, it, abs(fn(x)), (), "newton", fn.calls + _calls(dfn))
    raise ConvergenceError(f"newton: no convergence in {mi} iterations", mi, x)


def _calls(d: _Fn | None) -> int:
    return d.calls if d is not None else 0


def secant(
    f: Callable[[float], float], x0: float, x1: float, *, rtol: float = 1e-12,
    atol: float = 1e-14, maxiter: int = 100,
) -> RootResult:
    """Secant method from two distinct starting points."""
    rt, at, mi = _tols(rtol, atol, maxiter)
    fn = _Fn(f)
    xa, xb = _real(x0, "x0"), _real(x1, "x1")
    if xa == xb:
        raise ValidationError("x0 and x1 must differ")
    fa, fb = fn(xa), fn(xb)
    for it in range(1, mi + 1):
        if fb == 0.0:
            return RootResult(xb, True, it - 1, 0.0, (), "secant", fn.calls)
        if fb == fa:
            raise ConvergenceError(f"secant: flat step (f equal at both points) near x={xb:.6g}",
                                   it, xb)
        xc = xb - fb * (xb - xa) / (fb - fa)
        if not np.isfinite(xc):
            raise ConvergenceError("secant: iterate diverged", it, xb)
        xa, fa, xb = xb, fb, xc
        fb = fn(xb)
        if abs(xb - xa) <= at + rt * abs(xb):
            return RootResult(xb, True, it, abs(fb), (), "secant", fn.calls)
    raise ConvergenceError(f"secant: no convergence in {mi} iterations", mi, xb)


# -- polynomials ---------------------------------------------------------------------
def polyroots(coeffs: ArrayLike) -> RootResult:
    """All roots of ``c[0]*x^n + ... + c[n]`` (highest power first, real or complex coeffs).

    Leading zeros are dropped. A nonzero constant has no roots (empty array); all-zero
    coefficients are rejected. Roots are sorted by real then imaginary part; ``residual`` is
    the largest ``|p(r)|``. Real-coefficient input gives conjugate pairs; roots whose imaginary
    part is exactly zero are returned as real.
    """
    c = as_vector(coeffs, "coeffs")
    nz = np.flatnonzero(c)
    if nz.size == 0:
        raise ValidationError("coeffs: all coefficients are zero (every x is a root)")
    c = c[nz[0]:]
    if c.size == 1:
        return RootResult(np.empty(0), True, 0, 0.0, (), "polyroots")
    r = np.roots(c)
    if not np.iscomplexobj(c) and np.all(r.imag == 0):
        r = r.real
    order = np.lexsort((r.imag, r.real)) if np.iscomplexobj(r) else np.argsort(r)
    r = r[order]
    res = float(np.max(np.abs(np.polyval(c, r))))
    return RootResult(r, True, 0, res, (), "polyroots (companion eigenvalues)")


# -- systems -------------------------------------------------------------------------
def fsolve(
    f: Callable[[NDArray], ArrayLike], x0: ArrayLike, *,
    jac: Callable[[NDArray], ArrayLike] | None = None, rtol: float = 1e-10, atol: float = 1e-12,
    maxiter: int = 100,
) -> RootResult:
    """Solve ``f(x) = 0`` for ``f: R^n -> R^n`` by damped Newton (backtracking on ||f||).

    Converges when the full step satisfies ``||dx|| <= atol + rtol * ||x||``. A singular
    Jacobian raises ``SingularMatrixError``; a stalled line search raises ``ConvergenceError``.
    """
    rt, at, mi = _tols(rtol, atol, maxiter)
    if not callable(f):
        raise ValidationError("f: expected a callable")
    if jac is not None and not callable(jac):
        raise ValidationError("jac: expected a callable")
    x = as_vector(x0, "x0", allow_complex=False)
    n = x.size
    nfev = 0

    def F(v: NDArray) -> NDArray:
        nonlocal nfev
        nfev += 1
        return as_vector(f(v.copy()), "f(x)", allow_complex=False, length=n)

    diags: list[Diagnostic] = []
    fx = F(x)
    for it in range(1, mi + 1):
        if jac is not None:
            jm = np.asarray(jac(x.copy()), dtype=float)
            if jm.shape != (n, n):
                raise DimensionError(f"jac must return {n}x{n}, got {jm.shape}")
        else:
            jm = calculus.jacobian(F, x)
        sol = linalg.solve(jm, -fx)
        diags.extend(d for d in sol.diagnostics if d not in diags)
        dx = sol.x
        f0 = float(np.linalg.norm(fx))
        lam = 1.0
        tiny = float(np.linalg.norm(dx)) <= at + rt * float(np.linalg.norm(x))
        while True:
            xn = x + lam * dx
            try:
                fn_ = F(xn)
                # near the root ||f|| sits at round-off level, so a tiny full step is accepted
                if float(np.linalg.norm(fn_)) < f0 or f0 == 0.0 or (tiny and lam == 1.0):
                    break
            except ValidationError:
                pass  # trial point outside the domain: shrink the step
            lam *= 0.5
            if lam < 1e-10:
                raise ConvergenceError("fsolve: line search stalled (local minimum of ||f||?)",
                                       it, x)
        step = float(np.linalg.norm(lam * dx))
        x, fx = xn, fn_
        if lam == 1.0 and step <= at + rt * float(np.linalg.norm(x)):
            return RootResult(x, True, it, float(np.linalg.norm(fx)), tuple(diags),
                              "damped Newton", nfev)
    raise ConvergenceError(f"fsolve: no convergence in {mi} iterations", mi, x)
