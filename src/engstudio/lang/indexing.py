"""Indexing and indexed assignment on interpreter values (T3.4b). Pure functions.

Index arguments are values (numeric or logical arrays) or the ``COLON`` sentinel (a bare ``:``).
All functions return new values; their inputs are never modified.

Read: ``index_value`` (``A(i)``, ``A(i,j)``; numeric, char, cell and 1-by-1 struct),
``cell_contents`` (``c{i}``, returns the list of selected elements in column-major order),
``end_value`` (what ``end`` means at an index position), ``get_field``.
Write: ``assign_index`` (``A(i) = x``, growth with zero/``[]`` fill, ``A(i) = []`` deletion),
``assign_cell_content`` (``c{i} = x``), ``set_field``.

MATLAB rules implemented: column-major linear indexing; result shape of ``A(idx)`` follows the
source orientation for vector-by-vector indexing and the shape of ``idx`` otherwise; ``A(:)``
is a column; a logical matrix mask selects in column-major order and gives a column; linear
growth of ``[]``, a scalar or a row gives a row, of a column gives a column, of a matrix is an
error; assigning a double into a char array keeps char, a char into a double array gives double.

Differences (v1): arrays are 2-D, so extra trailing indices must be ``1`` or ``:``; struct
arrays are not supported (``s(1)`` only); ``c{idx} = x`` needs exactly one selected element.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang.ops import _as_char
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
    is_value,
    to_value,
)

_INT = np.int64


class _Colon:
    __slots__ = ()

    def __repr__(self) -> str:
        return "COLON"


COLON = _Colon()
_INVALID = "Array indices must be positive integers or logical values."


# ------------------------------------------------------------------ resolution
def _prep(args: Sequence[object]) -> tuple[object, ...]:
    args = tuple(args)
    for k, a in enumerate(args[2:], start=2):
        ok = a is COLON or (
            isinstance(a, np.ndarray) and a.size == 1 and a.dtype.kind in "bfiu" and a.item() == 1
        )
        if not ok:
            raise ValidationError(
                f"Index in position {k + 1} exceeds array bounds. Index must not exceed 1."
            )
    return args[:2]


def _resolve(idx: object, n: int, pos: int) -> tuple[np.ndarray, tuple[int, int], bool]:
    """Return (0-based int indices in column-major order of ``idx``, shape of ``idx``, is_colon)."""
    if idx is COLON:
        return np.arange(n, dtype=_INT), (n, 1), True
    if not isinstance(idx, np.ndarray):
        raise ValidationError(
            "Subscript indices must either be real positive integers or logicals."
        )
    if idx.dtype == np.bool_:
        ind = np.flatnonzero(idx.ravel(order="F")).astype(_INT)
        if idx.shape == (0, 0):
            return ind, (0, 0), False
        shape = (1, ind.size) if idx.shape[0] == 1 else (ind.size, 1)
        return ind, shape, False
    bad = idx.dtype.kind == "c" or (
        idx.size > 0
        and (not np.all(np.isfinite(idx)) or np.any(idx != np.round(idx)) or np.any(idx < 1))
    )
    if bad:
        raise ValidationError(f"Index in position {pos + 1} is invalid. {_INVALID}")
    return idx.ravel(order="F").astype(_INT) - 1, idx.shape, False  # type: ignore[return-value]


def _check_bounds(ind: np.ndarray, n: int, pos: int, nargs: int) -> None:
    if ind.size and int(ind.max()) >= n:
        if nargs == 1:
            raise ValidationError(
                f"Index exceeds the number of array elements. Index must not exceed {n}."
            )
        raise ValidationError(
            f"Index in position {pos + 1} exceeds array bounds. Index must not exceed {n}."
        )


def end_value(v: object, position: int, nargs: int) -> int:
    """Value of ``end`` at index ``position`` (0-based) of an ``nargs``-index expression."""
    if isinstance(v, (np.ndarray, CharArray, CellArray)):
        r, c = v.shape
    else:
        class_of(v)  # raises for non-values
        r, c = 1, 1
    if nargs == 1:
        return r * c
    return (r, c, 1)[min(position, 2)]


def _unwrap(v: object) -> tuple[str, np.ndarray]:
    if isinstance(v, np.ndarray):
        return "num", v
    if isinstance(v, CharArray):
        return "char", v.data
    if isinstance(v, CellArray):
        return "cell", v.data
    raise ValidationError(f"Indexing is not supported for {class_of(v)} values here.")


def _wrap(kind: str, arr: np.ndarray) -> object:
    if kind == "num":
        return arr
    return CharArray(arr) if kind == "char" else CellArray(arr)


# ------------------------------------------------------------------------ read
def _read(arr: np.ndarray, args: tuple[object, ...]) -> np.ndarray:
    r, c = arr.shape
    if not args:
        return arr.copy()
    if len(args) == 1:
        n = r * c
        ind, ishape, is_colon = _resolve(args[0], n, 0)
        if is_colon:
            return arr.reshape(n, 1, order="F").copy()
        _check_bounds(ind, n, 0, 1)
        out = arr.ravel(order="F")[ind]
        src_vec = (r == 1) != (c == 1)
        idx_vec = (ishape[0] == 1) != (ishape[1] == 1)
        if src_vec and idx_vec:
            shape = (1, ind.size) if r == 1 else (ind.size, 1)
        else:
            shape = ishape
        return out.reshape(shape, order="F")
    rows, _, _ = _resolve(args[0], r, 0)
    cols, _, _ = _resolve(args[1], c, 1)
    _check_bounds(rows, r, 0, 2)
    _check_bounds(cols, c, 1, 2)
    return arr[np.ix_(rows, cols)]


_F64 = np.dtype(np.float64)


def _scalar_index(v: np.ndarray, args: Sequence[object]) -> np.ndarray | None:
    """Fast path for ``v(k)`` / ``v(i, j)`` with in-range positive integer double scalars;
    None sends everything else (and every error) to the general code."""
    subs = []
    for a in args:
        if type(a) is not np.ndarray or a.shape != (1, 1) or a.dtype != _F64:
            return None
        k = float(a[0, 0])
        if not (1 <= k <= 2.0 ** 53 and k.is_integer()):  # rejects NaN and inf too
            return None
        subs.append(int(k))
    rows, cols = v.shape
    if len(subs) == 1:
        k = subs[0] - 1
        if k >= rows * cols:
            return None
        r, c = k % rows, k // rows  # column-major linear index
    else:
        r, c = subs[0] - 1, subs[1] - 1
        if r >= rows or c >= cols:
            return None
    return v[r:r + 1, c:c + 1].copy()


def index_value(v: object, args: Sequence[object]) -> object:
    """``v(args...)`` for numeric, char and cell values (cell gives a cell) and 1x1 structs."""
    if type(v) is np.ndarray and v.ndim == 2 and 1 <= len(args) <= 2:
        fast = _scalar_index(v, args)
        if fast is not None:
            return fast
    args = _prep(args)
    if isinstance(v, StructValue):
        if _read(np.zeros((1, 1)), args).shape != (1, 1):
            raise NotSupportedError("struct arrays are not supported yet")
        return v
    if isinstance(v, FunctionHandle):
        raise ValidationError("A function handle is called, not indexed, with ().")
    kind, arr = _unwrap(v)
    return _wrap(kind, _read(arr, args))


def cell_contents(v: object, args: Sequence[object]) -> list[object]:
    """``c{args...}``: the selected elements in column-major order (a comma-separated list)."""
    if not isinstance(v, CellArray):
        raise ValidationError("Brace indexing is not supported for variables of this type.")
    sub = _read(v.data, _prep(args))
    return list(sub.ravel(order="F"))


# ----------------------------------------------------------------------- write
def _is_null(rhs: object) -> bool:
    return isinstance(rhs, np.ndarray) and rhs.dtype == np.float64 and rhs.shape == (0, 0)


def _empty_like(rhs: object) -> object:
    if isinstance(rhs, np.ndarray):
        return np.zeros((0, 0), dtype=rhs.dtype)
    if isinstance(rhs, CharArray):
        return CharArray.from_str("")
    return CellArray.empty(0, 0)


def _coerce(base: object, rhs: object) -> tuple[str, np.ndarray, np.ndarray]:
    """Common kind/dtype for base and rhs: returns (kind, base array, rhs array)."""
    if isinstance(rhs, (StructValue, FunctionHandle)):
        if base is None:
            raise NotSupportedError("struct arrays and handle arrays are not supported yet")
        raise ValidationError(
            f"Conversion to {class_of(base)} from {class_of(rhs)} is not possible."
        )
    if base is None:
        base = _empty_like(rhs)
    if isinstance(base, StructValue):
        raise NotSupportedError("struct arrays are not supported yet")
    if isinstance(base, FunctionHandle):
        raise ValidationError(
            f"Conversion to function_handle from {class_of(rhs)} is not possible."
        )
    is_blank = isinstance(base, (np.ndarray, CharArray)) and base.shape == (0, 0)
    if isinstance(rhs, CellArray) and is_blank and not isinstance(base, CellArray):
        return "cell", np.empty((0, 0), dtype=object), rhs.data
    if isinstance(base, np.ndarray):
        if isinstance(rhs, CharArray) and base.shape == (0, 0) and base.dtype == np.float64:
            return "char", np.empty((0, 0), dtype="<U1"), rhs.data
        if isinstance(rhs, CellArray):
            raise ValidationError("Conversion to double from cell is not possible.")
        rarr = rhs.codes() if isinstance(rhs, CharArray) else rhs
        dtype = np.result_type(base.dtype, rarr.dtype)
        return "num", base.astype(dtype), rarr.astype(dtype)
    if isinstance(base, CharArray):
        if isinstance(rhs, CellArray):
            raise ValidationError("Conversion to char from cell is not possible.")
        return "char", base.data, rhs.data if isinstance(rhs, CharArray) else _as_char(rhs)
    if not isinstance(rhs, CellArray):
        raise ValidationError(f"Conversion to cell from {class_of(rhs)} is not possible.")
    return "cell", base.data, rhs.data  # type: ignore[union-attr]


def _filled(kind: str, dtype: np.dtype, shape: tuple[int, int]) -> np.ndarray:
    if kind == "cell":
        out = np.empty(shape, dtype=object)
        for i in range(shape[0]):
            for j in range(shape[1]):
                out[i, j] = empty_double()
        return out
    if kind == "char":
        return np.full(shape, "\x00", dtype="<U1")
    return np.zeros(shape, dtype=dtype)


def _grow(arr: np.ndarray, kind: str, shape: tuple[int, int]) -> np.ndarray:
    if shape == arr.shape:
        return arr.copy()
    out = _filled(kind, arr.dtype, shape)
    r, c = arr.shape
    out[:r, :c] = arr
    return out


def _repeat(item: object, dtype: np.dtype, shape: tuple[int, ...]) -> np.ndarray:
    """Array of ``shape`` filled with ``item`` (object arrays are filled element by element)."""
    out = np.empty(shape, dtype=dtype)
    if np.dtype(dtype).kind == "O":
        for pos in np.ndindex(*shape):
            out[pos] = item
    else:
        out[...] = item
    return out


def _vals(rarr: np.ndarray, k: int) -> np.ndarray:
    """Right-hand side as a 1-D array of length ``k`` (scalar expansion, column-major)."""
    if rarr.size == 1:
        return _repeat(rarr.ravel()[0], rarr.dtype, (k,))
    if rarr.size != k:
        raise ValidationError(
            "Unable to perform assignment because the left and right sides have a different "
            "number of elements."
        )
    return rarr.ravel(order="F")


def _assign_linear(arr: np.ndarray, kind: str, idx: object, rarr: np.ndarray) -> np.ndarray:
    r, c = arr.shape
    n = r * c
    ind, _, _ = _resolve(idx, n, 0)
    vals = _vals(rarr, ind.size)
    top = int(ind.max()) + 1 if ind.size else 0
    if top > n:
        if r == 1:
            shape = (1, top)
        elif c == 1:
            shape = (top, 1)
        elif (r, c) == (0, 0):
            shape = (1, top)
        else:
            raise ValidationError("Attempt to grow array along ambiguous dimension.")
        grown = _filled(kind, arr.dtype, shape)
        grown.reshape(-1)[:n] = arr.ravel(order="F")
        arr = grown
    flat = arr.ravel(order="F").copy()
    if arr.dtype == object:
        for pos, k in enumerate(ind):
            flat[k] = vals[pos]
    else:
        flat[ind] = vals
    return flat.reshape(arr.shape, order="F")


def _assign_2d(
    arr: np.ndarray, kind: str, args: tuple[object, ...], rarr: np.ndarray
) -> np.ndarray:
    r, c = arr.shape
    sel: list[np.ndarray] = []
    pending: list[int] = []
    for pos, n in enumerate((r, c)):
        ind, _, is_colon = _resolve(args[pos], n, pos)
        sel.append(ind)
        if is_colon and n == 0:
            pending.append(pos)
    if pending:
        if rarr.size == 1:
            ext = [1, 1]
        elif len(pending) == 2:
            ext = list(rarr.shape)
        else:
            other = sel[1 - pending[0]].size
            if other == 0 or rarr.size % other:
                raise ValidationError(_size_msg((sel[0].size, sel[1].size), rarr.shape))
            ext = [rarr.size // other] * 2
        for p in pending:
            sel[p] = np.arange(ext[p], dtype=_INT)
    nr, nc = sel[0].size, sel[1].size
    if rarr.size == 1:
        block = _repeat(rarr.ravel()[0], rarr.dtype, (nr, nc))
    else:
        squeezed = tuple(d for d in rarr.shape if d != 1)
        if squeezed != tuple(d for d in (nr, nc) if d != 1):
            raise ValidationError(_size_msg((nr, nc), rarr.shape))
        block = rarr.reshape(nr, nc, order="F")
    new_r = max(r, int(sel[0].max()) + 1) if nr else r
    new_c = max(c, int(sel[1].max()) + 1) if nc else c
    out = _grow(arr, kind, (new_r, new_c))
    if arr.dtype == object:
        for i in range(nr):
            for j in range(nc):
                out[sel[0][i], sel[1][j]] = block[i, j]
    elif nr and nc:
        out[np.ix_(sel[0], sel[1])] = block
    return out


def _size_msg(left: tuple[int, int], right: tuple[int, ...]) -> str:
    return (
        f"Unable to perform assignment because the size of the left side is "
        f"{left[0]}-by-{left[1]} and the size of the right side is {right[0]}-by-{right[1]}."
    )


def assign_index(base: object | None, args: Sequence[object], rhs: object) -> object:
    """``base(args...) = rhs``. ``base=None`` means an undefined variable.

    ``rhs`` equal to the 0-by-0 double ``[]`` deletes the selected elements instead.
    """
    args = _prep(args)
    if not args:
        raise ValidationError("Assignment needs at least one index.")
    if _is_null(rhs):
        return _delete(base, args)
    kind, arr, rarr = _coerce(base, rhs)
    if len(args) == 1:
        out = _assign_linear(arr, kind, args[0], rarr)
    else:
        out = _assign_2d(arr, kind, args, rarr)
    return _wrap(kind, out)


def _all_selected(ind: np.ndarray, n: int, is_colon: bool) -> bool:
    return is_colon or (n > 0 and np.unique(ind).size == n)


def _delete(base: object | None, args: tuple[object, ...]) -> object:
    if base is None:
        base = empty_double()
    kind, arr = _unwrap(base)
    r, c = arr.shape
    if len(args) == 1:
        n = r * c
        ind, _, is_colon = _resolve(args[0], n, 0)
        if is_colon:
            return _wrap(kind, np.empty((0, 0), dtype=arr.dtype))
        _check_bounds(ind, n, 0, 1)
        if ind.size == 0:
            return base
        keep = np.ones(n, dtype=bool)
        keep[ind] = False
        flat = arr.ravel(order="F")[keep]
        shape = (flat.size, 1) if (c == 1 and r != 1) else (1, flat.size)
        return _wrap(kind, flat.reshape(shape))
    rows, _, rc = _resolve(args[0], r, 0)
    cols, _, cc = _resolve(args[1], c, 1)
    _check_bounds(rows, r, 0, 2)
    _check_bounds(cols, c, 1, 2)
    if _all_selected(cols, c, cc):
        keep = np.ones(r, dtype=bool)
        keep[rows] = False
        return _wrap(kind, arr[keep, :])
    if _all_selected(rows, r, rc):
        keep = np.ones(c, dtype=bool)
        keep[cols] = False
        return _wrap(kind, arr[:, keep])
    raise ValidationError("A null assignment can have only one non-colon index.")


def _selected_count(shape: tuple[int, int], args: tuple[object, ...]) -> int:
    if len(args) == 1:
        ind, _, is_colon = _resolve(args[0], shape[0] * shape[1], 0)
        return int(ind.size)
    count = 1
    for pos in (0, 1):
        ind, _, _ = _resolve(args[pos], shape[pos], pos)
        count *= int(ind.size)
    return count


def assign_cell_content(base: object | None, args: Sequence[object], rhs: object) -> CellArray:
    """``base{args...} = rhs`` (``base=None`` or ``[]`` starts a new cell array)."""
    args = _prep(args)
    if not args:
        raise ValidationError("Assignment needs at least one index.")
    if base is None or (isinstance(base, np.ndarray) and base.shape == (0, 0)):
        base = CellArray.empty(0, 0)
    if not isinstance(base, CellArray):
        raise ValidationError(f"Cannot assign with {{}} into a {class_of(base)} value.")
    if _selected_count(base.shape, args) != 1:
        raise ValidationError("Cell contents assignment needs exactly one element: c{i} = x.")
    value = rhs if is_value(rhs) else to_value(rhs)
    one = np.empty((1, 1), dtype=object)
    one[0, 0] = value
    return assign_index(base, args, CellArray(one))  # type: ignore[return-value]


# --------------------------------------------------------------------- structs
def get_field(v: object, name: str) -> object:
    """``v.name`` for a struct."""
    if not isinstance(v, StructValue):
        raise ValidationError("Dot indexing is not supported for variables of this type.")
    return v.get(name)


def set_field(base: object | None, name: str, rhs: object) -> StructValue:
    """``base.name = rhs`` (``base=None`` or ``[]`` starts a new struct)."""
    if base is None or (isinstance(base, np.ndarray) and base.shape == (0, 0)):
        return StructValue({name: rhs})
    if not isinstance(base, StructValue):
        raise ValidationError(
            "Dot indexing assignment requires a struct or an undefined variable."
        )
    return base.with_field(name, rhs)
