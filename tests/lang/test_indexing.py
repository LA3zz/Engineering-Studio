"""Tests for engstudio.lang.indexing (T3.4b). Expected results follow MATLAB's documented
indexing rules (column-major order, result shapes, growth, deletion)."""

import numpy as np
import pytest

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang import indexing as ix
from engstudio.lang.indexing import COLON
from engstudio.lang.ops import colon_range
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    to_value,
)


def v(x):
    return to_value(x)


def check(actual, expected, dtype=None):
    expected = np.asarray(expected)
    assert isinstance(actual, np.ndarray)
    assert actual.shape == expected.shape, (actual.shape, expected.shape)
    np.testing.assert_array_equal(actual, expected)
    if dtype is not None:
        assert actual.dtype == dtype


ROW = [10, 20, 30, 40, 50]
MAT = [[1, 2, 3], [4, 5, 6]]


# ---------------------------------------------------------------- reading
def test_linear_index_on_row():
    x = v(ROW)
    check(ix.index_value(x, [v(3)]), [[30]])
    check(ix.index_value(x, [v([1, 3, 5])]), [[10, 30, 50]])
    check(ix.index_value(x, [v([[1], [2]])]), [[10, 20]])  # source orientation wins
    check(ix.index_value(x, [colon_range(v(2), None, v(4))]), [[20, 30, 40]])
    check(ix.index_value(x, [v([5, 5, 1])]), [[50, 50, 10]])


def test_linear_index_on_column_and_scalar():
    col = v([[1], [2], [3]])
    check(ix.index_value(col, [v([1, 2])]), [[1], [2]])
    check(ix.index_value(v(7), [v([1, 1, 1])]), [[7, 7, 7]])
    check(ix.index_value(v(7), [v([[1], [1]])]), [[7], [7]])


def test_colon_and_empty_index():
    x = v(ROW)
    check(ix.index_value(x, [COLON]), np.array(ROW, dtype=float).reshape(5, 1))
    assert ix.index_value(x, [v([])]).shape == (0, 0)
    assert ix.index_value(x, [np.zeros((1, 0))]).shape == (1, 0)
    check(ix.index_value(v(MAT), [COLON]), [[1], [4], [2], [5], [3], [6]])


def test_matrix_linear_index_is_column_major():
    a = v(MAT)
    check(ix.index_value(a, [v(4)]), [[5]])
    check(ix.index_value(a, [v([1, 2, 3])]), [[1, 4, 2]])
    check(ix.index_value(a, [v([[1, 2], [3, 4]])]), [[1, 4], [2, 5]])


def test_two_index():
    a = v(MAT)
    check(ix.index_value(a, [v(2), v(3)]), [[6]])
    check(ix.index_value(a, [COLON, v(2)]), [[2], [5]])
    check(ix.index_value(a, [v(1), COLON]), [[1, 2, 3]])
    check(ix.index_value(a, [v([1, 2]), v([1, 3])]), [[1, 3], [4, 6]])
    check(ix.index_value(a, [COLON, COLON]), MAT)
    check(ix.index_value(a, [v([2, 1]), v(1)]), [[4], [1]])


def test_logical_masks():
    x = v(ROW)
    mask = np.array([[False, False, True, True, True]])
    check(ix.index_value(x, [mask]), [[30, 40, 50]])
    a = v(MAT)
    check(ix.index_value(a, [a > 3]), [[4], [5], [6]])  # matrix mask -> column
    check(ix.index_value(a, [np.array([[False, True]]), COLON]), [[4, 5, 6]])
    check(ix.index_value(a, [COLON, np.array([[True, False, True]])]), [[1, 3], [4, 6]])
    assert ix.index_value(x, [np.zeros((1, 5), dtype=bool)]).shape == (1, 0)


def test_trailing_ones_allowed():
    a = v(MAT)
    check(ix.index_value(a, [v(2), v(3), v(1)]), [[6]])
    check(ix.index_value(a, [v(2), v(3), COLON]), [[6]])
    with pytest.raises(ValidationError, match="position 3"):
        ix.index_value(a, [v(2), v(3), v(2)])


