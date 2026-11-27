"""Tests for engstudio.lang.ops (T3.4a). Expected values are hand-computed or follow the
MATLAB documentation for implicit expansion, colon ranges and concatenation."""

import numpy as np
import pytest

from engstudio.core.errors import (
    DimensionError,
    NotSupportedError,
    SingularMatrixError,
    ValidationError,
)
from engstudio.lang import ops
from engstudio.lang.values import CellArray, CharArray, FunctionHandle, StructValue, to_value


def v(x):
    return to_value(x)


def check(actual, expected, dtype=None):
    expected = np.asarray(expected)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=0)
    if dtype is not None:
        assert actual.dtype == dtype


# ---------------------------------------------------------------- arithmetic
def test_elementwise_basic():
    check(ops.binary_op("+", v([1, 2, 3]), v([10, 20, 30])), [[11, 22, 33]])
    check(ops.binary_op("-", v(5), v([1, 2])), [[4, 3]])
    check(ops.binary_op(".*", v([1, 2]), v([3, 4])), [[3, 8]])
    check(ops.binary_op("./", v([1, 2]), v([2, 8])), [[0.5, 0.25]])
    check(ops.binary_op(".\\", v([2, 8]), v([1, 2])), [[0.5, 0.25]])
    check(ops.binary_op(".^", v([2, 3]), v(2)), [[4, 9]])


def test_implicit_expansion():
    out = ops.binary_op("+", v([1, 2, 3]), v([[10], [20]]))
    check(out, [[11, 12, 13], [21, 22, 23]])
    with pytest.raises(DimensionError):
        ops.binary_op("+", v([1, 2, 3]), v([1, 2]))
    with pytest.raises(DimensionError):
        ops.binary_op(".*", v([[1, 2], [3, 4]]), v([[1, 2, 3]]))


def test_bool_and_char_operands_become_double():
    out = ops.binary_op("+", v(True), v(True))
    check(out, [[2]], np.float64)
    check(ops.binary_op("+", CharArray.from_str("a"), v(1)), [[98]])
    check(ops.binary_op("-", CharArray.from_str("c"), CharArray.from_str("a")), [[2]])


def test_division_by_zero_gives_inf_and_nan():
    out = ops.binary_op("./", v([1, -1, 0]), v(0))
    assert out[0, 0] == np.inf and out[0, 1] == -np.inf and np.isnan(out[0, 2])


def test_power_branches():
    check(ops.binary_op(".^", v([4, 9]), v(0.5)), [[2, 3]], np.float64)
    check(ops.binary_op(".^", v(-2), v(2)), [[4]], np.float64)
    out = ops.binary_op(".^", v(-8), v(1 / 3))
    assert out.dtype == np.complex128
    np.testing.assert_allclose(out, [[1 + 1.7320508075688772j]], rtol=1e-14)
    check(ops.binary_op(".^", v(0), v(0)), [[1]])
    assert ops.binary_op(".^", v(0), v(-1))[0, 0] == np.inf


def test_complex_arithmetic_and_narrowing():
    out = ops.binary_op("*", v(2j), v(2j))
    check(out, [[-4]], np.float64)
    out = ops.binary_op("*", v(1 + 2j), v(1 - 2j))
    check(out, [[5]], np.float64)
    out = ops.binary_op("+", v(1 + 2j), v(1))
    assert out.dtype == np.complex128 and out[0, 0] == 2 + 2j


def test_matrix_multiply_known_result():
    a = v([[1, 2], [3, 4]])
    b = v([[5, 6], [7, 8]])
    check(ops.binary_op("*", a, b), [[19, 22], [43, 50]])
    check(ops.binary_op("*", v([1, 2, 3]), v([[4], [5], [6]])), [[32]])
    check(ops.binary_op("*", v([[4], [5], [6]]), v([1, 2, 3])),
          [[4, 8, 12], [5, 10, 15], [6, 12, 18]])
    check(ops.binary_op("*", v(2), a), [[2, 4], [6, 8]])
    check(ops.binary_op("*", a, v(2)), [[2, 4], [6, 8]])
    with pytest.raises(DimensionError, match="matrix multiplication"):
        ops.binary_op("*", v([1, 2, 3]), v([1, 2, 3]))


