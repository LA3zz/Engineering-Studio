"""Linear algebra tests against analytic results (hand-derived values in comments)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, SingularMatrixError, ValidationError
from engstudio.engine import linalg as la


def test_solve_2x2_analytic():
    # 2x + y = 3, x + 3y = 5  ->  x = (9 - 5) / 5 = 0.8, y = 3 - 1.6 = 1.4
    r = la.solve([[2, 1], [1, 3]], [3, 5])
    assert r.x.shape == (2,)
    assert r.x == pytest.approx([0.8, 1.4], abs=1e-14)
    assert r.residual_norm < 1e-14
    assert r.diagnostics == ()
    assert 0.0 < r.rcond <= 1.0


def test_solve_matrix_rhs_keeps_shape():
    r = la.solve(np.eye(3) * 2, np.eye(3))
    assert r.x.shape == (3, 3)
    assert r.x == pytest.approx(np.eye(3) * 0.5)


def test_solve_complex():
    # diag(i, 2) x = [i, 4]  ->  x = [1, 2]
    r = la.solve([[1j, 0], [0, 2]], [1j, 4])
    assert r.x == pytest.approx([1, 2])


def test_solve_random_well_conditioned():
    rng = np.random.default_rng(12345)
    n = 25
    a = rng.standard_normal((n, n)) + n * np.eye(n)
    x_true = rng.standard_normal(n)
    r = la.solve(a, a @ x_true)
    assert r.x == pytest.approx(x_true, abs=1e-10)


def test_solve_exactly_singular():
    with pytest.raises(SingularMatrixError) as exc:
        la.solve([[1, 2], [2, 4]], [1, 2])
    assert getattr(exc.value, "rcond", None) is not None
    assert exc.value.rcond < 1e-15


def test_solve_zero_matrix_is_singular():
    with pytest.raises(SingularMatrixError):
        la.solve(np.zeros((3, 3)), [1, 2, 3])


def test_solve_ill_conditioned_warns():
    # diag(1, 1e-13): 1-norm condition number is exactly 1e13 -> rcond = 1e-13
    r = la.solve(np.diag([1.0, 1e-13]), [1.0, 1e-13])
    assert r.rcond == pytest.approx(1e-13, rel=1e-12)
    assert [d.severity for d in r.diagnostics] == ["warning"]
    assert r.diagnostics[0].code == "ILL_CONDITIONED"
    assert r.x == pytest.approx([1.0, 1.0])


def test_solve_below_eps_is_error():
    with pytest.raises(SingularMatrixError):
        la.solve(np.diag([1.0, 1e-17]), [1.0, 1.0])


def test_solve_dimension_errors():
    with pytest.raises(DimensionError):
        la.solve([[1, 2, 3], [4, 5, 6]], [1, 2])
    with pytest.raises(DimensionError):
        la.solve(np.eye(3), [1, 2])


def test_solve_rejects_nan():
    with pytest.raises(ValidationError):
        la.solve([[1, np.nan], [0, 1]], [1, 1])


def test_inv_analytic():
    # [[4,7],[2,6]]: det = 10, inverse = 1/10 [[6,-7],[-2,4]]
    r = la.inv([[4, 7], [2, 6]])
    assert r.value == pytest.approx(np.array([[0.6, -0.7], [-0.2, 0.4]]))
    assert r.diagnostics == ()


def test_inv_singular_and_warning():
    with pytest.raises(SingularMatrixError):
        la.inv([[1, 2], [2, 4]])
    assert la.inv(np.diag([1.0, 1e-13])).diagnostics[0].code == "ILL_CONDITIONED"


def test_rcond_values():
    assert la.rcond(np.eye(4)) == pytest.approx(1.0)
    assert la.rcond([[1, 2], [2, 4]]) == 0.0
    assert la.rcond(np.diag([1.0, 1e-3])) == pytest.approx(1e-3)


def test_det():
    assert la.det([[1, 2], [3, 4]]) == pytest.approx(-2.0)
    assert la.det(np.eye(3)) == pytest.approx(1.0)
    assert la.det([[2, 5, 1], [0, 3, 7], [0, 0, 4]]) == pytest.approx(24.0)  # product of diag
    assert la.det([[1j, 0], [0, 1j]]) == pytest.approx(-1.0)
    with pytest.raises(DimensionError):
        la.det([[1, 2, 3], [4, 5, 6]])


def test_trace_matmul_transpose():
    assert la.trace([[1, 2], [3, 4]]) == 5.0
    assert la.matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == pytest.approx(
        np.array([[19, 22], [43, 50]]))
    assert la.transpose([[1, 2, 3]]).shape == (3, 1)
    assert la.ctranspose([[1 + 2j, 3]])[0, 0] == 1 - 2j
    with pytest.raises(DimensionError):
        la.matmul(np.ones((2, 3)), np.ones((2, 3)))


def test_dot_and_cross():
    assert la.dot([1, 2, 3], [4, 5, 6]) == 32.0
    assert la.dot([1j], [1j]) == pytest.approx(1.0)  # conj(i) * i
    assert la.cross([1, 0, 0], [0, 1, 0]) == pytest.approx([0, 0, 1])
    assert la.cross([1, 2, 3], [4, 5, 6]) == pytest.approx([-3, 6, -3])
    with pytest.raises(DimensionError):
        la.dot([1, 2], [1, 2, 3])
    with pytest.raises(DimensionError):
        la.cross([1, 2], [3, 4])


def test_norms():
    assert la.norm([3, 4]) == pytest.approx(5.0)
    assert la.norm([3, -4], 1) == pytest.approx(7.0)
    assert la.norm([3, -4], np.inf) == pytest.approx(4.0)
    a = [[1, 2], [3, 4]]
    assert la.norm(a, "fro") == pytest.approx(math.sqrt(30))
    assert la.norm(a, 1) == pytest.approx(6.0)        # max column sum
    assert la.norm(a, np.inf) == pytest.approx(7.0)   # max row sum
    # A^T A = [[10,14],[14,20]], eigenvalues 15 +- sqrt(221)
    assert la.norm(a, 2) == pytest.approx(math.sqrt(15 + math.sqrt(221)))
    with pytest.raises(ValidationError):
        la.norm(a, 3)
    with pytest.raises(ValidationError):
        la.norm([1, 2], "bad")
    with pytest.raises(ValidationError):
        la.norm([1, 2], 0.5)


def test_rank():
    assert la.rank(np.eye(3)) == 3
    assert la.rank([[1, 2], [2, 4]]) == 1
    assert la.rank(np.zeros((3, 3))) == 0
    assert la.rank(np.outer([1, 2, 3], [4, 5, 6])) == 1
    assert la.rank([[1, 0, 0], [0, 1, 0]]) == 2
    assert la.rank(np.diag([1.0, 1e-3]), tol=1e-2) == 1
    with pytest.raises(ValidationError):
        la.rank(np.eye(2), tol=-1)


def test_cond():
    assert la.cond(np.eye(3)) == pytest.approx(1.0)
    assert la.cond(np.diag([1.0, 10.0])) == pytest.approx(10.0)
    assert la.cond(np.diag([1.0, 1e-3]), 1) == pytest.approx(1e3)
    # ||D||_F = sqrt(20), ||D^-1||_F = sqrt(1/4 + 1/16) = sqrt(5)/4  ->  product = 100^0.5/4 = 2.5
    assert la.cond(np.diag([2.0, 4.0]), "fro") == pytest.approx(2.5)
    assert la.cond([[1, 2], [2, 4]]) == float("inf")
    assert la.cond([[1, 2], [2, 4]], 1) == float("inf")
    with pytest.raises(DimensionError):
        la.cond(np.ones((2, 3)), 1)
    with pytest.raises(ValidationError):
        la.cond(np.eye(2), 3)


def test_inputs_not_mutated():
    a = np.array([[2.0, 1.0], [1.0, 3.0]])
    b = np.array([3.0, 5.0])
    a0, b0 = a.copy(), b.copy()
    la.solve(a, b)
    la.inv(a)
    la.rank(a)
    assert (a == a0).all() and (b == b0).all()
