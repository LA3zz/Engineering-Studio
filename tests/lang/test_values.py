"""Tests for engstudio.lang.values (T3.4a): the interpreter value model."""

import numpy as np
import pytest

from engstudio.core.errors import NotSupportedError, ValidationError
from engstudio.lang import ast as A
from engstudio.lang.values import (
    CellArray,
    CharArray,
    FunctionHandle,
    StructValue,
    class_of,
    empty_double,
    is_empty,
    is_true,
    is_value,
    numel_of,
    size_of,
    to_value,
    values_equal,
)


def test_to_value_numbers():
    x = to_value(3)
    assert x.shape == (1, 1) and x.dtype == np.float64 and x[0, 0] == 3.0
    assert to_value(2.5)[0, 0] == 2.5
    z = to_value(1 + 2j)
    assert z.dtype == np.complex128 and z.shape == (1, 1)
    b = to_value(True)
    assert b.dtype == np.bool_ and b.shape == (1, 1)
    assert to_value(np.float32(1.5)).dtype == np.float64


def test_to_value_sequences():
    row = to_value([1, 2, 3])
    assert row.shape == (1, 3) and row.dtype == np.float64
    mat = to_value([[1, 2], [3, 4]])
    assert mat.shape == (2, 2)
    assert to_value([]).shape == (0, 0)
    assert to_value(np.array([True, False])).dtype == np.bool_
    assert to_value(np.arange(3)).dtype == np.float64


def test_to_value_passthrough_and_text():
    arr = np.ones((2, 2))
    assert to_value(arr) is arr
    c = to_value("abc")
    assert isinstance(c, CharArray) and c.to_str() == "abc"
    assert to_value(c) is c


def test_to_value_rejects():
    with pytest.raises(NotSupportedError):
        to_value(np.zeros((2, 2, 2)))
    with pytest.raises(ValidationError):
        to_value(object())
    with pytest.raises(ValidationError):
        to_value([[1, 2], [3]])
    with pytest.raises(ValidationError):
        to_value(np.array([1, 2], dtype=object))
    with pytest.raises(ValidationError):
        to_value(None)


def test_is_value():
    assert is_value(np.zeros((1, 1)))
    assert not is_value(np.zeros(3))
    assert not is_value(np.zeros((1, 1), dtype=np.float32))
    assert not is_value("abc")
    assert is_value(CharArray.from_str("a"))


def test_class_size_numel():
    assert class_of(to_value(1)) == "double"
    assert class_of(to_value(1j)) == "double"
    assert class_of(to_value(True)) == "logical"
    assert class_of(CharArray.from_str("a")) == "char"
    assert class_of(CellArray.empty(1, 1)) == "cell"
    assert class_of(StructValue()) == "struct"
    assert class_of(FunctionHandle(name="sin")) == "function_handle"
    with pytest.raises(ValidationError):
        class_of(3)
    assert size_of(to_value([[1, 2, 3], [4, 5, 6]])) == (2, 3)
    assert size_of(StructValue()) == (1, 1)
    assert size_of(FunctionHandle(name="f")) == (1, 1)
    assert numel_of(CharArray.from_str("abcd")) == 4
    assert is_empty(empty_double()) and not is_empty(to_value(0))


def test_chararray():
    c = CharArray.from_str("hello")
    assert c.shape == (1, 5) and c.to_str() == "hello"
    e = CharArray.from_str("")
    assert e.shape == (0, 0) and e.to_str() == ""
    np.testing.assert_array_equal(CharArray.from_str("AB").codes(), [[65.0, 66.0]])
    assert CharArray.from_str("a") == CharArray.from_str("a")
    assert CharArray.from_str("a") != CharArray.from_str("b")
    assert CharArray.from_str("ab") != CharArray.from_str("a")
    assert repr(CharArray.from_str("hi")) == "CharArray('hi')"
    two = CharArray(np.array([["a", "b"], ["c", "d"]], dtype="<U1"))
    with pytest.raises(ValidationError):
        two.to_str()
    with pytest.raises(ValidationError):
        CharArray(np.array([["ab"]]))
    with pytest.raises(ValidationError):
        CharArray(np.array(["a", "b"], dtype="<U1"))
    with pytest.raises(ValidationError):
        CharArray.from_str(5)


