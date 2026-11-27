"""Tests for engstudio.lang.builtins_decomp (B2a): eig, lu, qr, chol, svd.

Expected values are known results (eigenvalues of small matrices, the 1D Laplacian
2 - sqrt(2), 2, 2 + sqrt(2), singular values of [1 2; 3 4]); factorisations are checked by
their defining identities, never by signs of individual vectors.
"""

import math

import numpy as np
import pytest

from engstudio.lang.builtins_core import install_core
from engstudio.lang.builtins_decomp import install_decomp
from engstudio.lang.interp import EvalError, Host, Interpreter


class Rec(Host):
    def __init__(self):
        self.diags = []

    def diagnostic(self, diagnostic):
        self.diags.append(diagnostic)


def run(src):
    host = Rec()
    interp = Interpreter(host=host)
    install_core(interp)
    install_decomp(interp)
    interp.execute(src)
    return interp.workspace, host


def check(actual, expected, atol=1e-12):
    expected = np.asarray(expected)
    assert isinstance(actual, np.ndarray)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=atol)


def fails(src, fragment=""):
    with pytest.raises(EvalError) as info:
        run(src)
    assert fragment in str(info.value), str(info.value)


SQ2 = math.sqrt(2.0)
EIG_CASES = [
    ("[2 0; 0 3]", [[2], [3]]),
    ("[2 1; 1 2]", [[1], [3]]),
    ("[4 1; 2 3]", [[2], [5]]),
    ("[1 2; 3 4]", [[(5 - math.sqrt(33)) / 2], [(5 + math.sqrt(33)) / 2]]),
    ("[2 -1 0; -1 2 -1; 0 -1 2]", [[2 - SQ2], [2], [2 + SQ2]]),
    ("[0 1; -1 0]", [[-1j], [1j]]),
    ("[3 0 0; 0 -1 0; 0 0 2]", [[-1], [2], [3]]),
    ("5", [[5]]),
    ("[]", np.zeros((0, 0))),
]


@pytest.mark.parametrize("matrix,expected", EIG_CASES)
def test_eigenvalues(matrix, expected):
    ws, _ = run(f"r = eig({matrix});")
    check(ws["r"], expected)


def test_real_results_are_real_and_complex_ones_complex():
    ws, _ = run("a = eig([4 1; 2 3]); b = eig([2 1; 1 2]); c = eig([0 1; -1 0]);")
    assert ws["a"].dtype == np.float64 and ws["b"].dtype == np.float64
    assert ws["c"].dtype == np.complex128


@pytest.mark.parametrize("matrix", [
    "[2 1; 1 2]", "[4 1; 2 3]", "[0 1; -1 0]", "[2 -1 0; -1 2 -1; 0 -1 2]",
    "[1 2 3; 4 5 6; 7 8 10]", "[1 -2; 3 1]",
])
def test_eigenvectors_satisfy_the_definition(matrix):
    ws, _ = run(f"A = {matrix}; [V, D] = eig(A);")
    a, v, d = ws["A"], ws["V"], ws["D"]
    np.testing.assert_allclose(a @ v, v @ d, atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(v, axis=0), 1.0, atol=1e-12)
    assert np.count_nonzero(d - np.diag(np.diag(d))) == 0
    assert d.shape == a.shape == v.shape


def test_symmetric_matrices_get_orthonormal_vectors_and_ascending_values():
    ws, _ = run("A = [4 1 0; 1 3 1; 0 1 2]; [V, D] = eig(A); lam = eig(A);")
    v = ws["V"]
    np.testing.assert_allclose(v.T @ v, np.eye(3), atol=1e-12)
    lam = ws["lam"].ravel()
    assert np.all(np.diff(lam) > 0) and lam.dtype == np.float64
    np.testing.assert_allclose(np.diag(ws["D"]), lam)
    assert abs(lam.sum() - 9) < 1e-12 and abs(lam.prod() - np.linalg.det(ws["A"])) < 1e-10


def test_diagonal_matrix_gives_identity_vectors_up_to_sign():
    ws, _ = run("[V, D] = eig([2 0; 0 3]);")
    check(np.abs(ws["V"]), np.eye(2))
    check(ws["D"], [[2, 0], [0, 3]])


def test_defective_matrix_warns():
    ws, host = run("e = eig([1 1; 0 1]);")
    check(ws["e"], [[1], [1]])
    assert [d.code for d in host.diags] == ["DEFECTIVE_EIGENVECTORS"]
    _, host = run("e = eig([2 0; 0 3]);")
    assert host.diags == []


def test_eig_errors():
    fails("eig()", "Not enough input arguments")
    fails("eig(1, 2)", "Too many input arguments")
    fails("[a, b, c] = eig(1);", "Too many output arguments")
    fails("eig([1 2 3])", "")
    fails("eig(1 + 2i)", "complex")
    fails("eig({})", "must be numeric")


# ------------------------------------------------------------------------- lu
def test_lu_known_result_and_identities():
    ws, _ = run("A = [1 2; 3 4]; [L, U, P] = lu(A);")
    check(ws["P"], [[0, 1], [1, 0]])
    check(ws["L"], [[1, 0], [1 / 3, 1]])
    check(ws["U"], [[3, 4], [0, 2 / 3]])
    ws, _ = run("A = [2 1 1; 4 3 3; 8 7 9]; [L, U, P] = lu(A); [L2, U2] = lu(A); Y = lu(A);")
    np.testing.assert_allclose(ws["P"] @ ws["A"], ws["L"] @ ws["U"], atol=1e-12)
    np.testing.assert_allclose(ws["L2"] @ ws["U2"], ws["A"], atol=1e-12)
    np.testing.assert_allclose(ws["Y"], ws["L"] + ws["U"] - np.eye(3), atol=1e-12)
    assert np.allclose(np.tril(ws["U"], -1), 0) and np.allclose(np.triu(ws["L"], 1), 0)


