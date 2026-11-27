"""Input validation helpers shared by the engine modules.

Conventions: results are float64/complex128 copies (inputs are never mutated or aliased);
NaN/Inf, empty, non-numeric and ragged inputs raise ``ValidationError``; wrong shapes raise
``DimensionError``. A 1-D input to ``as_matrix`` is a column vector.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from engstudio.core.errors import DimensionError, SingularMatrixError, ValidationError

__all__ = ["as_matrix", "as_vector", "singular_error"]


def _numeric(a: ArrayLike, name: str, allow_complex: bool, allow_empty: bool) -> NDArray:
    try:
        arr = np.asarray(a)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{name}: not a regular numeric array ({exc})") from exc
    if arr.dtype.kind not in "biufc":
        raise ValidationError(f"{name}: expected numeric data, got dtype {arr.dtype}")
    if arr.dtype.kind == "c":
        if not allow_complex:
            raise ValidationError(f"{name}: complex values are not supported here")
        out = np.array(arr, dtype=np.complex128)
    else:
        out = np.array(arr, dtype=np.float64)
    if out.size == 0 and not allow_empty:
        raise ValidationError(f"{name}: must not be empty")
    if not np.all(np.isfinite(out)):
        raise ValidationError(f"{name}: contains NaN or Inf")
    return out


def as_matrix(
    a: ArrayLike, name: str = "a", *, allow_complex: bool = True, square: bool = False,
    allow_empty: bool = False,
) -> NDArray:
    """Validated 2-D float64/complex128 copy. Scalar -> 1x1, 1-D -> column, >2-D -> error."""
    arr = _numeric(a, name, allow_complex, allow_empty)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        raise DimensionError(f"{name}: expected a scalar, vector or matrix, got {arr.ndim}-D")
    if square and arr.shape[0] != arr.shape[1]:
        raise DimensionError(f"{name}: must be square, got shape {arr.shape}")
    return arr


def as_vector(
    a: ArrayLike, name: str = "a", *, allow_complex: bool = True, allow_empty: bool = False,
    length: int | None = None,
) -> NDArray:
    """Validated 1-D copy. Accepts scalar, 1-D, or a 2-D row/column."""
    arr = _numeric(a, name, allow_complex, allow_empty)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    elif arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    elif arr.ndim != 1:
        raise DimensionError(f"{name}: expected a vector, got shape {arr.shape}")
    if length is not None and arr.shape[0] != length:
        raise DimensionError(f"{name}: expected length {length}, got {arr.shape[0]}")
    return arr


def singular_error(message: str, rcond: float) -> SingularMatrixError:
    """Build a ``SingularMatrixError`` carrying ``.rcond`` (contract, ARCHITECTURE section 6)."""
    try:
        return SingularMatrixError(message, rcond=rcond)
    except TypeError:
        err = SingularMatrixError(message)
        try:
            err.rcond = rcond
        except AttributeError:
            pass
        return err