def test_division_forms():
    check(ops.binary_op("/", v([2, 4]), v(2)), [[1, 2]])
    check(ops.binary_op("\\", v(2), v([2, 4])), [[1, 2]])
    a = v([[1, 2], [3, 4]])
    # A\b: x = [0; 0.5] since 1*0+2*0.5 = 1 and 3*0+4*0.5 = 2
    check(ops.binary_op("\\", a, v([[1], [2]])), [[0], [0.5]])
    # b/A: x = [1 0] since [1 0]*A = [1 2]
    check(ops.binary_op("/", v([1, 2]), a), [[1, 0]])
    np.testing.assert_allclose(ops.binary_op("\\", a, a), np.eye(2), atol=1e-14)
    with pytest.raises(DimensionError):
        ops.binary_op("\\", a, v([1, 2]))
    with pytest.raises(DimensionError):
        ops.binary_op("/", v([1, 2, 3]), a)


def test_least_squares_for_non_square():
    # y = 1 + 2x through (1,3), (2,5), (3,7): exact fit, coefficients [1; 2]
    design = v([[1, 1], [1, 2], [1, 3]])
    check(ops.binary_op("\\", design, v([[3], [5], [7]])), [[1], [2]])
    out = ops.binary_op("\\", v([[1, 0], [0, 1], [1, 1]]), v([[1], [2], [3]]))
    np.testing.assert_allclose(out, [[1], [2]], atol=1e-14)
    assert ops.binary_op("\\", v(np.zeros((0, 0))), v(np.zeros((0, 0)))).shape == (0, 0)


def test_singular_and_ill_conditioned_division():
    with pytest.raises(SingularMatrixError):
        ops.binary_op("\\", v([[1, 2], [2, 4]]), v([[1], [2]]))
    hilbert = np.array([[1.0 / (i + j + 1) for j in range(10)] for i in range(10)])
    diag = []
    out = ops.binary_op("\\", hilbert, np.ones((10, 1)), diag)
    assert out.shape == (10, 1)
    assert len(diag) == 1 and diag[0].severity == "warning" and diag[0].code == "ILL_CONDITIONED"
    ops.binary_op("\\", v([[2, 0], [0, 2]]), v([[1], [1]]), diag)
    assert len(diag) == 1  # well-conditioned: nothing appended


def test_complex_matrix_division_not_supported():
    with pytest.raises(NotSupportedError):
        ops.binary_op("\\", v([[1j, 0], [0, 1]]), v([[1], [1]]))
    with pytest.raises(NotSupportedError):
        ops.binary_op("/", v([1, 1]), v([[1j, 0], [0, 1]]))


def test_matrix_power():
    a = v([[1, 1], [0, 1]])
    check(ops.binary_op("^", a, v(3)), [[1, 3], [0, 1]])
    check(ops.binary_op("^", a, v(0)), [[1, 0], [0, 1]])
    check(ops.binary_op("^", v(2), v(3)), [[8]])
    check(ops.binary_op("^", v([[2, 0], [0, 3]]), v(2)), [[4, 0], [0, 9]])
    check(ops.binary_op("^", a, v(-1)), [[1, -1], [0, 1]])
    check(ops.binary_op("^", a, v(-2)), [[1, -2], [0, 1]])
    with pytest.raises(DimensionError):
        ops.binary_op("^", v([[1, 2, 3], [4, 5, 6]]), v(2))
    with pytest.raises(DimensionError):
        ops.binary_op("^", v(2), a)
    with pytest.raises(NotSupportedError):
        ops.binary_op("^", a, v(0.5))
    with pytest.raises(NotSupportedError):
        ops.binary_op("^", a, v(np.inf))
    with pytest.raises(SingularMatrixError):
        ops.binary_op("^", v([[1, 2], [2, 4]]), v(-1))
    with pytest.raises(NotSupportedError):
        ops.binary_op("^", v([[1j, 0], [0, 1]]), v(-1))


