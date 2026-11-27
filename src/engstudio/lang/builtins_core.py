"""Core builtin functions of the interpreter, part 1 (B1a).

``core_functions(interp)`` returns ``{name: fn}`` where ``fn(args, nargout) -> list of values``;
``install_core(interp)`` registers them. Pure functions are module-level; ``disp``, ``fprintf``,
``error``, ``warning`` and the ``engine.linalg`` bindings need the interpreter's host and are
created per interpreter.

Contents: constants (pi, e, Inf, NaN, eps, i, j, true, false), constructors (zeros, ones, eye,
linspace, logspace, repmat, reshape, diag, triu, tril, meshgrid, horzcat, vertcat), size and type
queries, conversions, elementwise math, reductions (sum, prod, mean, min, max, cumsum, cumprod,
any, all, sort, find, diff), isequal, linear algebra (inv, det, trace, rank, cond, rcond, norm, dot,
cross) and output (disp, sprintf, fprintf, num2str, error, warning).

MATLAB conventions kept: reductions work along the first non-singleton dimension; ``round``
rounds halves away from zero; ``mod`` takes the sign of the divisor; ``max``/``min`` ignore NaN;
``sqrt``/``log``/``asin``/``acos`` return complex results outside their real domain;
``sprintf('%d', 1.5)`` switches to ``%e``. Differences: arrays are 2-D; complex matrices are
not supported by the linear-algebra bindings; ``min``/``max`` reject complex input;
``fprintf`` always writes to the host (file ids are ignored).
"""

from __future__ import annotations

import math
import re
import warnings
from collections import deque
from collections.abc import Callable, Sequence

import numpy as np

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import (
    DimensionError,
    EngStudioError,
    NotSupportedError,
    ValidationError,
)
from engstudio.engine import linalg
from engstudio.lang import ops
from engstudio.lang.display import format_disp
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
    numel_of,
    size_of,
    values_equal,
)

Builtin = Callable[[list, int], list]
_PURE: dict[str, Builtin] = {}


class UserError(EngStudioError):
    """Raised by the ``error`` builtin; ``identifier`` is exposed as ``err.identifier``."""

    code = "E_USER"

    def __init__(self, message: str, identifier: str = "") -> None:
        super().__init__(message)
        self.identifier = identifier


def _register(*names: str) -> Callable[[Builtin], Builtin]:
    def deco(fn: Builtin) -> Builtin:
        for name in names:
            _PURE[name] = fn
        return fn

    return deco


def _scalar(x: float | bool) -> np.ndarray:
    return np.array([[x]], dtype=np.bool_ if isinstance(x, (bool, np.bool_)) else np.float64)


def _need(name: str, args: Sequence, low: int, high: int | None = None) -> None:
    high = low if high is None else high
    if len(args) < low:
        raise ValidationError(f"{name}: Not enough input arguments.")
    if len(args) > high:
        raise ValidationError(f"{name}: Too many input arguments.")


def _arith(v: object, name: str) -> np.ndarray:
    """Numeric view of ``v``: logical becomes double, char becomes character codes."""
    if isinstance(v, np.ndarray):
        return v.astype(np.float64) if v.dtype == np.bool_ else v
    if isinstance(v, CharArray):
        return v.codes()
    raise ValidationError(f"{name}: argument must be numeric, not {class_of(v)}.")


def _real(v: object, name: str) -> np.ndarray:
    x = _arith(v, name)
    if x.dtype.kind == "c":
        raise NotSupportedError(f"{name}: complex input is not supported")
    return x


def _text(v: object, name: str) -> str:
    if isinstance(v, CharArray) and v.shape[0] <= 1:
        return v.to_str()
    raise ValidationError(f"{name}: argument must be a character vector.")


def _int(v: object, name: str) -> int:
    x = _real(v, name)
    if x.size != 1 or not math.isfinite(x[0, 0]) or x[0, 0] != round(x[0, 0]):
        raise ValidationError(f"{name}: expected a finite integer scalar.")
    return int(x[0, 0])


def _on_array(v: object, fn: Callable[[np.ndarray], np.ndarray], name: str) -> object:
    if isinstance(v, np.ndarray):
        return fn(v)
    if isinstance(v, CharArray):
        return CharArray(fn(v.data))
    if isinstance(v, CellArray):
        return CellArray(fn(v.data))
    raise ValidationError(f"{name}: argument must be an array, not {class_of(v)}.")


