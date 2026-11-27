"""Ordinary differential equations: initial value problems (E9).

``solve_ode`` wraps SciPy ``solve_ivp`` (RK45, RK23, DOP853, Radau, BDF, LSODA) with validated
inputs, explicit tolerances and typed errors.

Conventions:
- ``f(t, y)`` returns dy/dt as a real vector of the same length as ``y`` (a scalar is allowed
  for a 1-state problem). ``y0`` and all states are real.
- Result ``y`` has shape ``(len(t), n_states)``: one row per time point (differs from SciPy,
  whose ``y`` is ``(n_states, len(t))``).
- ``rtol`` must be at least ``100 * eps``; ``atol`` is a scalar or a vector of length n_states.
- ``t_span`` may run backwards (``t1 < t0``). ``t_eval``, if given, must lie inside the span and
  be strictly monotonic in the direction of integration.
- Events follow the SciPy convention: ``event(t, y) -> float`` with optional attributes
  ``terminal`` and ``direction``. ``status`` is 0 (reached ``t1``) or 1 (stopped by a terminal
  event); failures raise ``ConvergenceError``.
- A right-hand side that returns NaN/Inf after the first call (typical for finite-time
  blow-up), or more than ``max_nfev`` evaluations, raises ``ConvergenceError``. Exceptions
  raised by ``f`` itself propagate unchanged.
- ``max_nfev`` counts every call of ``f`` including finite-difference Jacobian evaluations, so
  it can exceed the ``nfev`` reported by SciPy for implicit methods.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import solve_ivp

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ConvergenceError, DimensionError, ValidationError
from engstudio.engine.validation import as_vector

__all__ = ["METHODS", "OdeResult", "solve_ode"]

METHODS = ("RK45", "RK23", "DOP853", "Radau", "BDF", "LSODA")
_IMPLICIT = ("Radau", "BDF", "LSODA")
EPS = float(np.finfo(float).eps)
RTOL_MIN = 100 * EPS
STIFF_HINT_NFEV = 20_000


@dataclass(frozen=True, eq=False)
class OdeResult:
    t: NDArray
    y: NDArray
    status: int
    nfev: int
    diagnostics: tuple[Diagnostic, ...] = ()
    method: str = ""
    message: str = ""
    t_events: tuple[NDArray, ...] = ()
    y_events: tuple[NDArray, ...] = ()


class _NonFinite(Exception):
    """Internal: the right-hand side returned NaN/Inf."""


class _Budget(Exception):
    """Internal: the evaluation budget was exhausted."""


class _Rhs:
    """Validated wrapper around the user's f: shape/finite checks, call budget, last point."""

    def __init__(self, f: Callable, n: int, max_nfev: int, t0: float, y0: NDArray) -> None:
        self._f = f
        self._n = n
        self._max = max_nfev
        self.calls = 0
        self.last = (t0, y0.copy())

    def __call__(self, t: float, y: NDArray) -> NDArray:
        self.calls += 1
        if self.calls > self._max:
            raise _Budget
        yc = np.array(y, dtype=float)
        self.last = (float(t), yc)
        arr = np.asarray(self._f(float(t), yc.copy()))
        if arr.dtype.kind not in "biuf":
            raise ValidationError("f(t, y): must return real numeric data")
        out = arr.astype(float)
        if out.ndim == 0 or (out.ndim == 2 and 1 in out.shape):
            out = out.reshape(-1)
        if out.ndim != 1 or out.size != self._n:
            raise DimensionError(
                f"f(t, y): expected {self._n} derivative(s), got shape {arr.shape}")
        if not np.all(np.isfinite(out)):
            if self.calls == 1:
                raise ValidationError("f(t0, y0) returned NaN or Inf")
            raise _NonFinite
        return out