def test_read_errors():
    x, a = v(ROW), v(MAT)
    with pytest.raises(ValidationError, match="positive integers"):
        ix.index_value(x, [v(0)])
    with pytest.raises(ValidationError, match="positive integers"):
        ix.index_value(x, [v(1.5)])
    with pytest.raises(ValidationError, match="positive integers"):
        ix.index_value(x, [v(-1)])
    with pytest.raises(ValidationError, match="positive integers"):
        ix.index_value(x, [v(1j)])
    with pytest.raises(ValidationError, match="positive integers"):
        ix.index_value(x, [v(np.nan)])
    with pytest.raises(ValidationError, match="must not exceed 5"):
        ix.index_value(x, [v(6)])
    with pytest.raises(ValidationError, match=r"position 1 exceeds array bounds.*2"):
        ix.index_value(a, [v(3), v(1)])
    with pytest.raises(ValidationError, match=r"position 2 exceeds array bounds.*3"):
        ix.index_value(a, [v(1), v(4)])
    with pytest.raises(ValidationError, match="Subscript indices"):
        ix.index_value(x, [CellArray.empty(1, 1)])
    with pytest.raises(ValidationError, match="Subscript indices"):
        ix.index_value(x, [CharArray.from_str("a")])
    with pytest.raises(ValidationError):
        ix.index_value(FunctionHandle(name="sin"), [v(1)])
    with pytest.raises(ValidationError, match="must not exceed 6"):
        ix.index_value(a, [np.array([[True] * 7])])


def test_no_args_returns_copy():
    x = v(ROW)
    out = ix.index_value(x, [])
    check(out, [ROW])
    assert out is not x


def test_results_do_not_alias_the_source():
    x = v(ROW)
    out = ix.index_value(x, [COLON])
    out[0, 0] = 99
    out2 = ix.index_value(x, [v([1, 2])])
    out2[0, 0] = 99
    out3 = ix.index_value(v(MAT), [COLON, COLON])
    out3[0, 0] = 99
    assert x[0, 0] == 10.0


def test_char_and_cell_reads():
    s = CharArray.from_str("hello")
    assert ix.index_value(s, [v([1, 5])]) == CharArray.from_str("ho")
    assert ix.index_value(s, [COLON]).shape == (5, 1)
    c = CellArray.from_rows([[1, "a", [1, 2, 3]]])
    sub = ix.index_value(c, [v(2)])
    assert isinstance(sub, CellArray) and sub.shape == (1, 1)
    assert sub.data[0, 0] == CharArray.from_str("a")
    assert ix.index_value(c, [v([1, 3])]).shape == (1, 2)
    with pytest.raises(ValidationError):
        ix.index_value(c, [v(4)])


def test_cell_contents():
    c = CellArray.from_rows([[1, "a", [1, 2, 3]], [4, "b", 6]])
    check(ix.cell_contents(c, [v(1), v(3)])[0], [[1, 2, 3]])
    items = ix.cell_contents(c, [COLON])
    assert len(items) == 6
    assert items[0][0, 0] == 1.0 and items[1][0, 0] == 4.0  # column-major
    assert ix.cell_contents(c, [v(2), COLON])[1] == CharArray.from_str("b")
    assert ix.cell_contents(c, [v([])]) == []
    with pytest.raises(ValidationError, match="Brace indexing"):
        ix.cell_contents(v(ROW), [v(1)])
    with pytest.raises(ValidationError):
        ix.cell_contents(c, [v(7)])


def test_struct_paren_read():
    s = StructValue({"a": 1})
    assert ix.index_value(s, [v(1)]) is s
    assert ix.index_value(s, [v(1), v(1)]) is s
    with pytest.raises(ValidationError):
        ix.index_value(s, [v(2)])
    with pytest.raises(NotSupportedError):
        ix.index_value(s, [v([1, 1])])


def test_end_value():
    a = v(MAT)
    assert ix.end_value(a, 0, 1) == 6
    assert ix.end_value(a, 0, 2) == 2
    assert ix.end_value(a, 1, 2) == 3
    assert ix.end_value(a, 2, 3) == 1
    assert ix.end_value(CharArray.from_str("abc"), 0, 1) == 3
    assert ix.end_value(CellArray.empty(2, 2), 1, 2) == 2
    assert ix.end_value(StructValue(), 0, 1) == 1
    assert ix.end_value(v([]), 0, 1) == 0
    with pytest.raises(ValidationError):
        ix.end_value(3, 0, 1)