def test_lu_rectangular_and_errors():
    ws, _ = run("A = [1 2 3; 4 5 6]; [L, U, P] = lu(A);")
    assert ws["L"].shape == (2, 2) and ws["U"].shape == (2, 3)
    np.testing.assert_allclose(ws["P"] @ ws["A"], ws["L"] @ ws["U"], atol=1e-12)
    fails("Y = lu([1 2 3; 4 5 6]);", "square")
    fails("[a, b, c, d] = lu(1);", "Too many output arguments")


# ------------------------------------------------------------------------- qr
def test_qr_identities():
    ws, _ = run("A = [1 2; 3 4]; [Q, R] = qr(A); R1 = qr(A);")
    np.testing.assert_allclose(ws["Q"] @ ws["R"], ws["A"], atol=1e-12)
    np.testing.assert_allclose(ws["Q"].T @ ws["Q"], np.eye(2), atol=1e-12)
    assert np.allclose(np.tril(ws["R"], -1), 0)
    np.testing.assert_allclose(np.abs(ws["R1"]), np.abs(ws["R"]), atol=1e-12)


def test_qr_economy_and_full_shapes():
    ws, _ = run("A = [1 2; 3 4; 5 6]; [Q, R] = qr(A); [Qe, Re] = qr(A, 0); "
                "[Qf, Rf] = qr(A, 'econ');")
    assert ws["Q"].shape == (3, 3) and ws["R"].shape == (3, 2)
    assert ws["Qe"].shape == (3, 2) and ws["Re"].shape == (2, 2)
    assert ws["Qf"].shape == (3, 2) and ws["Rf"].shape == (2, 2)
    np.testing.assert_allclose(ws["Qe"] @ ws["Re"], ws["A"], atol=1e-12)
    np.testing.assert_allclose(ws["Q"] @ ws["R"], ws["A"], atol=1e-12)


def test_qr_errors():
    fails("[Q, R] = qr([1 2; 3 4], 5);", "0 or 'econ'")
    fails("[Q, R] = qr([1 2; 3 4], 'full');", "unknown option")
    fails("[a, b, c] = qr(1);", "Too many output arguments")


# ----------------------------------------------------------------------- chol
def test_chol_known_result_and_identities():
    ws, _ = run("A = [4 2; 2 3]; R = chol(A); L = chol(A, 'lower'); U = chol(A, 'upper');")
    check(ws["R"], [[2, 1], [0, SQ2]])
    check(ws["L"], [[2, 0], [1, SQ2]])
    check(ws["U"], ws["R"])
    ws, _ = run("A = [6 3 4; 3 6 5; 4 5 10]; R = chol(A);")
    np.testing.assert_allclose(ws["R"].T @ ws["R"], ws["A"], atol=1e-12)


def test_chol_errors():
    fails("chol([1 2; 2 1])", "positive definite")
    fails("chol([1 2; 3 4])", "Hermitian")
    fails("chol([4 2; 2 3], 'middle')", "'lower' or 'upper'")
    fails("[R, p] = chol([4 2; 2 3]);", "Too many output arguments")


# ------------------------------------------------------------------------ svd
def test_singular_values_known_results():
    ws, _ = run("s = svd([3 0; 0 4]); t = svd([1 2; 3 4]);")
    check(ws["s"], [[4], [3]])
    check(ws["t"], [[5.464985704219043], [0.36596619062625746]])
    assert abs(ws["t"][0, 0] * ws["t"][1, 0] - 2.0) < 1e-12  # product = |det|


def test_svd_factors_full_and_economy():
    ws, _ = run("A = [1 0; 0 2; 0 0]; [U, S, V] = svd(A); [Ue, Se, Ve] = svd(A, 'econ'); "
                "[U0, S0, V0] = svd(A, 0);")
    a = ws["A"]
    assert ws["U"].shape == (3, 3) and ws["S"].shape == (3, 2) and ws["V"].shape == (2, 2)
    np.testing.assert_allclose(ws["U"] @ ws["S"] @ ws["V"].T, a, atol=1e-12)
    assert ws["Ue"].shape == (3, 2) and ws["Se"].shape == (2, 2) and ws["Ve"].shape == (2, 2)
    np.testing.assert_allclose(ws["Ue"] @ ws["Se"] @ ws["Ve"].T, a, atol=1e-12)
    np.testing.assert_allclose(ws["S0"], ws["Se"])
    np.testing.assert_allclose(ws["U"].T @ ws["U"], np.eye(3), atol=1e-12)
    np.testing.assert_allclose(np.diag(ws["Se"]), [2, 1])


def test_svd_rank_deficient_matrix():
    ws, _ = run("s = svd([1 2; 2 4]);")
    assert ws["s"][1, 0] < 1e-15 and abs(ws["s"][0, 0] - 5) < 1e-12


def test_svd_errors():
    fails("[U, S] = svd([1 2; 3 4]);", "one output")
    fails("[a, b, c, d] = svd(1);", "Too many output arguments")
    fails("s = svd([1 2; 3 4], 'thin');", "unknown option")
    fails("s = svd(1 + 1i);", "complex")