def _positive_int(v: object, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v < 1:
        raise ValidationError(f"{name}: must be a positive integer")
    return int(v)


def _real(v: object, name: str) -> float:
    arr = np.asarray(v)
    if arr.size != 1 or arr.dtype.kind not in "biuf" or not np.isfinite(float(arr.reshape(-1)[0])):
        raise ValidationError(f"{name}: expected a finite real scalar")
    return float(arr.reshape(-1)[0])


def _check_t_eval(t_eval: ArrayLike, t0: float, t1: float) -> NDArray:
    te = as_vector(t_eval, "t_eval", allow_complex=False)
    direction = 1.0 if t1 > t0 else -1.0
    lo, hi = min(t0, t1), max(t0, t1)
    if te.min() < lo or te.max() > hi:
        raise ValidationError("t_eval: values must lie inside t_span")
    if te.size > 1 and not np.all(direction * np.diff(te) > 0):
        raise ValidationError("t_eval: must be strictly monotonic in the direction of t_span")
    return te


def _check_events(events: object) -> list[Callable] | Callable | None:
    if events is None:
        return None
    if callable(events):
        return events  # type: ignore[return-value]
    if isinstance(events, Sequence) and len(events) > 0 and all(callable(e) for e in events):
        return list(events)
    raise ValidationError("events: expected a callable or a non-empty sequence of callables")


def _check_atol(atol: ArrayLike, n: int) -> float | NDArray:
    arr = np.asarray(atol)
    if arr.size == 1:
        v = _real(arr.reshape(-1)[0], "atol")
        if v < 0:
            raise ValidationError("atol: must be >= 0")
        return v
    vec = as_vector(atol, "atol", allow_complex=False, length=n)
    if np.any(vec < 0):
        raise ValidationError("atol: must be >= 0")
    return vec


def _check_jac(jac: object, method: str, n: int) -> object:
    if jac is None:
        return None
    if method not in _IMPLICIT:
        raise ValidationError(f"jac: only used by {', '.join(_IMPLICIT)}, not {method}")
    if callable(jac):
        return jac
    arr = np.asarray(jac)
    if arr.dtype.kind not in "biuf" or arr.shape != (n, n) or not np.all(np.isfinite(arr)):
        raise ValidationError(f"jac: expected a callable or a finite real {n}x{n} matrix")
    return arr.astype(float)


def solve_ode(
    f: Callable[[float, NDArray], ArrayLike], t_span: ArrayLike, y0: ArrayLike, *,
    method: str = "RK45", rtol: float = 1e-6, atol: ArrayLike = 1e-9,
    t_eval: ArrayLike | None = None,
    events: Callable[[float, NDArray], float] | Sequence[Callable] | None = None,
    jac: Callable[[float, NDArray], ArrayLike] | ArrayLike | None = None,
    max_step: float = np.inf, first_step: float | None = None, max_nfev: int = 200_000,
) -> OdeResult:
    """Solve dy/dt = f(t, y), y(t0) = y0 over ``t_span = (t0, t1)``."""
    if not callable(f):
        raise ValidationError("f: expected a callable f(t, y)")
    if method not in METHODS:
        raise ValidationError(f"method: must be one of {', '.join(METHODS)} (got {method!r})")
    span = as_vector(t_span, "t_span", allow_complex=False, length=2)
    t0, t1 = float(span[0]), float(span[1])
    if t0 == t1:
        raise ValidationError("t_span: start and end must differ")
    state = as_vector(y0, "y0", allow_complex=False)
    n = state.size
    rt = _real(rtol, "rtol")
    if rt < RTOL_MIN:
        raise ValidationError(f"rtol: must be >= {RTOL_MIN:.2e} (100*eps), got {rt:.2e}")
    at = _check_atol(atol, n)
    te = None if t_eval is None else _check_t_eval(t_eval, t0, t1)
    ev = _check_events(events)
    jc = _check_jac(jac, method, n)
    ms = _real(max_step, "max_step") if np.isfinite(max_step) else np.inf
    if ms <= 0:
        raise ValidationError("max_step: must be positive")
    options: dict = {}
    if first_step is not None:
        fs = _real(first_step, "first_step")
        if fs <= 0:
            raise ValidationError("first_step: must be positive")
        options["first_step"] = fs
    budget = _positive_int(max_nfev, "max_nfev")
    if jc is not None:
        options["jac"] = jc
    rhs = _Rhs(f, n, budget, t0, state)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        try:
            sol = solve_ivp(rhs, (t0, t1), state, method=method, t_eval=te, events=ev,
                            rtol=rt, atol=at, max_step=ms, **options)
        except _NonFinite:
            tl, yl = rhs.last
            raise ConvergenceError(
                f"{method}: right-hand side became non-finite near t = {tl:.6g}; the solution "
                "may blow up in finite time", iterations=rhs.calls,
                last_estimate=(tl, yl)) from None
        except _Budget:
            tl, yl = rhs.last
            hint = ("; the problem may be stiff, try Radau, BDF or LSODA"
                    if method not in _IMPLICIT else "")
            raise ConvergenceError(
                f"{method}: exceeded max_nfev = {budget} near t = {tl:.6g}{hint}",
                iterations=rhs.calls, last_estimate=(tl, yl)) from None
    diags: list[Diagnostic] = [
        Diagnostic("warning", "ODE_WARNING", f"{method}: {str(w.message).strip()}")
        for w in caught if issubclass(w.category, RuntimeWarning)]

    if sol.status == -1 or not np.all(np.isfinite(sol.y)):
        last = (float(sol.t[-1]), np.array(sol.y[:, -1], dtype=float)) if sol.t.size else rhs.last
        raise ConvergenceError(f"{method}: {sol.message}", iterations=int(sol.nfev),
                               last_estimate=last)
    if sol.status == 1:
        diags.append(Diagnostic(
            "info", "ODE_EVENT", f"integration stopped by a terminal event at t = "
            f"{float(sol.t[-1]):.10g}"))
    if method not in _IMPLICIT and sol.nfev > STIFF_HINT_NFEV:
        diags.append(Diagnostic(
            "warning", "ODE_STIFF_SUSPECTED",
            f"{method} needed {int(sol.nfev)} evaluations; if the problem is stiff, "
            "Radau, BDF or LSODA are usually much cheaper"))
    t_ev = tuple(np.asarray(a, dtype=float) for a in (sol.t_events or ()))
    y_ev = tuple(np.asarray(a, dtype=float).reshape(-1, n) for a in (sol.y_events or ()))
    return OdeResult(
        t=np.asarray(sol.t, dtype=float), y=np.asarray(sol.y, dtype=float).T.copy(),
        status=int(sol.status), nfev=int(sol.nfev), diagnostics=tuple(diags), method=method,
        message=str(sol.message), t_events=t_ev, y_events=y_ev)
