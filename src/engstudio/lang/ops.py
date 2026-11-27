"""Operators, ranges and concatenation on interpreter values (T3.4a). Pure functions.

Semantics follow MATLAB documentation unless noted:

* implicit expansion (broadcasting) for elementwise operators; size mismatch raises
  ``DimensionError``;
* logical operands are converted to double for arithmetic; char operands act as character codes;
* complex results whose imaginary parts are all zero are narrowed to real;
* ordering comparisons (``< <= > >=``) use real parts of complex operands;
* ``a:b`` ranges use a tolerance so ``0:0.1:0.3`` has four elements.

Differences from MATLAB (v1): range operands must be finite scalars; ``A\\B`` and ``B/A`` use
``engine.linalg.solve`` for square real ``A`` (a singular matrix raises ``SingularMatrixError``
instead of warning and returning Inf; an ill-conditioned one appends a warning ``Diagnostic``)
and least squares (minimum-norm) for non-square ``A``; ``A^n`` needs a square real matrix and an
integer ``n`` (negative via ``engine.linalg.inv``); complex matrix division/inversion, non-integer
matrix powers and ``scalar^matrix`` are not supported; concatenating cells with non-cells,
structs or function handles is not supported.
"""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, Sequence

import numpy as np

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import DimensionError, NotSupportedError, ValidationError
from engstudio.engine import linalg
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
)

_MAX_RANGE = 50_000_000


# ------------------------------------------------------------------ helpers
def _num(v: object, op: str) -> np.ndarray:
    if isinstance(v, np.ndarray):
        return v
    if isinstance(v, CharArray):
        return v.codes()
    raise ValidationError(f"Operator '{op}' is undefined for {class_of(v)} operands.")


def _arith(v: object, op: str) -> np.ndarray:
    x = _num(v, op)
    return x.astype(np.float64) if x.dtype == np.bool_ else x


def _ew(fn: Callable[..., np.ndarray], *args: np.ndarray) -> np.ndarray:
    try:
        with np.errstate(all="ignore"):
            return fn(*args)
    except ValueError as exc:
        raise DimensionError("Arrays have incompatible sizes for this operation.") from exc


def _narrow(z: np.ndarray) -> np.ndarray:
    if z.dtype.kind == "c" and not np.any(z.imag):
        return z.real.copy()
    return z


def _logical(v: object, op: str) -> np.ndarray:
    x = _num(v, op)
    if x.dtype.kind in "fc" and np.isnan(x).any():
        raise ValidationError("NaN's cannot be converted to logicals.")
    return x != 0


def _power(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if (
        x.dtype.kind != "c"
        and y.dtype.kind != "c"
        and bool(np.any(x < 0))
        and bool(np.any(y != np.round(y)))
    ):
        x = x.astype(np.complex128)
    return np.power(x, y)


# ---------------------------------------------------------------- binary ops
def _elementwise(fn: Callable[..., np.ndarray], swap: bool = False):
    def handler(op: str, a: object, b: object) -> np.ndarray:
        x, y = _arith(a, op), _arith(b, op)
        return _narrow(_ew(fn, y, x) if swap else _ew(fn, x, y))

    return handler


def _mtimes(op: str, a: object, b: object) -> np.ndarray:
    x, y = _arith(a, op), _arith(b, op)
    if x.size == 1 or y.size == 1:
        return _narrow(_ew(np.multiply, x, y))
    if x.shape[1] != y.shape[0]:
        raise DimensionError(
            "Incorrect dimensions for matrix multiplication. Check that the number of columns "
            "in the first matrix matches the number of rows in the second matrix. To perform "
            "elementwise multiplication, use '.*'."
        )
    return _narrow(_ew(np.matmul, x, y))


def _real_only(op: str, *arrays: np.ndarray) -> None:
    if any(a.dtype.kind == "c" for a in arrays):
        raise NotSupportedError(f"complex operands are not supported for matrix '{op}' yet")


def _solve(a: np.ndarray, b: np.ndarray, diag: list[Diagnostic] | None) -> np.ndarray:
    """Solve ``a x = b``: LU for square ``a``, minimum-norm least squares otherwise."""
    if a.shape[0] != b.shape[0]:
        raise DimensionError("Matrix dimensions must agree for this division.")
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[1], b.shape[1]))
    if a.shape[0] == a.shape[1]:
        result = linalg.solve(a, b)
        if diag is not None:
            diag.extend(result.diagnostics)
        return result.x
    return np.linalg.lstsq(a, b, rcond=None)[0]