def test_undefined_operands():
    cell = CellArray.empty(1, 1)
    for bad in (cell, StructValue(), FunctionHandle(name="f")):
        with pytest.raises(ValidationError, match="undefined for"):
            ops.binary_op("+", v(1), bad)
        with pytest.raises(ValidationError):
            ops.binary_op("==", bad, v(1))
        with pytest.raises(ValidationError):
            ops.binary_op("&", bad, v(1))
        with pytest.raises(ValidationError):
            ops.unary_op("-", bad)
    with pytest.raises(ValidationError):
        ops.binary_op("**", v(1), v(1))
    with pytest.raises(ValidationError):
        ops.binary_op("&&", v(1), v(1))


# --------------------------------------------------------------- comparisons
def test_comparisons():
    check(ops.binary_op("<", v([1, 2, 3]), v(2)), [[True, False, False]], np.bool_)
    check(ops.binary_op("<=", v([1, 2, 3]), v(2)), [[True, True, False]])
    check(ops.binary_op(">", v([1, 2, 3]), v(2)), [[False, False, True]])
    check(ops.binary_op(">=", v([1, 2, 3]), v(2)), [[False, True, True]])
    check(ops.binary_op("==", v([1, 2]), v([1, 3])), [[True, False]])
    check(ops.binary_op("~=", v([1, 2]), v([1, 3])), [[False, True]])
    check(ops.binary_op("==", CharArray.from_str("abc"), CharArray.from_str("abd")),
          [[True, True, False]])
    out = ops.binary_op("==", v([np.nan]), v([np.nan]))
    assert not out[0, 0]
    assert ops.binary_op("~=", v(np.nan), v(np.nan))[0, 0]


def test_complex_comparisons():
    assert ops.binary_op("<", v(1 + 5j), v(2 + 0j))[0, 0]  # real parts only
    assert not ops.binary_op("==", v(1 + 5j), v(1))[0, 0]  # equality uses both parts
    assert ops.binary_op("==", v(1 + 0j), v(1))[0, 0]


# ------------------------------------------------------------------- logical
def test_logical_ops():
    check(ops.binary_op("&", v([1, 0, 1]), v([1, 1, 0])), [[True, False, False]], np.bool_)
    check(ops.binary_op("|", v([1, 0, 0]), v([0, 0, 1])), [[True, False, True]])
    with pytest.raises(ValidationError, match="NaN"):
        ops.binary_op("&", v(np.nan), v(1))
    with pytest.raises(DimensionError):
        ops.binary_op("|", v([1, 0]), v([1, 0, 1]))


def test_unary_ops():
    check(ops.unary_op("-", v(True)), [[-1]], np.float64)
    check(ops.unary_op("-", v([1, -2])), [[-1, 2]])
    check(ops.unary_op("+", CharArray.from_str("a")), [[97]], np.float64)
    check(ops.unary_op("~", v([0, 2])), [[True, False]], np.bool_)
    with pytest.raises(ValidationError):
        ops.unary_op("~", v(np.nan))
    with pytest.raises(ValidationError):
        ops.unary_op("!", v(1))


def test_to_logical_scalar():
    assert ops.to_logical_scalar(v(2), "&&") is True
    assert ops.to_logical_scalar(v(0), "||") is False
    assert ops.to_logical_scalar(v(True), "&&") is True
    for bad in (v([1, 1]), v(np.zeros((0, 0)))):
        with pytest.raises(ValidationError, match="logical scalar"):
            ops.to_logical_scalar(bad, "&&")
    with pytest.raises(ValidationError):
        ops.to_logical_scalar(v(np.nan), "||")


