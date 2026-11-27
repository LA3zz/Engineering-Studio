"""Handle-based numerical builtins (B2b-3): functions that take a function handle.

``fzero``, ``integral``/``quad``/``quadgk``, ``integral2``, ``ode45``/``ode23``/``ode15s``,
``fminsearch`` and ``fsolve``, bound to ``engine.roots``, ``engine.calculus``, ``engine.ode``
and ``engine.optimize``. ``install_funcs(interp)`` registers them. The function argument may be
a handle (``@f``, ``@(x) ...``) or a function name given as text. User functions are called
through ``interp.call`` with scalar arguments (vector problems: an array shaped like ``x0``).

Differences from MATLAB (documented, never silent):
- ``odeset`` options RelTol, AbsTol, MaxStep and InitialStep are used by ode45/ode23/ode15s;
  other odeset names are accepted and ignored, except Events and Jacobian (not supported).
  ``deg2rad``/``rad2deg`` live here too.
- ``optimset`` option structs are not supported; ``integral`` accepts only the
  name-value pairs ``'AbsTol'`` and ``'RelTol'`` (defaults 1.49e-8, tighter than MATLAB's).
- ``fzero(f, x0)`` with a scalar start searches outward for a sign change (MATLAB-style steps);
  ``fzero(f, [a b])`` needs ``f(a)``, ``f(b)`` of opposite sign. Outputs: ``[x, fval, exitflag]``
  (``exitflag`` is 1; failure raises an error instead of returning a flag).
- ``integral`` is evaluated point by point, so non-vectorised integrands work too.
  ``integral2`` needs numeric limits. Second output: error estimate.
- ``ode45`` -> RK45, ``ode23`` -> RK23, ``ode15s`` -> BDF (variable order, stiff). Call as
  ``[t, y] = ode45(f, tspan, y0)``; ``y`` has one row per time point. Two-element ``tspan``
  returns the solver's own steps (these differ from MATLAB's), a longer ``tspan`` returns
  exactly those times. Tolerances rtol 1e-6, atol 1e-9 (tighter than MATLAB's 1e-3, 1e-6).
- ``fminsearch`` is Nelder-Mead (tol 1e-8, local minimum only); ``fsolve`` is damped Newton.
  Both return ``x`` shaped like ``x0``.
"""

from __future__ import annotations

import math

import numpy as np

from engstudio.core.errors import ConvergenceError, NotSupportedError, ValidationError
from engstudio.engine import calculus, ode, optimize, roots
from engstudio.lang.builtins_core import Builtin, _need, _real, _text
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray, FunctionHandle, StructValue

_FZERO_STEPS = (-0.01, 0.025, -0.05, 0.1, -0.25, 0.5, -1.0, 2.5, -5.0, 10.0, -50.0, 100.0,
                -500.0, 1000.0)


def _handle(v: object, name: str) -> FunctionHandle:
    if isinstance(v, FunctionHandle):
        return v
    if isinstance(v, CharArray):
        return FunctionHandle(name=_text(v, name))
    raise ValidationError(f"{name}: the first argument must be a function handle or a name.")


def _num(v: object, name: str, what: str = "argument") -> float:
    x = _real(v, name)
    if x.size != 1:
        raise ValidationError(f"{name}: {what} must be a scalar.")
    return float(x.reshape(-1)[0])


def _flat(v: object, name: str) -> np.ndarray:
    return _real(v, name).reshape(-1, order="F")


# odeset option name -> solve_ode keyword; other odeset names are accepted and ignored.
_ODE_OPTIONS = {"RelTol": "rtol", "AbsTol": "atol", "MaxStep": "max_step",
                "InitialStep": "first_step"}
_ODE_IGNORED = ("Refine", "Stats", "OutputFcn", "OutputSel", "NormControl", "BDF", "MaxOrder",
                "Vectorized", "Mass", "MStateDependence", "MvPattern", "MassSingular",
                "InitialSlope", "JPattern", "NonNegative", "Events", "Jacobian")


