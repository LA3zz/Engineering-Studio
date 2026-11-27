"""Decomposition and eigenvalue tests against analytic results."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine import decomp as dc

RNG = np.random.default_rng(2024)


def test_lu_analytic():
    # rows of [[1,2],[3,4]] swap; l21 = 1/3, u22 = 2 - 4/3 = 2/3
    r = dc.lu([[1, 2], [3, 4]])
    np.testing.assert_allclose(r.P, [[0, 1], [1, 0]], rtol=0, atol=1e-12)
    np.testing.assert_allclose(r.L, [[1, 0], [1 / 3, 1]], rtol=1e-6, atol=1e-12)
    np.testing.assert_allclose(r.U, [[3, 4], [0, 2 / 3]], rtol=1e-6, atol=1e-12)


@pytest.mark.parametrize("shape", [(5, 5), (4, 6), (6, 4)])
def test_lu_reconstruction(shape):
    a = RNG.standard_normal(shape)
    r = dc.lu(a)
    assert r.P @ a == pytest.approx(r.L @ r.U, abs=1e-12)
    assert np.allclose(np.diag(r.L), 1.0)
    assert np.allclose(np.triu(r.U), r.U)


def test_lu_singular_is_valid():
    r = dc.lu([[1, 2], [2, 4]])
    assert abs(r.U[1, 1]) < 1e-15


@pytest.mark.parametrize("mode,shapes", [("full", ((5, 5), (5, 3))),
                                         ("economic", ((5, 3), (3, 3)))])
def test_qr_shapes_and_reconstruction(mode, shapes):
    a = RNG.standard_normal((5, 3))
    r = dc.qr(a, mode)
    assert (r.Q.shape, r.R.shape) == shapes
    assert r.Q @ r.R == pytest.approx(a, abs=1e-12)
    assert r.Q.T @ r.Q == pytest.approx(np.eye(r.Q.shape[1]), abs=1e-12)
    assert np.allclose(np.tril(r.R, -1), 0.0)


def test_qr_analytic_magnitudes():
    # q1 = (3,4)/5 so r11 = 5; r12 = q1 . (0,5) = 4; r22 = |(0,5) - 4 q1| = |(-2.4, 1.8)| = 3
    r = dc.qr([[3, 0], [4, 5]])
    np.testing.assert_allclose(np.abs(r.R), [[5, 4], [0, 3]], rtol=0, atol=1e-12)
    with pytest.raises(ValidationError):
        dc.qr(np.eye(2), mode="x")


def test_cholesky_analytic():
    # [[4,2],[2,3]]: r11=2, r12=1, r22=sqrt(3-1)
    r = dc.cholesky([[4, 2], [2, 3]])
    np.testing.assert_allclose(r.factor, [[2, 1], [0, math.sqrt(2)]], rtol=1e-12)
    low = dc.cholesky([[4, 2], [2, 3]], lower=True)
    np.testing.assert_allclose(low.factor, [[2, 0], [1, math.sqrt(2)]], rtol=1e-6, atol=1e-12)


def test_cholesky_random_spd_and_complex():
    b = RNG.standard_normal((5, 5)) + 1j * RNG.standard_normal((5, 5))
    a = b @ b.conj().T + 5 * np.eye(5)
    r = dc.cholesky(a)
    assert r.factor.conj().T @ r.factor == pytest.approx(a, abs=1e-10)


def test_cholesky_errors():
    with pytest.raises(ValidationError):
        dc.cholesky([[1, 2], [2, 1]])        # eigenvalues 3 and -1
    with pytest.raises(ValidationError):
        dc.cholesky([[1, 2], [0, 1]])        # not symmetric
    with pytest.raises(DimensionError):
        dc.cholesky(np.ones((2, 3)))


def test_svd_analytic():
    assert dc.svd([[3, 0], [0, -2]]).s == pytest.approx([3, 2])
    # A^T A = [[10,14],[14,20]], eigenvalues 15 +- sqrt(221)
    s = dc.svd([[1, 2], [3, 4]]).s
    assert s == pytest.approx([math.sqrt(15 + math.sqrt(221)), math.sqrt(15 - math.sqrt(221))])


def test_svd_shapes_and_reconstruction():
    a = RNG.standard_normal((4, 2)) + 1j * RNG.standard_normal((4, 2))
    eco = dc.svd(a)
    assert (eco.U.shape, eco.s.shape, eco.V.shape) == ((4, 2), (2,), (2, 2))
    assert eco.U @ np.diag(eco.s) @ eco.V.conj().T == pytest.approx(a, abs=1e-12)
    assert dc.svd(a, full=True).U.shape == (4, 4)
    assert np.all(np.diff(eco.s) <= 0)


def test_svd_rank_one():
    s = dc.svd(np.outer([1, 2, 3], [4, 5, 6])).s
    assert s[0] == pytest.approx(math.sqrt(14) * math.sqrt(77))
    assert s[1:] == pytest.approx([0, 0], abs=1e-12)


def test_eig_diagonal_and_triangular():
    assert dc.eig(np.diag([3.0, 2.0])).values == pytest.approx([2, 3])
    t = dc.eig([[5, 1, 2], [0, 1, 7], [0, 0, 3]])
    assert t.values == pytest.approx([1, 3, 5])      # triangular: eigenvalues = diagonal


def test_eig_symmetric_2x2_pairs():
    r = dc.eig([[2, 1], [1, 2]])
    assert r.values == pytest.approx([1, 3])
    assert r.residual < 1e-14
    assert r.vectors.T @ r.vectors == pytest.approx(np.eye(2), abs=1e-12)
    assert r.diagnostics == ()


def test_eig_complex_pair():
    # rotation by 90 degrees: lambda = -+ i
    r = dc.eig([[0, -1], [1, 0]])
    assert r.values == pytest.approx([-1j, 1j])
    assert r.residual < 1e-14


def test_eig_characteristic_polynomial_roots():
    # companion of x^2 - 3x + 2 has eigenvalues 1 and 2
    assert dc.eig([[3, -2], [1, 0]]).values == pytest.approx([1, 2])


def test_eig_tridiagonal_closed_form():
    # tridiag(-1, 2, -1), n = 3: 2 - 2 cos(k pi / 4) = 2 - sqrt2, 2, 2 + sqrt2
    a = [[2, -1, 0], [-1, 2, -1], [0, -1, 2]]
    expected = [2 - math.sqrt(2), 2, 2 + math.sqrt(2)]
    assert dc.eig(a).values == pytest.approx(expected)
    h = dc.eigh(a)
    assert h.values == pytest.approx(expected)
    assert np.sum(h.values) == pytest.approx(6.0)      # trace
    assert np.prod(h.values) == pytest.approx(4.0)     # det = 4


def test_eig_defective_warns():
    r = dc.eig([[1, 1], [0, 1]])
    assert r.values == pytest.approx([1, 1])
    assert [d.code for d in r.diagnostics] == ["DEFECTIVE_EIGENVECTORS"]


def test_eig_random_residual():
    a = RNG.standard_normal((8, 8))
    r = dc.eig(a)
    assert r.residual < 1e-12
    assert np.sum(r.values) == pytest.approx(np.trace(a), abs=1e-12)


def test_eigh_complex_hermitian():
    b = RNG.standard_normal((4, 4)) + 1j * RNG.standard_normal((4, 4))
    a = b + b.conj().T
    r = dc.eigh(a)
    assert np.isrealobj(r.values) and np.all(np.diff(r.values) >= 0)
    assert r.vectors.conj().T @ r.vectors == pytest.approx(np.eye(4), abs=1e-12)
    assert r.residual < 1e-12


def test_eigh_rejects_nonsymmetric_and_nonsquare():
    with pytest.raises(ValidationError):
        dc.eigh([[1, 2], [0, 1]])
    with pytest.raises(DimensionError):
        dc.eig(np.ones((2, 3)))


def test_inputs_not_mutated():
    a = np.array([[2.0, 1.0], [1.0, 3.0]])
    a0 = a.copy()
    dc.lu(a), dc.qr(a), dc.cholesky(a), dc.svd(a), dc.eig(a), dc.eigh(a)
    assert (a == a0).all()