# ---------------------------------------------------------------- assignment
def test_assign_basic_and_no_mutation():
    x = v([1, 2, 3])
    out = ix.assign_index(x, [v(2)], v(20))
    check(out, [[1, 20, 3]])
    check(x, [[1, 2, 3]])
    check(ix.assign_index(x, [v([1, 3])], v([7, 9])), [[7, 2, 9]])
    check(ix.assign_index(x, [v([1, 3])], v(0)), [[0, 2, 0]])
    check(ix.assign_index(x, [COLON], v(5)), [[5, 5, 5]])
    check(ix.assign_index(x, [COLON], v([[7], [8], [9]])), [[7, 8, 9]])


def test_assign_with_mask():
    x = v([1, 5, 2, 8])
    check(ix.assign_index(x, [x > 3], v(0)), [[1, 0, 2, 0]])
    a = v(MAT)
    check(ix.assign_index(a, [a > 4], v(0)), [[1, 2, 3], [4, 0, 0]])


def test_repeated_index_last_wins():
    check(ix.assign_index(v([1, 2]), [v([1, 1])], v([5, 6])), [[6, 2]])


def test_linear_growth():
    check(ix.assign_index(v([1, 2, 3]), [v(5)], v(7)), [[1, 2, 3, 0, 7]])
    check(ix.assign_index(None, [v(3)], v(5)), [[0, 0, 5]])
    check(ix.assign_index(v([]), [v(2)], v(5)), [[0, 5]])
    check(ix.assign_index(v(5), [v(3)], v(1)), [[5, 0, 1]])
    check(ix.assign_index(v([[1], [2]]), [v(4)], v(9)), [[1], [2], [0], [9]])
    check(ix.assign_index(v([1, 2]), [v(3)], v(3)), [[1, 2, 3]])
    with pytest.raises(ValidationError, match="ambiguous dimension"):
        ix.assign_index(v(MAT), [v(10)], v(1))
    # end+1 idiom
    x = v([1, 2])
    n = ix.end_value(x, 0, 1)
    check(ix.assign_index(x, [v(n + 1)], v(3)), [[1, 2, 3]])


def test_two_index_assign_and_growth():
    a = v([[1, 2], [3, 4]])
    check(ix.assign_index(a, [v(1), v(2)], v(9)), [[1, 9], [3, 4]])
    check(ix.assign_index(a, [v(3), v(3)], v(9)), [[1, 2, 0], [3, 4, 0], [0, 0, 9]])
    check(ix.assign_index(a, [COLON, v(1)], v([7, 8])), [[7, 2], [8, 4]])
    check(ix.assign_index(a, [v(1), COLON], v([9, 9])), [[9, 9], [3, 4]])
    check(ix.assign_index(a, [v(1), COLON], v(0)), [[0, 0], [3, 4]])
    check(ix.assign_index(a, [COLON, COLON], v(1)), [[1, 1], [1, 1]])
    check(ix.assign_index(a, [v([1, 2]), v([1, 2])], v([[5, 6], [7, 8]])), [[5, 6], [7, 8]])
    check(ix.assign_index(None, [v(2), v(2)], v(1)), [[0, 0], [0, 1]])
    check(ix.assign_index(a, [v(1), v(3)], v(5)), [[1, 2, 5], [3, 4, 0]])


def test_assign_colon_linear_uses_column_major():
    a = v([[1, 2], [3, 4]])
    check(ix.assign_index(a, [COLON], v([1, 2, 3, 4])), [[1, 3], [2, 4]])
    with pytest.raises(ValidationError, match="different number of elements"):
        ix.assign_index(a, [COLON], v([1, 2, 3]))


def test_two_index_squeezed_shapes_and_colon_on_empty():
    z = v(np.zeros((3, 3)))
    check(ix.assign_index(z, [v(1), COLON], v([[1], [2], [3]])),
          [[1, 2, 3], [0, 0, 0], [0, 0, 0]])
    check(ix.assign_index(v([]), [COLON, v(1)], v([[1], [2], [3]])), [[1], [2], [3]])
    check(ix.assign_index(v([]), [COLON, v(1)], v([1, 2, 3])), [[1], [2], [3]])
    check(ix.assign_index(v([]), [v(1), COLON], v([1, 2, 3])), [[1, 2, 3]])
    check(ix.assign_index(v([]), [COLON, COLON], v([[1, 2]])), [[1, 2]])
    with pytest.raises(ValidationError, match="size of the left side is 2-by-2"):
        ix.assign_index(v(MAT), [v([1, 2]), v([1, 2])], v([1, 2, 3]))
    with pytest.raises(ValidationError, match="left side is 1-by-3"):
        ix.assign_index(v(MAT), [v(1), COLON], v([[1, 2], [3, 4]]))