# ----------------------------------------------------------------- transpose
def test_transpose():
    z = v([[1 + 1j, 2], [3, 4 - 2j]])
    check(ops.transpose(z, True), [[1 - 1j, 3], [2, 4 + 2j]])
    check(ops.transpose(z, False), [[1 + 1j, 3], [2, 4 - 2j]])
    check(ops.transpose(v([1, 2, 3]), True), [[1], [2], [3]])
    c = ops.transpose(CharArray.from_str("ab"), True)
    assert isinstance(c, CharArray) and c.shape == (2, 1)
    cell = ops.transpose(CellArray.from_rows([[1, 2, 3]]), False)
    assert isinstance(cell, CellArray) and cell.shape == (3, 1)
    with pytest.raises(ValidationError):
        ops.transpose(StructValue(), True)


# -------------------------------------------------------------------- ranges
def rng(a, b, c=None):
    return ops.colon_range(v(a), None if b is None else v(b), v(c))


def test_ranges():
    check(rng(1, None, 5), [[1, 2, 3, 4, 5]])
    check(rng(1, 2, 10), [[1, 3, 5, 7, 9]])
    check(rng(5, -1, 1), [[5, 4, 3, 2, 1]])
    check(rng(10, -2.5, 0), [[10, 7.5, 5, 2.5, 0]])
    check(rng(3, None, 3), [[3]])
    check(rng(1.5, None, 4), [[1.5, 2.5, 3.5]])


def test_empty_ranges():
    assert rng(1, None, 0).shape == (1, 0)
    assert rng(1, -1, 5).shape == (1, 0)
    assert rng(1, 0, 5).shape == (1, 0)
    assert ops.colon_range(v(np.zeros((0, 0))), None, v(5)).shape == (1, 0)


def test_range_floating_point_tolerance():
    out = rng(0, 0.1, 0.3)
    assert out.shape == (1, 4) and out[0, -1] == 0.3
    assert rng(0, 0.1, 1).shape == (1, 11)
    out = rng(1, 0.1, 2)
    assert out.shape == (1, 11) and out[0, -1] <= 2.0


def test_range_operand_rules():
    check(ops.colon_range(v(True), None, v(3)), [[1, 2, 3]])
    check(ops.colon_range(CharArray.from_str("a"), None, CharArray.from_str("c")),
          [[97, 98, 99]])
    with pytest.raises(ValidationError, match="scalars"):
        ops.colon_range(v([1, 2]), None, v(5))
    with pytest.raises(ValidationError, match="finite"):
        ops.colon_range(v(1), None, v(np.inf))
    with pytest.raises(ValidationError, match="finite"):
        ops.colon_range(v(np.nan), None, v(3))
    with pytest.raises(ValidationError):
        ops.colon_range(v(1), None, CellArray.empty(1, 1))
    with pytest.raises(ValidationError, match="Maximum variable size"):
        ops.colon_range(v(1), None, v(1e12))


# ------------------------------------------------------------ concatenation
def test_horzcat_vertcat_numeric():
    check(ops.horzcat([v([1, 2]), v(3)]), [[1, 2, 3]])
    check(ops.vertcat([v([1, 2]), v([3, 4])]), [[1, 2], [3, 4]])
    check(ops.horzcat([v([[1], [2]]), v([[3], [4]])]), [[1, 3], [2, 4]])
    check(ops.horzcat([v(np.zeros((0, 0))), v(1), v(2)]), [[1, 2]])
    check(ops.vertcat([v(np.zeros((0, 0))), v([1, 2])]), [[1, 2]])
    out = ops.horzcat([v(1), v(np.zeros((1, 0)))])
    check(out, [[1]])


def test_concat_dtype_promotion():
    assert ops.horzcat([v(True), v(False)]).dtype == np.bool_
    assert ops.horzcat([v(True), v(2)]).dtype == np.float64
    assert ops.horzcat([v(1), v(2j)]).dtype == np.complex128