# ------------------------------------------------------------------ constants
def _constant(name: str, value: complex | float | bool) -> None:
    arr = np.array([[value]])
    if isinstance(value, bool):
        arr = arr.astype(bool)

    @_register(name)
    def const(args: list, nargout: int) -> list:
        _need(name, args, 0)
        return [arr.copy()]


for _n, _v in (("pi", math.pi), ("e", math.e), ("Inf", math.inf), ("inf", math.inf),
               ("NaN", math.nan), ("nan", math.nan), ("eps", float(np.finfo(float).eps)),
               ("i", 1j), ("j", 1j), ("true", True), ("false", False),
               ("realmax", float(np.finfo(float).max)), ("realmin", float(np.finfo(float).tiny))):
    _constant(_n, _v)


# --------------------------------------------------------------- constructors
def _dims(name: str, args: list) -> tuple[int, int]:
    args = list(args)
    if args and isinstance(args[-1], CharArray):
        cls = _text(args.pop(), name)
        if cls != "double":
            raise NotSupportedError(f"{name}: class argument {cls!r} is not supported")
    if not args:
        return 1, 1
    nums = [_real(a, name) for a in args]
    if len(nums) == 1:
        flat = [_int(_scalar(x), name) for x in nums[0].ravel(order="F")]
    else:
        if any(a.size != 1 for a in nums):
            raise ValidationError(f"{name}: size arguments must be scalars.")
        flat = [_int(a, name) for a in nums]
    if len(flat) == 1:
        flat = [flat[0], flat[0]]
    if len(flat) < 1 or any(d != 1 for d in flat[2:]):
        raise NotSupportedError(f"{name}: only 2-D arrays are supported")
    return max(flat[0], 0), max(flat[1], 0)


@_register("zeros")
def _zeros(args: list, nargout: int) -> list:
    return [np.zeros(_dims("zeros", args))]


@_register("ones")
def _ones(args: list, nargout: int) -> list:
    return [np.ones(_dims("ones", args))]


@_register("eye")
def _eye(args: list, nargout: int) -> list:
    r, c = _dims("eye", args)
    return [np.eye(r, c)]


@_register("linspace")
def _linspace(args: list, nargout: int) -> list:
    _need("linspace", args, 2, 3)
    a, b = _arith(args[0], "linspace"), _arith(args[1], "linspace")
    if a.size != 1 or b.size != 1:
        raise ValidationError("linspace: endpoints must be scalars.")
    n = max(_int(args[2], "linspace"), 0) if len(args) == 3 else 100
    if n == 0:
        return [np.zeros((1, 0))]
    if n == 1:
        return [b.reshape(1, 1).copy()]
    out = np.linspace(a[0, 0], b[0, 0], n)
    out[-1] = b[0, 0]
    return [out.reshape(1, -1)]


@_register("logspace")
def _logspace(args: list, nargout: int) -> list:
    _need("logspace", args, 2, 3)
    lin = _linspace(args, 1)[0]
    return [np.power(10.0, lin)]


@_register("repmat")
def _repmat(args: list, nargout: int) -> list:
    _need("repmat", args, 2, 3)
    reps = _dims("repmat", args[1:])
    return [_on_array(args[0], lambda a: np.tile(a, reps), "repmat")]


@_register("reshape")
def _reshape(args: list, nargout: int) -> list:
    _need("reshape", args, 2, 3)
    total = numel_of(args[0])
    spec = [args[1]] if len(args) == 2 else list(args[1:])
    if len(spec) == 1:
        dims = [_int(_scalar(x), "reshape") for x in _real(spec[0], "reshape").ravel(order="F")]
    else:
        blanks = [k for k, a in enumerate(spec) if isinstance(a, np.ndarray) and a.size == 0]
        dims = [0 if k in blanks else _int(a, "reshape") for k, a in enumerate(spec)]
        if len(blanks) > 1:
            raise ValidationError("reshape: only one dimension can be empty.")
        if blanks:
            known = int(np.prod([d for k, d in enumerate(dims) if k not in blanks]))
            if known == 0 or total % known:
                raise ValidationError("reshape: Size of the empty dimension cannot be inferred.")
            dims[blanks[0]] = total // known
    if len(dims) < 2 or any(d != 1 for d in dims[2:]):
        raise NotSupportedError("reshape: only 2-D arrays are supported")
    r, c = dims[0], dims[1]
    if r * c != total:
        raise ValidationError("reshape: Number of elements must not change.")
    return [_on_array(args[0], lambda a: a.reshape((r, c), order="F").copy(), "reshape")]