def test_assign_trailing_ones():
    check(ix.assign_index(v(MAT), [v(1), v(1), v(1)], v(0)), [[0, 2, 3], [4, 5, 6]])
    with pytest.raises(ValidationError, match="position 3"):
        ix.assign_index(v(MAT), [v(1), v(1), v(2)], v(0))


def test_class_promotion():
    out = ix.assign_index(v([True, False]), [v(1)], v(5))
    assert out.dtype == np.float64
    check(out, [[5, 0]])
    out = ix.assign_index(v([1.0, 2.0]), [v(1)], v(True))
    assert out.dtype == np.float64
    out = ix.assign_index(v([True, False]), [v(2)], v(True))
    assert out.dtype == np.bool_
    out = ix.assign_index(None, [v(2)], v(True))
    assert out.dtype == np.bool_
    check(out, [[False, True]])
    out = ix.assign_index(v([1.0, 2.0]), [v(1)], v(1j))
    assert out.dtype == np.complex128
    out = ix.assign_index(v([1.0, 2.0]), [v(2)], CharArray.from_str("a"))
    check(out, [[1, 97]], np.float64)


def test_char_assignment():
    s = CharArray.from_str("abc")
    assert ix.assign_index(s, [v(2)], v(100)) == CharArray.from_str("adc")
    assert ix.assign_index(s, [v(2)], CharArray.from_str("X")) == CharArray.from_str("aXc")
    assert ix.assign_index(v([]), [v([1, 2, 3])], CharArray.from_str("abc")) == s
    padded = ix.assign_index(None, [v(3)], CharArray.from_str("x"))
    assert padded.shape == (1, 3) and padded.to_str() == "\x00\x00x"
    np.testing.assert_array_equal(padded.codes(), [[0, 0, 120]])
    assert s == CharArray.from_str("abc")
    with pytest.raises(ValidationError, match="character codes"):
        ix.assign_index(s, [v(1)], v(1.5))


def test_cell_paren_assignment():
    c = CellArray.from_rows([[1, 2]])
    out = ix.assign_index(c, [v(2)], CellArray.from_rows([["x"]]))
    assert out.data[0, 1] == CharArray.from_str("x") and out.shape == (1, 2)
    grown = ix.assign_index(c, [v(4)], CellArray.from_rows([[7]]))
    assert grown.shape == (1, 4)
    assert grown.data[0, 2].shape == (0, 0) and grown.data[0, 3][0, 0] == 7.0
    assert c.shape == (1, 2)
    wide = ix.assign_index(c, [v(1)], CellArray.from_rows([[8]]))
    assert wide.data[0, 0][0, 0] == 8.0
    with pytest.raises(ValidationError, match="Conversion to cell from double"):
        ix.assign_index(c, [v(1)], v(5))
    with pytest.raises(ValidationError, match="Conversion to double from cell"):
        ix.assign_index(v([1, 2]), [v(1)], CellArray.from_rows([[1]]))
    out = ix.assign_index(v([]), [v(2)], CellArray.from_rows([[1]]))
    assert isinstance(out, CellArray) and out.shape == (1, 2)
    out = ix.assign_index(None, [v(1), v(2)], CellArray.from_rows([[1]]))
    assert out.shape == (1, 2)


def test_assign_type_errors():
    with pytest.raises(NotSupportedError):
        ix.assign_index(None, [v(1)], StructValue({"a": 1}))
    with pytest.raises(ValidationError):
        ix.assign_index(v([1, 2]), [v(1)], StructValue({"a": 1}))
    with pytest.raises(NotSupportedError):
        ix.assign_index(StructValue(), [v(1)], v(1))
    with pytest.raises(ValidationError):
        ix.assign_index(FunctionHandle(name="f"), [v(1)], v(1))
    with pytest.raises(ValidationError, match="positive integers"):
        ix.assign_index(v([1, 2]), [v(0)], v(1))
    with pytest.raises(ValidationError, match="at least one index"):
        ix.assign_index(v([1, 2]), [], v(1))