def test_chararray_nul_character_regression():
    """numpy drops NUL from '<U1' elements; char(0) must still round-trip (MATLAB pads with it)."""
    c = CharArray.from_str("a\x00b")
    assert c.shape == (1, 3) and c.to_str() == "a\x00b"
    np.testing.assert_array_equal(c.codes(), [[97, 0, 98]])


def test_cellarray():
    c = CellArray.empty(2, 3)
    assert c.shape == (2, 3) and all(is_empty(x) for x in c.data.ravel())
    d = CellArray.from_rows([[1, "a"], [[1, 2], True]])
    assert d.shape == (2, 2)
    assert isinstance(d.data[0, 1], CharArray) and d.data[1, 0].shape == (1, 2)
    assert d == CellArray.from_rows([[1, "a"], [[1, 2], True]])
    assert d != CellArray.from_rows([[1, "b"], [[1, 2], True]])
    assert CellArray.from_rows([]).shape == (0, 0)
    with pytest.raises(ValidationError):
        CellArray.from_rows([[1, 2], [3]])
    bad = np.empty((1, 1), dtype=object)
    bad[0, 0] = 3
    with pytest.raises(ValidationError):
        CellArray(bad)
    with pytest.raises(ValidationError):
        CellArray(np.zeros((1, 1)))


def test_struct():
    s = StructValue({"a": 1, "b": "x"})
    assert s.names() == ("a", "b") and len(s) == 2 and s.has("a")
    assert s.get("a")[0, 0] == 1.0
    s2 = s.with_field("c", 3)
    assert s.names() == ("a", "b") and s2.names() == ("a", "b", "c")
    assert StructValue({"a": 1, "b": 2}) == StructValue({"b": 2, "a": 1})
    assert StructValue({"a": 1}) != StructValue({"a": 2})
    assert StructValue({"a": 1}) != StructValue({"a": 1, "b": 1})
    with pytest.raises(ValidationError, match="non-existent field 'zz'"):
        s.get("zz")
    for bad in ("", "1a", "a b", 3):
        with pytest.raises(ValidationError):
            StructValue({bad: 1})
    with pytest.raises(ValidationError):
        s.with_field("x y", 1)


def test_function_handle():
    f = FunctionHandle(name="sin")
    assert not f.is_anonymous and f == FunctionHandle(name="sin")
    assert f != FunctionHandle(name="cos")
    body = A.Ident("x")
    g = FunctionHandle(params=("x",), body=body, captured={"k": 2})
    assert g.is_anonymous and g.captured["k"][0, 0] == 2.0
    assert g == g
    assert g != FunctionHandle(params=("x",), body=body, captured={"k": 2})
    assert g != f
    with pytest.raises(ValidationError):
        FunctionHandle()
    with pytest.raises(ValidationError):
        FunctionHandle(name="f", body=body)
    with pytest.raises(ValidationError):
        FunctionHandle(name="1bad")
    with pytest.raises(ValidationError):
        FunctionHandle(name="f", params=("x",))
    with pytest.raises(ValidationError):
        FunctionHandle(params=("x", "x"), body=body)


def test_values_equal():
    assert values_equal(to_value([1, 2]), to_value([1, 2]))
    assert not values_equal(to_value([1, 2]), to_value([1, 2, 3]))
    assert not values_equal(to_value(np.nan), to_value(np.nan))
    assert values_equal(to_value(True), to_value(1))
    assert not values_equal(to_value(1), CharArray.from_str("a"))
    assert values_equal(CharArray.from_str("a"), CharArray.from_str("a"))
    assert values_equal(StructValue({"a": 1}), StructValue({"a": 1}))
    assert not values_equal(StructValue(), CellArray.empty(1, 1))


def test_is_true():
    assert is_true(to_value(1)) and not is_true(to_value(0))
    assert is_true(to_value([1, 2, 3])) and not is_true(to_value([1, 0, 3]))
    assert not is_true(empty_double())
    assert is_true(to_value(1j)) and is_true(to_value(True))
    assert is_true(CharArray.from_str("a"))
    with pytest.raises(ValidationError, match="NaN"):
        is_true(to_value(np.nan))
    with pytest.raises(ValidationError):
        is_true(CellArray.empty(1, 1))
    with pytest.raises(ValidationError):
        is_true(StructValue())