@_register("diag")
def _diag(args: list, nargout: int) -> list:
    _need("diag", args, 1, 2)
    x = _arith(args[0], "diag")
    k = _int(args[1], "diag") if len(args) == 2 else 0
    if min(x.shape) == 1:
        return [np.diag(x.ravel(order="F"), k)]
    return [np.diag(x, k).reshape(-1, 1).copy()]


def _make_tri(name: str, fn: Callable) -> None:
    @_register(name)
    def tri(args: list, nargout: int) -> list:
        _need(name, args, 1, 2)
        k = _int(args[1], name) if len(args) == 2 else 0
        return [fn(_arith(args[0], name), k)]


_make_tri("triu", np.triu)
_make_tri("tril", np.tril)


@_register("meshgrid")
def _meshgrid(args: list, nargout: int) -> list:
    _need("meshgrid", args, 1, 2)
    x = _arith(args[0], "meshgrid").ravel(order="F")
    y = _arith(args[-1], "meshgrid").ravel(order="F")
    xx = np.tile(x, (y.size, 1))
    yy = np.tile(y.reshape(-1, 1), (1, x.size))
    return [xx, yy][: max(nargout, 1)]


@_register("horzcat")
def _horzcat(args: list, nargout: int) -> list:
    return [ops.horzcat(args)]


@_register("vertcat")
def _vertcat(args: list, nargout: int) -> list:
    return [ops.vertcat(args)]


# ------------------------------------------------------------- size and type
@_register("size")
def _size(args: list, nargout: int) -> list:
    _need("size", args, 1, 2)
    r, c = size_of(args[0])
    if len(args) == 2:
        d = _int(args[1], "size")
        if d < 1:
            raise ValidationError("size: dimension must be a positive integer.")
        return [_scalar(float((r, c)[d - 1] if d <= 2 else 1))]
    if nargout <= 1:
        return [np.array([[float(r), float(c)]])]
    return [_scalar(float(r)), _scalar(float(c))] + [_scalar(1.0)] * (nargout - 2)


def _query(name: str, fn: Callable[[object], float | bool]) -> None:
    @_register(name)
    def query(args: list, nargout: int) -> list:
        _need(name, args, 1)
        return [_scalar(fn(args[0]))]


def _is_numeric(v: object) -> bool:
    return isinstance(v, np.ndarray) and v.dtype != np.bool_


def _is_real(v: object) -> bool:
    return (isinstance(v, np.ndarray) and v.dtype.kind != "c") or isinstance(v, CharArray)


def _length(v: object) -> float:
    r, c = size_of(v)
    return 0.0 if r * c == 0 else float(max(r, c))


for _name, _fn in (
    ("numel", lambda v: float(numel_of(v))),
    ("length", _length),
    ("ndims", lambda v: 2.0),
    ("isempty", lambda v: numel_of(v) == 0),
    ("isscalar", lambda v: numel_of(v) == 1),
    ("isvector", lambda v: min(size_of(v)) == 1),
    ("isrow", lambda v: size_of(v)[0] == 1),
    ("iscolumn", lambda v: size_of(v)[1] == 1),
    ("ismatrix", lambda v: True),
    ("issquare", lambda v: size_of(v)[0] == size_of(v)[1]),
    ("isnumeric", _is_numeric),
    ("isreal", _is_real),
    ("iscomplex", lambda v: isinstance(v, np.ndarray) and v.dtype.kind == "c"),
    ("islogical", lambda v: isinstance(v, np.ndarray) and v.dtype == np.bool_),
    ("ischar", lambda v: isinstance(v, CharArray)),
    ("iscell", lambda v: isinstance(v, CellArray)),
    ("isstruct", lambda v: isinstance(v, StructValue)),
    ("is_function_handle", lambda v: isinstance(v, FunctionHandle)),
):
    _query(_name, _fn)


@_register("class")
def _class(args: list, nargout: int) -> list:
    _need("class", args, 1)
    return [CharArray.from_str(class_of(args[0]))]


@_register("isa")
def _isa(args: list, nargout: int) -> list:
    _need("isa", args, 2)
    want = _text(args[1], "isa")
    got = class_of(args[0])
    ok = got == want or (want == "numeric" and _is_numeric(args[0])) or (
        want == "float" and got == "double")
    return [_scalar(ok)]