# ------------------------------------------------------------------ deletion
def test_delete_linear():
    x = v([1, 2, 3, 4, 5])
    check(ix.assign_index(x, [v(2)], v([])), [[1, 3, 4, 5]])
    check(ix.assign_index(x, [v([1, 5])], v([])), [[2, 3, 4]])
    check(ix.assign_index(v([[1], [2], [3]]), [v(2)], v([])), [[1], [3]])
    check(ix.assign_index(v(MAT), [v(1)], v([])), [[4, 2, 5, 3, 6]])
    check(ix.assign_index(v(5), [v(1)], v([])), np.zeros((1, 0)))
    assert ix.assign_index(x, [COLON], v([])).shape == (0, 0)
    check(ix.assign_index(x, [v([])], v([])), [[1, 2, 3, 4, 5]])
    check(x, [[1, 2, 3, 4, 5]])
    check(ix.assign_index(x, [x > 3], v([])), [[1, 2, 3]])
    with pytest.raises(ValidationError, match="must not exceed 5"):
        ix.assign_index(x, [v(6)], v([]))
    with pytest.raises(ValidationError):
        ix.assign_index(None, [v(1)], v([]))


def test_delete_rows_and_columns():
    a = v([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    check(ix.assign_index(a, [v(2), COLON], v([])), [[1, 2, 3], [7, 8, 9]])
    check(ix.assign_index(a, [COLON, v([1, 3])], v([])), [[2], [5], [8]])
    check(ix.assign_index(a, [v([1, 2, 3]), v(2)], v([])), [[1, 3], [4, 6], [7, 9]])
    with pytest.raises(ValidationError, match="only one non-colon index"):
        ix.assign_index(a, [v(1), v(1)], v([]))
    with pytest.raises(ValidationError, match="exceeds array bounds"):
        ix.assign_index(a, [v(4), COLON], v([]))


def test_delete_in_char_and_cell():
    assert ix.assign_index(CharArray.from_str("abc"), [v(2)], v([])) == CharArray.from_str("ac")
    c = CellArray.from_rows([[1, "a", 3]])
    out = ix.assign_index(c, [v(2)], v([]))
    assert out.shape == (1, 2) and out.data[0, 1][0, 0] == 3.0
    # a 0-by-0 double inside a cell is stored, not deleted
    kept = ix.assign_cell_content(c, [v(2)], v([]))
    assert kept.shape == (1, 3) and kept.data[0, 1].shape == (0, 0)


# -------------------------------------------------------------- cell braces
def test_assign_cell_content():
    out = ix.assign_cell_content(None, [v(2)], v(5))
    assert isinstance(out, CellArray) and out.shape == (1, 2)
    assert out.data[0, 0].shape == (0, 0) and out.data[0, 1][0, 0] == 5.0
    out2 = ix.assign_cell_content(out, [v(1)], "x")
    assert out2.data[0, 0] == CharArray.from_str("x")
    assert out.data[0, 0].shape == (0, 0)  # original untouched
    out3 = ix.assign_cell_content(v([]), [v(1), v(1)], v(1))
    assert out3.shape == (1, 1)
    nested = ix.assign_cell_content(out, [v(1)], CellArray.from_rows([[1, 2]]))
    assert isinstance(nested.data[0, 0], CellArray)
    with pytest.raises(ValidationError, match="exactly one element"):
        ix.assign_cell_content(out, [v([1, 2])], v(1))
    with pytest.raises(ValidationError, match="exactly one element"):
        ix.assign_cell_content(out, [COLON], v(1))
    with pytest.raises(ValidationError, match="Cannot assign with"):
        ix.assign_cell_content(v([1, 2]), [v(1)], v(1))
    with pytest.raises(ValidationError, match="at least one index"):
        ix.assign_cell_content(out, [], v(1))


# ------------------------------------------------------------------- structs
def test_struct_fields():
    s = ix.set_field(None, "a", 1)
    assert isinstance(s, StructValue) and s.get("a")[0, 0] == 1.0
    s2 = ix.set_field(s, "b", "txt")
    assert s2.names() == ("a", "b") and s.names() == ("a",)
    assert ix.get_field(s2, "b") == CharArray.from_str("txt")
    assert ix.set_field(v([]), "x", 2).names() == ("x",)
    with pytest.raises(ValidationError, match="non-existent field"):
        ix.get_field(s, "zz")
    with pytest.raises(ValidationError, match="Dot indexing"):
        ix.get_field(v(1), "a")
    with pytest.raises(ValidationError, match="Dot indexing"):
        ix.set_field(v([1, 2]), "a", 1)
    with pytest.raises(ValidationError):
        ix.set_field(None, "1bad", 1)