def _mrdivide(op: str, a: object, b: object, diag: list[Diagnostic] | None) -> np.ndarray:
    x, y = _arith(a, op), _arith(b, op)
    if y.size == 1:
        return _narrow(_ew(np.divide, x, y))
    _real_only(op, x, y)
    return _solve(y.T, x.T, diag).T


def _mldivide(op: str, a: object, b: object, diag: list[Diagnostic] | None) -> np.ndarray:
    x, y = _arith(a, op), _arith(b, op)
    if x.size == 1:
        return _narrow(_ew(np.divide, y, x))
    _real_only(op, x, y)
    return _solve(x, y, diag)


def _mpower(op: str, a: object, b: object, diag: list[Diagnostic] | None) -> np.ndarray:
    x, y = _arith(a, op), _arith(b, op)
    if x.size == 1 and y.size == 1:
        return _narrow(_ew(_power, x, y))
    if y.size != 1 or x.shape[0] != x.shape[1]:
        raise DimensionError(
            "Incorrect dimensions for raising a matrix to a power. Check that the matrix is "
            "square and the power is a scalar. To perform elementwise matrix powers, use '.^'."
        )
    p = y.item()
    if isinstance(p, complex) or not np.isfinite(p) or p != round(p):
        raise NotSupportedError("matrix power is supported only for integer powers")
    n = int(p)
    if n < 0:
        _real_only(op, x)
        result = linalg.inv(x)
        if diag is not None:
            diag.extend(result.diagnostics)
        x, n = result.value, -n
    return _narrow(np.linalg.matrix_power(x, n))


_MATRIX_OPS = {"/": _mrdivide, "\\": _mldivide, "^": _mpower}


def _compare(fn: Callable[..., np.ndarray], ordering: bool):
    def handler(op: str, a: object, b: object) -> np.ndarray:
        x, y = _num(a, op), _num(b, op)
        if ordering:
            x, y = np.real(x), np.real(y)
        return _ew(fn, x, y)

    return handler


def _logic(fn: Callable[..., np.ndarray]):
    def handler(op: str, a: object, b: object) -> np.ndarray:
        return _ew(fn, _logical(a, op), _logical(b, op))

    return handler


_BINARY: dict[str, Callable[[str, object, object], np.ndarray]] = {
    "+": _elementwise(np.add),
    "-": _elementwise(np.subtract),
    ".*": _elementwise(np.multiply),
    "./": _elementwise(np.divide),
    ".\\": _elementwise(np.divide, swap=True),
    ".^": _elementwise(_power),
    "*": _mtimes,
    "==": _compare(np.equal, False),
    "~=": _compare(np.not_equal, False),
    "<": _compare(np.less, True),
    "<=": _compare(np.less_equal, True),
    ">": _compare(np.greater, True),
    ">=": _compare(np.greater_equal, True),
    "&": _logic(np.logical_and),
    "|": _logic(np.logical_or),
}


_S11 = (1, 1)
_F64 = np.dtype(np.float64)
_SCALAR_ARITH = {"+": operator.add, "-": operator.sub, ".*": operator.mul,
                 "*": operator.mul}
_SCALAR_CMP = {"==": operator.eq, "~=": operator.ne, "<": operator.lt, "<=": operator.le,
               ">": operator.gt, ">=": operator.ge}


def _scalar_op(op: str, x: float, y: float) -> np.ndarray | None:
    """Fast path for two real double scalars (ODE right-hand sides, loops). Returns None when
    the general code must decide (division by zero, overflow, complex powers, logic ops), so
    results are always identical to the general path (IEEE double arithmetic either way)."""
    fn = _SCALAR_ARITH.get(op)
    if fn is not None:
        return np.array([[fn(x, y)]])
    cmp = _SCALAR_CMP.get(op)
    if cmp is not None:
        return np.array([[cmp(x, y)]])
    if op in ("/", "./") and y != 0:
        return np.array([[x / y]])
    if op in ("\\", ".\\") and x != 0:
        return np.array([[y / x]])
    if op in ("^", ".^") and math.isfinite(x) and math.isfinite(y) and (x > 0 or y == round(y)):
        try:
            r = x ** y
        except (OverflowError, ZeroDivisionError):
            return None
        return np.array([[r]]) if isinstance(r, float) else None
    return None


