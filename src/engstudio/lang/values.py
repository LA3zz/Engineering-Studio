"""Value model of the Engineering Studio interpreter (T3.4a).

==============  ====================================================================
MATLAB-like     representation
==============  ====================================================================
double/complex  ``numpy.ndarray`` float64 / complex128, always 2-D
logical         ``numpy.ndarray`` bool, always 2-D
char            ``CharArray`` (2-D array of single characters, dtype ``<U1``)
cell            ``CellArray`` (2-D object array of values)
struct          ``StructValue`` (one struct, ordered fields; struct arrays: later)
function handle ``FunctionHandle`` (named, or anonymous with captured variables)
==============  ====================================================================

Values are immutable by convention: no function in ``lang`` modifies an existing value; every
operation returns a new one. Only 2-D arrays are supported in v1 (a documented difference
from MATLAB). Complex results with all-zero imaginary parts are narrowed to real by ``ops``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang import ast as A

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_VALUE_DTYPES = (np.dtype(np.float64), np.dtype(np.complex128), np.dtype(np.bool_))
_CHAR_DTYPE = np.dtype("<U1")


def empty_double() -> np.ndarray:
    """The 0-by-0 double matrix ``[]``."""
    return np.zeros((0, 0))


class CharArray:
    """2-D character array. ``CharArray.from_str("abc")`` is 1-by-3; ``""`` is 0-by-0."""

    __slots__ = ("data",)

    def __init__(self, data: np.ndarray) -> None:
        if not isinstance(data, np.ndarray) or data.dtype != _CHAR_DTYPE or data.ndim != 2:
            raise ValidationError("CharArray needs a 2-D numpy array of dtype '<U1'")
        self.data = data

    @classmethod
    def from_str(cls, text: str) -> CharArray:
        if not isinstance(text, str):
            raise ValidationError("CharArray.from_str needs a str")
        if text == "":
            return cls(np.empty((0, 0), dtype=_CHAR_DTYPE))
        return cls(np.array(list(text), dtype=_CHAR_DTYPE).reshape(1, -1))

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    def to_str(self) -> str:
        """The text of an empty or single-row array; raises for several rows."""
        if self.data.shape[0] > 1:
            raise ValidationError("char array has more than one row; cannot convert to text")
        return "" if self.data.size == 0 else "".join(c or "\x00" for c in self.data[0])

    def codes(self) -> np.ndarray:
        """Character codes as a float64 array of the same shape."""
        # numpy drops a NUL character from '<U1' elements, so '' stands for char(0)
        flat = [float(ord(c)) if c else 0.0 for c in self.data.ravel()]
        return np.array(flat, dtype=np.float64).reshape(self.data.shape)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, CharArray)
            and self.data.shape == other.data.shape
            and bool(np.all(self.data == other.data))
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        if self.data.shape[0] <= 1:
            return f"CharArray({self.to_str()!r})"
        return f"CharArray(shape={self.shape})"


class CellArray:
    """2-D cell array; every element is a value."""

    __slots__ = ("data",)

    def __init__(self, data: np.ndarray) -> None:
        if not isinstance(data, np.ndarray) or data.dtype != object or data.ndim != 2:
            raise ValidationError("CellArray needs a 2-D numpy array of dtype object")
        for item in data.ravel():
            if not is_value(item):
                raise ValidationError(f"cell element is not a value: {type(item).__name__}")
        self.data = data

    @classmethod
    def empty(cls, rows: int, cols: int) -> CellArray:
        """A cell array whose elements are all ``[]``."""
        arr = np.empty((rows, cols), dtype=object)
        for i in range(rows):
            for j in range(cols):
                arr[i, j] = empty_double()
        return cls(arr)

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[object]]) -> CellArray:
        """Build from equal-length rows of values (converted with ``to_value``)."""
        width = len(rows[0]) if rows else 0
        if any(len(r) != width for r in rows):
            raise ValidationError("cell rows must have equal length")
        arr = np.empty((len(rows), width), dtype=object)
        for i, r in enumerate(rows):
            for j, item in enumerate(r):
                arr[i, j] = to_value(item)
        return cls(arr)

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape  # type: ignore[return-value]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CellArray) or self.data.shape != other.data.shape:
            return False
        pairs = zip(self.data.ravel(), other.data.ravel(), strict=True)
        return all(values_equal(a, b) for a, b in pairs)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"CellArray(shape={self.shape})"


class StructValue:
    """A 1-by-1 struct with ordered fields. Immutable: ``with_field`` returns a new struct."""

    __slots__ = ("_fields",)

    def __init__(self, fields: Mapping[str, object] | None = None) -> None:
        d: dict[str, object] = {}
        for name, value in (fields or {}).items():
            _check_field_name(name)
            d[name] = to_value(value)
        self._fields = d

    def names(self) -> tuple[str, ...]:
        return tuple(self._fields)

    def items(self) -> Iterator[tuple[str, object]]:
        return iter(self._fields.items())

    def has(self, name: str) -> bool:
        return name in self._fields

    def get(self, name: str) -> object:
        try:
            return self._fields[name]
        except KeyError:
            raise ValidationError(f"Reference to non-existent field '{name}'.") from None

    def with_field(self, name: str, value: object) -> StructValue:
        _check_field_name(name)
        d = dict(self._fields)
        d[name] = to_value(value)
        return StructValue(d)

    def __len__(self) -> int:
        return len(self._fields)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructValue) or set(self._fields) != set(other._fields):
            return False
        return all(values_equal(v, other._fields[k]) for k, v in self._fields.items())

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"StructValue({', '.join(self._fields)})"


def _check_field_name(name: object) -> None:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValidationError(f"invalid field name {name!r}")


class FunctionHandle:
    """``@name`` (named) or ``@(params) body`` (anonymous, with captured variables).

    Anonymous handles compare equal only to themselves.
    """

    __slots__ = ("name", "params", "body", "captured")

    def __init__(
        self,
        name: str | None = None,
        params: Sequence[str] = (),
        body: A.Node | None = None,
        captured: Mapping[str, object] | None = None,
    ) -> None:
        if (name is None) == (body is None):
            raise ValidationError("FunctionHandle needs either a name or an anonymous body")
        if name is not None:
            if not _NAME_RE.match(name):
                raise ValidationError(f"invalid function name {name!r}")
            if params or captured:
                raise ValidationError("a named FunctionHandle has no params or captured values")
        elif len(set(params)) != len(tuple(params)):
            raise ValidationError("duplicate parameter name")
        self.name = name
        self.params = tuple(params)
        self.body = body
        self.captured = {k: to_value(x) for k, x in (captured or {}).items()}

    @property
    def is_anonymous(self) -> bool:
        return self.body is not None

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        return (
            isinstance(other, FunctionHandle)
            and not self.is_anonymous
            and not other.is_anonymous
            and self.name == other.name
        )

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"FunctionHandle(@{self.name})" if self.name else "FunctionHandle(@(...))"


class SymValue:
    """A symbolic scalar: wraps ``engine.symbolic.SymExpr`` (class ``sym``). Immutable."""

    __slots__ = ("expr",)

    def __init__(self, expr: object) -> None:
        self.expr = expr

    @property
    def shape(self) -> tuple[int, int]:
        return (1, 1)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SymValue) and str(self.expr) == str(other.expr)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"SymValue({self.expr})"


class LtiValue:
    """A linear system (class 'tf', 'zpk' or 'ss'): wraps ``control.lti.LtiSystem``.
    Immutable; operators and builtins live in ``lang.builtins_control``."""

    __slots__ = ("system",)

    def __init__(self, system: object) -> None:
        self.system = system

    @property
    def shape(self) -> tuple[int, int]:
        return self.system.shape  # type: ignore[attr-defined,no-any-return]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LtiValue):
            return False
        a, b = self.system, other.system
        return (a.form == b.form and a.dt == b.dt  # type: ignore[attr-defined]
                and all(np.array_equal(np.asarray(x), np.asarray(y))
                        for x, y in zip(a.data, b.data, strict=True)))  # type: ignore[attr-defined]

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"LtiValue({self.system.form})"  # type: ignore[attr-defined]


# ------------------------------------------------------------------ predicates
def is_value(x: object) -> bool:
    if isinstance(x, np.ndarray):
        return x.ndim == 2 and x.dtype in _VALUE_DTYPES
    return isinstance(x, (CharArray, CellArray, StructValue, FunctionHandle, SymValue, LtiValue))


def to_value(x: object) -> object:
    """Convert Python data to a value (values pass through unchanged).

    ints/floats become float64, bools stay logical, ``str`` becomes ``CharArray``; a scalar
    becomes 1-by-1, a 1-D sequence a row, an empty sequence the 0-by-0 matrix.
    """
    if is_value(x):
        return x
    if isinstance(x, str):
        return CharArray.from_str(x)
    if isinstance(x, (bool, np.bool_)):
        return np.array([[bool(x)]], dtype=bool)
    try:
        arr = np.asarray(x)
    except ValueError as exc:
        raise ValidationError(f"cannot convert {type(x).__name__} to a value: {exc}") from exc
    kind = arr.dtype.kind
    if kind == "b":
        out = arr
    elif kind in "iuf":
        out = arr.astype(np.float64)
    elif kind == "c":
        out = arr.astype(np.complex128)
    else:
        raise ValidationError(f"cannot convert {type(x).__name__} to a value")
    if out.ndim == 0:
        return out.reshape(1, 1)
    if out.ndim == 1:
        return out.reshape(0, 0) if out.size == 0 else out.reshape(1, -1)
    if out.ndim > 2:
        raise NotSupportedError("arrays with more than 2 dimensions are not supported")
    return out


def class_of(v: object) -> str:
    if isinstance(v, np.ndarray):
        return "logical" if v.dtype == np.bool_ else "double"
    if isinstance(v, CharArray):
        return "char"
    if isinstance(v, CellArray):
        return "cell"
    if isinstance(v, StructValue):
        return "struct"
    if isinstance(v, FunctionHandle):
        return "function_handle"
    if isinstance(v, SymValue):
        return "sym"
    if isinstance(v, LtiValue):
        return v.system.form  # type: ignore[attr-defined,no-any-return]
    raise ValidationError(f"not a value: {type(v).__name__}")


def size_of(v: object) -> tuple[int, int]:
    if isinstance(v, np.ndarray):
        return v.shape  # type: ignore[return-value]
    if isinstance(v, (CharArray, CellArray, LtiValue)):
        return v.shape
    class_of(v)  # raises for non-values
    return (1, 1)


def numel_of(v: object) -> int:
    rows, cols = size_of(v)
    return rows * cols


def is_empty(v: object) -> bool:
    return numel_of(v) == 0


def values_equal(a: object, b: object) -> bool:
    """Strict structural equality (NaN is not equal to NaN, like MATLAB ``isequal``)."""
    if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
        return a.shape == b.shape and bool(np.array_equal(a, b))
    if type(a) is not type(b):
        return False
    return bool(a == b)


def is_true(v: object) -> bool:
    """Truth value for ``if``/``while``: non-empty and all elements nonzero."""
    if isinstance(v, np.ndarray):
        x = v
    elif isinstance(v, CharArray):
        x = v.codes()
    else:
        raise ValidationError(f"Conversion to logical from {class_of(v)} is not possible.")
    if x.size == 0:
        return False
    if x.dtype.kind in "fc" and np.isnan(x).any():
        raise ValidationError("NaN's cannot be converted to logicals.")
    return bool(np.all(x != 0))