def _ode_options(opts: StructValue, name: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for field, value in opts.items():
        if isinstance(value, np.ndarray) and value.size == 0:
            continue
        if field in ("Events", "Jacobian"):
            raise NotSupportedError(f"{name}: the odeset option {field} is not supported yet.")
        if field in _ODE_OPTIONS:
            x = _flat(value, name)
            out[_ODE_OPTIONS[field]] = float(x[0]) if x.size == 1 or field != "AbsTol" else x
    return out


def _odeset(args: list, nargout: int) -> list:
    """odeset('RelTol', 1e-8, ...) -> struct with the given fields (names as in MATLAB)."""
    if len(args) % 2:
        raise ValidationError("odeset: options must be name-value pairs.")
    known = {k.lower(): k for k in (*_ODE_OPTIONS, *_ODE_IGNORED)}
    fields: dict[str, object] = {}
    for key, value in zip(args[::2], args[1::2], strict=True):
        text = _text(key, "odeset")
        if text.lower() not in known:
            raise ValidationError(f"odeset: unrecognized option {text!r}.")
        fields[known[text.lower()]] = value
    return [StructValue(fields)]


def _deg2rad(args: list, nargout: int) -> list:
    _need("deg2rad", args, 1)
    return [_real(args[0], "deg2rad").astype(float) * (math.pi / 180)]


def _rad2deg(args: list, nargout: int) -> list:
    _need("rad2deg", args, 1)
    return [_real(args[0], "rad2deg").astype(float) * (180 / math.pi)]


def _outs(name: str, values: list, nargout: int) -> list:
    wanted = max(nargout, 1)
    if wanted > len(values):
        raise ValidationError(f"{name}: Too many output arguments.")
    return values[:wanted]


def _cell(x: float) -> np.ndarray:
    return np.array([[x]], dtype=np.float64)


def _bracket_search(f, x0: float) -> tuple[float, float]:
    f0 = f(x0)
    if not math.isfinite(f0):
        raise ValidationError(f"fzero: the function is not finite at x0 = {x0:g}.")
    if f0 == 0.0:
        return x0, x0
    base = x0 if x0 != 0.0 else 1.0
    for step in _FZERO_STEPS:
        b = x0 + base * step
        fb = f(b)
        if math.isfinite(fb) and (fb == 0.0 or (fb > 0) != (f0 > 0)):
            return min(x0, b), max(x0, b)
    raise ConvergenceError(
        "fzero: could not find an interval around x0 where the function changes sign; "
        "give an interval [a b] instead.", 0, x0)


def funcs_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The B2b-3 builtins bound to ``interp``."""
    host = interp.host

    def call(h: FunctionHandle, args: list, name: str):
        out = interp.call(h, args, 1)
        if not out:
            raise ValidationError(f"{name}: the function did not return a value.")
        return out[0]

    def scalar_fn(h: FunctionHandle, name: str):
        return lambda x: _num(call(h, [_cell(x)], name), name, "the function value")

    def forward(diagnostics) -> None:
        for d in diagnostics:
            host.diagnostic(d)

    def fzero(args: list, nargout: int) -> list:
        _need("fzero", args, 2)
        f = scalar_fn(_handle(args[0], "fzero"), "fzero")
        x0 = _flat(args[1], "fzero")
        if x0.size == 2:
            a, b = float(x0[0]), float(x0[1])
        elif x0.size == 1:
            a, b = _bracket_search(f, float(x0[0]))
        else:
            raise ValidationError("fzero: x0 must be a starting point or an interval [a b].")
        root = a if a == b else roots.brentq(f, a, b).root
        return _outs("fzero", [_cell(root), _cell(f(root)), _cell(1.0)], nargout)

    def quadrature(name: str) -> Builtin:
        def run(args: list, nargout: int) -> list:
            _need(name, args, 3, 7)
            f = scalar_fn(_handle(args[0], name), name)
            a, b = _num(args[1], name, "the limit"), _num(args[2], name, "the limit")
            rtol = atol = 1.49e-8
            opts = args[3:]
            if len(opts) % 2:
                raise ValidationError(f"{name}: options must be name-value pairs.")
            for key, val in zip(opts[::2], opts[1::2], strict=True):
                k = _text(key, name)
                if k.lower() == "abstol":
                    atol = _num(val, name, "AbsTol")
                elif k.lower() == "reltol":
                    rtol = _num(val, name, "RelTol")
                else:
                    raise NotSupportedError(
                        f"{name}: option '{k}' is not supported (only AbsTol and RelTol).")
            res = calculus.quad(f, a, b, rtol=rtol, atol=atol)
            forward(res.diagnostics)
            return _outs(name, [_cell(res.value), _cell(res.error_estimate)], nargout)

        return run

    def integral2(args: list, nargout: int) -> list:
        _need("integral2", args, 5)
        h = _handle(args[0], "integral2")
        lim = [_num(a, "integral2", "the limit") for a in args[1:]]
        res = calculus.dblquad(
            lambda x, y: _num(call(h, [_cell(x), _cell(y)], "integral2"), "integral2",
                              "the function value"), *lim)
        forward(res.diagnostics)
        return _outs("integral2", [_cell(res.value), _cell(res.error_estimate)], nargout)

    def ode_solver(name: str, method: str) -> Builtin:
        def solve(args: list, nargout: int) -> list:
            _need(name, args, 3, 4)
            if nargout < 2:
                raise NotSupportedError(
                    f"{name}: call it as [t, y] = {name}(f, tspan, y0); the single-output "
                    "structure form is not supported.")
            opts: dict[str, object] = {}
            if len(args) == 4 and not (isinstance(args[3], np.ndarray) and args[3].size == 0):
                if not isinstance(args[3], StructValue):
                    raise ValidationError(f"{name}: options must be a struct from odeset.")
                opts = _ode_options(args[3], name)
            h = _handle(args[0], name)
            tspan = _flat(args[1], name)
            if tspan.size < 2:
                raise ValidationError(f"{name}: tspan needs at least two values.")
            y0 = _flat(args[2], name)

            def rhs(t: float, y: np.ndarray) -> np.ndarray:
                return _flat(call(h, [_cell(t), y.reshape(-1, 1)], name), name)

            res = ode.solve_ode(rhs, (float(tspan[0]), float(tspan[-1])), y0, method=method,
                                t_eval=tspan if tspan.size > 2 else None,
                                **opts)  # type: ignore[arg-type]
            forward(res.diagnostics)
            return _outs(name, [res.t.reshape(-1, 1), res.y], nargout)

        return solve

    def fminsearch(args: list, nargout: int) -> list:
        _need("fminsearch", args, 2)
        h = _handle(args[0], "fminsearch")
        x0 = _real(args[1], "fminsearch")
        shape = x0.shape

        def objective(x: np.ndarray) -> float:
            return _num(call(h, [x.reshape(shape, order="F").copy()], "fminsearch"),
                        "fminsearch", "the function value")

        res = optimize.minimize(objective, x0.reshape(-1, order="F"), method="Nelder-Mead",
                                tol=1e-8)
        forward(res.diagnostics)
        x = np.asarray(res.x).reshape(shape, order="F")
        return _outs("fminsearch", [x, _cell(res.fun), _cell(1.0)], nargout)

    def fsolve(args: list, nargout: int) -> list:
        _need("fsolve", args, 2)
        h = _handle(args[0], "fsolve")
        x0 = _real(args[1], "fsolve")
        shape = x0.shape

        def raw(x: np.ndarray) -> np.ndarray:
            return _real(call(h, [np.asarray(x, dtype=float).reshape(shape, order="F")],
                              "fsolve"), "fsolve")

        res = roots.fsolve(lambda x: raw(x).reshape(-1, order="F"), x0.reshape(-1, order="F"))
        forward(res.diagnostics)
        x = np.asarray(res.root).reshape(shape, order="F")
        return _outs("fsolve", [x, raw(x.reshape(-1, order="F")), _cell(1.0)], nargout)

    return {
        "fzero": fzero,
        "integral": quadrature("integral"),
        "quad": quadrature("quad"),
        "quadgk": quadrature("quadgk"),
        "integral2": integral2,
        "ode45": ode_solver("ode45", "RK45"),
        "ode23": ode_solver("ode23", "RK23"),
        "ode15s": ode_solver("ode15s", "BDF"),
        "odeset": _odeset,
        "deg2rad": _deg2rad,
        "rad2deg": _rad2deg,
        "fminsearch": fminsearch,
        "fsolve": fsolve,
    }


def install_funcs(interp: Interpreter) -> None:
    """Register the B2b-3 builtins on ``interp``."""
    interp.functions.update(funcs_functions(interp))
