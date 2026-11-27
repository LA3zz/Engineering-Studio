"""Numerical optimization (E7).

``minimize_scalar`` (bounded Brent), ``minimize`` (BFGS, Nelder-Mead, L-BFGS-B, SLSQP) and
``linprog`` (HiGHS). All return a ``MinimizeResult``.

Method choice: ``method=None`` picks SLSQP with constraints, L-BFGS-B with bounds, else BFGS.
BFGS needs a smooth objective; Nelder-Mead is derivative free but slow and only locally
convergent. All methods find a *local* minimum; a result is never guaranteed global.
Without ``jac`` gradients are finite differences, which limits the reachable accuracy to about
1e-7 in ``x`` for smooth problems; supply ``jac`` for tight tolerances.

Constraints follow SciPy: ``{"type": "eq", "fun": g}`` means ``g(x) == 0`` and
``{"type": "ineq", "fun": g}`` means ``g(x) >= 0`` (``g`` returns a scalar or a vector).
Bounds are one ``(lower, upper)`` pair per variable, ``None`` for no limit. The initial point
must lie within the bounds.

Failures: iteration or evaluation limit, an infeasible or unbounded problem, or a constraint
violated at the returned point raise ``ConvergenceError``. When a gradient method only stops
because of round-off ("precision loss") the result is returned with ``converged=False`` and a
warning diagnostic. ``linprog`` variables are free by default (as in MATLAB), unlike SciPy.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import optimize

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector

__all__ = ["MinimizeResult", "linprog", "minimize", "minimize_scalar"]

_METHODS = ("BFGS", "Nelder-Mead", "L-BFGS-B", "SLSQP")
_BOUND_TOL = 1e-8
_CONSTRAINT_TOL = 1e-6


@dataclass(frozen=True, eq=False)
class MinimizeResult:
    x: float | NDArray
    fun: float
    converged: bool
    iterations: int
    nfev: int
    diagnostics: tuple[Diagnostic, ...] = ()
    method: str = ""


# -- helpers -------------------------------------------------------------------------
def _real(v: object, name: str) -> float:
    arr = np.asarray(v)
    if arr.size != 1 or arr.dtype.kind not in "biuf":
        raise ValidationError(f"{name}: expected a real scalar")
    out = float(arr.reshape(-1)[0])
    if not np.isfinite(out):
        raise ValidationError(f"{name}: must be finite (got {out})")
    return out


def _check_limits(tol: float, maxiter: int) -> None:
    if _real(tol, "tol") <= 0:
        raise ValidationError("tol: must be > 0")
    if isinstance(maxiter, bool) or not isinstance(maxiter, int) or maxiter < 1:
        raise ValidationError("maxiter must be a positive integer")


def _scalar_fn(f: object, name: str, vector: bool) -> Callable[..., float]:
    if not callable(f):
        raise ValidationError(f"{name}: expected a callable")

    def wrapped(x: object) -> float:
        arg = np.array(x, dtype=float) if vector else float(x)  # type: ignore[arg-type]
        arr = np.asarray(f(arg))
        if arr.size != 1 or arr.dtype.kind not in "biuf":
            raise ValidationError(f"{name}: must return a real scalar")
        v = float(arr.reshape(-1)[0])
        if not np.isfinite(v):
            raise ValidationError(f"{name}: returned non-finite value {v}")
        return v

    return wrapped


def _bounds(bounds: Sequence[tuple[float | None, float | None]] | None, n: int
            ) -> tuple[list[tuple[float | None, float | None]] | None, NDArray, NDArray]:
    if bounds is None:
        return None, np.full(n, -np.inf), np.full(n, np.inf)
    if len(bounds) != n:
        raise DimensionError(f"bounds: expected {n} (lower, upper) pairs, got {len(bounds)}")
    lo, hi = np.full(n, -np.inf), np.full(n, np.inf)
    for i, pair in enumerate(bounds):
        try:
            a, b = pair
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"bounds[{i}]: expected (lower, upper)") from exc
        if a is not None:
            lo[i] = _real(a, f"bounds[{i}] lower")
        if b is not None:
            hi[i] = _real(b, f"bounds[{i}] upper")
    if np.any(lo > hi):
        raise ValidationError("bounds: lower must be <= upper")
    pairs = [(None if np.isinf(a) else float(a), None if np.isinf(b) else float(b))
             for a, b in zip(lo, hi, strict=True)]
    return pairs, lo, hi


def _constraints(constraints: Sequence[dict] | None, n: int) -> list[dict]:
    out: list[dict] = []
    for i, c in enumerate(constraints or ()):
        if not isinstance(c, dict) or c.get("type") not in ("eq", "ineq") \
                or not callable(c.get("fun")):
            raise ValidationError(
                f"constraints[{i}]: expected {{'type': 'eq'|'ineq', 'fun': callable}}")
        out.append({"type": c["type"], "fun": _vector_fn(c["fun"], f"constraints[{i}]")})
    return out


def _vector_fn(
    g: Callable[..., ArrayLike], name: str, length: int | None = None
) -> Callable[[NDArray], NDArray]:
    def wrapped(x: NDArray) -> NDArray:
        return as_vector(g(np.array(x, dtype=float)), name, allow_complex=False, length=length)

    return wrapped


# -- scalar --------------------------------------------------------------------------
def minimize_scalar(
    f: Callable[[float], float], a: float, b: float, *, xtol: float = 1e-10, maxiter: int = 500,
) -> MinimizeResult:
    """Local minimum of scalar ``f`` on [a, b] (bounded Brent: golden section + parabolas)."""
    _check_limits(xtol, maxiter)
    lo, hi = _real(a, "a"), _real(b, "b")
    if lo >= hi:
        raise ValidationError("a must be < b")
    fn = _scalar_fn(f, "f", vector=False)
    res = optimize.minimize_scalar(fn, bounds=(lo, hi), method="bounded",
                                   options={"xatol": xtol, "maxiter": maxiter})
    if not res.success:
        raise ConvergenceError(f"minimize_scalar: {res.message}", int(res.nit), float(res.x))
    return MinimizeResult(float(res.x), float(res.fun), True, int(res.nit), int(res.nfev), (),
                          "bounded Brent")


# -- multivariate --------------------------------------------------------------------
def minimize(
    f: Callable[[NDArray], float], x0: ArrayLike, *,
    jac: Callable[[NDArray], ArrayLike] | None = None,
    bounds: Sequence[tuple[float | None, float | None]] | None = None,
    constraints: Sequence[dict] | None = None, method: str | None = None,
    tol: float = 1e-8, maxiter: int = 1000,
) -> MinimizeResult:
    """Minimize ``f(x)`` (x a 1-D array) starting at ``x0``."""
    _check_limits(tol, maxiter)
    start = as_vector(x0, "x0", allow_complex=False)
    n = start.size
    fn = _scalar_fn(f, "f", vector=True)
    pairs, lo, hi = _bounds(bounds, n)
    if np.any(start < lo) or np.any(start > hi):
        raise ValidationError("x0: initial point must lie within bounds")
    cons = _constraints(constraints, n)
    if method is None:
        method = "SLSQP" if cons else ("L-BFGS-B" if pairs else "BFGS")
    if method not in _METHODS:
        raise ValidationError(f"method {method!r} is not supported; use one of {_METHODS}")
    if cons and method != "SLSQP":
        raise ValidationError(f"constraints require method 'SLSQP', not {method!r}")
    if pairs and method == "BFGS":
        raise ValidationError("bounds require method 'L-BFGS-B' or 'SLSQP' (or 'Nelder-Mead')")
    if jac is not None:
        if method == "Nelder-Mead":
            raise ValidationError("jac is not used by 'Nelder-Mead'")
        if not callable(jac):
            raise ValidationError("jac: expected a callable")
        jac_fn: Callable[[NDArray], NDArray] | None = _vector_fn(jac, "jac", n)
    else:
        jac_fn = None
    options: dict[str, object] = {"maxiter": maxiter}
    if method == "Nelder-Mead":
        options.update(xatol=tol, fatol=tol, maxfev=maxiter * n * 2)
    kwargs: dict[str, object] = {"method": method, "options": options}
    if method != "Nelder-Mead":
        kwargs["tol"] = tol
        kwargs["jac"] = jac_fn
    if pairs:
        kwargs["bounds"] = pairs
    if cons:
        kwargs["constraints"] = cons
    res = optimize.minimize(fn, start, **kwargs)
    x = np.asarray(res.x, dtype=float)
    diags: list[Diagnostic] = []
    converged = bool(res.success)
    if not converged:
        if "precision loss" in str(res.message).lower():
            diags.append(Diagnostic(
                "warning", "PRECISION_LOSS",
                f"minimize: stopped because of round-off before reaching tol={tol:g}; "
                "supply jac or loosen tol"))
        else:
            raise ConvergenceError(f"minimize ({method}): {res.message}",
                                   int(getattr(res, "nit", 0)), x)
    _check_feasible(x, lo, hi, cons)
    return MinimizeResult(x, float(res.fun), converged, int(getattr(res, "nit", 0)),
                          int(res.nfev), tuple(diags), method)


def _check_feasible(x: NDArray, lo: NDArray, hi: NDArray, cons: list[dict]) -> None:
    scale = 1.0 + np.abs(x)
    if np.any(x < lo - _BOUND_TOL * scale) or np.any(x > hi + _BOUND_TOL * scale):
        raise ConvergenceError("minimize: result violates the bounds", None, x)
    for i, c in enumerate(cons):
        g = c["fun"](x)
        bad = np.any(np.abs(g) > _CONSTRAINT_TOL) if c["type"] == "eq" \
            else np.any(g < -_CONSTRAINT_TOL)
        if bad:
            raise ConvergenceError(f"minimize: constraint {i} is violated at the result "
                                   "(problem may be infeasible)", None, x)


# -- linear programming ----------------------------------------------------------------
def linprog(
    c: ArrayLike, A_ub: ArrayLike | None = None, b_ub: ArrayLike | None = None,
    A_eq: ArrayLike | None = None, b_eq: ArrayLike | None = None,
    bounds: Sequence[tuple[float | None, float | None]] | None = None,
) -> MinimizeResult:
    """Minimize ``c @ x`` s.t. ``A_ub @ x <= b_ub``, ``A_eq @ x == b_eq``, bounds (HiGHS).

    ``bounds`` is one (lower, upper) pair per variable; the default is free variables.
    """
    cv = as_vector(c, "c", allow_complex=False)
    n = cv.size
    if (A_ub is None) != (b_ub is None):
        raise ValidationError("A_ub and b_ub must be given together")
    if (A_eq is None) != (b_eq is None):
        raise ValidationError("A_eq and b_eq must be given together")

    def block(a: ArrayLike | None, b: ArrayLike | None, na: str, nb: str
              ) -> tuple[NDArray | None, NDArray | None]:
        if a is None:
            return None, None
        am = as_matrix(a, na, allow_complex=False)
        if am.shape[1] != n:
            raise DimensionError(f"{na} must have {n} columns, got {am.shape[1]}")
        return am, as_vector(b, nb, allow_complex=False, length=am.shape[0])

    aub, bub = block(A_ub, b_ub, "A_ub", "b_ub")
    aeq, beq = block(A_eq, b_eq, "A_eq", "b_eq")
    if bounds is None:
        pairs = [(None, None)] * n
    else:
        pairs, _, _ = _bounds(bounds, n)
    res = optimize.linprog(cv, A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=beq, bounds=pairs,
                           method="highs")
    if res.status == 2:
        raise ConvergenceError("linprog: problem is infeasible", int(res.nit), None)
    if res.status == 3:
        raise ConvergenceError("linprog: problem is unbounded", int(res.nit), None)
    if not res.success:
        raise ConvergenceError(f"linprog: {res.message}", int(res.nit), None)
    return MinimizeResult(np.asarray(res.x, dtype=float), float(res.fun), True, int(res.nit), 0,
                          (), "HiGHS")