def binary_op(
    op: str, a: object, b: object, diagnostics: list[Diagnostic] | None = None
) -> np.ndarray:
    """Apply a binary operator (every ``lang.ast.BINARY_OPS`` entry except ``&&``/``||``).

    Warnings from the linear-algebra routines (ill-conditioning) are appended to
    ``diagnostics`` when a list is given.
    """
    if (type(a) is np.ndarray and type(b) is np.ndarray and a.shape == _S11 == b.shape
            and a.dtype == _F64 and b.dtype == _F64):
        fast = _scalar_op(op, float(a[0, 0]), float(b[0, 0]))
        if fast is not None:
            return fast
    if op in ("&&", "||"):
        raise ValidationError(f"'{op}' short-circuits and is evaluated by the interpreter")
    if op in _MATRIX_OPS:
        return _MATRIX_OPS[op](op, a, b, diagnostics)
    handler = _BINARY.get(op)
    if handler is None:
        raise ValidationError(f"unknown binary operator {op!r}")
    return handler(op, a, b)


def to_logical_scalar(v: object, op: str) -> bool:
    """Operand of ``&&``/``||``: must be a non-empty scalar convertible to logical."""
    x = _num(v, op)
    if x.size != 1:
        raise ValidationError(
            f"Operands to the {op} operator must be convertible to logical scalar values."
        )
    return bool(_logical(x, op).item())


# ------------------------------------------------------------ unary/transpose
def unary_op(op: str, a: object) -> np.ndarray:
    if op == "-":
        return -_arith(a, op)
    if op == "+":
        return _arith(a, op)
    if op == "~":
        return ~_logical(a, op)
    raise ValidationError(f"unknown unary operator {op!r}")


def transpose(a: object, conjugate: bool) -> object:
    """``a'`` (``conjugate=True``) or ``a.'``. Works on numeric, char and cell values."""
    if isinstance(a, np.ndarray):
        return a.conj().T if conjugate and a.dtype.kind == "c" else a.T
    if isinstance(a, CharArray):
        return CharArray(a.data.T)
    if isinstance(a, CellArray):
        return CellArray(a.data.T)
    raise ValidationError(f"Operator \"'\" is undefined for {class_of(a)} operands.")


# -------------------------------------------------------------------- ranges
def _range_arg(v: object) -> float | None:
    x = _num(v, ":")
    if x.size == 0:
        return None
    if x.size != 1:
        raise ValidationError("Colon operands must be scalars.")
    val = float(np.real(x.item()))
    if not np.isfinite(val):
        raise ValidationError("Colon operands must be finite.")
    return val


def colon_range(start: object, step: object | None, stop: object) -> np.ndarray:
    """``start:step:stop`` (``step=None`` means 1). Returns a 1-by-n row; n may be 0."""
    s, e = _range_arg(start), _range_arg(stop)
    st = 1.0 if step is None else _range_arg(step)
    if s is None or e is None or st is None:
        return np.zeros((1, 0))
    if st == 0 or (st > 0 and s > e) or (st < 0 and s < e):
        return np.zeros((1, 0))
    q = (e - s) / st
    tol = 4 * np.finfo(float).eps * max(abs(s), abs(e), abs(st)) / abs(st)
    count = int(np.floor(q + tol)) + 1
    if count > _MAX_RANGE:
        raise ValidationError("Maximum variable size allowed by the program is exceeded.")
    out = s + st * np.arange(count, dtype=np.float64)
    if st > 0:
        out[-1] = min(out[-1], e)
    else:
        out[-1] = max(out[-1], e)
    return out.reshape(1, -1)


# ------------------------------------------------------------- concatenation
def _is_00(v: object) -> bool:
    return isinstance(v, (np.ndarray, CharArray, CellArray)) and tuple(v.shape) == (0, 0)


def _shape(v: object) -> tuple[int, int]:
    return tuple(v.shape)  # type: ignore[union-attr,return-value]