@_register("double")
def _double(args: list, nargout: int) -> list:
    _need("double", args, 1)
    return [_arith(args[0], "double").copy()]


@_register("logical")
def _logical(args: list, nargout: int) -> list:
    _need("logical", args, 1)
    x = _arith(args[0], "logical")
    if np.isnan(x).any():
        raise ValidationError("logical: NaN's cannot be converted to logicals.")
    return [x != 0]


@_register("char")
def _char(args: list, nargout: int) -> list:
    _need("char", args, 1)
    if isinstance(args[0], CharArray):
        return [args[0]]
    return [CharArray(ops._as_char(args[0]))]


@_register("isequal")
def _isequal(args: list, nargout: int) -> list:
    _need("isequal", args, 2, 1000)
    return [_scalar(all(values_equal(args[0], other) for other in args[1:]))]


# --------------------------------------------------------- elementwise math
def _per_part(fn: Callable) -> Callable:
    def apply(x: np.ndarray) -> np.ndarray:
        if x.dtype.kind == "c":
            return fn(x.real) + 1j * fn(x.imag)
        return fn(x)

    return apply


def _round_half_away(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def _asin(x: np.ndarray) -> np.ndarray:
    if x.dtype.kind == "c" or not np.any(np.abs(x) > 1):
        return np.arcsin(x)
    big = np.arccosh(np.maximum(np.abs(x), 1.0))
    inside = np.arcsin(np.clip(x, -1.0, 1.0)).astype(np.complex128)
    return np.where(x > 1, math.pi / 2 - 1j * big,
                    np.where(x < -1, -math.pi / 2 + 1j * big, inside))


def _acos(x: np.ndarray) -> np.ndarray:
    if x.dtype.kind == "c" or not np.any(np.abs(x) > 1):
        return np.arccos(x)
    big = np.arccosh(np.maximum(np.abs(x), 1.0))
    inside = np.arccos(np.clip(x, -1.0, 1.0)).astype(np.complex128)
    return np.where(x > 1, 1j * big, np.where(x < -1, math.pi - 1j * big, inside))


def _sign(x: np.ndarray) -> np.ndarray:
    if x.dtype.kind != "c":
        return np.sign(x)
    mag = np.abs(x)
    return np.where(mag == 0, 0, x / np.where(mag == 0, 1, mag))


_UNARY: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "abs": np.abs, "sqrt": np.emath.sqrt, "exp": np.exp, "log": np.emath.log,
    "log2": np.emath.log2, "log10": np.emath.log10, "sin": np.sin, "cos": np.cos,
    "tan": np.tan, "asin": _asin, "acos": _acos, "atan": np.arctan, "sinh": np.sinh,
    "cosh": np.cosh, "tanh": np.tanh, "floor": _per_part(np.floor), "ceil": _per_part(np.ceil),
    "round": _per_part(_round_half_away), "fix": _per_part(np.trunc), "sign": _sign,
    "real": np.real, "imag": np.imag, "conj": np.conj, "angle": np.angle,
}
_PREDICATES: dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "isnan": np.isnan, "isinf": np.isinf, "isfinite": np.isfinite,
}


def _make_unary(name: str, fn: Callable, predicate: bool) -> None:
    @_register(name)
    def unary(args: list, nargout: int) -> list:
        _need(name, args, 1)
        x = _arith(args[0], name)
        with np.errstate(all="ignore"):
            out = np.array(fn(x))
        if not predicate and out.dtype.kind == "c" and not np.any(out.imag):
            out = out.real.copy()
        return [out.astype(np.float64) if out.dtype.kind in "iu" else out]


for _name, _fn in _UNARY.items():
    _make_unary(_name, _fn, predicate=False)
for _name, _fn in _PREDICATES.items():
    _make_unary(_name, _fn, predicate=True)


def _mod(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.where(y == 0, x, np.mod(x, y))


_BINARY: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "atan2": np.arctan2, "hypot": np.hypot, "mod": _mod, "rem": np.fmod,
}


def _make_binary(name: str, fn: Callable) -> None:
    @_register(name)
    def binary(args: list, nargout: int) -> list:
        _need(name, args, 2)
        x, y = _real(args[0], name), _real(args[1], name)
        try:
            with np.errstate(all="ignore"):
                return [np.asarray(fn(x, y), dtype=np.float64)]
        except ValueError as exc:
            raise DimensionError(f"{name}: Arrays have incompatible sizes.") from exc


