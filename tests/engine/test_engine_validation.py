"""Validation helper tests."""

from __future__ import annotations

import numpy as np
import pytest

from engstudio.core.errors import DimensionError, ValidationError
from engstudio.engine.validation import as_matrix, as_vector


def test_shapes():
    assert as_matrix(3).shape == (1, 1)
    assert as_matrix([1, 2, 3]).shape == (3, 1)
    assert as_matrix([[1, 2], [3, 4]]).shape == (2, 2)
    assert as_vector(3).shape == (1,)
    assert as_vector([[1, 2, 3]]).shape == (3,)
    assert as_vector([[1], [2]]).shape == (2,)


def test_dtypes_and_bool():
    assert as_matrix([[1, 2]]).dtype == np.float64
    assert as_matrix([True, False]).dtype == np.float64
    assert as_matrix([1j]).dtype == np.complex128


def test_input_not_mutated_or_aliased():
    src = np.array([[1.0, 2.0], [3.0, 4.0]])
    out = as_matrix(src)
    out[0, 0] = 99.0
    assert src[0, 0] == 1.0


@pytest.mark.parametrize("bad", [[1, np.nan], [np.inf], "abc", ["a", "b"], [[1, 2], [3]], [],
                                 None, [object()]])
def test_invalid_values(bad):
    with pytest.raises(ValidationError):
        as_matrix(bad)


def test_empty_allowed_when_requested():
    assert as_matrix([], allow_empty=True).size == 0


def test_complex_rejected_when_not_allowed():
    with pytest.raises(ValidationError):
        as_matrix([1j], allow_complex=False)


def test_dimension_errors():
    with pytest.raises(DimensionError):
        as_matrix(np.zeros((2, 2, 2)))
    with pytest.raises(DimensionError):
        as_matrix([[1, 2, 3], [4, 5, 6]], square=True)
    with pytest.raises(DimensionError):
        as_vector([[1, 2], [3, 4]])
    with pytest.raises(DimensionError):
        as_vector([1, 2, 3], length=2)
    assert issubclass(DimensionError, ValidationError)
