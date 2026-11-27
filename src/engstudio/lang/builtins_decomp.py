"""Matrix-decomposition builtins (B2a): ``eig``, ``lu``, ``qr``, ``chol``, ``svd``.

Thin bindings over ``engine.decomp`` (LAPACK). ``install_decomp(interp)`` registers them;
warnings from the engine (nearly defective eigenvector matrix) go to the interpreter's host.

MATLAB conventions kept: ``eig(A)`` is a column of eigenvalues, ``[V, D] = eig(A)`` gives
eigenvectors and a diagonal matrix, a symmetric matrix gets real ascending eigenvalues and
orthonormal eigenvectors, results with zero imaginary parts are real; ``[L, U, P] = lu(A)``
has ``P*A = L*U`` and ``[L, U] = lu(A)`` a permuted ``L``; ``R = qr(A)`` returns R;
``chol`` returns the upper factor (``'lower'`` for the lower one); ``svd(A)`` returns the
singular values, ``[U, S, V] = svd(A)`` the full factors and ``svd(A, 'econ')`` or
``svd(A, 0)`` the economy-size ones.

Differences (as documented in ``engine.decomp``): eigenvalues of non-symmetric matrices are
sorted by real part (MATLAB returns LAPACK order), eigenvector and singular-vector signs or
phases may differ from MATLAB, ``chol`` raises an error for a matrix that is not symmetric
instead of reading only its upper triangle. Complex matrices are not supported yet.
"""

from __future__ import annotations

import numpy as np

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.engine import decomp
from engstudio.lang.builtins_core import Builtin, _need, _real, _text
from engstudio.lang.interp import Interpreter
from engstudio.lang.values import CharArray, empty_double


def _narrow(z: np.ndarray) -> np.ndarray:
    """Real array when every imaginary part is exactly zero (as MATLAB returns it)."""
    return z.real.copy() if z.dtype.kind == "c" and not np.any(z.imag) else z


def _max_outputs(name: str, nargout: int, limit: int) -> None:
    if nargout > limit:
        raise ValidationError(f"{name}: Too many output arguments.")


def _economy(name: str, arg: object) -> bool:
    """``0`` or ``'econ'`` select the economy-size factorisation."""
    if isinstance(arg, CharArray):
        if _text(arg, name) == "econ":
            return True
        raise ValidationError(f"{name}: unknown option {_text(arg, name)!r}; use 'econ' or 0.")
    flag = _real(arg, name)
    if flag.size == 1 and flag[0, 0] == 0:
        return True
    raise ValidationError(f"{name}: the second argument must be 0 or 'econ'.")


def decomp_functions(interp: Interpreter) -> dict[str, Builtin]:
    """The decomposition builtins bound to ``interp``."""
    host = interp.host

    def eig(args: list, nargout: int) -> list:
        _need("eig", args, 1)
        _max_outputs("eig", nargout, 2)
        a = _real(args[0], "eig")
        if a.size == 0:
            return [empty_double(), empty_double()][: max(nargout, 1)]
        symmetric = a.shape[0] == a.shape[1] and np.array_equal(a, a.T)
        result = decomp.eigh(a) if symmetric else decomp.eig(a)
        for d in result.diagnostics:
            host.diagnostic(d)
        values = _narrow(np.asarray(result.values))
        if nargout <= 1:
            return [values.reshape(-1, 1)]
        return [_narrow(np.asarray(result.vectors)), np.diag(values)]

    def lu(args: list, nargout: int) -> list:
        _need("lu", args, 1)
        _max_outputs("lu", nargout, 3)
        a = _real(args[0], "lu")
        r = decomp.lu(a)
        if nargout >= 3:
            return [r.L, r.U, r.P]
        if nargout == 2:
            return [r.P.T @ r.L, r.U]
        if a.shape[0] != a.shape[1]:
            raise NotSupportedError("lu: a single output requires a square matrix")
        return [r.L + r.U - np.eye(a.shape[0])]

    def qr(args: list, nargout: int) -> list:
        _need("qr", args, 1, 2)
        _max_outputs("qr", nargout, 2)
        mode = "economic" if len(args) == 2 and _economy("qr", args[1]) else "full"
        r = decomp.qr(_real(args[0], "qr"), mode)
        return [r.R] if nargout <= 1 else [r.Q, r.R]

    def chol(args: list, nargout: int) -> list:
        _need("chol", args, 1, 2)
        _max_outputs("chol", nargout, 1)
        lower = False
        if len(args) == 2:
            kind = _text(args[1], "chol")
            if kind not in ("lower", "upper"):
                raise ValidationError("chol: the option must be 'lower' or 'upper'.")
            lower = kind == "lower"
        return [decomp.cholesky(_real(args[0], "chol"), lower=lower).factor]

    def svd(args: list, nargout: int) -> list:
        _need("svd", args, 1, 2)
        if nargout == 2:
            raise ValidationError("svd: use one output (singular values) or three [U, S, V].")
        _max_outputs("svd", nargout, 3)
        a = _real(args[0], "svd")
        economy = len(args) == 2 and _economy("svd", args[1])
        r = decomp.svd(a, full=nargout == 3 and not economy)
        if nargout <= 1:
            return [r.s.reshape(-1, 1)]
        m, n = a.shape
        if economy:
            s_matrix = np.diag(r.s)
        else:
            s_matrix = np.zeros((m, n))
            s_matrix[: r.s.size, : r.s.size] = np.diag(r.s)
        return [r.U, s_matrix, r.V]

    return {"eig": eig, "lu": lu, "qr": qr, "chol": chol, "svd": svd}


def install_decomp(interp: Interpreter) -> None:
    """Register the decomposition builtins on ``interp``."""
    interp.functions.update(decomp_functions(interp))

