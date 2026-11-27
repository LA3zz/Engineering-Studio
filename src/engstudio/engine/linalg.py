"""Dense linear algebra with validation, conditioning checks and typed errors (E1).

Differences from MATLAB: ``rank`` uses the same default tolerance (max(m, n) * eps * smax);
``cond`` of a singular matrix is ``inf``; ``solve`` raises ``SingularMatrixError`` instead of
returning a warning and an inaccurate answer; a 1-D right-hand side gives a 1-D solution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector, singular_error

__all__ = [
    "InvResult", "SolveResult", "cond", "cross", "det", "dot", "inv", "matmul", "norm", "rank",
    "rcond", "solve", "trace", "transpose", "ctranspose", "ILL_CONDITIONED_RCOND",
]

EPS = float(np.finfo(float).eps)
ILL_CONDITIONED_RCOND = 1e-12


@dataclass(frozen=True, eq=False)
class SolveResult:
    x: NDArray
    residual_norm: float
    rcond: float
    method: str
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, eq=False)
class InvResult:
    value: NDArray
    rcond: float
    diagnostics: tuple[Diagnostic, ...] = ()


def _rcond(m: NDArray) -> float:
    """Reciprocal 1-norm condition number; 0.0 for singular matrices."""
    n1 = float(np.linalg.norm(m, 1))
    if n1 == 0.0:
        return 0.0
    try:
        inverse = np.linalg.inv(m)
    except np.linalg.LinAlgError:
        return 0.0
    if not np.all(np.isfinite(inverse)):
        return 0.0
    return float(1.0 / (n1 * np.linalg.norm(inverse, 1)))


def _check_conditioning(rc: float, what: str) -> tuple[Diagnostic, ...]:
    if rc < EPS:
        raise singular_error(f"{what}: matrix is singular to working precision (rcond={rc:.3g})",
                             rc)
    if rc < ILL_CONDITIONED_RCOND:
        return (Diagnostic(
            severity="warning", code="ILL_CONDITIONED",
            message=f"{what}: matrix is badly conditioned (rcond={rc:.3g}); "
                    "results may have lost many digits"),)
    return ()


def rcond(a: ArrayLike) -> float:
    """Reciprocal condition number in the 1-norm (0 for a singular matrix)."""
    return _rcond(as_matrix(a, "a", square=True))


def solve(a: ArrayLike, b: ArrayLike) -> SolveResult:
    """Solve ``a @ x = b`` for square ``a`` (LU with partial pivoting, LAPACK gesv)."""
    m = as_matrix(a, "a", square=True)
    rhs = as_matrix(b, "b")
    vector_rhs = np.ndim(b) <= 1
    if rhs.shape[0] != m.shape[0]:
        raise DimensionError(f"b has {rhs.shape[0]} rows but a is {m.shape[0]}x{m.shape[1]}")
    rc = _rcond(m)
    diags = _check_conditioning(rc, "solve")
    try:
        x = np.linalg.solve(m, rhs)
    except np.linalg.LinAlgError as exc:
        raise singular_error(f"solve: matrix is singular ({exc})", rc) from exc
    residual = float(np.linalg.norm(m @ x - rhs))
    return SolveResult(x[:, 0] if vector_rhs else x, residual, rc, "LU (LAPACK gesv)", diags)


def inv(a: ArrayLike) -> InvResult:
    """Matrix inverse with conditioning check."""
    m = as_matrix(a, "a", square=True)
    rc = _rcond(m)
    diags = _check_conditioning(rc, "inv")
    return InvResult(np.linalg.inv(m), rc, diags)


def det(a: ArrayLike) -> float | complex:
    m = as_matrix(a, "a", square=True)
    d = np.linalg.det(m)
    return complex(d) if np.iscomplexobj(d) else float(d)


def trace(a: ArrayLike) -> float | complex:
    m = as_matrix(a, "a", square=True)
    t = np.trace(m)
    return complex(t) if np.iscomplexobj(t) else float(t)


def matmul(a: ArrayLike, b: ArrayLike) -> NDArray:
    ma, mb = as_matrix(a, "a"), as_matrix(b, "b")
    if ma.shape[1] != mb.shape[0]:
        raise DimensionError(f"inner dimensions must agree: {ma.shape} @ {mb.shape}")
    return ma @ mb


def transpose(a: ArrayLike) -> NDArray:
    return as_matrix(a, "a").T.copy()


def ctranspose(a: ArrayLike) -> NDArray:
    """Conjugate transpose."""
    return as_matrix(a, "a").conj().T.copy()


def dot(a: ArrayLike, b: ArrayLike) -> float | complex:
    """sum(conj(a) * b) for equal-length vectors (MATLAB ``dot`` convention)."""
    va = as_vector(a, "a")
    vb = as_vector(b, "b", length=va.shape[0])
    d = np.vdot(va, vb)
    return complex(d) if np.iscomplexobj(d) else float(d)


def cross(a: ArrayLike, b: ArrayLike) -> NDArray:
    va = as_vector(a, "a", length=3)
    vb = as_vector(b, "b", length=3)
    return np.cross(va, vb)


def norm(x: ArrayLike, kind: float | str = 2) -> float:
    """Vector norm (1, 2, inf or p >= 1) or matrix norm (1, 2, inf or 'fro')."""
    m = as_matrix(x, "x")
    if min(m.shape) == 1:
        v = m.reshape(-1)
        if kind == "fro":
            kind = 2
        if isinstance(kind, str) or not np.isreal(kind) or kind < 1:
            raise ValidationError(f"unsupported vector norm {kind!r}; use 1, 2, inf or p >= 1")
        return float(np.linalg.norm(v, kind))
    if isinstance(kind, str):
        if kind != "fro":
            raise ValidationError(f"unsupported matrix norm {kind!r}")
    elif kind not in (1, 2, np.inf):
        raise ValidationError(f"unsupported matrix norm {kind!r}; use 1, 2, inf or 'fro'")
    return float(np.linalg.norm(m, kind))


def rank(a: ArrayLike, tol: float | None = None) -> int:
    """Numerical rank from singular values; default tol = max(m, n) * eps * smax."""
    m = as_matrix(a, "a")
    if tol is not None and not tol >= 0:
        raise ValidationError("tol must be >= 0")
    s = np.linalg.svd(m, compute_uv=False)
    limit = max(m.shape) * EPS * s[0] if tol is None else tol
    return int(np.sum(s > limit))


def cond(a: ArrayLike, p: float | str = 2) -> float:
    """Condition number in the 1, 2, inf or Frobenius norm; ``inf`` if (numerically) singular."""
    m = as_matrix(a, "a")
    if p == 2:
        s = np.linalg.svd(m, compute_uv=False)
        if s[-1] <= max(m.shape) * EPS * s[0]:  # numerically rank-deficient, same rule as rank()
            return float("inf")
        return float(s[0] / s[-1])
    if p not in (1, np.inf, "fro"):
        raise ValidationError(f"unsupported norm {p!r}; use 1, 2, inf or 'fro'")
    if m.shape[0] != m.shape[1]:
        raise DimensionError("cond with this norm requires a square matrix")
    try:
        inverse = np.linalg.inv(m)
    except np.linalg.LinAlgError:
        return float("inf")
    if not np.all(np.isfinite(inverse)):
        return float("inf")
    return float(np.linalg.norm(m, p) * np.linalg.norm(inverse, p))