for _name, _fn in _BINARY.items():
    _make_binary(_name, _fn)


# ---------------------------------------------------------------- reductions
def _axis(x: np.ndarray, dim: int | None) -> int:
    if dim is None:
        return 1 if x.shape[0] == 1 else 0
    if dim not in (1, 2):
        raise ValidationError("dimension must be 1 or 2 (arrays are 2-D).")
    return dim - 1


def _xdim(name: str, args: list, high: int = 2) -> tuple[np.ndarray, int | None]:
    _need(name, args, 1, high)
    x = _arith(args[0], name)
    dim = _int(args[1], name) if len(args) > 1 else None
    return x, dim


def _make_reduction(name: str, fn: Callable, empty: float | bool) -> None:
    @_register(name)
    def reduction(args: list, nargout: int) -> list:
        x, dim = _xdim(name, args)
        if x.shape == (0, 0) and dim is None:
            return [_scalar(empty)]
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return [np.asarray(fn(x, axis=_axis(x, dim), keepdims=True))]


_make_reduction("sum", np.sum, 0.0)
_make_reduction("prod", np.prod, 1.0)
_make_reduction("mean", np.mean, math.nan)
_make_reduction("any", lambda x, **kw: np.any(x != 0, **kw), False)
_make_reduction("all", lambda x, **kw: np.all(x != 0, **kw), True)


def _make_cumulative(name: str, fn: Callable) -> None:
    @_register(name)
    def cumulative(args: list, nargout: int) -> list:
        x, dim = _xdim(name, args)
        if x.size == 0:
            return [x.copy()]
        return [fn(x, axis=_axis(x, dim))]


_make_cumulative("cumsum", np.cumsum)
_make_cumulative("cumprod", np.cumprod)


def _make_minmax(name: str, is_max: bool) -> None:
    pick = np.fmax if is_max else np.fmin

    @_register(name)
    def minmax(args: list, nargout: int) -> list:
        _need(name, args, 1, 3)
        x = _real(args[0], name)
        if len(args) == 2:
            if nargout > 1:
                raise ValidationError(f"{name}: two-argument form has one output.")
            y = _real(args[1], name)
            try:
                return [np.asarray(pick(x, y), dtype=np.float64)]
            except ValueError as exc:
                raise DimensionError(f"{name}: Arrays have incompatible sizes.") from exc
        dim = _int(args[2], name) if len(args) == 3 else None
        if len(args) == 3 and numel_of(args[1]) != 0:
            raise ValidationError(f"{name}: second argument must be [] with a dimension.")
        if x.size == 0:
            return [empty_double(), empty_double()][: max(nargout, 1)]
        axis = _axis(x, dim)
        data = x.astype(np.float64) if x.dtype == np.bool_ else x
        nan = np.isnan(data)
        fill = -np.inf if is_max else np.inf
        filled = np.where(nan, fill, data)
        idx = (np.argmax if is_max else np.argmin)(filled, axis=axis)
        # NaN entries are ignored; an all-NaN slice picks position 1 and yields NaN
        best = np.take_along_axis(data, np.expand_dims(idx, axis), axis=axis)
        index = (np.expand_dims(idx, axis) + 1).astype(np.float64)
        return [best, index][: max(nargout, 1)]


_make_minmax("max", True)
_make_minmax("min", False)


def _argsort(v: np.ndarray, descend: bool) -> np.ndarray:
    nan = np.isnan(v)
    good = np.flatnonzero(~nan)
    bad = np.flatnonzero(nan)
    order = good[np.argsort(-v[good] if descend else v[good], kind="stable")]
    return np.concatenate([bad, order]) if descend else np.concatenate([order, bad])


@_register("sort")
def _sort(args: list, nargout: int) -> list:
    _need("sort", args, 1, 3)
    x = _real(args[0], "sort")
    dim, descend = None, False
    for extra in args[1:]:
        if isinstance(extra, CharArray):
            mode = _text(extra, "sort")
            if mode not in ("ascend", "descend"):
                raise ValidationError("sort: mode must be 'ascend' or 'descend'.")
            descend = mode == "descend"
        else:
            dim = _int(extra, "sort")
    if x.size == 0:
        return [x.copy(), x.copy()][: max(nargout, 1)]
    axis = _axis(x, dim)
    moved = np.moveaxis(x.astype(np.float64), axis, 0)
    out = np.empty_like(moved)
    idx = np.empty_like(moved)
    for k in range(moved.shape[1]):
        order = _argsort(moved[:, k], descend)
        out[:, k] = moved[order, k]
        idx[:, k] = order + 1
    return [np.moveaxis(out, 0, axis), np.moveaxis(idx, 0, axis)][: max(nargout, 1)]


