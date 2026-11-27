"""Analysis builtins (B2b-4): ``interp2``, ``fminbnd``, ``fminunc``, ``linprog``, ``quantile``,
``prctile``, ``ttest``, ``ttest2``. ``install_analysis(interp)`` registers them.

Bindings over ``engine.interp``, ``engine.optimize`` and ``engine.stats``.

Differences from MATLAB (the engine raises instead of returning a doubtful value):
- ``interp2``: methods linear, nearest, cubic (``spline`` is not supported). A query outside the
  grid is an error unless a fill value follows the method (``interp2(..., 'linear', NaN)``).
  Queries: matching shapes are evaluated point by point; a row ``xq`` with a column ``yq`` gives
  the full grid. ``X``/``Y`` may be vectors or ``meshgrid`` matrices.
- ``fminbnd`` and ``fminunc`` return ``[x, fval, exitflag]``; no options struct. ``fminunc`` is
  BFGS with finite-difference gradients, tol 1e-6 (exitflag 2 = stopped by round-off, with
  a warning).
- ``linprog(f, A, b, Aeq, beq, lb, ub)``: variables are free unless bounded; ``[x, fval,
  exitflag]`` with ``x`` a column. Infeasible or unbounded problems raise an error (MATLAB
  returns exitflag -2/-3).
- ``quantile`` uses MATLAB's rule (points at (i - 0.5)/n). For a vector the result has the
  orientation of ``x``; a matrix is processed per column. ``prctile`` takes p in [0, 100].
  The ``dim`` argument is not supported.
- ``ttest(x, m, 'Alpha', a, 'Tail', t)``, ``ttest2(x, y, 'Vartype', v, 'Alpha', a, 'Tail', t)``:
  outputs ``[h, p, ci, stats]`` (``stats.tstat``, ``stats.df``, ``stats.sd``). ``ttest2``
  defaults to pooled variance (``'Vartype','equal'``) as in MATLAB. Vector input only; NaN is
  rejected, not ignored.
"""

from __future__ import annotations

import math

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.engine import interp as engine_interp
from engstudio.engine import optimize
from engstudio.engine import stats as engine_stats
from engstudio.lang.builtins_core import Builtin, _need, _real, _text
from engstudio.lang.builtins_funcs import _cell, _handle, _num, _outs
from engstudio.lang.builtins_poly import _flat as _vector
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray, StructValue

_TAILS = {"both": "two-sided", "right": "greater", "left": "less"}


def _given(args: list, index: int) -> bool:
    """True when optional argument ``index`` exists and is not ``[]``."""
    return len(args) > index and not (isinstance(args[index], np.ndarray)
                                      and args[index].size == 0)


