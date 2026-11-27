"""Matrix decompositions and eigenproblems (E2), built on LAPACK through NumPy/SciPy.

Differences from MATLAB (documented, not hidden):
- ``lu`` follows MATLAB's ``P @ A = L @ U`` (SciPy's own P is the transpose).
- ``qr`` and ``svd``: signs of columns are LAPACK's and may differ from MATLAB; compare
  reconstructions, not individual signs. ``svd`` returns ``V`` (not ``V^H``).
- ``eig`` sorts eigenvalues by real part (ties within 1e-10 by imaginary part) for
  reproducibility; MATLAB returns LAPACK order. Eigenvectors have unit 2-norm; their phase or
  sign is arbitrary. ``eigh`` returns ascending real eigenvalues.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.linalg as sla
from numpy.typing import ArrayLike, NDArray

from engstudio.core.diagnostics import Diagnostic
from engstudio.core.errors import ValidationError
from engstudio.engine.linalg import rcond
from engstudio.engine.validation import as_matrix

__all__ = [
    "CholResult", "EigResult", "LuResult", "QrResult", "SvdResult",
    "cholesky", "eig", "eigh", "lu", "qr", "svd", "DEFECTIVE_RCOND", "HERMITIAN_TOL",
]

DEFECTIVE_RCOND = 1e-12
HERMITIAN_TOL = 1e-12


@dataclass(frozen=True, eq=False)
class LuResult:
    """``P @ A = L @ U`` with partial pivoting; works for rectangular ``A`` too."""
    P: NDArray
    L: NDArray
    U: NDArray


@dataclass(frozen=True, eq=False)
class QrResult:
    Q: NDArray
    R: NDArray
    mode: str


@dataclass(frozen=True, eq=False)
class CholResult:
    """``factor`` is upper ``R`` with ``R^H R = A`` (or lower ``L`` with ``L L^H = A``)."""
    factor: NDArray
    lower: bool


@dataclass(frozen=True, eq=False)
class SvdResult:
    """``A = U @ diag(s) @ V^H``; ``s`` is descending and non-negative."""
    U: NDArray
    s: NDArray
    V: NDArray


@dataclass(frozen=True, eq=False)
class EigResult:
    values: NDArray
    vectors: NDArray
    residual: float            # max over columns of ||A v - lambda v||_2
    vector_rcond: float        # reciprocal condition of the eigenvector matrix
    diagnostics: tuple[Diagnostic, ...] = ()


def _check_hermitian(m: NDArray, what: str, tol: float) -> None:
    scale = max(1.0, float(np.max(np.abs(m))))
    if float(np.max(np.abs(m - m.conj().T))) > tol * scale:
        raise ValidationError(f"{what}: matrix is not Hermitian (symmetric) within tol={tol:g}")


def lu(a: ArrayLike) -> LuResult:
    m = as_matrix(a, "a")
    p, low, up = sla.lu(m)
    return LuResult(P=p.T.copy(), L=low, U=up)


def qr(a: ArrayLike, mode: str = "full") -> QrResult:
    """QR by Householder reflections; ``mode`` is ``'full'`` or ``'economic'``."""
    if mode not in ("full", "economic"):
        raise ValidationError(f"qr: unknown mode {mode!r}; use 'full' or 'economic'")
    q, r = sla.qr(as_matrix(a, "a"), mode=mode)
    return QrResult(Q=q, R=r, mode=mode)


def cholesky(a: ArrayLike, lower: bool = False, tol: float = HERMITIAN_TOL) -> CholResult:
    """Cholesky factor of a Hermitian positive-definite matrix."""
    m = as_matrix(a, "a", square=True)
    _check_hermitian(m, "cholesky", tol)
    try:
        low = np.linalg.cholesky(m)
    except np.linalg.LinAlgError as exc:
        raise ValidationError("cholesky: matrix is not positive definite") from exc
    return CholResult(factor=low if lower else low.conj().T.copy(), lower=lower)


def svd(a: ArrayLike, full: bool = False) -> SvdResult:
    """Singular value decomposition; ``full=False`` gives the economy-size factors."""
    u, s, vh = np.linalg.svd(as_matrix(a, "a"), full_matrices=full)
    return SvdResult(U=u, s=s, V=vh.conj().T.copy())


def _sorted(values: NDArray, vectors: NDArray) -> tuple[NDArray, NDArray]:
    order = np.lexsort((values.imag, np.round(values.real, 10)))
    return values[order], vectors[:, order]


def _eig_result(m: NDArray, values: NDArray, vectors: NDArray) -> EigResult:
    residual = float(np.max(np.linalg.norm(m @ vectors - vectors * values, axis=0)))
    vrc = rcond(vectors)
    diags: tuple[Diagnostic, ...] = ()
    if vrc < DEFECTIVE_RCOND:
        diags = (Diagnostic(
            severity="warning", code="DEFECTIVE_EIGENVECTORS",
            message=f"eig: eigenvector matrix is nearly singular (rcond={vrc:.3g}); the matrix "
                    "is defective or has nearly repeated eigenvalues, so eigenvectors are "
                    "not reliable"),)
    return EigResult(values, vectors, residual, vrc, diags)


def eig(a: ArrayLike) -> EigResult:
    """Eigenvalues and right eigenvectors of a general square matrix."""
    m = as_matrix(a, "a", square=True)
    values, vectors = np.linalg.eig(m)
    values, vectors = _sorted(values, vectors)
    return _eig_result(m, values, vectors)


def eigh(a: ArrayLike, tol: float = HERMITIAN_TOL) -> EigResult:
    """Eigenvalues (real, ascending) and orthonormal eigenvectors of a Hermitian matrix."""
    m = as_matrix(a, "a", square=True)
    _check_hermitian(m, "eigh", tol)
    values, vectors = np.linalg.eigh((m + m.conj().T) / 2)
    return _eig_result(m, values, vectors)