@_register("find")
def _find(args: list, nargout: int) -> list:
    _need("find", args, 1, 2)
    x = _arith(args[0], "find")
    found = np.flatnonzero(x.ravel(order="F") != 0)
    if len(args) == 2:
        found = found[: max(_int(args[1], "find"), 0)]
    r = x.shape[0]
    if nargout >= 2:
        parts = [(found % r + 1).astype(np.float64), (found // r + 1).astype(np.float64)]
        vals = x.ravel(order="F")[found]
        shaped = [_find_shape(p, x) for p in parts + ([vals] if nargout >= 3 else [])]
        return shaped[:nargout]
    return [_find_shape((found + 1).astype(np.float64), x)]


def _find_shape(values: np.ndarray, x: np.ndarray) -> np.ndarray:
    if x.shape == (0, 0) or (x.shape == (1, 1) and values.size == 0):
        return np.zeros((0, 0))
    if x.shape[0] == 1 and x.shape[1] != 1:
        return values.reshape(1, -1)
    return values.reshape(-1, 1)


@_register("diff")
def _diff(args: list, nargout: int) -> list:
    x, order = _xdim("diff", args)  # the second argument is the order
    k = 1 if order is None else order
    if x.size <= 1:
        return [empty_double()]
    out = x.astype(np.float64) if x.dtype == np.bool_ else x
    axis = 1 if out.shape[0] == 1 else 0
    for _ in range(max(k, 0)):
        if out.shape[axis] <= 1:
            return [empty_double()]
        out = np.diff(out, axis=axis)
    return [out]


@_register("fliplr")
def _fliplr(args: list, nargout: int) -> list:
    _need("fliplr", args, 1)
    return [_on_array(args[0], lambda a: a[:, ::-1].copy(), "fliplr")]


@_register("flipud")
def _flipud(args: list, nargout: int) -> list:
    _need("flipud", args, 1)
    return [_on_array(args[0], lambda a: a[::-1, :].copy(), "flipud")]


# ---------------------------------------------------------------- formatting
_SPEC = re.compile(r"%(%|([-+ 0#]*)(\d+)?(?:\.(\d+))?([diouxXfFeEgGcs]))")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
            "\\": "\\", '"': '"', "'": "'"}


def _unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in _ESCAPES:
            out.append(_ESCAPES[text[i + 1]])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _parse_format(fmt: str) -> list[tuple]:
    segments: list[tuple] = []
    pos = 0
    for m in _SPEC.finditer(fmt):
        if m.start() > pos:
            segments.append(("lit", fmt[pos:m.start()]))
        if m.group(1) == "%":
            segments.append(("lit", "%"))
        else:
            segments.append(("conv", m.group(2) or "", m.group(3) or "", m.group(4), m.group(5)))
        pos = m.end()
    if pos < len(fmt):
        segments.append(("lit", fmt[pos:]))
    return segments


def _format_items(args: Sequence, name: str) -> deque:
    items: deque = deque()
    for a in args:
        if isinstance(a, CharArray):
            items.append("".join(a.data.ravel(order="F")) if a.data.size else "")
        elif isinstance(a, np.ndarray):
            for x in a.ravel(order="F"):
                if a.dtype.kind == "c":
                    items.extend((float(x.real), float(x.imag)))
                else:
                    items.append(float(x))
        else:
            raise ValidationError(f"{name}: unsupported argument type {class_of(a)}.")
    return items


def _padded(flags: str, width: str, text: str) -> str:
    return ("%" + ("-" if "-" in flags else "") + width + "s") % text


def _convert(segment: tuple, items: deque) -> str:
    _, flags, width, prec, conv = segment
    item = items.popleft()
    if isinstance(item, str):
        if conv == "s":
            return ("%" + flags + width + (f".{prec}" if prec is not None else "") + "s") % item
        if item == "":
            return ""
        if conv == "c":
            if item[1:]:
                items.appendleft(item[1:])
            return _padded(flags, width, item[0])
        items.extendleft(float(ord(ch)) for ch in reversed(item))
        item = items.popleft()
    x = item
    if not math.isfinite(x):
        return _padded(flags, width, "NaN" if math.isnan(x) else ("Inf" if x > 0 else "-Inf"))
    whole = x == int(x)
    precision = f".{prec}" if prec is not None else ""
    if conv in "sc":
        if whole and 0 <= x < 0x110000:
            return _padded(flags, width, chr(int(x)))
        return ("%" + flags + width + "e") % x
    if conv in "diouxX":
        if whole:
            return ("%" + flags + width + precision + ("d" if conv == "i" else conv)) % int(x)
        return ("%" + flags + width + "e") % x
    return ("%" + flags + width + precision + conv) % x


def format_text(fmt: str, args: Sequence, name: str = "sprintf") -> str:
    """MATLAB ``sprintf``: the format is reused until all arguments are consumed."""
    segments = _parse_format(_unescape(fmt))
    if not any(s[0] == "conv" for s in segments):
        return "".join(s[1] for s in segments)
    items = _format_items(args, name)
    had_items = bool(items)
    out: list[str] = []
    while True:
        for seg in segments:
            if seg[0] == "lit":
                out.append(seg[1])
            elif items:
                out.append(_convert(seg, items))
            elif had_items:
                return "".join(out)
        if not items:
            return "".join(out)


def _num2str_scalar(x: complex, fmt: str | None, precision: int | None) -> str:
    if isinstance(x, complex) and x.imag != 0:
        im = _num2str_scalar(abs(x.imag), fmt, precision)
        return f"{_num2str_scalar(x.real, fmt, precision)}{'-' if x.imag < 0 else '+'}{im}i"
    x = float(x.real if isinstance(x, complex) else x)
    if fmt is not None:
        return format_text(fmt, [_scalar(x)])
    if not math.isfinite(x):
        return "NaN" if math.isnan(x) else ("Inf" if x > 0 else "-Inf")
    if precision is not None:
        return f"{x:.{precision}g}"
    if x == int(x):
        return str(int(x))
    digits = max(int(math.floor(math.log10(abs(x)))) + 5, 5)
    return f"{x:.{digits}g}"


@_register("num2str")
def _num2str(args: list, nargout: int) -> list:
    _need("num2str", args, 1, 2)
    if isinstance(args[0], CharArray):
        return [args[0]]
    x = _arith(args[0], "num2str")
    fmt = precision = None
    if len(args) == 2:
        if isinstance(args[1], CharArray):
            fmt = _text(args[1], "num2str")
        else:
            precision = _int(args[1], "num2str")
    if x.size == 0:
        return [CharArray.from_str("")]
    rows = ["  ".join(_num2str_scalar(v, fmt, precision) for v in row) for row in x]
    width = max(len(r) for r in rows)
    padded = [r.ljust(width) for r in rows]
    if len(padded) == 1:
        return [CharArray.from_str(padded[0])]
    return [CharArray(np.array([list(r) for r in padded], dtype="<U1"))]


@_register("sprintf")
def _sprintf(args: list, nargout: int) -> list:
    _need("sprintf", args, 1, 1000)
    return [CharArray.from_str(format_text(_text(args[0], "sprintf"), args[1:]))]


# ------------------------------------------------------------ bound builtins
_IDENTIFIER = re.compile(r"[A-Za-z]\w*(:[A-Za-z_]\w*)+\Z")


def _linalg_matrix(v: object, name: str) -> np.ndarray:
    x = _arith(v, name)
    if x.dtype.kind == "c":
        raise NotSupportedError(f"{name}: complex matrices are not supported yet")
    return x


def core_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The core builtins bound to ``interp`` (its host receives output and warnings)."""
    table: dict[str, Builtin] = dict(_PURE)
    host = interp.host

    def disp(args: list, nargout: int) -> list:
        _need("disp", args, 1)
        host.write(format_disp(args[0]))
        return []

    def fprintf(args: list, nargout: int) -> list:
        _need("fprintf", args, 1, 1000)
        rest = list(args)
        if isinstance(rest[0], np.ndarray) and len(rest) > 1:
            rest = rest[1:]  # file id: everything goes to the host
        host.write(format_text(_text(rest[0], "fprintf"), rest[1:], "fprintf"))
        return []

    def error(args: list, nargout: int) -> list:
        _need("error", args, 1, 1000)
        first = _text(args[0], "error")
        ident = ""
        if len(args) > 1 and _IDENTIFIER.match(first):
            ident, rest = first, args[1:]
            message = format_text(_text(rest[0], "error"), rest[1:], "error")
        elif len(args) > 1:
            message = format_text(first, args[1:], "error")
        else:
            message = first
        raise UserError(message, ident)

    def warning(args: list, nargout: int) -> list:
        _need("warning", args, 1, 1000)
        first = _text(args[0], "warning")
        if first in ("on", "off", "error", "query"):
            return []
        ident = ""
        rest = list(args)
        if len(rest) > 1 and _IDENTIFIER.match(first):
            ident, rest = first, rest[1:]
        message = format_text(_text(rest[0], "warning"), rest[1:], "warning")
        host.diagnostic(Diagnostic(severity="warning", code=ident or "W_USER", message=message))
        return []

    def forward(diagnostics: Sequence[Diagnostic]) -> None:
        for d in diagnostics:
            host.diagnostic(d)

    def inv(args: list, nargout: int) -> list:
        _need("inv", args, 1)
        result = linalg.inv(_linalg_matrix(args[0], "inv"))
        forward(result.diagnostics)
        return [result.value]

    def scalar_fn(name: str, fn: Callable) -> Builtin:
        def call(args: list, nargout: int) -> list:
            _need(name, args, 1)
            return [_scalar(fn(_linalg_matrix(args[0], name)))]

        return call

    def rank(args: list, nargout: int) -> list:
        _need("rank", args, 1, 2)
        tol = float(_real(args[1], "rank")[0, 0]) if len(args) == 2 else None
        return [_scalar(float(linalg.rank(_linalg_matrix(args[0], "rank"), tol)))]

    def cond(args: list, nargout: int) -> list:
        _need("cond", args, 1, 2)
        p = _norm_kind(args[1]) if len(args) == 2 else 2
        return [_scalar(float(linalg.cond(_linalg_matrix(args[0], "cond"), p)))]

    def norm(args: list, nargout: int) -> list:
        _need("norm", args, 1, 2)
        p = _norm_kind(args[1]) if len(args) == 2 else 2
        x = _linalg_matrix(args[0], "norm")
        if x.size and 1 in x.shape:  # vector: p-norm of the elements
            if p == "fro":
                p = 2
            if p < 1:
                raise ValidationError("norm: p of a vector p-norm must be at least 1.")
            return [_scalar(float(np.linalg.norm(x.ravel(order="F"), ord=p)))]
        return [_scalar(float(linalg.norm(x, p)))]

    def dot(args: list, nargout: int) -> list:
        _need("dot", args, 2)
        a, b = (_linalg_matrix(a, "dot").ravel(order="F") for a in args)
        if a.size != b.size:
            raise DimensionError("dot: vectors must have the same number of elements.")
        return [_scalar(float(linalg.dot(a, b)))]

    def cross(args: list, nargout: int) -> list:
        _need("cross", args, 2)
        a = _linalg_matrix(args[0], "cross")
        b = _linalg_matrix(args[1], "cross")
        if a.size != 3 or b.size != 3:
            raise ValidationError("cross: inputs must have 3 elements.")
        out = linalg.cross(a.ravel(order="F"), b.ravel(order="F"))
        return [out.reshape(a.shape)]

    table.update({
        "disp": disp, "fprintf": fprintf, "error": error, "warning": warning, "inv": inv,
        "det": scalar_fn("det", linalg.det), "trace": scalar_fn("trace", linalg.trace),
        "rcond": scalar_fn("rcond", linalg.rcond), "rank": rank, "cond": cond, "norm": norm,
        "dot": dot, "cross": cross,
    })
    return table


def _norm_kind(v: object) -> float | str:
    if isinstance(v, CharArray):
        text = _text(v, "norm")
        if text.lower() == "fro":
            return "fro"
        if text.lower() == "inf":
            return math.inf
        raise ValidationError(f"norm: unsupported norm {text!r}.")
    x = _real(v, "norm")
    if x.size != 1:
        raise ValidationError("norm: the norm type must be a scalar.")
    return float(x[0, 0])


def install_core(interp: Interpreter) -> None:
    """Register the core builtins on ``interp`` (core names overwrite entries of that name)."""
    interp.functions.update(core_functions(interp))


__all__ = ["UserError", "core_functions", "format_text", "install_core"]