def _concat(values: Sequence[object], axis: int) -> object:
    values = list(values)
    for v in values:
        if isinstance(v, (StructValue, FunctionHandle)):
            raise NotSupportedError(f"concatenation of {class_of(v)} values is not supported")
    items = [v for v in values if not _is_00(v)]
    if not items:
        if any(isinstance(v, CharArray) for v in values):
            return CharArray(np.empty((0, 0), dtype="<U1"))
        if any(isinstance(v, CellArray) for v in values):
            return CellArray.empty(0, 0)
        return empty_double()
    if any(isinstance(v, CellArray) for v in items):
        if not all(isinstance(v, CellArray) for v in items):
            raise NotSupportedError("concatenating cell arrays with other types is not supported")
        arrays = [v.data for v in items]  # type: ignore[union-attr]
        wrap = CellArray
    elif any(isinstance(v, CharArray) for v in items):
        arrays = [_as_char(v) for v in items]
        wrap = CharArray
    else:
        arrays = _numeric_common([v for v in items if isinstance(v, np.ndarray)])
        wrap = None
    first = arrays[0].shape
    other = 0 if axis == 1 else 1  # dimension that must agree
    for arr in arrays[1:]:
        if arr.shape[other] != first[other]:
            kind = "Horizontal" if axis == 1 else "Vertical"
            raise DimensionError(
                f"{kind} dimensions mismatch ({first[0]}x{first[1]} vs "
                f"{arr.shape[0]}x{arr.shape[1]})"
            )
    out = np.concatenate(arrays, axis=axis)
    return out if wrap is None else wrap(out)


def _numeric_common(arrays: list[np.ndarray]) -> list[np.ndarray]:
    if any(a.dtype.kind == "c" for a in arrays):
        dtype = np.complex128
    elif any(a.dtype.kind == "f" for a in arrays):
        dtype = np.float64
    else:
        dtype = np.bool_
    return [a.astype(dtype, copy=False) for a in arrays]


def _as_char(v: object) -> np.ndarray:
    if isinstance(v, CharArray):
        return v.data
    x = _num(v, "[]")
    if x.dtype.kind == "c" or not np.all(x == np.round(x)) or np.any(x < 0) or np.any(x > 0x10FFFF):
        raise ValidationError("numbers concatenated with char must be valid character codes")
    flat = [chr(int(c)) for c in x.ravel()]
    return np.array(flat, dtype="<U1").reshape(x.shape)


def horzcat(values: Sequence[object]) -> object:
    """``[a, b, ...]``. 0-by-0 operands are skipped, as in MATLAB."""
    return _concat(values, axis=1)


def vertcat(values: Sequence[object]) -> object:
    """``[a; b; ...]``."""
    return _concat(values, axis=0)


def build_matrix(rows: Sequence[Sequence[object]]) -> object:
    """Matrix literal ``[r1; r2; ...]`` where each row is a sequence of evaluated elements."""
    if not rows:
        return empty_double()
    fast = _build_double(rows)
    if fast is not None:
        return fast
    return vertcat([horzcat(r) for r in rows])


def _build_double(rows: Sequence[Sequence[object]]) -> np.ndarray | None:
    """Fast path for literals made only of non-empty real double arrays with matching sizes
    (e.g. ``[y(2); -k*y(1)]``); anything else (empty, char, logical, cells, mismatched
    sizes -> the general code and its error messages) returns None."""
    built = []
    for row in rows:
        if not row:
            return None
        for e in row:
            if type(e) is not np.ndarray or e.dtype != _F64 or e.size == 0 or e.ndim != 2:
                return None
        h = row[0].shape[0]
        if any(e.shape[0] != h for e in row):
            return None
        built.append(row[0] if len(row) == 1 else np.concatenate(row, axis=1))
    w = built[0].shape[1]
    if any(b.shape[1] != w for b in built):
        return None
    return built[0].copy() if len(built) == 1 else np.concatenate(built, axis=0)


def build_cell(rows: Sequence[Sequence[object]]) -> CellArray:
    """Cell literal ``{...}``: every element becomes one cell entry (cells are not flattened)."""
    rows = [r for r in rows if len(r)]
    if not rows:
        return CellArray.empty(0, 0)
    if any(len(r) != len(rows[0]) for r in rows):
        raise DimensionError("Dimensions of arrays being concatenated are not consistent.")
    arr = np.empty((len(rows), len(rows[0])), dtype=object)
    for i, r in enumerate(rows):
        for j, item in enumerate(r):
            arr[i, j] = item
    return CellArray(arr)
