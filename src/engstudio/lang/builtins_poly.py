"""Polynomial builtins (B2b-1): ``poly``, ``roots``, ``polyval``, ``polyfit``.

Thin bindings over ``engine.roots.polyroots``, ``engine.regression`` and ``engine.decomp``.
``install_poly(interp)`` registers them.

MATLAB conventions kept: coefficients are highest power first; ``roots`` returns a column vector
(``[]`` for a constant or all-zero input); ``poly`` of a vector gives the polynomial with those
roots, of a square matrix its characteristic polynomial (from the eigenvalues); ``polyfit``
returns a row vector; results with zero imaginary parts are real.

Differences: ``polyfit`` accepts one output only (no ``S``/``mu``) and raises an error when there
are fewer points than ``n + 1`` (MATLAB returns a minimum-norm fit with a warning); ``roots``
sorts by real then imaginary part; complex matrices are not supported by ``poly``.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.engine import decomp, regression
from engstudio.engine import roots as engine_roots
from engstudio.lang.builtins_core import Builtin, _arith, _int, _need, _real
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import empty_double


def _narrow(z: np.ndarray) -> np.ndarray:
    """Real array when every imaginary part is exactly zero."""
    return z.real.copy() if z.dtype.kind == "c" and not np.any(z.imag) else z


def _flat(x: np.ndarray, name: str) -> np.ndarray:
    """Column-major 1-D copy of a vector (or empty) argument."""
    if x.size and x.shape[0] != 1 and x.shape[1] != 1:
        raise ValidationError(f"{name}: input must be a vector.")
    return x.ravel(order="F")


def poly_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The polynomial builtins bound to ``interp``."""
    host = interp.host

    def poly(args: list, nargout: int) -> list:
        _need("poly", args, 1)
        x = _arith(args[0], "poly")
        if x.size == 0:
            return [np.ones((1, 1))]
        if not np.all(np.isfinite(x)):
            raise ValidationError("poly: input must be finite.")
        if x.shape[0] == x.shape[1] and x.shape[0] > 1:
            if x.dtype.kind == "c":
                raise NotSupportedError("poly: complex matrices are not supported yet")
            res = decomp.eigh(x) if np.array_equal(x, x.T) else decomp.eig(x)
            for d in res.diagnostics:
                host.diagnostic(d)
            r = np.asarray(res.values)
        elif 1 in x.shape:
            r = x.ravel(order="F")
        else:
            raise ValidationError("poly: input must be a vector or a square matrix.")
        c = _narrow(np.atleast_1d(np.poly(r)))
        return [c.reshape(1, -1)]

    def roots(args: list, nargout: int) -> list:
        _need("roots", args, 1)
        c = _flat(_arith(args[0], "roots"), "roots")
        if c.size == 0 or not np.any(c):
            return [empty_double()]
        r = np.asarray(engine_roots.polyroots(c).root)
        if r.size == 0:
            return [empty_double()]
        return [_narrow(r).reshape(-1, 1)]

    def polyval(args: list, nargout: int) -> list:
        _need("polyval", args, 2)
        p = _flat(_arith(args[0], "polyval"), "polyval")
        if p.size == 0:
            raise ValidationError("polyval: the coefficient vector is empty.")
        x = _arith(args[1], "polyval")
        if x.size == 0:
            return [np.zeros(x.shape)]
        out = np.asarray(regression.polyval(p, x)).reshape(x.shape)
        return [_narrow(out)]

    def polyfit(args: list, nargout: int) -> list:
        _need("polyfit", args, 3)
        if nargout > 1:
            raise NotSupportedError("polyfit: only one output is supported yet (no S or mu).")
        x = _flat(_real(args[0], "polyfit"), "polyfit")
        y = _flat(_real(args[1], "polyfit"), "polyfit")
        res = regression.polyfit(x, y, _int(args[2], "polyfit"))
        for d in res.diagnostics:
            host.diagnostic(d)
        return [np.asarray(res.params, dtype=float).reshape(1, -1)]

    return {"poly": poly, "roots": roots, "polyval": polyval, "polyfit": polyfit}


def install_poly(interp: Interpreter) -> None:
    """Register the polynomial builtins on ``interp``."""
    interp.functions.update(poly_functions(interp))
