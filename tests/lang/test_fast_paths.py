"""Scalar fast paths in lang.ops / lang.indexing must give exactly what the general code gives
(value, dtype, shape) or defer to it (errors, special cases)."""

import itertools

import numpy as np
import pytest

from engstudio.core.errors import EngStudioError
from engstudio.lang import indexing as ix
from engstudio.lang import ops

VALUES = [0.0, -0.0, 1.0, -1.0, 2.5, -2.5, 3.0, -3.0, 1e308, -1e-308, np.inf, -np.inf, np.nan,
          0.5, 7.0]
OPS = ["+", "-", ".*", "*", "./", "/", ".\\", "\\", ".^", "^", "==", "~=", "<", "<=", ">", ">="]


def general(op, a, b):
    if op in ops._MATRIX_OPS:
        return ops._MATRIX_OPS[op](op, a, b, [])
    return ops._BINARY[op](op, a, b)


def same(x, y):
    if x.shape != y.shape or x.dtype != y.dtype or not np.array_equal(x, y, equal_nan=True):
        return False
    if x.dtype.kind == "c":
        return np.array_equal(np.signbit(x.real), np.signbit(y.real)) and np.array_equal(
            np.signbit(x.imag), np.signbit(y.imag))
    return x.dtype.kind == "b" or np.array_equal(np.signbit(x), np.signbit(y))


@pytest.mark.parametrize("op", OPS)
def test_scalar_ops_match_general_path(op):
    for x, y in itertools.product(VALUES, VALUES):
        a, b = np.array([[x]]), np.array([[y]])
        fast = ops.binary_op(op, a, b, [])
        ref = general(op, a, b)
        assert same(np.asarray(fast), np.asarray(ref)), (op, x, y, fast, ref)


def test_non_double_operands_skip_the_fast_path():
    t = np.array([[True]])
    assert ops.binary_op("+", t, np.array([[1.0]])).item() == 2.0
    z = ops.binary_op("+", np.array([[1j]]), np.array([[1.0]]))
    assert z.dtype.kind == "c"


def test_build_matrix_fast_matches_general():
    a, b = np.array([[1.0, 2.0]]), np.array([[3.0, 4.0]])
    c = np.array([[5.0], [6.0]])
    for rows in ([[a], [b]], [[a, b]], [[np.array([[1.0]]), np.array([[2.0]])]],
                 [[c, c]], [[a]]):
        fast = ops.build_matrix(rows)
        ref = ops.vertcat([ops.horzcat(r) for r in rows])
        assert same(fast, ref)
    with pytest.raises(EngStudioError):
        ops.build_matrix([[a], [c]])  # mismatched sizes still get the general error
    assert ops.build_matrix([[np.zeros((0, 0)), a]]).shape == (1, 2)  # [] is skipped


def test_build_matrix_result_is_not_an_alias():
    a = np.array([[1.0, 2.0]])
    out = ops.build_matrix([[a]])
    assert not np.shares_memory(out, a)


@pytest.mark.parametrize("shape", [(1, 1), (3, 1), (1, 4), (3, 4)])
def test_scalar_index_matches_general(shape):
    v = np.arange(1.0, shape[0] * shape[1] + 1).reshape(shape, order="F")
    n = v.size
    for k in range(1, n + 1):
        fast = ix.index_value(v, [np.array([[float(k)]])])
        ref = ix._wrap(*_general(v, [np.array([[float(k)]])]))
        assert same(fast, ref)
    for i, j in itertools.product(range(1, shape[0] + 1), range(1, shape[1] + 1)):
        args = [np.array([[float(i)]]), np.array([[float(j)]])]
        assert same(ix.index_value(v, args), ix._wrap(*_general(v, args)))


def _general(v, args):
    kind, arr = ix._unwrap(v)
    return kind, ix._read(arr, ix._prep(args))


@pytest.mark.parametrize("bad", [0.0, 2.5, -1.0, 99.0, np.nan, np.inf])
def test_bad_scalar_index_still_errors(bad):
    with pytest.raises(EngStudioError):
        ix.index_value(np.array([[1.0, 2.0]]), [np.array([[bad]])])


def test_logical_and_bool_arrays_keep_general_semantics():
    v = np.array([[True, False]])
    assert ix.index_value(v, [np.array([[2.0]])]).dtype == np.bool_
    assert ix.index_value(np.array([[5.0, 6.0]]), [np.array([[True, False]])]).tolist() == [[5.0]]
