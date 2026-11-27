"""Numerical-analysis, statistics and FFT builtins (B2b-2), none of which take function handles.

``trapz``, ``cumtrapz``, ``interp1``, ``std``, ``var``, ``median``, ``rms``, ``zscore``, ``fft``,
``ifft``: bindings over ``engine.calculus``, ``engine.interp``, ``engine.stats`` and
``engine.transforms``. ``install_data(interp)`` registers them.

MATLAB conventions kept: a vector is processed as a whole and keeps its orientation, a matrix is
processed column by column; ``std``/``var``/``zscore`` take the flag 0 (N-1, default) or 1 (N);
``interp1(v, xq)`` uses x = 1:numel(v); ``interp1(..., 'extrap')`` extrapolates and a numeric
last argument fills points outside the data (``NaN`` gives MATLAB's usual behaviour);
``'cubic'`` means ``'pchip'``.

Differences (the engine raises instead of returning a doubtful value): ``interp1`` outside the
data range is an error unless ``'extrap'`` or a fill value is given (MATLAB returns NaN);
``interp1`` needs strictly increasing ``x`` and a vector ``v``; ``trapz``/``cumtrapz`` need at
least 2 samples and increasing ``x``; ``std``/``var`` need at least 2 values and ``zscore`` a
non-zero spread; empty input is an error; the ``dim`` argument and weights are not supported.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.engine import calculus, stats, transforms
from engstudio.engine import interp as engine_interp
from engstudio.lang.builtins_core import Builtin, _arith, _int, _need, _real, _text
from engstudio.lang.builtins_poly import _flat, _narrow
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray


def _apply(x: np.ndarray, fn, name: str) -> np.ndarray:
    """Apply ``fn`` to a vector (orientation kept) or to every column of a matrix."""
    if x.size == 0:
        raise ValidationError(f"{name}: input must not be empty.")
    if x.shape[0] == 1 or x.shape[1] == 1:
        out = np.asarray(fn(x.ravel(order="F")))
        return out.reshape(1, -1) if x.shape[0] == 1 else out.reshape(-1, 1)
    return np.column_stack([np.asarray(fn(x[:, j])) for j in range(x.shape[1])])


def _opt_int(args: list, index: int, default: int | None, name: str) -> int | None:
    """Optional integer argument; ``[]`` counts as not given."""
    if len(args) <= index or (isinstance(args[index], np.ndarray) and args[index].size == 0):
        return default
    return _int(args[index], name)


def data_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The B2b-2 builtins bound to ``interp``."""

    def integral(name: str, fn) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1, 2)
            y = _real(args[-1], name)
            x = _flat(_real(args[0], name), name) if len(args) == 2 else None
            return [_apply(y, lambda col: fn(col, x), name)]

        return call

    def spread(name: str, fn) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1, 2)
            flag = _opt_int(args, 1, 0, name)
            if flag not in (0, 1):
                raise ValidationError(f"{name}: the normalisation flag must be 0 or 1.")
            ddof = 1 - flag
            return [_apply(_real(args[0], name), lambda v: fn(v, ddof), name)]

        return call

    def plain(name: str, fn) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1)
            return [_apply(_real(args[0], name), fn, name)]

        return call

    def spectrum(name: str, fn) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1, 2)
            n = _opt_int(args, 1, None, name)
            out = _apply(_arith(args[0], name), lambda v: fn(v, n), name)
            return [_narrow(out)]

        return call

    def interp1(args: list, nargout: int) -> list:
        name = "interp1"
        _need(name, args, 2, 5)
        k = next((i for i, a in enumerate(args) if isinstance(a, CharArray)), len(args))
        nums, opts = args[:k], list(args[k:])
        if len(nums) == 3:
            x_arg, v_arg, xq = nums[0], nums[1], _real(nums[2], name)
        elif len(nums) == 2:
            x_arg, v_arg, xq = None, nums[0], _real(nums[1], name)
        else:
            raise ValidationError("interp1: use interp1(x, v, xq, ...) or interp1(v, xq, ...).")
        v = _real(v_arg, name)
        if v.size and 1 not in v.shape:
            raise NotSupportedError("interp1: a matrix v is not supported yet (use a vector).")
        v = v.ravel(order="F")
        x = _flat(_real(x_arg, name), name) if x_arg is not None else np.arange(1.0, v.size + 1)
        items = [_text(o, name).lower() if isinstance(o, CharArray) else o for o in opts]
        method, extrap, fill = "linear", "error", None
        if items and isinstance(items[0], str) and items[0] != "extrap":
            method = {"cubic": "pchip"}.get(items[0], items[0])
            items.pop(0)
        if items:
            last = items.pop(0)
            if isinstance(last, str):
                if last != "extrap":
                    raise ValidationError(f"interp1: unknown option {last!r}.")
                extrap = "extrapolate"
            else:
                value = _real(last, name)
                if value.size != 1:
                    raise ValidationError("interp1: the extrapolation value must be a scalar.")
                fill, extrap = float(value[0, 0]), "nan"
        if items:
            raise ValidationError("interp1: too many options.")
        if xq.size == 0:
            return [np.zeros(xq.shape)]
        try:
            out = np.asarray(engine_interp.interp1(x, v, xq, method=method, extrap=extrap))
        except ValidationError as exc:
            if "outside the data range" in str(exc):
                raise ValidationError(
                    "interp1: a query point is outside the data range; add 'extrap' or a fill "
                    "value (for example NaN) after the method.") from exc
            raise
        if fill is not None and not np.isnan(fill):
            out = np.where((xq < x.min()) | (xq > x.max()), fill, out)
        return [out]

    return {
        "trapz": integral("trapz", lambda y, x: calculus.trapz(y, x)),
        "cumtrapz": integral("cumtrapz", lambda y, x: calculus.cumtrapz(y, x)),
        "interp1": interp1,
        "std": spread("std", stats.std),
        "var": spread("var", stats.var),
        "zscore": spread("zscore", stats.zscore),
        "median": plain("median", stats.median),
        "rms": plain("rms", stats.rms),
        "fft": spectrum("fft", transforms.fft),
        "ifft": spectrum("ifft", transforms.ifft),
    }


def install_data(interp: Interpreter) -> None:
    """Register the B2b-2 builtins on ``interp``."""
    interp.functions.update(data_functions(interp))