def test_concat_mismatch_messages():
    with pytest.raises(DimensionError, match=r"Horizontal dimensions mismatch \(1x2 vs 2x1\)"):
        ops.horzcat([v([1, 2]), v([[1], [2]])])
    with pytest.raises(DimensionError, match=r"Vertical dimensions mismatch \(1x2 vs 1x3\)"):
        ops.vertcat([v([1, 2]), v([1, 2, 3])])


def test_concat_empty_results():
    assert ops.horzcat([]).shape == (0, 0)
    assert ops.horzcat([v([]), v([])]).shape == (0, 0)
    out = ops.horzcat([CharArray.from_str(""), CharArray.from_str("")])
    assert isinstance(out, CharArray) and out.shape == (0, 0)
    out = ops.horzcat([CellArray.empty(0, 0)])
    assert isinstance(out, CellArray) and out.shape == (0, 0)


def test_char_concat():
    out = ops.horzcat([CharArray.from_str("ab"), CharArray.from_str("cd")])
    assert out == CharArray.from_str("abcd")
    out = ops.horzcat([v(65), CharArray.from_str("b")])
    assert out == CharArray.from_str("Ab")
    out = ops.horzcat([CharArray.from_str(""), CharArray.from_str("a")])
    assert out == CharArray.from_str("a")
    out = ops.vertcat([CharArray.from_str("ab"), CharArray.from_str("cd")])
    assert out.shape == (2, 2)
    with pytest.raises(DimensionError):
        ops.vertcat([CharArray.from_str("ab"), CharArray.from_str("c")])
    with pytest.raises(ValidationError, match="character codes"):
        ops.horzcat([v(1.5), CharArray.from_str("a")])
    with pytest.raises(ValidationError, match="character codes"):
        ops.horzcat([v(-1), CharArray.from_str("a")])


def test_cell_concat_and_unsupported():
    a, b = CellArray.from_rows([[1]]), CellArray.from_rows([[2, 3]])
    assert ops.horzcat([a, b]).shape == (1, 3)
    assert ops.vertcat([a, a]).shape == (2, 1)
    with pytest.raises(NotSupportedError):
        ops.horzcat([a, v(1)])
    with pytest.raises(NotSupportedError):
        ops.horzcat([StructValue(), StructValue()])
    with pytest.raises(NotSupportedError):
        ops.vertcat([FunctionHandle(name="f")])


def test_build_matrix():
    check(ops.build_matrix([[v(1), v(2)], [v(3), v(4)]]), [[1, 2], [3, 4]])
    assert ops.build_matrix([]).shape == (0, 0)
    check(ops.build_matrix([[v([1, 2]), v(3)], [v(4), v(5), v(6)]]), [[1, 2, 3], [4, 5, 6]])
    out = ops.build_matrix([[CharArray.from_str("ab")], [CharArray.from_str("cd")]])
    assert out.shape == (2, 2)
    with pytest.raises(DimensionError):
        ops.build_matrix([[v(1), v(2)], [v(3)]])


def test_build_cell():
    c = ops.build_cell([[v(1), CharArray.from_str("a")], [v(2), CharArray.from_str("b")]])
    assert c.shape == (2, 2)
    assert c.data[1, 1] == CharArray.from_str("b") and c.data[0, 0][0, 0] == 1.0
    assert ops.build_cell([]).shape == (0, 0)
    nested = ops.build_cell([[CellArray.from_rows([[1, 2]]), v(3)]])
    assert nested.shape == (1, 2) and isinstance(nested.data[0, 0], CellArray)
    with pytest.raises(DimensionError):
        ops.build_cell([[v(1), v(2)], [v(3)]])


def test_inputs_are_not_mutated():
    a = v([[1, 2], [3, 4]])
    b = v([[5, 6], [7, 8]])
    snapshot = (a.copy(), b.copy())
    for op in ("+", "*", ".^", "<", "&"):
        ops.binary_op(op, a, b)
    ops.transpose(a, True)
    ops.horzcat([a, b])
    np.testing.assert_array_equal(a, snapshot[0])
    np.testing.assert_array_equal(b, snapshot[1])