def _grid_axes(args: list, z: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    m, n = z.shape
    if len(args) == 3:
        return np.arange(1.0, n + 1), np.arange(1.0, m + 1)
    xm, ym = _real(args[0], name), _real(args[1], name)
    if m > 1 and xm.shape == (m, n) and ym.shape == (m, n):
        x, y = xm[0, :].copy(), ym[:, 0].copy()
        if not (np.array_equal(xm, np.tile(x, (m, 1)))
                and np.array_equal(ym, np.tile(y.reshape(-1, 1), (1, n)))):
            raise ValidationError(f"{name}: X and Y must be in meshgrid format.")
        return x, y
    if 1 in xm.shape and 1 in ym.shape and xm.size == n and ym.size == m:
        return xm.ravel(order="F"), ym.ravel(order="F")
    raise ValidationError(f"{name}: X and Y must be vectors or matrices matching size(Z).")


def _tail_ci(mean: float, se: float, dof: float, alpha: float, alt: str) -> np.ndarray:
    if alt == "two-sided":
        t = engine_stats.t_quantile(1.0 - alpha / 2.0, dof)
        return np.array([[mean - t * se], [mean + t * se]])
    t = engine_stats.t_quantile(1.0 - alpha, dof)
    if alt == "greater":
        return np.array([[mean - t * se], [math.inf]])
    return np.array([[-math.inf], [mean + t * se]])


def _test_options(name: str, rest: list, allowed: tuple[str, ...]) -> dict:
    if len(rest) % 2:
        raise ValidationError(f"{name}: options must be name-value pairs.")
    out: dict = {}
    for key, val in zip(rest[::2], rest[1::2], strict=True):
        k = _text(key, name)
        if k.lower() not in allowed:
            raise NotSupportedError(f"{name}: option '{k}' is not supported.")
        out[k.lower()] = val
    return out


def _alpha_tail(name: str, opts: dict) -> tuple[float, str]:
    alpha = _num(opts["alpha"], name, "Alpha") if "alpha" in opts else 0.05
    if not 0.0 < alpha < 1.0:
        raise ValidationError(f"{name}: Alpha must be between 0 and 1.")
    tail = _text(opts["tail"], name).lower() if "tail" in opts else "both"
    if tail not in _TAILS:
        raise ValidationError(f"{name}: Tail must be 'both', 'right' or 'left'.")
    return alpha, _TAILS[tail]


def analysis_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The B2b-4 builtins bound to ``interp``."""
    host = interp.host

    def forward(diagnostics) -> None:
        for d in diagnostics:
            host.diagnostic(d)

    def call_scalar(h, x, name: str) -> float:
        out = interp.call(h, [x], 1)
        if not out:
            raise ValidationError(f"{name}: the function did not return a value.")
        return _num(out[0], name, "the function value")

    def interp2(args: list, nargout: int) -> list:
        name = "interp2"
        _need(name, args, 3, 8)
        k = next((i for i, a in enumerate(args) if isinstance(a, CharArray)), len(args))
        nums, opts = args[:k], list(args[k:])
        if len(nums) not in (3, 5):
            raise ValidationError("interp2: use interp2(X, Y, Z, Xq, Yq) or interp2(Z, Xq, Yq).")
        z = _real(nums[-3], name)
        x, y = _grid_axes(nums, z, name)
        xq, yq = _real(nums[-2], name), _real(nums[-1], name)
        method, fill = "linear", None
        if opts:
            method = _text(opts[0], name).lower()
            if method == "spline":
                raise NotSupportedError("interp2: method 'spline' is not supported yet.")
            if len(opts) == 2:
                fill = _num(opts[1], name, "the extrapolation value")
            elif len(opts) > 2:
                raise ValidationError("interp2: too many options.")
        if xq.shape != yq.shape:
            if 1 in xq.shape and 1 in yq.shape:
                xq, yq = np.meshgrid(xq.ravel(order="F"), yq.ravel(order="F"))
            else:
                raise ValidationError("interp2: Xq and Yq must have the same size.")
        if xq.size == 0:
            return [np.zeros(xq.shape)]
        try:
            out = np.asarray(engine_interp.interp2(
                x, y, z, xq, yq, method=method, extrap="error" if fill is None else "nan"))
        except ValidationError as exc:
            if "outside the data range" in str(exc):
                raise ValidationError(
                    "interp2: a query point is outside the grid; add a fill value after the "
                    "method (for example 'linear', NaN).") from exc
            raise
        if fill is not None and not np.isnan(fill):
            outside = (xq < x.min()) | (xq > x.max()) | (yq < y.min()) | (yq > y.max())
            out = np.where(outside, fill, out)
        return [out.reshape(xq.shape)]

    def fminbnd(args: list, nargout: int) -> list:
        _need("fminbnd", args, 3)
        h = _handle(args[0], "fminbnd")
        a, b = _num(args[1], "fminbnd", "the interval end"), _num(
            args[2], "fminbnd", "the interval end")
        res = optimize.minimize_scalar(lambda x: call_scalar(h, _cell(x), "fminbnd"), a, b)
        return _outs("fminbnd", [_cell(float(res.x)), _cell(res.fun), _cell(1.0)], nargout)

    def fminunc(args: list, nargout: int) -> list:
        _need("fminunc", args, 2)
        h = _handle(args[0], "fminunc")
        x0 = _real(args[1], "fminunc")
        shape = x0.shape
        res = optimize.minimize(
            lambda x: call_scalar(h, x.reshape(shape, order="F").copy(), "fminunc"),
            x0.reshape(-1, order="F"), method="BFGS", tol=1e-6)
        forward(res.diagnostics)
        x = np.asarray(res.x).reshape(shape, order="F")
        return _outs("fminunc", [x, _cell(res.fun), _cell(1.0 if res.converged else 2.0)],
                     nargout)

    def linprog(args: list, nargout: int) -> list:
        name = "linprog"
        _need(name, args, 1, 7)
        c = _vector(_real(args[0], name), name)
        n = c.size

        def part(i: int):
            return _real(args[i], name) if _given(args, i) else None

        a, b, aeq, beq, lb, ub = (part(i) for i in range(1, 7))
        bounds = None
        if lb is not None or ub is not None:
            lo = _vector(lb, name) if lb is not None else np.full(n, -np.inf)
            hi = _vector(ub, name) if ub is not None else np.full(n, np.inf)
            if lo.size != n or hi.size != n:
                raise ValidationError(f"{name}: lb and ub must have {n} elements.")
            bounds = [(None if np.isneginf(p) else float(p), None if np.isposinf(q) else float(q))
                      for p, q in zip(lo, hi, strict=True)]
        res = optimize.linprog(
            c, a, None if b is None else _vector(b, name), aeq,
            None if beq is None else _vector(beq, name), bounds)
        forward(res.diagnostics)
        x = np.asarray(res.x, dtype=float).reshape(-1, 1)
        return _outs(name, [x, _cell(res.fun), _cell(1.0)], nargout)

    def quantile_like(name: str, scale: float) -> Builtin:
        def run(args: list, nargout: int) -> list:
            _need(name, args, 2)
            x, p = _real(args[0], name), _real(args[1], name)
            if x.size == 0 or p.size == 0:
                raise ValidationError(f"{name}: inputs must not be empty.")
            pv = p.ravel(order="F") / scale
            if np.any(pv < 0) or np.any(pv > 1):
                raise ValidationError(f"{name}: p must be between 0 and {scale:g}.")

            def q(v: np.ndarray) -> np.ndarray:
                return np.asarray(engine_stats.quantile(v, pv, method="matlab"), dtype=float)

            if 1 in x.shape:
                out = q(x.ravel(order="F"))
                return [out.reshape(1, -1) if x.shape[0] == 1 else out.reshape(-1, 1)]
            return [np.column_stack([q(x[:, j]) for j in range(x.shape[1])])]

        return run

    def result_struct(**fields: object) -> StructValue:
        return StructValue(fields)

    def ttest(args: list, nargout: int) -> list:
        name = "ttest"
        _need(name, args, 1, 6)
        x = _vector(_real(args[0], name), name)
        rest = list(args[1:])
        m = 0.0
        if rest and not isinstance(rest[0], CharArray):
            m = _num(rest.pop(0), name, "the hypothesised mean")
        alpha, alt = _alpha_tail(name, _test_options(name, rest, ("alpha", "tail")))
        res = engine_stats.ttest_1samp(x, m, alternative=alt)
        mu, s = engine_stats.mean(x), engine_stats.std(x)
        ci = _tail_ci(mu, s / math.sqrt(x.size), res.dof, alpha, alt)
        h = np.array([[res.p_value < alpha]], dtype=bool)
        st = result_struct(tstat=res.statistic, df=res.dof, sd=s)
        return _outs(name, [h, _cell(res.p_value), ci, st], nargout)

    def ttest2(args: list, nargout: int) -> list:
        name = "ttest2"
        _need(name, args, 2, 8)
        x = _vector(_real(args[0], name), name)
        y = _vector(_real(args[1], name), name)
        opts = _test_options(name, list(args[2:]), ("alpha", "tail", "vartype"))
        alpha, alt = _alpha_tail(name, opts)
        vartype = _text(opts["vartype"], name).lower() if "vartype" in opts else "equal"
        if vartype not in ("equal", "unequal"):
            raise ValidationError("ttest2: Vartype must be 'equal' or 'unequal'.")
        equal = vartype == "equal"
        res = engine_stats.ttest_ind(x, y, equal_var=equal, alternative=alt)
        n1, n2 = x.size, y.size
        v1, v2 = engine_stats.var(x), engine_stats.var(y)
        if equal:
            sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
            se, sd = math.sqrt(sp2 * (1.0 / n1 + 1.0 / n2)), _cell(math.sqrt(sp2))
        else:
            se, sd = math.sqrt(v1 / n1 + v2 / n2), np.array([[math.sqrt(v1)], [math.sqrt(v2)]])
        diff = engine_stats.mean(x) - engine_stats.mean(y)
        ci = _tail_ci(diff, se, res.dof, alpha, alt)
        h = np.array([[res.p_value < alpha]], dtype=bool)
        st = result_struct(tstat=res.statistic, df=res.dof, sd=sd)
        return _outs(name, [h, _cell(res.p_value), ci, st], nargout)

    return {
        "interp2": interp2,
        "fminbnd": fminbnd,
        "fminunc": fminunc,
        "linprog": linprog,
        "quantile": quantile_like("quantile", 1.0),
        "prctile": quantile_like("prctile", 100.0),
        "ttest": ttest,
        "ttest2": ttest2,
    }


def install_analysis(interp: Interpreter) -> None:
    """Register the B2b-4 builtins on ``interp``."""
    interp.functions.update(analysis_functions(interp))
